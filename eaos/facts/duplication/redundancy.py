"""Redundant work in flows (the L5 detector).

Four classes of redundancy:
  repeated_call     the same call with the same arguments appears twice in one scope
  hoistable_call    a call inside a loop does not depend on the loop variable
  n_plus_one        a data-access call inside a loop repeats for every iteration
  pass_through      a function whose body is one call forwarding its arguments

All four are syntactic observations: they show where a profiler should look.
None of them proves a problem exists at runtime. Python is read here by its syntax tree; JavaScript and TypeScript
from the recorded facts (eaos/facts/duplication/redundancy_js.py).
"""
import ast
from collections import defaultdict
from .. import call_name, digest, make
from .redundancy_js import JS_LANGUAGES, _index_js, _js_redundancies
from ..source import language_of

NAME = 'redundancy'
VERSION = '2'
LIMITATIONS = [
    'A repeated call is detected by signature equality; this is a structural hypothesis, not runtime proof.',
    'A hoistable call is detected by syntactic independence from the loop variable; runtime may still require it.',
    'N+1 detection is structural: any data access in a loop is flagged, even when the loop iterates once.',
    'A pass-through layer is one-call-forwarding; layers with hidden side effects are not detected.',
    'Only parsed languages produce redundancy facts; unparsed files stay out of the denominator.',
    'Redundancy detection reads Python by its syntax tree, and JavaScript and TypeScript from the recorded '
    'loops, calls, branches and data accesses; a file in any other language is counted as blocked, never '
    'as analysed-and-clean.',
    'For JavaScript and TypeScript only data access is judged: a query or request inside a loop or an '
    'iterating call (n_plus_one), and the same query twice on one unconditional path of a function '
    '(repeated_call). Hoistable and pass-through work is not looked for there.',
]

# Names that plausibly reach a store. 'get', 'all', 'first' and 'find' were here and matched
# dict.get, the all() builtin and str.find, which is how 1,014 false N+1 claims were produced.
# Only names that unambiguously reach a store. 'update', 'insert', 'delete' and 'save' were here
# and matched hashlib.update and dict.update, which is not data access.
_N1_NAMES = {'query', 'filter_by', 'execute', 'fetchone', 'fetchall', 'select',
             'get_or_404', 'find_one', 'aggregate', 'scalar', 'objects', 'fetch', 'download', 'request'}
# Calls kept for their effect, never for their value: hoisting them changes behaviour.
# Repeating these costs nothing worth a finding; reporting them buries the calls that do cost.
_TRIVIAL = {'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple', 'sorted', 'reversed',
            'isinstance', 'getattr', 'setattr', 'hasattr', 'type', 'repr', 'abs', 'min', 'max', 'sum',
            'range', 'enumerate', 'zip', 'get', 'keys', 'values', 'items', 'join', 'split', 'strip',
            'startswith', 'endswith', 'format', 'lower', 'upper', 'replace', 'append', 'path',
            'name', 'parent', 'resolve', 'exists', 'is_file', 'is_dir', 'read_text', 'rglob', 'glob',
            'any', 'all', 'next', 'iter', 'dumps', 'loads', 'encode', 'decode', 'copy', 'deepcopy'}
_SIDE_EFFECTS = {'print', 'log', 'debug', 'info', 'warning', 'error', 'exception', 'critical',
                 'write', 'writelines', 'append', 'add', 'extend', 'insert', 'update', 'remove',
                 'discard', 'pop', 'popleft', 'popitem', 'send', 'emit', 'publish', 'commit', 'flush', 'close', 'sleep',
                 'assert_called', 'raise_for_status', 'mkdir', 'unlink', 'rmtree'}


def _python_walk_calls(node):
    """Yield (Call node, enclosing_function_name) for every call inside a function body."""
    rows = []
    def visit(node, func_name):
        if isinstance(node, ast.Call):
            rows.append((node, func_name))
        for child in ast.iter_child_nodes(node):
            visit(child, func_name)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for child in ast.iter_child_nodes(node):
            visit(child, node.name)
    return rows


def _python_signature(call):
    """Stable signature of a call for equality checks."""
    def serialise(value):
        if isinstance(value, ast.Name): return ('name', value.id)
        if isinstance(value, ast.Attribute): return ('attr', value.attr)
        if isinstance(value, ast.Constant): return ('const', repr(value.value))
        if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            return (type(value).__name__, sorted(repr(serialise(item)) for item in value.elts))
        # A type name is not an identity: print(f"a") and print(f"b") are different calls.
        return ('expr', ast.dump(value, annotate_fields=False))
    # The callee is part of the signature: two different no-argument calls are not the same call.
    name = call_name(call.func) or '<expr>'
    # a.encode() and b.encode() share an attribute name and nothing else.
    if isinstance(call.func, ast.Attribute):
        name = ast.dump(call.func, annotate_fields=False)
    keywords = tuple(sorted((kw.arg or '**', serialise(kw.value)) for kw in call.keywords))
    return repr((name, tuple(serialise(arg) for arg in call.args), keywords))


def _exclusive_branches(func_node):
    """Pairs of statement groups that never both execute: if/elif/else arms and try/except arms."""
    spans = []
    for arms in _branch_groups(func_node):
        arm_spans = [lines for lines in (_arm_lines(arm) for arm in arms) if lines]
        if len(arm_spans) > 1: spans.append(arm_spans)
    return spans


def _branch_groups(func_node):
    for node in ast.walk(func_node):
        if isinstance(node, ast.If): yield [node.body, node.orelse]
        elif isinstance(node, ast.Try): yield [node.body] + [h.body for h in node.handlers]


def _arm_lines(arm):
    return {line for statement in arm for node in ast.walk(statement)
            for line in [getattr(node, 'lineno', None)] if line}


def _apart_in(arms, line_a, line_b):
    """Whether the two lines sit in different arms of one branch, and in no arm together."""
    in_a = {index for index, lines in enumerate(arms) if line_a in lines}
    in_b = {index for index, lines in enumerate(arms) if line_b in lines}
    return bool(in_a and in_b and not (in_a & in_b))


def _mutually_exclusive(line_a, line_b, spans):
    return any(_apart_in(arms, line_a, line_b) for arms in spans)


def _python_repeated_calls(func_node):
    """Pairs of (Call, Call) inside the same function whose signature is equal."""
    calls = _python_walk_calls(func_node)
    by_sig = defaultdict(list)
    for call, fn in calls:
        sig = _python_signature(call)
        by_sig[sig].append(call)
    pairs = []
    exclusive = _exclusive_branches(func_node)
    for sig, group in by_sig.items():
        group.sort(key=lambda c: c.lineno)
        for i in range(1, len(group)):
            a, b = group[i-1], group[i]
            if b.lineno - a.lineno > 5: continue  # far apart, may be intentional
            callee = call_name(a.func) or '<expr>'
            if callee.lower() in _TRIVIAL: continue
            if a.lineno == b.lineno: continue      # two objects created deliberately in one statement
            if _mutually_exclusive(a.lineno, b.lineno, exclusive): continue
            pairs.append({'callee': callee, 'start_line': a.lineno, 'end_line': b.lineno})
    return pairs


def _python_loop_vars(loop_node):
    """Every name that can differ between iterations.

    The loop target alone is not enough: a value assigned inside the body changes on every pass,
    so a call using it is not loop-invariant. Missing that produced most of the false hoists.
    """
    bound = _names_in(loop_node.target) if isinstance(loop_node, (ast.For, ast.AsyncFor)) else set()
    for statement in _python_loop_body(loop_node):
        for node in ast.walk(statement): bound |= _bound_by(node)
    return bound


def _names_in(node):
    return {inner.id for inner in ast.walk(node) if isinstance(inner, ast.Name)}


def _bound_by(node):
    """The names a statement or clause (re)binds: assignment targets, loop and comprehension targets, `with ... as`."""
    if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        return set().union(*(_names_in(target) for target in targets))
    if isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)): return _names_in(node.target)
    if isinstance(node, ast.withitem) and node.optional_vars is not None: return _names_in(node.optional_vars)
    return set()


def _python_loop_body(loop_node):
    """The statements a loop repeats. The iterable is evaluated once and is not part of it."""
    return list(getattr(loop_node, 'body', [])) + list(getattr(loop_node, 'orelse', []))


def _value_producing_calls(node):
    """Calls whose result is bound to a name.

    A bare call statement, a raise, or a mutation is kept for its effect; moving it out of a loop
    changes behaviour. Only a computation whose value is stored can be hoisted, so only that is
    reported — a vocabulary of "safe" names could never cover every library.
    """
    produced = set()
    for statement in ast.walk(node):
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            value = statement.value
            if isinstance(value, ast.Call): produced.add(id(value))
    return produced


def _python_hoistable_calls(func_node):
    """Loop-invariant computations whose value is stored, and could be computed once."""
    value_calls = _value_producing_calls(func_node)
    return [{'callee': callee, 'loop_line': loop.lineno, 'call_line': sub.lineno}
            for loop, sub, bound in _loop_calls(func_node, (ast.For, ast.AsyncFor, ast.While))
            if (callee := _hoistable(sub, bound, value_calls))]


def _loop_calls(func_node, kinds):
    """(loop, call, the names that vary between its iterations) for every call in the body of every loop of `kinds`."""
    for loop in ast.walk(func_node):
        if not isinstance(loop, kinds): continue
        bound = _python_loop_vars(loop)
        for statement in _python_loop_body(loop):
            yield from ((loop, sub, bound) for sub in ast.walk(statement) if isinstance(sub, ast.Call))


def _hoistable(sub, bound, value_calls):
    """The callee of a loop-invariant call whose value is stored, or None."""
    if _names_in(sub) & bound: return None
    callee = call_name(sub.func) or '<expr>'
    # A call kept for its effect cannot be hoisted, however loop-invariant its arguments are;
    # and hoisting a cheap builtin is not a finding.
    if callee.lower() in _SIDE_EFFECTS or callee.lower() in _TRIVIAL: return None
    if id(sub) not in value_calls: return None  # kept for its effect, not its value
    return callee


def _python_n_plus_one(func_node):
    """Calls to data-access functions inside a loop."""
    rows = []
    for loop, sub, bound in _loop_calls(func_node, (ast.For, ast.AsyncFor)):
        callee = call_name(sub.func) or ''
        # Attribute calls (self.x, order.get, profile.fetch) on a loop-bound value are the N+1 idiom;
        # invariant work is hoistable, not an N+1.
        if _names_in(sub) & bound and callee.lower() in _N1_NAMES:
            rows.append({'callee': callee, 'loop_line': loop.lineno, 'call_line': sub.lineno})
    return rows


def _python_pass_through(func_node):
    """A function whose body is exactly one call forwarded from the parameters.

    The forwarded arguments must reference the function's parameters; otherwise the
    pass-through is a coincidence and we keep quiet.
    """
    returns = [n for n in ast.walk(func_node) if isinstance(n, ast.Return)]
    if len(returns) != 1: return None
    value = returns[0].value
    if not isinstance(value, ast.Call): return None
    # If there are no statements other than the return, the body is a pass-through.
    body_stmts = [n for n in ast.iter_child_nodes(func_node)
                  if not isinstance(n, (ast.arguments, ast.Expr, ast.Pass))]
    if len(body_stmts) > 1: return None
    if not _forwards_parameters(func_node, value): return None
    return {'callee': call_name(value.func) or '<expr>',
              'line': returns[0].lineno}


def _forwards_parameters(func_node, call):
    """Whether the call's arguments name any of the function's parameters."""
    param_names = {a.arg for a in func_node.args.args}
    arg_names = {n.id for arg in call.args for n in ast.walk(arg) if isinstance(n, ast.Name)}
    return bool(arg_names & param_names)


def _python_walk_functions(tree):
    """Yield every FunctionDef/AsyncFunctionDef in the tree."""
    scope = []
    def visit(node, path):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qualified = '.'.join(scope + [node.name])
            yield node, qualified
            scope.append(node.name)
            for child in ast.iter_child_nodes(node):
                yield from visit(child, qualified)
            scope.pop()
            return
        if isinstance(node, ast.ClassDef):
            scope.append(node.name)
            for child in ast.iter_child_nodes(node):
                yield from visit(child, None)
            scope.pop()
            return
        for child in ast.iter_child_nodes(node):
            yield from visit(child, None)
    for node in tree.body:
        yield from visit(node, None)


def _python_redundancies(text, rel):
    try: tree = ast.parse(text)
    except SyntaxError: return None
    rows = []
    for func, qualified in _python_walk_functions(tree):
        body_lines = (func.end_lineno or func.lineno) - func.lineno + 1
        if body_lines < 2: continue
        for pair in _python_repeated_calls(func):
            rows.append({'kind': 'repeated_call', 'path': rel, 'symbol': qualified,
                          'start_line': pair['start_line'], 'end_line': pair['end_line'],
                          'callee': pair['callee']})
        for h in _python_hoistable_calls(func):
            rows.append({'kind': 'hoistable_call', 'path': rel, 'symbol': qualified,
                          'start_line': h['call_line'], 'end_line': h['call_line'],
                          'callee': h['callee']})
        for h in _python_n_plus_one(func):
            rows.append({'kind': 'n_plus_one', 'path': rel, 'symbol': qualified,
                          'start_line': h['call_line'], 'end_line': h['call_line'],
                          'callee': h['callee']})
        passthrough = _python_pass_through(func)
        if passthrough:
            rows.append({'kind': 'pass_through', 'path': rel, 'symbol': qualified,
                          'start_line': passthrough['line'], 'end_line': passthrough['line'],
                          'callee': passthrough['callee']})
    return rows




def _tree_sitter_redundancies(text, language):
    """Not implemented for tree-sitter languages, and it says so instead of returning nothing found.

    This returned an empty list, which the caller reads as "analysed, nothing here". Every
    non-Python file then counted as observed, so 1021 Go files produced zero redundancy facts and
    the dashboard reported a perfect minimal path. Returning None puts those files in
    `files_blocked`, which is the bucket for what we could not look at.
    """
    return None


def _texts(source):
    """(path, language, text) of every readable file in a known language."""
    for item in source.readable():
        rel = item['path']; language = language_of(rel)
        if language is None: continue
        text = source.text(rel)
        if text is not None: yield rel, language, text


def _redundancies(rel, language, text, js):
    """A file's redundancy rows, or None when its language is not read: the file is blocked, not clean."""
    if language == 'python': return _python_redundancies(text, rel)
    # JavaScript and TypeScript are judged from the facts; without them the file is blocked, not clean.
    if language in JS_LANGUAGES and js is not None: return _js_redundancies(rel, js[rel], text)
    return _tree_sitter_redundancies(text, language)


def run(target, source, symbols=None, structure=None, entrypoints=None, **options):
    from ..code import syntax as syntax_module
    if symbols is None:
        syntax_result = syntax_module.run(target, source)
        symbols = [f for f in syntax_result['facts'] if f['kind'] == 'symbol']
    js = _index_js(structure, entrypoints) if structure is not None and entrypoints is not None else None
    facts = []
    counts = defaultdict(int)
    files_observed = 0; files_blocked = 0
    for rel, language, text in _texts(source):
        rows = _redundancies(rel, language, text, js)
        if rows is None: files_blocked += 1; continue
        files_observed += 1
        for row in rows:
            counts[row['kind']] += 1
            facts.append(make('redundancy', NAME, VERSION, digest(repr(sorted(row.items())).encode()),
                                {'path': row['path'], 'start_line': row['start_line'],
                                 'end_line': row['end_line'], 'symbol': row['symbol']},
                                {'kind': row['kind'], 'callee': row['callee']},
                                limitations=LIMITATIONS))
    summary = {'files_observed': files_observed, 'files_blocked': files_blocked,
               'repeated_calls': counts['repeated_call'],
               'hoistable_calls': counts['hoistable_call'],
               'n_plus_one': counts['n_plus_one'],
               'pass_through': counts['pass_through'],
               'interpretation': 'Each fact is a structural hypothesis about redundant work; the runtime never proves '
                                 'the work is wasted; a profiler is the only honest verification.'}
    return {'facts': facts, 'summary': summary, 'available': True,
            'input_sha': digest(b''), 'reason': None}

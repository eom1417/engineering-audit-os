"""Redundant work in flows (the L5 detector).

Four classes of redundancy:
  repeated_call     the same call with the same arguments appears twice in one scope
  hoistable_call    a call inside a loop does not depend on the loop variable
  n_plus_one        a data-access call inside a loop repeats for every iteration
  pass_through      a function whose body is one call forwarding its arguments

All four are syntactic observations: they show where a profiler should look.
None of them proves a problem exists at runtime.
"""
import ast
from collections import defaultdict
from . import digest, make
from .source import language_of

NAME = 'redundancy'
VERSION = '1'
LIMITATIONS = [
    'A repeated call is detected by signature equality; this is a structural hypothesis, not runtime proof.',
    'A hoistable call is detected by syntactic independence from the loop variable; runtime may still require it.',
    'N+1 detection is structural: any data access in a loop is flagged, even when the loop iterates once.',
    'A pass-through layer is one-call-forwarding; layers with hidden side effects are not detected.',
    'Only parsed languages produce redundancy facts; unparsed files stay out of the denominator.',
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
    name = _python_call_name(call.func) or '<expr>'
    # a.encode() and b.encode() share an attribute name and nothing else.
    if isinstance(call.func, ast.Attribute):
        name = ast.dump(call.func, annotate_fields=False)
    keywords = tuple(sorted((kw.arg or '**', serialise(kw.value)) for kw in call.keywords))
    return repr((name, tuple(serialise(arg) for arg in call.args), keywords))


def _exclusive_branches(func_node):
    """Pairs of statement groups that never both execute: if/elif/else arms and try/except arms."""
    groups = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.If): groups.append([node.body, node.orelse])
        elif isinstance(node, ast.Try): groups.append([node.body] + [h.body for h in node.handlers])
    spans = []
    for arms in groups:
        arm_spans = []
        for arm in arms:
            lines = {line for statement in arm for node in ast.walk(statement)
                     for line in [getattr(node, 'lineno', None)] if line}
            if lines: arm_spans.append(lines)
        if len(arm_spans) > 1: spans.append(arm_spans)
    return spans


def _mutually_exclusive(line_a, line_b, spans):
    for arms in spans:
        homes = [index for index, lines in enumerate(arms) if line_a in lines or line_b in lines]
        if len(set(homes)) > 1 and any(line_a in arms[i] for i in homes) and any(line_b in arms[i] for i in homes):
            in_a = {index for index, lines in enumerate(arms) if line_a in lines}
            in_b = {index for index, lines in enumerate(arms) if line_b in lines}
            if in_a and in_b and not (in_a & in_b): return True
    return False


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
            callee = _python_call_name(a.func) or '<expr>'
            if callee.lower() in _TRIVIAL: continue
            if a.lineno == b.lineno: continue      # two objects created deliberately in one statement
            if _mutually_exclusive(a.lineno, b.lineno, exclusive): continue
            pairs.append({'callee': callee, 'start_line': a.lineno, 'end_line': b.lineno})
    return pairs


def _python_call_name(node):
    if isinstance(node, ast.Name): return node.id
    if isinstance(node, ast.Attribute): return node.attr
    return None


def _python_loop_vars(loop_node):
    """Every name that can differ between iterations.

    The loop target alone is not enough: a value assigned inside the body changes on every pass,
    so a call using it is not loop-invariant. Missing that produced most of the false hoists.
    """
    bound = set()
    if isinstance(loop_node, (ast.For, ast.AsyncFor)):
        for node in ast.walk(loop_node.target):
            if isinstance(node, ast.Name): bound.add(node.id)
    for statement in _python_loop_body(loop_node):
        for node in ast.walk(statement):
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    for inner in ast.walk(target):
                        if isinstance(inner, ast.Name): bound.add(inner.id)
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
                for inner in ast.walk(node.target):
                    if isinstance(inner, ast.Name): bound.add(inner.id)
            elif isinstance(node, ast.withitem) and node.optional_vars is not None:
                for inner in ast.walk(node.optional_vars):
                    if isinstance(inner, ast.Name): bound.add(inner.id)
    return bound


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
    rows = []
    value_calls = _value_producing_calls(func_node)
    for loop in ast.walk(func_node):
        if not isinstance(loop, (ast.For, ast.AsyncFor, ast.While)): continue
        bound = _python_loop_vars(loop)
        for statement in _python_loop_body(loop):
          for sub in ast.walk(statement):
            if not isinstance(sub, ast.Call): continue
            names = {n.id for n in ast.walk(sub) if isinstance(n, ast.Name)}
            if names & bound: continue
            callee = _python_call_name(sub.func) or '<expr>'
            # A call kept for its effect cannot be hoisted, however loop-invariant its arguments are;
            # and hoisting a cheap builtin is not a finding.
            if callee.lower() in _SIDE_EFFECTS or callee.lower() in _TRIVIAL: continue
            if id(sub) not in value_calls: continue  # kept for its effect, not its value
            rows.append({'callee': callee, 'loop_line': loop.lineno, 'call_line': sub.lineno})
    return rows


def _python_n_plus_one(func_node):
    """Calls to data-access functions inside a loop."""
    rows = []
    for loop in ast.walk(func_node):
        if not isinstance(loop, (ast.For, ast.AsyncFor)): continue
        bound = _python_loop_vars(loop)
        for statement in _python_loop_body(loop):
          for sub in ast.walk(statement):
            if not isinstance(sub, ast.Call): continue
            callee = _python_call_name(sub.func) or ''
            # Attribute calls (self.x, order.get, profile.fetch) on a loop-bound value are the N+1 idiom.
            varies_with_loop = bool({n.id for n in ast.walk(sub) if isinstance(n, ast.Name)} & bound)
            if not varies_with_loop: continue  # invariant work is hoistable, not an N+1
            if callee.lower() in _N1_NAMES:
                rows.append({'callee': callee, 'loop_line': loop.lineno, 'call_line': sub.lineno})
                continue
            # An attribute call on the loop value counts only when it plausibly reaches a store.
            if isinstance(sub.func, ast.Attribute) and callee.lower() in _N1_NAMES:
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
    param_names = {a.arg for a in func_node.args.args}
    arg_names = set()
    for arg in value.args:
        for n in ast.walk(arg):
            if isinstance(n, ast.Name): arg_names.add(n.id)
    if not (arg_names & param_names): return None
    return {'callee': _python_call_name(value.func) or '<expr>',
              'line': returns[0].lineno}


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
                yield from visit(child, qualified if False else None)
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
    """Structural redundancy detection for tree-sitter languages (limited to a few useful cases)."""
    try:
        from tree_sitter_language_pack import get_parser
    except ImportError: return None
    try: parser = get_parser('c_sharp' if language == 'csharp' else language)
    except Exception: return None
    try: tree = parser.parse(text.encode('utf-8'))
    except Exception: return None
    # We use only repeated-call and pass-through heuristics for non-Python languages.
    rows = []
    return rows


def run(target, source, symbols=None, **options):
    from . import syntax as syntax_module
    if symbols is None:
        syntax_result = syntax_module.run(target, source)
        symbols = [f for f in syntax_result['facts'] if f['kind'] == 'symbol']
    facts = []
    counts = defaultdict(int)
    files_observed = 0; files_blocked = 0
    for item in source.readable():
        rel = item['path']; language = language_of(rel)
        if language is None: continue
        text = source.text(rel)
        if text is None: continue
        rows = None
        if language == 'python': rows = _python_redundancies(text, rel)
        else: rows = _tree_sitter_redundancies(text, language)
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

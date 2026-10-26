"""Module state, for the domain facts (eaos/facts/domain/model.py): the module-level values a program changes while it runs
(Python, Go, JavaScript and TypeScript), whether that state is private to its module, and the assignments a Python
module makes into another module's namespace.
"""
import ast
import re


MUTABLE = (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)


MUTATORS = {'append', 'extend', 'insert', 'pop', 'remove', 'clear', 'update', 'add', 'discard', 'setdefault', 'popitem', 'sort'}


def python_mutable_globals(text):
    """Module-level state that is actually mutated.

    A module-level dict used as a lookup table is a constant in practice. Reporting all of them
    would bury the few that are genuinely written to, which are the ones that cause surprises.
    """
    tree = _parse(text)
    if tree is None: return []
    bound = _mutable_bindings(tree)
    mutated = _mutations(tree, bound)
    found = [(name, shape, line, *mutated[name]) for name, (shape, line) in sorted(bound.items()) if name in mutated]
    found += [(name, 'rebound_global', where, how, where, scope) for name, (how, where, scope) in sorted(mutated.items())
              if name not in bound and how == 'global_statement']
    return found


def _parse(text):
    try: return ast.parse(text)
    except (SyntaxError, ValueError, RecursionError): return None


def _assign_targets(node):
    return node.targets if isinstance(node, ast.Assign) else [node.target]


def _mutable_bindings(tree):
    bound = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)): continue
        for target in _assign_targets(node):
            if isinstance(target, ast.Name) and isinstance(node.value, MUTABLE):
                bound[target.id] = (type(node.value).__name__, node.lineno)
    return bound


def _module_level_ids(tree):
    # A dict built up at module level is initialisation; the same write inside a function is
    # state that changes while the program runs, which is the case worth reporting.
    module_level = set()
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)): continue
        module_level.update(id(node) for node in ast.walk(statement))
    return module_level


def _is_mutator_call(node, bound):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id in bound
            and node.func.attr in MUTATORS)


def _is_item_of(target, bound):
    return isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id in bound


def _mutation_of(node, bound, module_level):
    """(name, (how, line, scope)) for every bound name this node changes."""
    scope = 'module' if id(node) in module_level else 'function'
    if isinstance(node, ast.Global):
        return [(name, ('global_statement', node.lineno, 'function')) for name in node.names]
    if _is_mutator_call(node, bound):
        return [(node.func.value.id, ('method:' + node.func.attr, node.lineno, scope))]
    if isinstance(node, (ast.Assign, ast.AugAssign)):
        return [(target.value.id, ('item_assignment', node.lineno, scope))
                for target in _assign_targets(node) if _is_item_of(target, bound)]
    return []


def _mutations(tree, bound):
    module_level = _module_level_ids(tree)
    mutated = {}
    for node in ast.walk(tree):
        for name, value in _mutation_of(node, bound, module_level): mutated[name] = value
    return mutated


def _imported_names(tree):
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update((alias.asname or alias.name).split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.update(alias.asname or alias.name for alias in node.names)
    return modules


def _writes_into(node, modules, owned):
    return [(target.value.id, target.attr, node.lineno) for target in _assign_targets(node)
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id in modules
            and (owned is None or target.value.id in owned)]


def python_external_writes(text, owned=None):
    """Assignments into another module's namespace: state written by someone who does not own it.

    Only modules this project owns count. Setting sys.dont_write_bytecode is an idiom, not a
    violation of somebody's invariant, and flagging it buries the case that matters.
    """
    tree = _parse(text)
    if tree is None: return []
    modules = _imported_names(tree)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AugAssign)): found += _writes_into(node, modules, owned)
    return found


GO_GLOBAL = re.compile(r'^var\s+(?P<name>[A-Za-z_]\w*)\s+(?P<shape>[^\n=]+)?(?:=.*)?$', re.M)


def go_mutable_globals(text):
    """Package variables that are guarded or changed after declaration."""
    found = []
    for match in GO_GLOBAL.finditer(text):
        name = match.group('name')
        shape = (match.group('shape') or 'inferred').strip()
        tail = text[match.end():]
        guarded = bool(re.search(r'\bsync\.(?:RW)?Mutex\b', shape))
        changed = bool(re.search(rf'(?:\b{re.escape(name)}\s*(?:=|\+\+|--)|'
                                 rf'{re.escape(name)}\s*\[[^]]+\]\s*=|'
                                 rf'{re.escape(name)}\.(?:Lock|RLock|Store|Delete)\s*\()', tail))
        if not guarded and not changed: continue
        line = text.count('\n', 0, match.start()) + 1
        found.append((name, shape, line, 'guarded' if guarded else 'assignment', line, 'function'))
    return found


JS_TOP_LET = re.compile(r'^(?:export\s+)?(?:let|var)\s+(?P<name>[A-Za-z_$][\w$]*)', re.M)
JS_TOP_CONTAINER = re.compile(r'^(?:export\s+)?const\s+(?P<name>[A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?P<shape>\[|\{|new\s+(?:Map|Set|WeakMap)\b)', re.M)


def js_mutable_globals(text):
    """Module-level state a function changes: a top-level let/var reassigned later, or a top-level const
    array, object, Map or Set mutated later. In a server it is shared by every request; in a browser, by
    every component of the tab."""
    found = []
    for match in JS_TOP_LET.finditer(text):
        name, tail = match.group('name'), text[match.end():]
        if re.search(rf'(?<![\w$.]){re.escape(name)}\s*(?:[-+*/]?=(?!=)|\+\+|--)', tail):
            line = text.count('\n', 0, match.start()) + 1
            found.append((name, 'let', line, 'assignment', line, 'function'))
    for match in JS_TOP_CONTAINER.finditer(text):
        name, tail = match.group('name'), text[match.end():]
        body = tail.split('\n', 1)[1] if '\n' in tail else ''
        if re.search(rf'(?<![\w$.]){re.escape(name)}\s*(?:\.(?:push|pop|shift|unshift|splice|set|add|delete|clear)\s*\(|\[[^\]]+\]\s*=(?!=)|\.[A-Za-z_$][\w$]*\s*=(?!=))', body):
            line = text.count('\n', 0, match.start()) + 1
            found.append((name, match.group('shape').split()[0].replace('new', 'collection'), line, 'mutation', line, 'function'))
    return found


def encapsulated(name, text, language):
    """Whether module state is private to its module: no other module can reach the variable itself, only the
    module's own functions. JavaScript: never exported. Python: a leading underscore, not in __all__. Go: an
    unexported name. Such state has an owner; whether it may stay per-process is a design decision."""
    if language == 'python':
        return name.startswith('_') and not re.search(rf'__all__[^\n]*[\'"]{re.escape(name)}[\'"]', text)
    if language == 'go':
        return name[:1].islower()
    escaped = re.escape(name)
    exported = (re.search(rf'\bexport\s+(?:let|var|const)\s+{escaped}\b', text)
                or re.search(rf'\bexport\s*\{{[^}}]*\b{escaped}\b[^}}]*\}}', text)
                or re.search(rf'\bexport\s+default\s+{escaped}\b', text)
                or re.search(rf'\b(?:module\.)?exports\.{escaped}\b|\bmodule\.exports\s*=\s*\{{[^}}]*\b{escaped}\b', text))
    return not exported

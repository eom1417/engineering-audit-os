"""Pipelines a project's own Python declares: module-level lists of stage records, a DAG run through a registry of
runners or a sequence of steps a driver calls, with their routes and error lanes (eaos/facts/declared_pipelines/detect.py). Their
context side channels: eaos/facts/declared_pipelines/context.py; the phases and orchestrators a function runs:
eaos/facts/declared_pipelines/orchestrators.py."""
import ast

from .context import context_channels
from .read import (slug, site, Found, _str, _strs, _root, _unparse, _method_call, describe, REQUIRES, PRODUCES,
                   CONSUMES, TIMEOUT_WORDS, ERROR_STATES)


def _registry_for(py, names):
    """A dict of stage name -> function whose keys are mostly these names: (rel, assignment, {key: (rel, def)})."""
    best = None
    for rel, assigns in py.assigns.items():
        for var, node in assigns.items():
            if not isinstance(node.value, ast.Dict) or len(node.value.keys) < 3: continue
            keys = _registry_keys(py, rel, var, node.value)
            share = len(set(keys) & set(names)) / max(len(names), 1)
            if share >= 0.6 and (best is None or share > best[0]):
                best = (share, rel, var, node, keys)
    return best


def _registry_keys(py, rel, var, value):
    """{key: (the function's name node, line)} of a registry dict, with the keys a later REGISTRY.update(a=a) adds."""
    keys = {}
    for key, item in zip(value.keys, value.values):
        label = _str(key) if key is not None else None
        if label is not None and isinstance(item, ast.Name): keys[label] = (item, key.lineno)
    for sub in ast.walk(py.trees[rel]):
        if _method_call(sub, var, 'update'):
            keys.update({k.arg: (k.value, sub.lineno) for k in sub.keywords if k.arg and isinstance(k.value, ast.Name)})
    return keys


def _drivers(py, list_rel, list_var):
    """Functions iterating a module-level list (directly or imported): [(rel, name, node, loop)]."""
    out = []
    for rel, name, node in py.functions():
        local = list_var if rel == list_rel else _imported_as(py, rel, list_rel, list_var)
        if not local: continue
        for sub in ast.walk(node):
            for item in _iterated(sub):
                if isinstance(item, ast.Name) and item.id == local:
                    target = sub.target if isinstance(sub, ast.For) else sub.generators[0].target
                    out.append((rel, name, node, sub, target.id if isinstance(target, ast.Name) else None))
    return out


def _imported_as(py, rel, list_rel, list_var):
    """The name a module imports another module's list under, or None."""
    return next((k for k, (m, a) in py.imports.get(rel, {}).items() if a == list_var and py.module_rel(m) == list_rel), None)


def _iterated(node):
    """What a for loop, list comprehension or generator iterates over."""
    if isinstance(node, ast.For): return [node.iter]
    return [g.iter for g in node.generators] if isinstance(node, (ast.GeneratorExp, ast.ListComp)) else []


def _element_parts(element):
    if isinstance(element, ast.Call): first, keywords, rest = (element.args[:1] or [None])[0], element.keywords, element.args[1:]
    elif isinstance(element, ast.Tuple): first, keywords, rest = (element.elts[:1] or [None])[0], [], element.elts[1:]
    else: return None
    label = _str(first) if first is not None else None
    if label is None: label = next((_str(k.value) for k in keywords if k.arg in ('name', 'id', 'task_id')), None)
    return None if label is None else (label, keywords, rest)


def _is_ai(py, rel, element, keywords):
    return any(k.arg == 'kind' and _str(k.value) == 'ai' for k in keywords) or (any(k.arg == 'routes' for k in keywords) and _default_kind(py, rel, element) == 'ai')


def _kw_strings(keywords, names):
    return [s for k in keywords if k.arg in names for s in _strs(k.value)]


def _declared_row(py, rel, element):
    label, keywords, rest = _element_parts(element) or (None, None, None)
    if label is None: return None
    return {'label': label, 'line': element.lineno, 'requires': _kw_strings(keywords, REQUIRES),
            'produces': _kw_strings(keywords, PRODUCES), 'consumes': _kw_strings(keywords, CONSUMES),
            'functions': _functions_named(py, rel, [*rest, *[k.value for k in keywords]]),
            'optional': _optional(keywords), 'ai': _is_ai(py, rel, element, keywords),
            'routes': [r for k in keywords if k.arg in ROUTES for r in _routes(k.value)], 'timeout': any(k.arg in TIMEOUT_WORDS for k in keywords)}


def _functions_named(py, rel, values):
    """The names among a record's values that are the project's own functions."""
    return [item.id for item in values if isinstance(item, ast.Name) and py.resolve(rel, item.id)]


def _optional(keywords):
    """Whether a stage record declares itself optional (necessity=Necessity.OPTIONAL)."""
    return any(k.arg == 'necessity' and 'optional' in _unparse(k.value).lower() for k in keywords)


def declared_lists(py, out):
    for rel, assigns in py.assigns.items():
        for var, node in assigns.items():
            if not isinstance(node.value, (ast.List, ast.Tuple)) or len(node.value.elts) < 3: continue
            rows = [_declared_row(py, rel, element) for element in node.value.elts]
            if None not in rows: _declare(py, (rel, var, node), rows, out)


def _declare(py, declared, rows, out):
    """`declared`: the list's file, name and node."""
    rel, var, _ = declared
    names = [r['label'] for r in rows]
    if len(set(names)) != len(names): return
    dag = sum(bool(set(r['requires']) & set(names)) for r in rows) >= 2
    drivers = _drivers(py, rel, var)
    if dag: _declared_dag(py, declared, rows, drivers, out)
    elif all(r['functions'] for r in rows) and _calls_steps(drivers): _declared_sequence(py, declared, rows, drivers, out)


def _calls_steps(drivers):
    """Whether a driver calls what its loop takes from the list (step.run(), step[1]()): the steps are run."""
    return any(isinstance(call, ast.Call) and isinstance(call.func, (ast.Subscript, ast.Attribute))
               and _root(call.func) == target
               for _, _, fn, _, target in drivers for call in ast.walk(fn) if target)


ROUTES = {'routes', 'branches'}


def _routes(value):
    """The declared branches of a stage record: Route(decision, to, when) calls or (decision, to, when) tuples, each
    with the line it is written on."""
    routes = [_route(item) for item in (value.elts if isinstance(value, (ast.Tuple, ast.List)) else [])]
    return [route for route in routes if route]


def _route(item):
    """One declared branch, Route(decision, to, when) or (decision, to, when): its condition, target and line, or None."""
    values, named = _route_parts(item)
    condition = values[0] if values else named.get('decision') or named.get('condition')
    to = values[1] if len(values) > 1 else named.get('to')
    return {'condition': condition, 'to': to, 'line': item.lineno} if condition and to else None


def _route_parts(item):
    """The positional strings and the named ones of a declared branch: a call's arguments, or a tuple's items."""
    if isinstance(item, ast.Call): return [_str(part) for part in item.args], {k.arg: _str(k.value) for k in item.keywords}
    return [_str(part) for part in item.elts] if isinstance(item, ast.Tuple) else [], {}


def _default_kind(py, rel, element):
    """The default of a record class's `kind` field (class Node(NamedTuple): kind: str = 'ai'), when the record
    leaves it out."""
    if not isinstance(element.func, ast.Name): return None
    for module in [rel] + [py.module_rel(m) for m, a in py.imports.get(rel, {}).values() if a == element.func.id]:
        cls = py.classes.get(module, {}).get(element.func.id) if module else None
        field = next((item for item in (cls.body if cls else []) if _is_kind_field(item)), None)
        if field: return _str(field.value)
    return None


def _is_kind_field(item):
    """Whether a class body's statement declares the `kind` field (kind: str = ...)."""
    return isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and item.target.id == 'kind'


def _declared_routes(py, rel, found, by_label):
    """Each stage's declared branches as a router after it: the decision is the branch's condition, and a target that
    is not a stage is where the work leaves the pipeline (a sink)."""
    for label, (key, row, _) in by_label.items():
        if not row['routes']: continue
        where = site(rel, row['line'], py.line(rel, row['line']))
        router = found.stage(f'{label} router', where, kind='router')
        found.edge(key, router, 'declared', where, kind='control')
        branches = []
        for route in row['routes']:
            at = site(rel, route['line'], py.line(rel, route['line']))
            to = by_label[route['to']][0] if route['to'] in by_label else found.stage(route['to'], at, kind='sink')
            branches.append({'condition': route['condition'], 'to': to, 'evidence': at})
        found.routers.append({'id': f'{found.id}:{slug(label)}:routes', 'pipeline': found.id, 'stage': router, 'kind': 'conditional_edges',
                              'table': label, 'on': 'decision', 'entry': where, 'branches': branches, 'total': True, 'default': None,
                              'unhandled': []})


def _declared_dag(py, declared, rows, drivers, out):
    """A module-level list of stage records with requirements between them (`declared`: its file, name and node)."""
    rel, var, node = declared
    names = [r['label'] for r in rows]
    driver = drivers[0] if drivers else None
    entry = site(driver[0], driver[2].lineno, py.line(driver[0], driver[2].lineno)) if driver else site(rel, node.lineno, py.line(rel, node.lineno))
    found = Found(f'{rel}:{var}', f'{var} ({rel})', 'declared_dag', entry, [site(rel, node.lineno, py.line(rel, node.lineno))])
    registry = _registry_for(py, names)
    by_label = {row['label']: _dag_stage(py, found, rel, row, registry) for row in rows}
    _dag_edges(py, found, rel, by_label)
    if driver: _driver_controls(py, found, driver)
    if registry: _registry_router(py, found, registry, by_label, names)
    else:
        for label, (key, _, _) in by_label.items():
            found.unresolved.append({'id': f'{key}:runner', 'pipeline': found.id, 'stage': key, 'call': label,
                                     'reason': 'no registry maps this stage to the function that runs it',
                                     'evidence': found.stages[key]['entry']})
    _declared_routes(py, rel, found, by_label)
    context_channels(py, found, [(t[0], t[1]) for _, _, t in by_label.values() if t])
    out.append(found)


def _dag_stage(py, found, rel, row, registry):
    """One stage record as a stage, at the function the registry runs for it when there is one: (key, row, function)."""
    target = None
    if registry and row['label'] in registry[4]:
        target = py.resolve(registry[1], registry[4][row['label']][0].id) or None
    where = site(target[0], target[1].lineno, py.line(target[0], target[1].lineno)) if target else site(rel, row['line'], py.line(rel, row['line']))
    key = found.stage(row['label'], where, symbol=f"{target[0][:-3].replace('/', '.')}.{target[1].name}" if target else None,
                      optional=row['optional'])
    stage = found.stages[key]
    stage['outputs'] = [{'name': name, 'kind': 'artifact', 'shape': None} for name in row['produces']]
    if target:
        found.functions.add((target[0], target[1].name))
        describe(py, target[0], target[1], stage)
    if row['timeout']: stage['timeout'] = True   # a time or cost budget declared on the stage's record
    if row['ai']:
        stage['kind'] = 'ai'
        stage['marks'] = sorted(set(stage['marks']) | {'ai', 'slow'})
    return key, row, target


def _dag_edges(py, found, rel, by_label):
    """An edge from each required stage, carrying the first artifacts it produces."""
    for label, (key, row, _) in by_label.items():
        for need in row['requires']:
            if need not in by_label: continue
            source = by_label[need]
            artifacts = source[1]['produces']
            found.stages[key]['inputs'] += [{'name': a, 'kind': 'artifact', 'shape': None} for a in artifacts[:3]
                                            if a not in {i['name'] for i in found.stages[key]['inputs']}]
            found.edge(source[0], key, 'declared', site(rel, row['line'], py.line(rel, row['line'])), names=artifacts[:3],
                       shape='files' if artifacts else None)


def _driver_controls(py, found, driver):
    """The loop of the function that runs the stages, the stages it skips on a condition, and where its failures go."""
    fn_rel, fn_name, fn_node, loop, _ = driver
    found.functions.add((fn_rel, fn_name))
    found.control.append({'id': f'{found.id}:loop', 'pipeline': found.id, 'stage': found.order[0], 'kind': 'loop',
                          'condition': _unparse(loop.iter if isinstance(loop, ast.For) else loop, 60),
                          'evidence': site(fn_rel, loop.lineno, py.line(fn_rel, loop.lineno))})
    skips = [sub for sub in loop.body if isinstance(sub, ast.If) and any(isinstance(s, ast.Continue) for s in sub.body)] \
        if isinstance(loop, ast.For) else []
    for sub in skips:
        found.control.append({'id': f'{found.id}:skip:{sub.lineno}', 'pipeline': found.id, 'stage': found.order[0],
                              'kind': 'conditional_skip', 'condition': _unparse(sub.test),
                              'evidence': site(fn_rel, sub.lineno, py.line(fn_rel, sub.lineno))})
    _error_lanes(py, fn_rel, fn_node, found)


def _returns_none_default(lookup):
    """True when the lookup function compares its result with None: a missing stage has a default."""
    return any(isinstance(s, ast.Compare) and any(isinstance(o, (ast.Is, ast.Eq)) for o in s.ops)
               and any(isinstance(c, ast.Constant) and c.value is None for c in s.comparators)
               for s in ast.walk(lookup[1]))


def _registry_router(py, found, registry, by_label, names):
    """The registry as a router: a branch per key, a dead stage per key no record names, the stages it misses."""
    share, reg_rel, reg_var, reg_node, keys = registry
    router_key = found.stage(reg_var, site(reg_rel, reg_node.lineno, py.line(reg_rel, reg_node.lineno)), kind='router',
                             symbol=f"{reg_rel[:-3].replace('/', '.')}.{reg_var}")
    lookup = _lookup(py, reg_var)
    if lookup:
        _error_lanes(py, lookup[0], lookup[1], found)
        found.functions.add((lookup[0], lookup[1].name))
    branches = []
    for label, (item, line) in keys.items():
        to = by_label.get(label, (None,))[0]
        branches.append({'condition': label, 'to': to, 'evidence': site(reg_rel, line, py.line(reg_rel, line))})
        if to is None:
            found.hidden.append({'id': f'{found.id}:dead:{slug(label)}', 'pipeline': found.id, 'kind': 'dead_stage',
                                 'channel': None, 'name': label, 'stages': [router_key],
                                 'evidence': site(reg_rel, line, py.line(reg_rel, line))})
    missing = [name for name in names if name not in keys]
    found.routers.append({'id': f'{found.id}:{slug(reg_var)}', 'pipeline': found.id, 'stage': router_key, 'kind': 'registry',
                          'table': reg_var, 'on': 'stage name',
                          'entry': site(lookup[0], lookup[2], py.line(lookup[0], lookup[2])) if lookup else
                          site(reg_rel, reg_node.lineno, py.line(reg_rel, reg_node.lineno)),
                          'branches': branches, 'total': not missing,
                          'default': 'failed' if lookup and _returns_none_default(lookup) else None, 'unhandled': missing})
    found.functions.add((reg_rel, reg_var))


def _lookup(py, registry_var):
    """The function that looks a stage's runner up in the registry: (rel, def, line)."""
    for rel, name, node in py.functions():
        for sub in ast.walk(node):
            if _gets_by_name(sub):
                local = _root(sub.func.value)
                if local and (local == registry_var or local.lower() == registry_var.lower()):
                    return rel, node, sub.lineno
    return None


def _gets_by_name(node):
    """Whether `node` is a `table.get(stage.name)` call (or .id, .kind)."""
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'get' and node.args
            and isinstance(node.args[0], ast.Attribute) and node.args[0].attr in ('name', 'id', 'kind'))


def _error_lanes(py, rel, node, found):
    """Where failures go inside the function that runs the stages: handlers and the states they record."""
    constants = _string_constants(py, rel)

    def states(body):
        for sub in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(sub, ast.Name) and constants.get(sub.id, '').lower() in ERROR_STATES: yield constants[sub.id].lower()

    seen = {(lane['to'], lane['kind'], lane.get('condition')) for lane in found.errors}
    for sub in ast.walk(node):
        for to, kind, condition in _lanes_of(sub, states):
            if (to, kind, condition) in seen: continue
            seen.add((to, kind, condition))
            found.errors.append({'id': f'{found.id}:error:{len(found.errors)}', 'pipeline': found.id, 'from': '*', 'to': to,
                                 'kind': kind, 'condition': condition, 'evidence': site(rel, sub.lineno, py.line(rel, sub.lineno))})


def _lanes_of(sub, states):
    """(to, kind, condition) of each error state one node records: in an except handler, an if, or a loop over dependencies."""
    if isinstance(sub, ast.ExceptHandler): return _handler_lanes(sub, states)
    if isinstance(sub, ast.If) and any(isinstance(s, (ast.Return, ast.Assign, ast.Expr, ast.Continue)) for s in sub.body):
        return [(state, ERROR_STATES[state], _unparse(sub.test)) for state in states(sub.body)]
    if isinstance(sub, ast.For) and 'depend' in _unparse(sub.iter).lower():
        return [(state, 'block', _unparse(sub.iter)) for state in states(sub.body) if ERROR_STATES[state] == 'block']
    return []


def _handler_lanes(handler, states):
    """(to, kind, condition) of each error state an except handler records: a skip when it or the state says so."""
    label = _unparse(handler.type) if handler.type is not None else 'any exception'
    return [(state, 'skip' if 'skip' in label.lower() or ERROR_STATES[state] == 'skip' else 'catch', label)
            for state in states(handler.body)]


def _string_constants(py, rel):
    """{name: string} of the module's top-level string constants, and of those it imports by name."""
    constants = {}
    def collect(module_rel, wanted=None, alias=None):
        for assign in py.trees[module_rel].body:
            if not isinstance(assign, ast.Assign): continue
            for item, value in _assigned_pairs(assign):
                if isinstance(item, ast.Name) and _str(value) is not None and (wanted is None or item.id == wanted):
                    constants[alias or item.id] = _str(value)
    collect(rel)
    for imported, (module, attr) in py.imports.get(rel, {}).items():
        if attr and (where := py.module_rel(module)): collect(where, attr, imported)
    return constants


def _assigned_pairs(assign):
    """(target, value) of each name an assignment sets, a tuple unpacked into its items (A, B = 'a', 'b')."""
    for target in assign.targets:
        names = target.elts if isinstance(target, ast.Tuple) else [target]
        values = assign.value.elts if isinstance(assign.value, ast.Tuple) and isinstance(target, ast.Tuple) else [assign.value]
        yield from zip(names, values)


def _declared_sequence(py, declared, rows, drivers, out):
    """A module-level list of stage records a driver runs in order (`declared`: its file, name and node)."""
    rel, var, node = declared
    driver = drivers[0]
    found = Found(f'{rel}:{var}', f'{var} ({rel})', 'declared_dag', site(driver[0], driver[2].lineno, py.line(driver[0], driver[2].lineno)),
                  [site(rel, node.lineno, py.line(rel, node.lineno))], confidence=0.8)
    previous = None
    for row in rows:
        function = py.resolve(rel, row['functions'][-1])
        where = site(rel, row['line'], py.line(rel, row['line']))
        key = found.stage(row['label'], where, symbol=f"{function[0][:-3].replace('/', '.')}.{function[1].name}" if function else None)
        if function:
            found.functions.add((function[0], function[1].name))
            describe(py, function[0], function[1], found.stages[key])
        if previous: found.edge(previous, key, 'order', where, kind='control')
        previous = key
    for fn_rel, fn_name, _, _, _ in drivers: found.functions.add((fn_rel, fn_name))
    out.append(found)

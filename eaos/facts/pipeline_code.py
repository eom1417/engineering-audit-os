"""Pipelines a project's own Python declares or runs: declared DAGs and sequences, registry loops, announced phases,
and orchestrators passing one stage's result to the next (eaos/facts/pipeline.py)."""
import ast
import sys
from collections import defaultdict

from .pipeline_read import (slug, site, Found, _str, _strs, _name, _root, _decorators, _literal_label, _unparse, describe, REQUIRES, PRODUCES, CONSUMES, TIMEOUT_WORDS, PIPELINE_WORDS, PHASE_CALLS, FLOW_DECORATORS, ERROR_STATES, CONTEXT_PARAMS, DICT_METHODS, MODEL_WORDS, SIGNATURES)


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
        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == 'update'
                and isinstance(sub.func.value, ast.Name) and sub.func.value.id == var):
            keys.update({k.arg: (k.value, sub.lineno) for k in sub.keywords if k.arg and isinstance(k.value, ast.Name)})
    return keys


def _drivers(py, list_rel, list_var):
    """Functions iterating a module-level list (directly or imported): [(rel, name, node, loop)]."""
    out = []
    for rel, name, node in py.functions():
        local = list_var if rel == list_rel else next((k for k, (m, a) in py.imports.get(rel, {}).items()
                                                        if a == list_var and py.module_rel(m) == list_rel), None)
        if not local: continue
        for sub in ast.walk(node):
            iters = [sub.iter] if isinstance(sub, ast.For) else [g.iter for g in sub.generators] if isinstance(sub, (ast.GeneratorExp, ast.ListComp)) else []
            for item in iters:
                if isinstance(item, ast.Name) and item.id == local:
                    target = sub.target if isinstance(sub, ast.For) else sub.generators[0].target
                    out.append((rel, name, node, sub, target.id if isinstance(target, ast.Name) else None))
    return out


def declared_lists(py, out):
    for rel, assigns in py.assigns.items():
        for var, node in assigns.items():
            value = node.value
            if not isinstance(value, (ast.List, ast.Tuple)) or len(value.elts) < 3: continue
            rows = []
            for element in value.elts:
                if isinstance(element, ast.Call): first, keywords, rest = (element.args[:1] or [None])[0], element.keywords, element.args[1:]
                elif isinstance(element, ast.Tuple): first, keywords, rest = (element.elts[:1] or [None])[0], [], element.elts[1:]
                else: break
                label = _str(first) if first is not None else None
                if label is None:
                    label = next((_str(k.value) for k in keywords if k.arg in ('name', 'id', 'task_id')), None)
                if label is None: break
                requires = [s for k in keywords if k.arg in REQUIRES for s in _strs(k.value)]
                produces = [s for k in keywords if k.arg in PRODUCES for s in _strs(k.value)]
                consumes = [s for k in keywords if k.arg in CONSUMES for s in _strs(k.value)]
                functions = [item.id for item in [*rest, *[k.value for k in keywords]]
                             if isinstance(item, ast.Name) and py.resolve(rel, item.id)]
                optional = any(k.arg == 'necessity' and 'optional' in _unparse(k.value).lower() for k in keywords)
                ai = any(k.arg == 'kind' and _str(k.value) == 'ai' for k in keywords) or (
                    any(k.arg == 'routes' for k in keywords) and _default_kind(py, rel, element) == 'ai')
                rows.append({'label': label, 'line': element.lineno, 'requires': requires, 'produces': produces,
                             'consumes': consumes, 'functions': functions, 'optional': optional, 'ai': ai,
                             'routes': [r for k in keywords if k.arg in ROUTES for r in _routes(k.value)],
                             'timeout': any(k.arg in TIMEOUT_WORDS for k in keywords)})
            else:
                names = [r['label'] for r in rows]
                if len(set(names)) != len(names): continue
                dag = sum(bool(set(r['requires']) & set(names)) for r in rows) >= 2
                drivers = _drivers(py, rel, var)
                called = any(isinstance(call, ast.Call) and isinstance(call.func, (ast.Subscript, ast.Attribute))
                             and _root(call.func) == target
                             for _, _, fn, _, target in drivers for call in ast.walk(fn) if target)
                sequence = not dag and all(r['functions'] for r in rows) and called
                if dag: _declared_dag(py, (rel, var, node), rows, drivers, out)
                elif sequence: _declared_sequence(py, rel, var, node, rows, drivers, out)


ROUTES = {'routes', 'branches'}


def _routes(value):
    """The declared branches of a stage record: Route(decision, to, when) calls or (decision, to, when) tuples, each
    with the line it is written on."""
    out = []
    for item in value.elts if isinstance(value, (ast.Tuple, ast.List)) else []:
        parts = item.args if isinstance(item, ast.Call) else item.elts if isinstance(item, ast.Tuple) else []
        named = {k.arg: _str(k.value) for k in item.keywords} if isinstance(item, ast.Call) else {}
        values = [_str(part) for part in parts]
        condition = values[0] if values else named.get('decision') or named.get('condition')
        to = values[1] if len(values) > 1 else named.get('to')
        if condition and to: out.append({'condition': condition, 'to': to, 'line': item.lineno})
    return out


def _default_kind(py, rel, element):
    """The default of a record class's `kind` field (class Node(NamedTuple): kind: str = 'ai'), when the record
    leaves it out."""
    if not isinstance(element.func, ast.Name): return None
    for module in [rel] + [py.module_rel(m) for m, a in py.imports.get(rel, {}).values() if a == element.func.id]:
        cls = py.classes.get(module, {}).get(element.func.id) if module else None
        for item in (cls.body if cls else []):
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and item.target.id == 'kind':
                return _str(item.value)
    return None


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
    _context_channels(py, found, [(t[0], t[1]) for _, _, t in by_label.values() if t])
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
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == 'get' and sub.args \
                    and isinstance(sub.args[0], ast.Attribute) and sub.args[0].attr in ('name', 'id', 'kind'):
                local = _root(sub.func.value)
                if local and (local == registry_var or local.lower() == registry_var.lower()):
                    return rel, node, sub.lineno
    return None


def _error_lanes(py, rel, node, found):
    """Where failures go inside the function that runs the stages: handlers and the states they record."""
    constants = {}

    def collect(module_rel, wanted=None, alias=None):
        for assign in py.trees[module_rel].body:
            if not isinstance(assign, ast.Assign): continue
            for target in assign.targets:
                names = target.elts if isinstance(target, ast.Tuple) else [target]
                values = assign.value.elts if isinstance(assign.value, ast.Tuple) and isinstance(target, ast.Tuple) else [assign.value]
                for item, value in zip(names, values):
                    if isinstance(item, ast.Name) and _str(value) is not None and (wanted is None or item.id == wanted):
                        constants[alias or item.id] = _str(value)

    collect(rel)
    for imported, (module, attr) in py.imports.get(rel, {}).items():
        where = py.module_rel(module)
        if where and attr: collect(where, attr, imported)

    def states(body):
        for sub in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(sub, ast.Name) and constants.get(sub.id, '').lower() in ERROR_STATES: yield constants[sub.id].lower()

    seen = {(lane['to'], lane['kind'], lane.get('condition')) for lane in found.errors}

    def add(to, kind, condition, line):
        if (to, kind, condition) in seen: return
        seen.add((to, kind, condition))
        found.errors.append({'id': f'{found.id}:error:{len(found.errors)}', 'pipeline': found.id, 'from': '*', 'to': to,
                             'kind': kind, 'condition': condition, 'evidence': site(rel, line, py.line(rel, line))})

    for sub in ast.walk(node):
        if isinstance(sub, ast.ExceptHandler):
            label = _unparse(sub.type) if sub.type is not None else 'any exception'
            for state in states(sub.body):
                add(state, 'skip' if 'skip' in label.lower() or ERROR_STATES[state] == 'skip' else 'catch', label, sub.lineno)
        elif isinstance(sub, ast.If):
            for state in states(sub.body):
                kind = ERROR_STATES[state]
                if not any(isinstance(s, (ast.Return, ast.Assign, ast.Expr, ast.Continue)) for s in sub.body): continue
                add(state, kind, _unparse(sub.test), sub.lineno)
        elif isinstance(sub, ast.For):
            for state in states(sub.body):
                if ERROR_STATES[state] == 'block' and 'depend' in _unparse(sub.iter).lower():
                    add(state, 'block', _unparse(sub.iter), sub.lineno)


def _context_channels(py, found, functions):
    """Keys of one shared context a stage writes and another reads: side channels beside the declared edges."""
    writes, reads, lines = defaultdict(set), defaultdict(set), {}
    stage_of = {(rel, node.name): key for key in found.order for rel, node in functions
                if found.stages[key]['entry']['path'] == rel and found.stages[key]['entry']['line'] == node.lineno}
    for (rel, name), key in stage_of.items():
        node = py.defs[rel].get(name)
        param = next((a.arg for a in node.args.args if a.arg in CONTEXT_PARAMS), None)
        if not param: continue
        for sub in ast.walk(node):
            used, written, noted = _context_use(sub, param)
            if used is None: continue
            (writes if written else reads)[used].add(key)
            if noted: lines.setdefault((used, key), (rel, sub.lineno))
    for name in sorted(writes): _context_channel(py, found, name, writes[name], reads.get(name, set()), lines)


def _context_use(sub, param):
    """(key, written, its line noted) when `sub` writes or reads a key of the context parameter; (None, ...) otherwise."""
    if isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name) and sub.value.id == param and _str(sub.slice):
        return _str(sub.slice), isinstance(sub.ctx, ast.Store), True
    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and isinstance(sub.func.value, ast.Name) \
            and sub.func.value.id == param and sub.func.attr == 'get' and sub.args and _str(sub.args[0]):
        return _str(sub.args[0]), False, True
    if isinstance(sub, ast.Compare) and any(isinstance(o, (ast.In, ast.NotIn)) for o in sub.ops) and _str(sub.left) \
            and any(isinstance(c, ast.Name) and c.id == param for c in sub.comparators):
        return _str(sub.left), False, False
    if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == param \
            and isinstance(sub.ctx, ast.Load) and sub.attr not in DICT_METHODS:
        return sub.attr, False, True
    return None, False, False


def _context_channel(py, found, name, writers, read_by, lines):
    """A context key read by a stage other than its writer is a side channel; one nobody reads is an unread output."""
    readers = {r for r in read_by if any(r != w for w in writers)}
    first = sorted(writers, key=found.order.index)[0]
    rel, line = lines.get((name, first), (found.stages[first]['entry']['path'], found.stages[first]['entry']['line']))
    if readers:
        found.hidden.append({'id': f'{found.id}:ctx:{slug(name)}', 'pipeline': found.id, 'kind': 'side_channel',
                             'channel': 'context', 'name': f"context['{name}']",
                             'stages': sorted(writers | readers, key=found.order.index), 'evidence': site(rel, line, py.line(rel, line))})
    elif not read_by:
        found.hidden.append({'id': f'{found.id}:ctx:{slug(name)}', 'pipeline': found.id, 'kind': 'unread_output',
                             'channel': 'context', 'name': f"context['{name}']", 'stages': sorted(writers, key=found.order.index),
                             'evidence': site(rel, line, py.line(rel, line))})


def _declared_sequence(py, rel, var, node, rows, drivers, out):
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


def registry_loops(py, out):
    for rel, name, node in py.functions():
        for loop in ast.walk(node):
            if not isinstance(loop, ast.For) or not isinstance(loop.target, ast.Name): continue
            table = _table_of(py, rel, loop, loop.target.id)
            if table: _registry_loop(py, (rel, name, node), loop, table, out)


def _looked_up(sub, var):
    """The name of the dict `sub` looks `var` up in (`table[var]` or `table.get(var)`), else None."""
    if isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name) and isinstance(sub.slice, ast.Name) and sub.slice.id == var:
        return sub.value.id
    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == 'get' and sub.args \
            and isinstance(sub.args[0], ast.Name) and sub.args[0].id == var and isinstance(sub.func.value, ast.Name):
        return sub.func.value.id
    return None


def _table_of(py, rel, loop, var):
    """(table name, line, (file, dict)) of the registry of three or more functions the loop looks each `var` up in."""
    for sub in ast.walk(loop):
        key = _looked_up(sub, var)
        if not key or not isinstance(sub.ctx if isinstance(sub, ast.Subscript) else ast.Load(), ast.Load): continue
        found_value = py.value(rel, key)
        if found_value and isinstance(found_value[1], ast.Dict) and len(found_value[1].keys) >= 3 and \
                all(_str(k) is not None and isinstance(v, ast.Name) for k, v in zip(found_value[1].keys, found_value[1].values)):
            return key, sub.lineno, found_value
    return None


def _accumulators(loop, var):
    """The names the loop keeps each stage's result in: `results[name] = ...`."""
    return {target.value.id for sub in ast.walk(loop) if isinstance(sub, ast.Assign) for target in sub.targets
            if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Name) and target.slice.id == var
            and isinstance(target.value, ast.Name)}


def _table_order(py, table_rel, keys):
    """The order the stages run in: a module-level list of most of the table's keys, else the table's own order."""
    for candidate in py.assigns.get(table_rel, {}).values():
        items = _strs(candidate.value) if isinstance(candidate.value, (ast.List, ast.Tuple)) else []
        if len(items) >= 3 and set(items) <= set(keys) and len(items) >= 0.5 * len(keys): return items
    return keys


def _registry_loop(py, function, loop, table, out):
    accumulators = _accumulators(loop, loop.target.id)
    if not accumulators: return
    reader = _RegistryLoop(py, function, loop, table, accumulators)
    reader.stages()
    reader.dispatch()
    reader.flows()
    out.append(reader.found)


class _RegistryLoop:
    """A loop over a registry table whose body runs each stage: its stages, its dispatch router and the values one stage
    hands the next through the loop's accumulators."""

    def __init__(self, py, function, loop, table, accumulators):
        self.py, (self.rel, self.fn_name, self.fn) = py, function
        self.loop, self.var, self.accumulators = loop, loop.target.id, accumulators
        self.key, self.line, (self.table_rel, self.table_node) = table
        self.keys = [_str(k) for k in self.table_node.keys]
        self.order = _table_order(py, self.table_rel, self.keys)
        self.found = Found(f'{self.rel}:{self.fn_name}', f'{self.key} ({self.rel})', 'registry_loop', self.at(self.rel, self.fn.lineno),
                           [self.at(self.table_rel, self.table_node.lineno), self.at(self.rel, loop.lineno)])
        self.found.functions.add((self.rel, self.fn_name))
        self.by_label, self.router = {}, None

    def at(self, rel, line):
        return site(rel, line, self.py.line(rel, line))

    def _stage_place(self, target):
        """(where, symbol) of what a table entry runs: its module's `run`, the function it names, or the entry itself."""
        py, table_rel = self.py, self.table_rel
        module_rel = py.resolve_module(table_rel, target.id)
        function = py.resolve(table_rel, target.id)
        if module_rel and 'run' in py.defs.get(module_rel, {}):
            return self.at(module_rel, py.defs[module_rel]['run'].lineno), f"{module_rel[:-3].replace('/', '.')}.run"
        if function:
            return self.at(function[0], function[1].lineno), f"{function[0][:-3].replace('/', '.')}.{function[1].name}"
        return self.at(table_rel, target.lineno), None

    def stages(self):
        values = dict(zip(self.keys, self.table_node.values))
        accumulator = sorted(self.accumulators)[0]
        for label in self.order:
            where, symbol = self._stage_place(values[label])
            stage_key = self.found.stage(label, where, symbol=symbol)
            self.found.stages[stage_key]['outputs'] = [{'name': f"{accumulator}[{label!r}]", 'kind': 'value', 'shape': None}]
        self.by_label = {self.found.stages[k]['label']: k for k in self.found.order}

    def dispatch(self):
        """The table as a router, a dead stage per key the run order leaves out, and the loop itself."""
        found, key, table_rel, table_node = self.found, self.key, self.table_rel, self.table_node
        self.router = found.stage(key, self.at(table_rel, table_node.lineno), kind='router',
                                  symbol=f"{table_rel[:-3].replace('/', '.')}.{key}")
        found.routers.append({'id': f'{found.id}:{slug(key)}', 'pipeline': found.id, 'stage': self.router, 'kind': 'dict_dispatch',
                              'table': key, 'on': self.var, 'entry': self.at(self.rel, self.line),
                              'branches': [{'condition': label, 'to': self.by_label.get(label), 'evidence': self.at(table_rel, k.lineno)}
                                           for label, k in zip(self.keys, table_node.keys)],
                              'total': set(self.order) <= set(self.keys), 'default': None,
                              'unhandled': [l for l in self.order if l not in self.keys]})
        for label in self.keys:
            if label not in self.order:
                found.hidden.append({'id': f'{found.id}:dead:{slug(label)}', 'pipeline': found.id, 'kind': 'dead_stage', 'channel': None,
                                     'name': label, 'stages': [self.router], 'evidence': site(table_rel, table_node.lineno, None)})
        found.control.append({'id': f'{found.id}:loop', 'pipeline': found.id, 'stage': self.router, 'kind': 'loop',
                              'condition': f'for {self.var} in {_unparse(self.loop.iter, 40)}', 'evidence': self.at(self.rel, self.loop.lineno)})

    def reads(self, body):
        """(stage label, line, accumulator) of each read of an earlier stage's result in `body`."""
        accumulators = self.accumulators
        for sub in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == 'get' \
                    and isinstance(sub.func.value, ast.Name) and sub.func.value.id in accumulators and sub.args and _str(sub.args[0]):
                yield _str(sub.args[0]), sub.lineno, sub.func.value.id
            elif isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name) and sub.value.id in accumulators and _str(sub.slice):
                yield _str(sub.slice), sub.lineno, sub.value.id
            elif isinstance(sub, ast.Compare) and _str(sub.left) and any(isinstance(c, ast.Name) and c.id in accumulators for c in sub.comparators):
                yield _str(sub.left), sub.lineno, next(c.id for c in sub.comparators if isinstance(c, ast.Name))

    def _unresolved(self, label, acc, targets, where):
        found, call = self.found, f"{acc}[{label!r}]"
        if any(u['call'] == call for u in found.unresolved): return
        found.unresolved.append({'id': f'{found.id}:unresolved:{slug(label)}', 'pipeline': found.id,
                                 'stage': self.by_label.get(targets[0]) if targets else self.router, 'call': call,
                                 'reason': 'read here, but no stage of this loop writes it', 'evidence': where})

    def flow(self, read_list, targets, condition):
        """A value edge from the stage each read names to each target stage; a read of no stage is unresolved."""
        found, by_label = self.found, self.by_label
        for label, line, acc in read_list:
            where = self.at(self.rel, line)
            if label not in by_label:
                self._unresolved(label, acc, targets, where)
                continue
            for target in (t for t in targets if t in by_label):
                found.edge(by_label[label], by_label[target], 'value', where, names=[f"{acc}[{label!r}]"], condition=condition)
                found.stages[by_label[target]]['inputs'].append({'name': f"{acc}[{label!r}]", 'kind': 'value', 'shape': None})

    def if_chain(self, statement):
        """An `if var == ...: elif ...: else:` chain: a branch per tested label, the values each branch reads."""
        branches, node, covered = [], statement, set()
        while True:
            labels = _tests(node, self.var)
            if not labels: break
            covered |= set(labels)
            branches += [{'condition': label, 'to': self.by_label.get(label), 'evidence': self.at(self.rel, node.lineno)} for label in labels]
            self.flow(list(self.reads(node.body)), labels, _unparse(node.test))
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                node = node.orelse[0]
                continue
            if node.orelse:
                branches.append({'condition': 'else', 'to': None, 'evidence': self.at(self.rel, node.orelse[0].lineno)})
                self.flow(list(self.reads(node.orelse)), [l for l in self.order if l not in covered], 'else')
            break
        if branches:
            found, at = self.found, self.at(self.rel, statement.lineno)
            router_key = found.stage(f'if {self.var} ==', at, kind='router')
            found.routers.append({'id': f'{found.id}:{slug(self.var)}-chain', 'pipeline': found.id, 'stage': router_key, 'kind': 'if_chain',
                                  'table': self.var, 'on': self.var, 'entry': at,
                                  'branches': branches, 'total': any(b['condition'] == 'else' for b in branches),
                                  'default': None, 'unhandled': []})

    def flows(self):
        for statement in self.loop.body:
            if isinstance(statement, ast.If) and _tests(statement, self.var): self.if_chain(statement)
            elif not isinstance(statement, ast.If) and not _writes_acc(statement, self.accumulators, self.var):
                self.flow(list(self.reads([statement])), self.order, None)   # read outside the if-chain: an input of every stage


def _writes_acc(statement, accumulators, var):
    return isinstance(statement, ast.Assign) and any(isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                                                     and t.value.id in accumulators for t in statement.targets)


def _tests(node, var):
    """The literal values an `if` compares a name with: x == 'a', x in {'a', 'b'}."""
    test = node.test
    if isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == var and len(test.ops) == 1:
        if isinstance(test.ops[0], ast.Eq) and _str(test.comparators[0]) is not None: return [_str(test.comparators[0])]
        if isinstance(test.ops[0], ast.In): return _strs(test.comparators[0])
    return []


def phases(py, out):
    for rel, name, node in py.functions():
        calls = []
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and (_name(sub.func) or '') in PHASE_CALLS and sub.args:
                label = _literal_label(sub.args[0])
                if label: calls.append((sub.lineno, label.rstrip(' :.-'), sub))
        if len({label for _, label, _ in calls}) < 3: continue
        calls.sort(key=lambda row: row[0])
        found = Found(f'{rel}:{name}', f'{name} ({rel})', 'orchestrator', site(rel, node.lineno, py.line(rel, node.lineno)),
                      [site(rel, calls[0][0], py.line(rel, calls[0][0]))], confidence=0.8)
        found.functions.add((rel, name))
        previous = None
        bounds = [line for line, _, _ in calls] + [node.end_lineno or calls[-1][0]]
        for index, (line, label, _) in enumerate(calls):
            where = site(rel, line, py.line(rel, line))
            key = found.stage(label, where, symbol=f"{rel[:-3].replace('/', '.')}.{name}")
            segment = [s for s in node.body if bounds[index] <= getattr(s, 'lineno', 0) < bounds[index + 1]] or \
                      [s for s in ast.walk(node) if isinstance(s, ast.stmt) and bounds[index] <= s.lineno < bounds[index + 1]]
            stage = found.stages[key]
            for statement in segment: describe(py, rel, statement, stage)
            if _calls_model(py, segment): stage['marks'] = sorted(set(stage['marks']) | {'ai', 'slow'}); stage['kind'] = 'ai'
            if previous and previous != key: found.edge(previous, key, 'order', where, kind='control')
            previous = key
        for handler in (s for s in ast.walk(node) if isinstance(s, ast.ExceptHandler)):
            found.errors.append({'id': f'{found.id}:error:{handler.lineno}', 'pipeline': found.id, 'from': '*', 'to': 'blocked',
                                 'kind': 'catch', 'condition': _unparse(handler.type) if handler.type else 'any exception',
                                 'evidence': site(rel, handler.lineno, py.line(rel, handler.lineno))})
        out.append(found)


def _calls_model(py, statements):
    """Whether these statements call a project function or method whose body reaches a model provider."""
    names = {(_name(s.func) or '') for st in statements for s in ast.walk(st) if isinstance(s, ast.Call)}
    for rel, defs in py.defs.items():
        for qualified, node in defs.items():
            if qualified.split('.')[-1] in names and any(MODEL_WORDS.search(_name(s) or '') for s in ast.walk(node)
                                                          if isinstance(s, (ast.Name, ast.Attribute))):
                return True
    return False


def _stage_call(py, rel, call, tasks):
    """The function a call runs as a stage: a project function by name, a task's signature, or an activity."""
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in ('execute_activity', 'start_activity') and call.args:
        target = _name(call.args[0])
        return (target, py.resolve(rel, target)) if target else None
    if isinstance(func, ast.Attribute) and func.attr in SIGNATURES and isinstance(func.value, ast.Name):
        target = py.resolve(rel, func.value.id)
        return (func.value.id, target) if target or func.value.id in tasks else None
    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
        and py.resolve_module(rel, func.value.id) else None
    if not name: return None
    if isinstance(func, ast.Attribute):
        where = py.resolve_module(rel, func.value.id)
        target = (where, py.defs[where][name]) if where and name in py.defs.get(where, {}) else None
    else:
        target = py.resolve(rel, name)
    if target is None or isinstance(target[1], ast.ClassDef) or name.startswith('_'): return None
    return name, target


def orchestrators(py, out, tasks, flows, covered):
    """Functions passing one stage's result to the next. Counted only with a pipeline signal (a flow decorator, a pipeline
    word in the function's own name, or a callable a declared DAG task runs) and a real chain: at least three stages, one
    feeding the next, of functions the project defines (helpers named with a leading underscore are not stages)."""
    for rel, name, node in py.functions():
        if (rel, name) in covered or (rel, name.split('.')[-1]) in covered: continue
        decorators = set(_decorators(node))
        declared = bool(decorators & FLOW_DECORATORS) or (rel, name) in flows
        if not declared and not PIPELINE_WORDS.search(name.split('.')[-1]): continue
        found = _chain(py, rel, name, node, tasks)
        if not found: continue
        stages = [k for k in found.order if found.stages[k].get('top')]
        longest = _longest(found, set(stages))
        if len(stages) >= 3 and len(found.edges) >= 2 and (longest >= 3 or declared):
            if decorators & {'flow'}: found.kind = 'prefect'
            elif decorators & {'job', 'graph'} and 'dagster' in str(py.imports.get(rel, {})): found.kind = 'dagster'
            elif decorators & {'dag'}: found.kind = 'airflow'
            elif decorators & {'workflow', 'run'} and 'temporal' in str(py.imports.get(rel, {})): found.kind = 'temporal'
            found.confidence = 0.85 if declared else 0.7
            out.append(found)


def _longest(found, among=None):
    """The number of stages on the longest path the edges draw (among some stages only, when given)."""
    outgoing = defaultdict(list)
    for a, b in found.edges:
        if among is None or (a in among and b in among): outgoing[a].append(b)
    memo = {}
    def depth(node, seen=()):
        if node in memo: return memo[node]
        best = 1 + max((depth(b, seen + (node,)) for b in outgoing[node] if b not in seen), default=0)
        memo[node] = best
        return best
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, 10 * len(found.stages) + 100))
    try: return max((depth(k) for k in found.order if among is None or k in among), default=0)
    finally: sys.setrecursionlimit(limit)


def _chain(py, rel, name, node, tasks):
    found = Found(f'{rel}:{name}', f'{name} ({rel})', 'orchestrator', site(rel, node.lineno, py.line(rel, node.lineno)),
                  [site(rel, node.lineno, py.line(rel, node.lineno))])
    found.functions.add((rel, name))
    origins, depth = {}, [0]

    def flow(expr):
        if expr is None: return set()
        if isinstance(expr, ast.Name): return set(origins.get(expr.id, set()))
        if isinstance(expr, ast.Call):
            stage = _stage_call(py, rel, expr, tasks)
            inputs = {}
            for arg in [*expr.args, *[k.value for k in expr.keywords]]:
                for source in flow(arg):
                    inputs.setdefault(source, set()).update(n.id for n in ast.walk(arg) if isinstance(n, ast.Name) and n.id in origins)
            if isinstance(expr.func, ast.Attribute) and not stage: inputs_from_object = flow(expr.func.value)
            else: inputs_from_object = set()
            if not stage:
                return set(inputs) | inputs_from_object
            label, target = stage
            where = site(rel, expr.lineno, py.line(rel, expr.lineno))
            key = found.stage(label, where, symbol=f"{target[0][:-3].replace('/', '.')}.{target[1].name}" if target else None)
            if depth[0] == 0: found.stages[key]['top'] = True
            if target:
                stage_row = found.stages[key]
                if stage_row['entry']['line'] == expr.lineno and stage_row['entry']['path'] == rel:
                    stage_row['entry'] = site(target[0], target[1].lineno, py.line(target[0], target[1].lineno))
                    describe(py, target[0], target[1], stage_row)
            for source, names in inputs.items():
                found.edge(source, key, 'value', where, names=sorted(names))
                for value in sorted(names):
                    if value not in {i['name'] for i in found.stages[key]['inputs']}:
                        found.stages[key]['inputs'].append({'name': value, 'kind': 'value', 'shape': None})
            return {key}
        out = set()
        nested = isinstance(expr, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Lambda))
        depth[0] += nested
        for child in ast.iter_child_nodes(expr):
            if isinstance(child, ast.expr): out |= flow(child)
            elif isinstance(child, ast.comprehension): out |= flow(child.iter)
        depth[0] -= nested
        return out

    def bind(target, values):
        if isinstance(target, ast.Name): origins[target.id] = set(values)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts: bind(item, values)
        elif isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
            origins[target.value.id] = origins.get(target.value.id, set()) | set(values)

    def walk(statements):
        for statement in statements:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)): continue
            if isinstance(statement, ast.Assign):
                values = flow(statement.value)
                for target in statement.targets: bind(target, values)
            elif isinstance(statement, (ast.AnnAssign, ast.AugAssign)) and statement.value is not None:
                bind(statement.target, flow(statement.value) | (flow(statement.target) if isinstance(statement, ast.AugAssign) else set()))
            elif isinstance(statement, (ast.Expr, ast.Return)):
                values = flow(statement.value)
                if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call) and isinstance(statement.value.func, ast.Attribute) \
                        and statement.value.func.attr in ('append', 'extend', 'add', 'update') and isinstance(statement.value.func.value, ast.Name):
                    bind(ast.Subscript(value=statement.value.func.value), values)
            elif isinstance(statement, (ast.For, ast.AsyncFor)):
                bind(statement.target, flow(statement.iter)); depth[0] += 1; walk(statement.body); depth[0] -= 1; walk(statement.orelse)
            elif isinstance(statement, ast.While): flow(statement.test); depth[0] += 1; walk(statement.body); depth[0] -= 1; walk(statement.orelse)
            elif isinstance(statement, ast.If): flow(statement.test); walk(statement.body); walk(statement.orelse)
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                for item in statement.items:
                    values = flow(item.context_expr)
                    if item.optional_vars is not None: bind(item.optional_vars, values)
                walk(statement.body)
            elif isinstance(statement, ast.Try):
                walk(statement.body)
                for handler in statement.handlers: walk(handler.body)
                walk(statement.orelse); walk(statement.finalbody)

    walk(node.body)
    for handler in (s for s in ast.walk(node) if isinstance(s, ast.ExceptHandler)):
        found.errors.append({'id': f'{found.id}:error:{handler.lineno}', 'pipeline': found.id, 'from': '*', 'to': 'raised',
                             'kind': 'catch', 'condition': _unparse(handler.type) if handler.type else 'any exception',
                             'evidence': site(rel, handler.lineno, py.line(rel, handler.lineno))})
    return found


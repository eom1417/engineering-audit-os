"""Pipelines that run as a loop over a registry table (`for name in ORDER: results[name] = STAGES[name](...)`), read
without running them (eaos/facts/declared_pipelines/detect.py): the table's stages in their run order, the table as a router, and the
values one stage hands the next through the loop's accumulators."""
import ast

from .read import slug, site, Found, _str, _strs, _unparse


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
    if _get_call(sub) and isinstance(sub.args[0], ast.Name) and sub.args[0].id == var and isinstance(sub.func.value, ast.Name):
        return sub.func.value.id
    return None


def _get_call(sub):
    """Whether `sub` is a `something.get(key, ...)` call."""
    return isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == 'get' and bool(sub.args)


def _table_of(py, rel, loop, var):
    """(table name, line, (file, dict)) of the registry of three or more functions the loop looks each `var` up in."""
    for sub in ast.walk(loop):
        key = _looked_up(sub, var)
        if not key or not isinstance(sub.ctx if isinstance(sub, ast.Subscript) else ast.Load(), ast.Load): continue
        found_value = py.value(rel, key)
        if found_value and _function_table(found_value[1]): return key, sub.lineno, found_value
    return None


def _function_table(value):
    """Whether a value is a dict of three or more functions, each under a string key."""
    return isinstance(value, ast.Dict) and len(value.keys) >= 3 and \
        all(_str(k) is not None and isinstance(v, ast.Name) for k, v in zip(value.keys, value.values))


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
    _stages(reader)
    _dispatch(reader)
    _flows(reader)
    out.append(reader.found)


class _RegistryLoop:
    """What the readers below share about one loop over a registry table: the table, the run order, the accumulators
    and the pipeline they fill."""

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


def _stage_place(r, target):
    """(where, symbol) of what a table entry runs: its module's `run`, the function it names, or the entry itself."""
    module_rel = r.py.resolve_module(r.table_rel, target.id)
    function = r.py.resolve(r.table_rel, target.id)
    if module_rel and 'run' in r.py.defs.get(module_rel, {}):
        return r.at(module_rel, r.py.defs[module_rel]['run'].lineno), f"{module_rel[:-3].replace('/', '.')}.run"
    if function:
        return r.at(function[0], function[1].lineno), f"{function[0][:-3].replace('/', '.')}.{function[1].name}"
    return r.at(r.table_rel, target.lineno), None


def _stages(r):
    values = dict(zip(r.keys, r.table_node.values))
    accumulator = sorted(r.accumulators)[0]
    for label in r.order:
        where, symbol = _stage_place(r, values[label])
        stage_key = r.found.stage(label, where, symbol=symbol)
        r.found.stages[stage_key]['outputs'] = [{'name': f"{accumulator}[{label!r}]", 'kind': 'value', 'shape': None}]
    r.by_label = {r.found.stages[k]['label']: k for k in r.found.order}


def _dispatch(r):
    """The table as a router, a dead stage per key the run order leaves out, and the loop itself."""
    found, key, table_rel, table_node = r.found, r.key, r.table_rel, r.table_node
    r.router = found.stage(key, r.at(table_rel, table_node.lineno), kind='router', symbol=f"{table_rel[:-3].replace('/', '.')}.{key}")
    found.routers.append({'id': f'{found.id}:{slug(key)}', 'pipeline': found.id, 'stage': r.router, 'kind': 'dict_dispatch',
                          'table': key, 'on': r.var, 'entry': r.at(r.rel, r.line),
                          'branches': [{'condition': label, 'to': r.by_label.get(label), 'evidence': r.at(table_rel, k.lineno)}
                                       for label, k in zip(r.keys, table_node.keys)],
                          'total': set(r.order) <= set(r.keys), 'default': None,
                          'unhandled': [l for l in r.order if l not in r.keys]})
    for label in r.keys:
        if label not in r.order:
            found.hidden.append({'id': f'{found.id}:dead:{slug(label)}', 'pipeline': found.id, 'kind': 'dead_stage', 'channel': None,
                                 'name': label, 'stages': [r.router], 'evidence': site(table_rel, table_node.lineno, None)})
    found.control.append({'id': f'{found.id}:loop', 'pipeline': found.id, 'stage': r.router, 'kind': 'loop',
                          'condition': f'for {r.var} in {_unparse(r.loop.iter, 40)}', 'evidence': r.at(r.rel, r.loop.lineno)})


def _named(node, names):
    """The name `node` is, when it is a bare name among `names`; else None."""
    return node.id if isinstance(node, ast.Name) and node.id in names else None


def _read_of(sub, accumulators):
    """(stage label, line, accumulator) when `sub` reads an earlier stage's result (`acc.get('a')`, `acc['a']`,
    `'a' in acc`), else None."""
    if _get_call(sub):
        acc, label = _named(sub.func.value, accumulators), _str(sub.args[0])
    elif isinstance(sub, ast.Subscript):
        acc, label = _named(sub.value, accumulators), _str(sub.slice)
    elif isinstance(sub, ast.Compare):
        acc, label = next((c.id for c in sub.comparators if _named(c, accumulators)), None), _str(sub.left)
    else:
        return None
    return (label, sub.lineno, acc) if acc and label else None


def _reads(r, body):
    """(stage label, line, accumulator) of each read of an earlier stage's result in `body`."""
    return [row for sub in ast.walk(ast.Module(body=body, type_ignores=[])) if (row := _read_of(sub, r.accumulators))]


def _unresolved(r, label, acc, targets, where):
    found, call = r.found, f"{acc}[{label!r}]"
    if any(u['call'] == call for u in found.unresolved): return
    found.unresolved.append({'id': f'{found.id}:unresolved:{slug(label)}', 'pipeline': found.id,
                             'stage': r.by_label.get(targets[0]) if targets else r.router, 'call': call,
                             'reason': 'read here, but no stage of this loop writes it', 'evidence': where})


def _flow(r, read_list, targets, condition):
    """A value edge from the stage each read names to each target stage; a read of no stage is unresolved."""
    found, by_label = r.found, r.by_label
    for label, line, acc in read_list:
        where = r.at(r.rel, line)
        if label not in by_label:
            _unresolved(r, label, acc, targets, where)
            continue
        for target in (t for t in targets if t in by_label):
            found.edge(by_label[label], by_label[target], 'value', where, names=[f"{acc}[{label!r}]"], condition=condition)
            found.stages[by_label[target]]['inputs'].append({'name': f"{acc}[{label!r}]", 'kind': 'value', 'shape': None})


def _if_chain(r, statement):
    """An `if var == ...: elif ...: else:` chain: a branch per tested label, the values each branch reads."""
    branches, node, covered = [], statement, set()
    while True:
        labels = _tests(node, r.var)
        if not labels: break
        covered |= set(labels)
        branches += [{'condition': label, 'to': r.by_label.get(label), 'evidence': r.at(r.rel, node.lineno)} for label in labels]
        _flow(r, _reads(r, node.body), labels, _unparse(node.test))
        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            node = node.orelse[0]
            continue
        if node.orelse:
            branches.append({'condition': 'else', 'to': None, 'evidence': r.at(r.rel, node.orelse[0].lineno)})
            _flow(r, _reads(r, node.orelse), [l for l in r.order if l not in covered], 'else')
        break
    if branches: _chain_router(r, statement, branches)


def _chain_router(r, statement, branches):
    """The if-chain as a router of its branches, total when it ends on an else."""
    found, at = r.found, r.at(r.rel, statement.lineno)
    router_key = found.stage(f'if {r.var} ==', at, kind='router')
    found.routers.append({'id': f'{found.id}:{slug(r.var)}-chain', 'pipeline': found.id, 'stage': router_key, 'kind': 'if_chain',
                          'table': r.var, 'on': r.var, 'entry': at,
                          'branches': branches, 'total': any(b['condition'] == 'else' for b in branches),
                          'default': None, 'unhandled': []})


def _flows(r):
    for statement in r.loop.body:
        if isinstance(statement, ast.If) and _tests(statement, r.var): _if_chain(r, statement)
        elif not isinstance(statement, ast.If) and not _writes_acc(statement, r.accumulators, r.var):
            _flow(r, _reads(r, [statement]), r.order, None)   # read outside the if-chain: an input of every stage


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

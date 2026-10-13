"""Pipelines declared in a framework's own syntax (Airflow, Celery, LangGraph, Luigi, queue topics) and in build, CI and
workflow files (GitHub Actions, Make, just, npm scripts, Step Functions, n8n, Node-RED), read without running them
(eaos/facts/pipeline.py)."""
import ast
import json
import re
from collections import defaultdict
from pathlib import Path

from . import call_name
from .pipeline_read import (slug, site, Found, _str, _strs, _decorators, _unparse, describe, TIMEOUT_WORDS, SIGNATURES)


SHIFTS = (ast.RShift, ast.LShift)


def airflow(py, out, flows):
    for rel, tree in py.trees.items():
        if not any((module or '').split('.')[0] == 'airflow' for module, _ in py.imports.get(rel, {}).values()): continue
        found, tasks = _dag(py, rel, tree)
        if found is None or not tasks: continue
        found.functions.add((rel, '<dag>'))
        keys = {var: _task_stage(py, found, rel, var, tasks, flows) for var in tasks}
        _declared_order(py, found, rel, tree, keys)
        _xcom_edges(py, found, keys)
        _match_joins(found)
        out.append(found)


def _dag(py, rel, tree):
    """(the pipeline of the file's first DAG with an id, {variable: (task_id, operator call)})."""
    found, tasks = None, {}
    for sub in ast.walk(tree):
        if found is None and isinstance(sub, ast.Call) and call_name(sub.func) == 'DAG': found = _found(py, rel, sub)
        if isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Call) and len(sub.targets) == 1 and isinstance(sub.targets[0], ast.Name):
            task_id = next((_str(k.value) for k in sub.value.keywords if k.arg == 'task_id'), None)
            if task_id: tasks[sub.targets[0].id] = (task_id, sub.value)
    return found, tasks


def _found(py, rel, call):
    dag_id = next((_str(k.value) for k in call.keywords if k.arg == 'dag_id'), None) or (_str(call.args[0]) if call.args else None)
    return Found(f'{rel}:{dag_id}', dag_id, 'airflow', site(rel, call.lineno, py.line(rel, call.lineno)),
                 [site(rel, call.lineno, py.line(rel, call.lineno))]) if dag_id else None


def _task_stage(py, found, rel, var, tasks, flows):
    """The stage of one task: its operator, the callable it runs, its retries and timeout; returns its key."""
    task_id, call = tasks[var]
    line = next((k.value.lineno for k in call.keywords if k.arg == 'task_id'), call.lineno)
    key = found.stage(task_id, site(rel, line, py.line(rel, line)), symbol=f"{rel[:-3].replace('/', '.')}.{var}", variable=var)
    stage = found.stages[key]
    stage['tools'] = [call_name(call.func) or 'Operator']
    for keyword in call.keywords:
        if keyword.arg == 'python_callable' and isinstance(keyword.value, ast.Name):
            _callable(py, found, key, rel, call, keyword.value.id, tasks, flows)
        if keyword.arg in ('retries', 'retry_delay'):
            found.control.append({'id': f'{key}:retry', 'pipeline': found.id, 'stage': key, 'kind': 'retry',
                                  'condition': _unparse(keyword.value), 'evidence': site(rel, call.lineno, py.line(rel, call.lineno))})
        if keyword.arg in TIMEOUT_WORDS: stage['timeout'] = True
    return key


def _callable(py, found, key, rel, call, name, tasks, flows):
    """The function a task runs, when it resolves: described on its stage, a branch operator's routes, its XCom pulls."""
    target = py.resolve(rel, name)
    if not target: return
    stage = found.stages[key]
    flows.add((target[0], target[1].name))
    stage['symbol'] = f"{target[0][:-3].replace('/', '.')}.{target[1].name}"
    stage['callable'] = (target[0], target[1].name)
    describe(py, target[0], target[1], stage)
    if 'Branch' in (call_name(call.func) or ''): _branch_operator(py, found, key, target, tasks, rel, call)
    for upstream, line in _xcom_pulls(target[1]): stage.setdefault('xcom', []).append((upstream, target[0], line))


def _xcom_pulls(function):
    """(task id, line) of every `xcom_pull(task_ids=...)` in a function."""
    return [(upstream, pull.lineno) for pull in ast.walk(function) if isinstance(pull, ast.Call) and call_name(pull.func) == 'xcom_pull'
            for keyword in pull.keywords if keyword.arg == 'task_ids' for upstream in _strs(keyword.value)]


def _ends(expr, keys):
    """The stages an expression of the `>>` syntax ends on."""
    if isinstance(expr, ast.Name) and expr.id in keys: return [keys[expr.id]]
    if isinstance(expr, (ast.List, ast.Tuple)): return [k for e in expr.elts for k in _ends(e, keys)]
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, SHIFTS): return _ends(expr.right if isinstance(expr.op, ast.RShift) else expr.left, keys)
    return []


def _heads(expr, keys):
    """The stages an expression of the `>>` syntax starts from."""
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, SHIFTS): return _heads(expr.left if isinstance(expr.op, ast.RShift) else expr.right, keys)
    return _ends(expr, keys)


def _declared_order(py, found, rel, tree, keys):
    """The edges `a >> b`, `a.set_downstream(b)` and `chain(a, b, ...)` declare."""
    at = lambda node: site(rel, node.lineno, py.line(rel, node.lineno))
    for sub in ast.walk(tree):
        if isinstance(sub, ast.BinOp) and isinstance(sub.op, SHIFTS): _shift(found, sub, keys, at(sub))
        elif _sets_stream(sub, keys): _stream(found, sub, keys, at(sub))
        elif isinstance(sub, ast.Call) and call_name(sub.func) == 'chain': _chain(found, sub, keys, at(sub))


def _shift(found, sub, keys, where):
    """`a >> b` (or `b << a`): an edge from each end of a to each head of b, and a fan when b holds several."""
    left, right = (sub.left, sub.right) if isinstance(sub.op, ast.RShift) else (sub.right, sub.left)
    sources, targets = _ends(left, keys), _heads(right, keys)
    for a in sources:
        for b in targets: found.edge(a, b, 'declared', where, kind='data')
    if len(targets) > 1:
        found.fans.extend({'id': f'{a}:fan:{sub.lineno}', 'pipeline': found.id, 'fork': a, 'join': None,
                           'branches': targets, 'matched': False, 'kind': 'parallel', 'evidence': where} for a in sources)


def _sets_stream(sub, keys):
    return isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr in ('set_downstream', 'set_upstream') \
        and isinstance(sub.func.value, ast.Name) and sub.func.value.id in keys


def _stream(found, sub, keys, where):
    a = keys[sub.func.value.id]
    for b in _ends(sub.args[0], keys) if sub.args else []:
        found.edge(*((a, b) if sub.func.attr == 'set_downstream' else (b, a)), 'declared', where)


def _chain(found, sub, keys, where):
    items = [_ends(arg, keys) for arg in sub.args]
    for a, b in [(a, b) for left, right in zip(items, items[1:]) for a in left for b in right]: found.edge(a, b, 'declared', where)


def _xcom_edges(py, found, keys):
    """An edge from the task whose value a callable pulls to the task that pulls it."""
    by_task = {found.stages[k]['label']: k for k in keys.values()}
    for key in keys.values():
        for upstream, path, line in found.stages[key].pop('xcom', []):
            if upstream in by_task: found.edge(by_task[upstream], key, 'value', site(path, line, py.line(path, line)), names=['xcom'])


def _match_joins(found):
    """A fan whose branches all feed one stage is joined there."""
    for fan in found.fans:
        joins = {b for (a, b) in found.edges for branch in fan['branches'] if a == branch}
        if len(joins) == 1 and all((branch, next(iter(joins))) in found.edges for branch in fan['branches']):
            fan['join'], fan['matched'] = next(iter(joins)), True


def _branch_operator(py, found, key, target, tasks, rel, call):
    returns = sorted(((_strs(s.value) or [], s.lineno) for s in ast.walk(target[1]) if isinstance(s, ast.Return) and s.value is not None),
                     key=lambda row: row[1])
    known = {task_id for task_id, _ in tasks.values()}
    branches = [{'condition': f'returns {value!r}', 'to': f"{found.id}/{slug(value)}" if value in known else None,
                 'evidence': site(target[0], line, py.line(target[0], line))} for values, line in returns for value in values]
    found.stages[key]['kind'] = 'router'
    found.routers.append({'id': f'{key}:branch', 'pipeline': found.id, 'stage': key, 'kind': 'branch_operator',
                          'table': found.stages[key]['label'], 'on': f'{target[1].name}()',
                          'entry': site(rel, call.lineno, py.line(rel, call.lineno)), 'branches': branches,
                          'total': None, 'default': None, 'unhandled': []})


def celery(py, out):
    tasks = {}
    for rel, name, node in py.functions():
        decorators = _decorators(node)
        if any(d in ('shared_task', 'task') for d in decorators) and any(
                (module or '').split('.')[0] in ('celery', 'director') or (module or '') in py.modules
                for module, _ in py.imports.get(rel, {}).values()):
            tasks[name] = (rel, node)
    if not tasks: return tasks
    by_file = {}
    for rel, fn_name, fn in py.functions():
        canvases = [sub for sub in ast.walk(fn) if isinstance(sub, ast.Call) and call_name(sub.func) in ('chain', 'group', 'chord')]
        pipes = [sub for sub in ast.walk(fn) if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.BitOr) and _signature(sub.left, tasks)]
        if not canvases and not pipes: continue
        found = by_file.get(rel)
        if found is None:
            first = (canvases or pipes)[0]
            found = by_file[rel] = Found(f'{rel}:canvas', f'Celery canvas ({rel})', 'celery', site(rel, fn.lineno, py.line(rel, fn.lineno)),
                                         [site(rel, first.lineno, py.line(rel, first.lineno))])
        found.functions.add((rel, fn_name))
        _canvas(py, found, rel, fn_name, canvases, pipes, tasks)
    out.extend(f for f in by_file.values() if f.stages)
    _task_routes(py, out, tasks)
    return tasks


def _canvas(py, found, rel, fn_name, canvases, pipes, tasks):
    """The stages and edges of one function's Celery canvas: chain, group, chord and `|`."""
    canvas = _Canvas(py, found, rel, fn_name, tasks)
    for call in canvases:
        kind = call_name(call.func)
        if kind == 'chain': canvas.chain(call)
        elif kind == 'group': canvas.group(call)
        elif kind == 'chord' and call.args: canvas.chord(call)
    for pipe in pipes: canvas.pipe(pipe)


class _Canvas:
    """One function's Celery canvas, read call by call into its pipeline's stages, edges and fans."""

    def __init__(self, py, found, rel, fn_name, tasks):
        self.py, self.found, self.rel, self.fn_name, self.tasks = py, found, rel, fn_name, tasks

    def where(self, node):
        return site(self.rel, node.lineno, self.py.line(self.rel, node.lineno))

    def stage_of(self, signature):
        name = _signature(signature, self.tasks)
        if not name: return None
        task_rel, task_node = self.tasks[name]
        key = self.found.stage(name, site(task_rel, task_node.lineno, self.py.line(task_rel, task_node.lineno)),
                               symbol=f"{task_rel[:-3].replace('/', '.')}.{name}")
        describe(self.py, task_rel, task_node, self.found.stages[key])
        _task_options(self.py, self.found, key, task_rel, task_node)
        return key

    def members(self, expr):
        if isinstance(expr, (ast.GeneratorExp, ast.ListComp)): return [self.stage_of(expr.elt)], True
        if isinstance(expr, (ast.List, ast.Tuple)): return [self.stage_of(e) for e in expr.elts], False
        return [self.stage_of(expr)], False

    def fork(self):
        return self.found.stage(f'{self.fn_name} fan-out', _def_site(self.py, self.rel, self.fn_name), kind='fork',
                                symbol=f"{self.rel[:-3].replace('/', '.')}.{self.fn_name}")

    def chain(self, call):
        keys = [self.stage_of(arg) for arg in call.args]
        for index, (a, b) in enumerate(zip(keys, keys[1:])):
            arg = call.args[index + 1]
            immutable = isinstance(arg, ast.Call) and call_name(arg.func) == 'si'
            if a and b: self.found.edge(a, b, 'order' if immutable else 'value', self.where(arg),
                                        names=[] if immutable else ['return value'], kind='control' if immutable else 'data')

    def group(self, call):
        header, mapped = self.members(call.args[0]) if len(call.args) == 1 else ([self.stage_of(a) for a in call.args], False)
        fork, found = self.fork(), self.found
        found.fans.append({'id': f'{found.id}:group:{call.lineno}', 'pipeline': found.id, 'fork': fork, 'join': None,
                           'branches': [k for k in header if k], 'matched': False, 'kind': 'map' if mapped else 'group',
                           'evidence': self.where(call)})

    def chord(self, call):
        first = call.args[0]
        header, mapped = self.members(first.args[0] if isinstance(first, ast.Call) and call_name(first.func) == 'group' and first.args else first)
        body = self.stage_of(call.args[1]) if len(call.args) > 1 else None
        fork, found, where = self.fork(), self.found, self.where(call)
        for key in header:
            if key and body: found.edge(key, body, 'value', where, names=['results'])
        found.fans.append({'id': f'{found.id}:chord:{call.lineno}', 'pipeline': found.id, 'fork': fork, 'join': body,
                           'branches': [k for k in header if k], 'matched': bool(body), 'kind': 'chord', 'evidence': where})

    def pipe(self, pipe):
        items, node = [], pipe
        while isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            items.insert(0, node.right)
            node = node.left
        items.insert(0, node)
        keys = [self.stage_of(i) for i in items]
        for a, b in zip(keys, keys[1:]):
            if a and b: self.found.edge(a, b, 'value', self.where(pipe), names=['return value'])


def _def_site(py, rel, name):
    node = py.defs.get(rel, {}).get(name)
    return site(rel, node.lineno if node else None, py.line(rel, node.lineno) if node else None)


def _signature(expr, tasks):
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr in SIGNATURES \
            and isinstance(expr.func.value, ast.Name) and expr.func.value.id in tasks:
        return expr.func.value.id
    return None


def _task_options(py, found, key, rel, node):
    for item in node.decorator_list:
        if not isinstance(item, ast.Call): continue
        for keyword in item.keywords:
            if keyword.arg in ('autoretry_for', 'max_retries', 'retry_backoff', 'retry_kwargs') and \
                    not any(c['id'] == f'{key}:retry' for c in found.control):
                text = _unparse(keyword.value).replace(' ', '')
                if text in ('()', '0', 'None', 'False') or re.search(r"max_retries['\"]?:0\b", text): continue
                found.control.append({'id': f'{key}:retry', 'pipeline': found.id, 'stage': key, 'kind': 'retry',
                                      'condition': _unparse(keyword.value), 'evidence': site(rel, item.lineno, py.line(rel, item.lineno))})
                found.errors.append({'id': f'{key}:retry', 'pipeline': found.id, 'from': key, 'to': key, 'kind': 'retry',
                                     'condition': _unparse(keyword.value), 'evidence': site(rel, item.lineno, py.line(rel, item.lineno))})
            if keyword.arg in TIMEOUT_WORDS: found.stages[key]['timeout'] = True
    for other in py.defs.get(rel, {}).values():
        for item in other.decorator_list:
            if isinstance(item, ast.Attribute) and item.attr == 'on_failure' and isinstance(item.value, ast.Name) and item.value.id == node.name:
                queue = next((_str(k.value) for s in ast.walk(other) if isinstance(s, ast.Call) for k in s.keywords if k.arg == 'queue'), None)
                found.errors.append({'id': f'{key}:on_failure', 'pipeline': found.id, 'from': key, 'to': queue or other.name, 'kind': 'fail',
                                     'condition': 'retries exhausted', 'evidence': site(rel, other.lineno, py.line(rel, other.lineno))})


def _task_routes(py, out, tasks):
    for rel, tree in py.trees.items():
        for sub in ast.walk(tree):
            if isinstance(sub, ast.Assign) and len(sub.targets) == 1 and _unparse(sub.targets[0]).endswith('task_routes') \
                    and isinstance(sub.value, ast.Dict):
                for found in out:
                    if found.kind != 'celery': continue
                    by_symbol = {(s['symbol'] or '').split('.', 1)[-1]: k for k, s in found.stages.items()}
                    by_symbol.update({(s['symbol'] or ''): k for k, s in found.stages.items()})
                    branches = []
                    for key, value in zip(sub.value.keys, sub.value.values):
                        label = _str(key)
                        if label is None: continue
                        queue = next((_str(v) for k, v in zip(value.keys, value.values) if _str(k) == 'queue'), None) if isinstance(value, ast.Dict) else None
                        to = next((k for symbol, k in by_symbol.items() if symbol and (label == symbol or label.endswith('.' + found.stages[k]['label'])
                                                                                   and symbol.endswith(found.stages[k]['label']))), None)
                        branches.append({'condition': label, 'to': to, 'evidence': site(rel, key.lineno, py.line(rel, key.lineno)), 'queue': queue})
                    if not any(b['to'] for b in branches): continue
                    router = found.stage('task_routes', site(rel, sub.lineno, py.line(rel, sub.lineno)), kind='router')
                    found.routers.append({'id': f'{found.id}:task_routes', 'pipeline': found.id, 'stage': router, 'kind': 'dict_dispatch',
                                          'table': 'task_routes', 'on': 'task name',
                                          'entry': site(rel, sub.lineno, py.line(rel, sub.lineno)),
                                          'branches': [{k: v for k, v in b.items() if k != 'queue'} | {'condition': b['condition']} for b in branches],
                                          'total': True, 'default': 'default queue', 'unhandled': []})
                    found.evidence.append(site(rel, sub.lineno, py.line(rel, sub.lineno)))
                    break


def _loop_values(tree):
    """A function giving, for a node, {name: [literal strings]} of the `for name in <literal list>` loops around it (the list
    written in place or assigned to a name), so `add_edge('a', name)` in such a loop means each listed value."""
    parents, lists = _parents(tree), _literal_lists(tree)

    def values(node):
        found, current = {}, parents.get(id(node))
        while current is not None:
            if isinstance(current, ast.For) and isinstance(current.target, ast.Name):
                items = _loop_items(current, lists)
                if items: found.setdefault(current.target.id, items)
            current = parents.get(id(current))
        return found
    return values


def _parents(tree):
    """{id(node): its parent} over the whole tree."""
    return {id(child): parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _literal_lists(tree):
    """{name: [strings]} of the names assigned a list or tuple of string literals."""
    lists = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and \
                isinstance(node.value, (ast.List, ast.Tuple)) and node.value.elts and all(_str(e) is not None for e in node.value.elts):
            lists[node.targets[0].id] = _strs(node.value)
    return lists


def _loop_items(loop, lists):
    """The strings a `for` loop walks: a list written in place, or one assigned to the name it iterates."""
    if isinstance(loop.iter, (ast.List, ast.Tuple)): return _strs(loop.iter)
    return lists.get(loop.iter.id) if isinstance(loop.iter, ast.Name) else None


def langgraph(py, out):
    for rel, tree in py.trees.items():
        if not any((module or '').split('.')[0] == 'langgraph' for module, _ in py.imports.get(rel, {}).values()): continue
        graphs = {}
        for sub in ast.walk(tree):
            if isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Call) and call_name(sub.value.func) in ('StateGraph', 'Graph', 'MessageGraph') \
                    and len(sub.targets) == 1 and isinstance(sub.targets[0], (ast.Name, ast.Attribute)):
                name = _unparse(sub.targets[0])
                graphs[name] = Found(f'{rel}:{name}', f'{name} ({rel})', 'langgraph', site(rel, sub.lineno, py.line(rel, sub.lineno)),
                                     [site(rel, sub.lineno, py.line(rel, sub.lineno))])
        if not graphs: continue
        loops = _loop_values(tree)
        calls = sorted((s for s in ast.walk(tree) if isinstance(s, ast.Call) and isinstance(s.func, ast.Attribute)
                        and _unparse(s.func.value) in graphs), key=lambda s: s.lineno)
        for call in calls:
            found, method, where = graphs[_unparse(call.func.value)], call.func.attr, site(rel, call.lineno, py.line(rel, call.lineno))
            bound = loops(call)
            node_key = lambda label: found.stage(label, where, kind='source' if label == 'START' else 'sink' if label == 'END' else 'stage')

            def labels(expr):
                if _str(expr) is not None: return [_str(expr)]
                if isinstance(expr, ast.Name): return bound.get(expr.id) or [expr.id]
                if isinstance(expr, (ast.List, ast.Tuple)): return [l for e in expr.elts for l in labels(e)]
                return []

            label_of = lambda expr: (labels(expr) or [None])[0]
            if method == 'add_node' and call.args:
                key = node_key(label_of(call.args[0]))
                fn = call.args[1] if len(call.args) > 1 else call.args[0]
                target = py.resolve(rel, fn.id) if isinstance(fn, ast.Name) else None
                found.stages[key]['symbol'] = f"{target[0][:-3].replace('/', '.')}.{target[1].name}" if target else _unparse(fn, 120)
                if target: describe(py, target[0], target[1], found.stages[key])
            elif method == 'add_edge' and len(call.args) >= 2:
                for a in labels(call.args[0]):
                    for b in labels(call.args[1]):
                        found.edge(node_key(a), node_key(b), 'declared', where, kind='data')
            elif method in ('set_entry_point', 'set_finish_point') and call.args:
                ends = (node_key('START'), node_key(label_of(call.args[0]))) if method == 'set_entry_point' else (node_key(label_of(call.args[0])), node_key('END'))
                found.edge(*ends, 'declared', where)
            elif method == 'add_conditional_edges' and len(call.args) >= 2:
                source = node_key(label_of(call.args[0]))
                mapping = call.args[2] if len(call.args) > 2 else next((k.value for k in call.keywords if k.arg in ('path_map', 'conditional_edge_mapping')), None)
                branches = []
                if isinstance(mapping, ast.Dict):
                    for key, value in zip(mapping.keys, mapping.values):
                        to = node_key(label_of(value))
                        branches.append({'condition': _str(key) or _unparse(key), 'to': to, 'evidence': site(rel, key.lineno if key else call.lineno, py.line(rel, key.lineno if key else call.lineno))})
                        found.edge(source, to, 'declared', where, kind='control', condition=_str(key) or _unparse(key))
                elif isinstance(mapping, (ast.List, ast.Tuple)):
                    for value in mapping.elts:
                        to = node_key(label_of(value))
                        branches.append({'condition': label_of(value), 'to': to, 'evidence': where})
                        found.edge(source, to, 'declared', where, kind='control', condition=label_of(value))
                else:
                    found.unresolved.append({'id': f'{source}:route:{call.lineno}', 'pipeline': found.id, 'stage': source,
                                             'call': _unparse(call.args[1]), 'reason': 'the router returns node names EAOS cannot list', 'evidence': where})
                router_fn = label_of(call.args[1]) or _unparse(call.args[1], 40) or 'router'
                router = found.stage(router_fn, where, kind='router')
                found.edge(source, router, 'declared', where, kind='control')
                found.routers.append({'id': f'{found.id}:{slug(router_fn)}:{call.lineno}', 'pipeline': found.id, 'stage': router,
                                      'kind': 'conditional_edges', 'table': router_fn, 'on': f'{router_fn}(state)', 'entry': where,
                                      'branches': branches, 'total': None if branches else False, 'default': None, 'unhandled': []})
        out.extend(f for f in graphs.values() if f.stages)


def luigi(py, out):
    tasks = {}
    for rel, classes in py.classes.items():
        for name, node in classes.items():
            if any(call_name(base) in ('Task', 'WrapperTask', 'ExternalTask') for base in node.bases) and \
                    any((m or '').startswith('luigi') for m, _ in py.imports.get(rel, {}).values()):
                tasks[name] = (rel, node)
    if len(tasks) < 2: return
    rel0 = sorted(tasks.values(), key=lambda t: t[0])[0][0]
    found = Found(f'{rel0}:luigi', f'luigi tasks ({rel0})', 'luigi', site(rel0, 1, py.line(rel0, 1)))
    for name, (rel, node) in tasks.items():
        found.stage(name, site(rel, node.lineno, py.line(rel, node.lineno)), symbol=f"{rel[:-3].replace('/', '.')}.{name}")
    for name, (rel, node) in tasks.items():
        requires = next((f for f in node.body if isinstance(f, ast.FunctionDef) and f.name == 'requires'), None)
        if not requires: continue
        for sub in ast.walk(requires):
            if isinstance(sub, ast.Call) and call_name(sub.func) in tasks:
                found.edge(f'{found.id}/{slug(call_name(sub.func))}', f'{found.id}/{slug(name)}', 'declared', site(rel, sub.lineno, py.line(rel, sub.lineno)))
    if found.edges: out.append(found)


def _need_values(value):
    """The jobs a `needs:` value names on its own line: a list in brackets or one name."""
    if value.startswith('['): return [v.strip(' "\'') for v in value.strip('[]').split(',') if v.strip()]
    return [value.strip('"\'')] if value else []


def _read_jobs(lines, jobs_at):
    """{job: {line, needs, needs_line}} of a workflow's `jobs:` block, its `needs` inline or as a list below."""
    jobs, current, indent, needs_line = {}, None, None, None
    for number, line in enumerate(lines[jobs_at + 1:], start=jobs_at + 2):
        if not line.strip() or line.lstrip().startswith('#'): continue
        depth = len(line) - len(line.lstrip())
        if depth == 0: break
        match = re.match(r'^(\s*)([A-Za-z0-9_-]+):\s*(#.*)?$', line)
        if indent is None and match: indent = depth
        if match and depth == indent:
            current, needs_line = match.group(2), None
            jobs[current] = {'line': number, 'needs': [], 'needs_line': None}
            continue
        if current is None: continue
        need = re.match(r'^\s*needs:\s*(.*)$', line)
        if need and depth == indent + 2:
            value = need.group(1).split('#')[0].strip()
            jobs[current]['needs_line'] = number
            jobs[current]['needs'] += _need_values(value)
            if not value: needs_line = depth
            continue
        if needs_line is not None:
            item = re.match(r'^\s*-\s*([A-Za-z0-9_-]+)', line)
            if item and depth > needs_line:
                jobs[current]['needs'].append(item.group(1))
                continue
            needs_line = None
    return jobs


def github_actions(rel, text, out):
    lines = text.splitlines()
    jobs_at = next((i for i, line in enumerate(lines) if re.match(r'^jobs:\s*$', line)), None)
    if jobs_at is None: return
    jobs = _read_jobs(lines, jobs_at)
    if not any(job['needs'] for job in jobs.values()): return
    found = Found(f'{rel}:jobs', f'{Path(rel).name} jobs', 'github_actions', site(rel, jobs_at + 1, lines[jobs_at]),
                  [site(rel, jobs_at + 1, lines[jobs_at])])
    for name, job in jobs.items(): found.stage(name, site(rel, job['line'], lines[job['line'] - 1]))
    for name, job in jobs.items():
        for need in job['needs']:
            found.edge(f'{found.id}/{slug(need)}', f'{found.id}/{slug(name)}', 'declared',
                       site(rel, job['needs_line'] or job['line'], lines[(job['needs_line'] or job['line']) - 1]), kind='control')
    _fans(found)
    out.append(found)


def _targets(lines, kind):
    """{target: (line, [targets it depends on])} of a Makefile or a justfile."""
    targets = {}
    pattern = re.compile(r'^([A-Za-z0-9_.\-/]+)\s*:(?!=)\s*([^#=]*)$' if kind == 'makefile' else r'^@?([A-Za-z0-9_-]+)(?:\s+[^:]*)?:\s*([^#=]*)$')
    for number, line in enumerate(lines, start=1):
        match = pattern.match(line)
        if match and not match.group(1).startswith('.'):
            targets[match.group(1)] = (number, [t for t in match.group(2).split() if not t.startswith(('$', '"', "'"))])
    return targets


def make_targets(rel, text, out, kind):
    lines = text.splitlines()
    targets = _targets(lines, kind)
    edges = [(need, name) for name, (_, needs) in targets.items() for need in needs if need in targets]
    if len(edges) < 2: return
    found = Found(f'{rel}:targets', f'{Path(rel).name} targets', kind, site(rel, 1, lines[0] if lines else ''))
    for name, (number, _) in targets.items():
        if any(name in edge for edge in edges): found.stage(name, site(rel, number, lines[number - 1]))
    for need, name in edges:
        found.edge(f'{found.id}/{slug(need)}', f'{found.id}/{slug(name)}', 'declared', site(rel, targets[name][0], lines[targets[name][0] - 1]), kind='control')
    out.append(found)


def npm_scripts(rel, text, out):
    try: scripts = (json.loads(text) or {}).get('scripts') or {}
    except (ValueError, AttributeError): return
    lines = text.splitlines()
    for name, command in scripts.items():
        if not isinstance(command, str) or '&&' not in command: continue
        parts = [p.strip() for p in command.split('&&') if p.strip()]
        if len(parts) < 2: continue
        number = next((i for i, line in enumerate(lines, start=1) if re.search(rf'"{re.escape(name)}"\s*:', line)), 1)
        found = Found(f'{rel}:{name}', f'npm run {name}', 'npm_scripts', site(rel, number, lines[number - 1] if lines else ''),
                      [site(rel, number, lines[number - 1] if lines else '')])
        previous = None
        for part in parts:
            match = re.match(r'^(?:npm|pnpm|yarn|bun)(?:\s+run)?\s+([A-Za-z0-9:_.-]+)', part)
            label = match.group(1) if match else part
            key = found.stage(label, site(rel, number, lines[number - 1]))
            found.stages[key]['tools'] = [part.split()[0]]
            if previous: found.edge(previous, key, 'order', site(rel, number, lines[number - 1]), kind='control')
            previous = key
        out.append(found)


def json_exports(rel, text, out):
    if not text.lstrip().startswith(('{', '[')) or len(text) > 2_000_000: return
    try: data = json.loads(text)
    except ValueError: return
    lines = text.splitlines()
    line_of = lambda word: next((i for i, line in enumerate(lines, start=1) if word in line), 1)
    if isinstance(data, dict) and isinstance(data.get('States'), dict) and data.get('StartAt'):
        out.append(_step_functions(rel, data, line_of))
        return
    if isinstance(data, dict) and isinstance(data.get('nodes'), list) and isinstance(data.get('connections'), dict):
        found = _n8n(rel, data, line_of)
    elif isinstance(data, list) and data and all(isinstance(n, dict) for n in data) and any('wires' in n for n in data):
        found = _node_red(rel, data, line_of)
    else:
        return
    if found.edges: out.append(found)


def _step_functions(rel, data, line_of):
    """A Step Functions state machine: its states, their next states, its choices and its catches."""
    found = Found(f'{rel}:states', f'{Path(rel).name} state machine', 'step_functions', site(rel, line_of('"StartAt"'), None))
    for name in data['States']: found.stage(name, site(rel, line_of(f'"{name}"'), None))
    for name, state in data['States'].items():
        if isinstance(state, dict): _state_links(found, rel, name, state, data['States'], site(rel, line_of(f'"{name}"'), None))
    return found


def _state_links(found, rel, name, state, states, where):
    """One state's edges to its next, default and chosen states, its choice router and its catches."""
    stage = f'{found.id}/{slug(name)}'
    for target in [state.get('Next'), state.get('Default')] + [c.get('Next') for c in state.get('Choices') or [] if isinstance(c, dict)]:
        if target in states: found.edge(stage, f'{found.id}/{slug(target)}', 'declared', where)
    if state.get('Type') == 'Choice':
        found.routers.append({'id': f'{found.id}:{slug(name)}', 'pipeline': found.id, 'stage': stage, 'kind': 'switch',
                              'table': name, 'on': name, 'entry': where,
                              'branches': [{'condition': _unparse_choice(c), 'to': f"{found.id}/{slug(c.get('Next'))}", 'evidence': where}
                                           for c in state.get('Choices') or [] if isinstance(c, dict)],
                              'total': bool(state.get('Default')), 'default': state.get('Default'), 'unhandled': []})
    for catch in state.get('Catch') or []:
        if isinstance(catch, dict) and catch.get('Next'):
            found.errors.append({'id': f'{found.id}:{slug(name)}:catch', 'pipeline': found.id, 'from': stage,
                                 'to': catch['Next'], 'kind': 'catch', 'condition': ','.join(catch.get('ErrorEquals') or []),
                                 'evidence': where})


def _n8n(rel, data, line_of):
    """An n8n workflow: its nodes and their main connections."""
    found = Found(f'{rel}:n8n', str(data.get('name') or Path(rel).stem), 'n8n', site(rel, line_of('"nodes"'), None))
    for node in data['nodes']:
        if isinstance(node, dict) and node.get('name'): found.stage(node['name'], site(rel, line_of(f'"{node["name"]}"'), None))
    for source, outputs in data['connections'].items():
        targets = [target for lane in (outputs or {}).get('main') or [] for target in lane or [] if isinstance(target, dict)]
        for target in targets:
            found.edge(f'{found.id}/{slug(source)}', f"{found.id}/{slug(target.get('node'))}", 'declared', site(rel, line_of(f'"{source}"'), None))
    return found


def _node_red(rel, data, line_of):
    """A Node-RED flow: its wired nodes and their wires."""
    found = Found(f'{rel}:flow', Path(rel).stem, 'node_red', site(rel, 1, None))
    ids = {n.get('id'): n.get('name') or n.get('type') or n.get('id') for n in data if n.get('id')}
    for node in data:
        if node.get('id') and node.get('wires') is not None: found.stage(ids[node['id']], site(rel, line_of(f'"{node["id"]}"'), None))
    for node in data:
        targets = [target for port in node.get('wires') or [] for target in port or [] if target in ids]
        for target in targets:
            found.edge(f'{found.id}/{slug(ids[node["id"]])}', f'{found.id}/{slug(ids[target])}', 'declared', site(rel, line_of(f'"{node["id"]}"'), None))
    return found


def _unparse_choice(choice):
    keys = [k for k in choice if k not in ('Next',)]
    return ' '.join(f'{k}={choice[k]}' for k in keys)[:80] or 'choice'


def _fans(found):
    """Forks (one stage feeding several) and their joins (one stage fed by all of them)."""
    outgoing, incoming = defaultdict(list), defaultdict(set)
    for a, b in found.edges: outgoing[a].append(b); incoming[b].add(a)
    for fork, branches in outgoing.items():
        if len(branches) < 2: continue
        joins = [stage for stage, sources in incoming.items() if set(branches) <= sources]
        found.fans.append({'id': f'{fork}:fan', 'pipeline': found.id, 'fork': fork, 'join': joins[0] if joins else None,
                           'branches': branches, 'matched': bool(joins), 'kind': 'parallel', 'evidence': found.stages[fork]['entry']})


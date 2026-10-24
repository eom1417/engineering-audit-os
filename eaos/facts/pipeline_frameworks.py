"""Pipelines declared in a Python framework's own syntax (Airflow, Celery, Luigi), read without running them
(eaos/facts/pipeline.py; LangGraph: eaos/facts/pipeline_langgraph.py; build, CI and workflow files:
eaos/facts/pipeline_files.py)."""
import ast
import re

from . import call_name
from .pipeline_read import slug, site, Found, _str, _strs, _decorators, _unparse, describe, TIMEOUT_WORDS, SIGNATURES


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
        task_id = _task_id(sub)
        if task_id: tasks[sub.targets[0].id] = (task_id, sub.value)
    return found, tasks


def _task_id(sub):
    """The task_id of `variable = Operator(task_id='...')`, or None."""
    if isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Call) and len(sub.targets) == 1 and isinstance(sub.targets[0], ast.Name):
        return next((_str(k.value) for k in sub.value.keywords if k.arg == 'task_id'), None)
    return None


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
    tasks = _celery_tasks(py)
    if not tasks: return tasks
    by_file = {}
    for rel, fn_name, fn in py.functions():
        canvases, pipes = _canvas_calls(fn, tasks)
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


def _celery_tasks(py):
    """{name: (rel, def)} of the functions a Celery (or director) task decorator declares."""
    tasks = {}
    for rel, name, node in py.functions():
        decorators = _decorators(node)
        if any(d in ('shared_task', 'task') for d in decorators) and any(
                (module or '').split('.')[0] in ('celery', 'director') or (module or '') in py.modules
                for module, _ in py.imports.get(rel, {}).values()):
            tasks[name] = (rel, node)
    return tasks


def _canvas_calls(fn, tasks):
    """A function's canvas calls (chain, group, chord) and its `|` pipes of task signatures."""
    canvases = [sub for sub in ast.walk(fn) if isinstance(sub, ast.Call) and call_name(sub.func) in ('chain', 'group', 'chord')]
    pipes = [sub for sub in ast.walk(fn) if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.BitOr) and _signature(sub.left, tasks)]
    return canvases, pipes


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
    """A task's retries and timeout (its decorator's options), and the handlers its failure goes to (@task.on_failure)."""
    for item in node.decorator_list:
        if isinstance(item, ast.Call): _decorator_options(py, found, key, rel, item)
    for other in py.defs.get(rel, {}).values():
        for item in other.decorator_list:
            if isinstance(item, ast.Attribute) and item.attr == 'on_failure' and isinstance(item.value, ast.Name) and item.value.id == node.name:
                found.errors.append({'id': f'{key}:on_failure', 'pipeline': found.id, 'from': key, 'to': _queue_of(other) or other.name,
                                     'kind': 'fail', 'condition': 'retries exhausted',
                                     'evidence': site(rel, other.lineno, py.line(rel, other.lineno))})


def _decorator_options(py, found, key, rel, item):
    """A task decorator's retry options (one retry lane, unless they turn retrying off) and its timeout."""
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


def _queue_of(handler):
    """The queue a failure handler sends to (a call's queue='...'), or None."""
    return next((_str(k.value) for s in ast.walk(handler) if isinstance(s, ast.Call) for k in s.keywords if k.arg == 'queue'), None)


def _task_routes(py, out, tasks):
    for rel, tree in py.trees.items():
        for sub in ast.walk(tree):
            if isinstance(sub, ast.Assign) and len(sub.targets) == 1 and _unparse(sub.targets[0]).endswith('task_routes') \
                    and isinstance(sub.value, ast.Dict):
                _route_table(py, out, rel, sub)


def _route_table(py, out, rel, sub):
    """The first Celery pipeline whose stages a task_routes table names gets the table as its router."""
    for found in out:
        if found.kind != 'celery': continue
        branches = _route_branches(py, rel, sub, found)
        if not any(b['to'] for b in branches): continue
        router = found.stage('task_routes', site(rel, sub.lineno, py.line(rel, sub.lineno)), kind='router')
        found.routers.append({'id': f'{found.id}:task_routes', 'pipeline': found.id, 'stage': router, 'kind': 'dict_dispatch',
                              'table': 'task_routes', 'on': 'task name',
                              'entry': site(rel, sub.lineno, py.line(rel, sub.lineno)),
                              'branches': [{k: v for k, v in b.items() if k != 'queue'} | {'condition': b['condition']} for b in branches],
                              'total': True, 'default': 'default queue', 'unhandled': []})
        found.evidence.append(site(rel, sub.lineno, py.line(rel, sub.lineno)))
        return


def _route_branches(py, rel, sub, found):
    """Each task name of the table, the stage it names (None when none) and its queue."""
    by_symbol = {(s['symbol'] or '').split('.', 1)[-1]: k for k, s in found.stages.items()}
    by_symbol.update({(s['symbol'] or ''): k for k, s in found.stages.items()})
    branches = []
    for key, value in zip(sub.value.keys, sub.value.values):
        label = _str(key)
        if label is None: continue
        queue = next((_str(v) for k, v in zip(value.keys, value.values) if _str(k) == 'queue'), None) if isinstance(value, ast.Dict) else None
        branches.append({'condition': label, 'to': _routed_stage(found, by_symbol, label),
                         'evidence': site(rel, key.lineno, py.line(rel, key.lineno)), 'queue': queue})
    return branches


def _routed_stage(found, by_symbol, label):
    """The stage a task name of the routes table names: its symbol, or a dotted name ending on the stage's task."""
    return next((k for symbol, k in by_symbol.items() if symbol and (label == symbol or label.endswith('.' + found.stages[k]['label'])
                                                                    and symbol.endswith(found.stages[k]['label']))), None)


def luigi(py, out):
    tasks = _luigi_tasks(py)
    if len(tasks) < 2: return
    rel0 = sorted(tasks.values(), key=lambda t: t[0])[0][0]
    found = Found(f'{rel0}:luigi', f'luigi tasks ({rel0})', 'luigi', site(rel0, 1, py.line(rel0, 1)))
    for name, (rel, node) in tasks.items():
        found.stage(name, site(rel, node.lineno, py.line(rel, node.lineno)), symbol=f"{rel[:-3].replace('/', '.')}.{name}")
    for name, (rel, node) in tasks.items():
        requires = _method(node, 'requires')
        if not requires: continue
        for sub in ast.walk(requires):
            if isinstance(sub, ast.Call) and call_name(sub.func) in tasks:
                found.edge(f'{found.id}/{slug(call_name(sub.func))}', f'{found.id}/{slug(name)}', 'declared', site(rel, sub.lineno, py.line(rel, sub.lineno)))
    if found.edges: out.append(found)


def _method(cls, name):
    """The method `name` a class defines, or None."""
    return next((f for f in cls.body if isinstance(f, ast.FunctionDef) and f.name == name), None)


def _luigi_tasks(py):
    """{name: (rel, class)} of the Luigi task classes of the modules importing luigi."""
    tasks = {}
    for rel, classes in py.classes.items():
        for name, node in classes.items():
            if any(call_name(base) in ('Task', 'WrapperTask', 'ExternalTask') for base in node.bases) and \
                    any((m or '').startswith('luigi') for m, _ in py.imports.get(rel, {}).values()):
                tasks[name] = (rel, node)
    return tasks

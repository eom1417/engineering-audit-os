"""Pipelines declared in a framework's own syntax (Airflow, Celery, LangGraph, Luigi, queue topics) and in build, CI and
workflow files (GitHub Actions, Make, just, npm scripts, Step Functions, n8n, Node-RED), read without running them
(eaos/facts/pipeline.py)."""
import ast
import json
import re
from collections import defaultdict
from pathlib import Path

from .pipeline_read import (slug, site, Found, _str, _strs, _name, _decorators, _unparse, describe, TIMEOUT_WORDS, SIGNATURES)


def airflow(py, out, flows):
    for rel, tree in py.trees.items():
        if not any((module or '').split('.')[0] == 'airflow' for module, _ in py.imports.get(rel, {}).values()): continue
        found = None
        tasks = {}
        for sub in ast.walk(tree):
            if isinstance(sub, ast.Call) and _name(sub.func) == 'DAG':
                dag_id = next((_str(k.value) for k in sub.keywords if k.arg == 'dag_id'), None) or (_str(sub.args[0]) if sub.args else None)
                if dag_id and found is None:
                    found = Found(f'{rel}:{dag_id}', dag_id, 'airflow', site(rel, sub.lineno, py.line(rel, sub.lineno)),
                                  [site(rel, sub.lineno, py.line(rel, sub.lineno))])
            if isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Call) and len(sub.targets) == 1 and isinstance(sub.targets[0], ast.Name):
                task_id = next((_str(k.value) for k in sub.value.keywords if k.arg == 'task_id'), None)
                if task_id: tasks[sub.targets[0].id] = (task_id, sub.value)
        if found is None or not tasks: continue
        found.functions.add((rel, '<dag>'))
        keys = {}
        for var, (task_id, call) in tasks.items():
            line = next((k.value.lineno for k in call.keywords if k.arg == 'task_id'), call.lineno)
            keys[var] = found.stage(task_id, site(rel, line, py.line(rel, line)), symbol=f"{rel[:-3].replace('/', '.')}.{var}", variable=var)
            stage = found.stages[keys[var]]
            stage['tools'] = [_name(call.func) or 'Operator']
            for keyword in call.keywords:
                if keyword.arg == 'python_callable' and isinstance(keyword.value, ast.Name):
                    target = py.resolve(rel, keyword.value.id)
                    if target:
                        flows.add((target[0], target[1].name))
                        stage['symbol'] = f"{target[0][:-3].replace('/', '.')}.{target[1].name}"
                        stage['callable'] = (target[0], target[1].name)
                        describe(py, target[0], target[1], stage)
                        if 'Branch' in (_name(call.func) or ''): _branch_operator(py, found, keys[var], target, tasks, rel, call)
                        for pull in ast.walk(target[1]):
                            if isinstance(pull, ast.Call) and _name(pull.func) == 'xcom_pull':
                                for keyword2 in pull.keywords:
                                    if keyword2.arg == 'task_ids':
                                        for upstream in _strs(keyword2.value):
                                            stage.setdefault('xcom', []).append((upstream, target[0], pull.lineno))
                if keyword.arg in ('retries', 'retry_delay'):
                    found.control.append({'id': f'{keys[var]}:retry', 'pipeline': found.id, 'stage': keys[var], 'kind': 'retry',
                                          'condition': _unparse(keyword.value), 'evidence': site(rel, call.lineno, py.line(rel, call.lineno))})
                if keyword.arg in TIMEOUT_WORDS: stage['timeout'] = True
        by_task = {found.stages[k]['label']: k for k in keys.values()}

        def ends(expr):
            if isinstance(expr, ast.Name) and expr.id in keys: return [keys[expr.id]]
            if isinstance(expr, (ast.List, ast.Tuple)): return [k for e in expr.elts for k in ends(e)]
            if isinstance(expr, ast.BinOp) and isinstance(expr.op, (ast.RShift, ast.LShift)): return ends(expr.right if isinstance(expr.op, ast.RShift) else expr.left)
            return []

        def heads(expr):
            if isinstance(expr, ast.BinOp) and isinstance(expr.op, (ast.RShift, ast.LShift)): return heads(expr.left if isinstance(expr.op, ast.RShift) else expr.right)
            return ends(expr)

        for sub in ast.walk(tree):
            if isinstance(sub, ast.BinOp) and isinstance(sub.op, (ast.RShift, ast.LShift)):
                left, right = (sub.left, sub.right) if isinstance(sub.op, ast.RShift) else (sub.right, sub.left)
                where = site(rel, sub.lineno, py.line(rel, sub.lineno))
                sources = ends(left)
                targets = heads(right)
                for a in sources:
                    for b in targets: found.edge(a, b, 'declared', where, kind='data')
                if len(targets) > 1:
                    for a in sources:
                        found.fans.append({'id': f'{a}:fan:{sub.lineno}', 'pipeline': found.id, 'fork': a, 'join': None,
                                           'branches': targets, 'matched': False, 'kind': 'parallel', 'evidence': where})
            elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr in ('set_downstream', 'set_upstream') \
                    and isinstance(sub.func.value, ast.Name) and sub.func.value.id in keys:
                for b in ends(sub.args[0]) if sub.args else []:
                    a = keys[sub.func.value.id]
                    found.edge(*((a, b) if sub.func.attr == 'set_downstream' else (b, a)), 'declared', site(rel, sub.lineno, py.line(rel, sub.lineno)))
            elif isinstance(sub, ast.Call) and _name(sub.func) == 'chain':
                items = [ends(arg) for arg in sub.args]
                for left, right in zip(items, items[1:]):
                    for a in left:
                        for b in right: found.edge(a, b, 'declared', site(rel, sub.lineno, py.line(rel, sub.lineno)))
        for key in keys.values():
            for upstream, path, line in found.stages[key].pop('xcom', []):
                if upstream in by_task:
                    found.edge(by_task[upstream], key, 'value', site(path, line, py.line(path, line)), names=['xcom'])
        for fan in found.fans:
            joins = {b for (a, b) in found.edges for branch in fan['branches'] if a == branch}
            if len(joins) == 1 and all((branch, next(iter(joins))) in found.edges for branch in fan['branches']):
                fan['join'], fan['matched'] = next(iter(joins)), True
        out.append(found)


def _branch_operator(py, found, key, target, tasks, rel, call):
    returns = sorted(((_strs(s.value) or [], s.lineno) for s in ast.walk(target[1]) if isinstance(s, ast.Return) and s.value is not None),
                     key=lambda row: row[1])
    by_task = {task_id: None for task_id, _ in tasks.values()}
    branches = []
    for values, line in returns:
        for value in values:
            branches.append({'condition': f'returns {value!r}', 'to': f"{found.id}/{slug(value)}" if value in by_task else None,
                             'evidence': site(target[0], line, py.line(target[0], line))})
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
        canvases = [sub for sub in ast.walk(fn) if isinstance(sub, ast.Call) and _name(sub.func) in ('chain', 'group', 'chord')]
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
    def stage_of(signature):
        name = _signature(signature, tasks)
        if not name: return None
        task_rel, task_node = tasks[name]
        key = found.stage(name, site(task_rel, task_node.lineno, py.line(task_rel, task_node.lineno)),
                          symbol=f"{task_rel[:-3].replace('/', '.')}.{name}")
        describe(py, task_rel, task_node, found.stages[key])
        _task_options(py, found, key, task_rel, task_node)
        return key

    def members(expr):
        if isinstance(expr, (ast.GeneratorExp, ast.ListComp)): return [stage_of(expr.elt)], True
        if isinstance(expr, (ast.List, ast.Tuple)): return [stage_of(e) for e in expr.elts], False
        return [stage_of(expr)], False

    for call in canvases:
        kind = _name(call.func)
        where = site(rel, call.lineno, py.line(rel, call.lineno))
        if kind == 'chain':
            keys = [stage_of(arg) for arg in call.args]
            for index, (a, b) in enumerate(zip(keys, keys[1:])):
                immutable = isinstance(call.args[index + 1], ast.Call) and _name(call.args[index + 1].func) == 'si'
                if a and b: found.edge(a, b, 'order' if immutable else 'value', site(rel, call.args[index + 1].lineno, py.line(rel, call.args[index + 1].lineno)),
                                       names=[] if immutable else ['return value'], kind='control' if immutable else 'data')
        elif kind == 'group':
            header, mapped = members(call.args[0]) if len(call.args) == 1 else ([stage_of(a) for a in call.args], False)
            fork = found.stage(f'{fn_name} fan-out', _def_site(py, rel, fn_name), kind='fork', symbol=f"{rel[:-3].replace('/', '.')}.{fn_name}")
            found.fans.append({'id': f'{found.id}:group:{call.lineno}', 'pipeline': found.id, 'fork': fork, 'join': None,
                               'branches': [k for k in header if k], 'matched': False, 'kind': 'map' if mapped else 'group', 'evidence': where})
        elif kind == 'chord' and call.args:
            header, mapped = members(call.args[0].args[0] if isinstance(call.args[0], ast.Call) and _name(call.args[0].func) == 'group'
                                     and call.args[0].args else call.args[0])
            body = stage_of(call.args[1]) if len(call.args) > 1 else None
            fork = found.stage(f'{fn_name} fan-out', _def_site(py, rel, fn_name), kind='fork', symbol=f"{rel[:-3].replace('/', '.')}.{fn_name}")
            for key in header:
                if key and body: found.edge(key, body, 'value', where, names=['results'])
            found.fans.append({'id': f'{found.id}:chord:{call.lineno}', 'pipeline': found.id, 'fork': fork, 'join': body,
                               'branches': [k for k in header if k], 'matched': bool(body), 'kind': 'chord', 'evidence': where})
    for pipe in pipes:
        items, node = [], pipe
        while isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr): items.insert(0, node.right); node = node.left
        items.insert(0, node)
        keys = [stage_of(i) for i in items]
        for a, b in zip(keys, keys[1:]):
            if a and b: found.edge(a, b, 'value', site(rel, pipe.lineno, py.line(rel, pipe.lineno)), names=['return value'])


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
    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent): parents[id(child)] = parent
    lists = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and \
                isinstance(node.value, (ast.List, ast.Tuple)) and node.value.elts and all(_str(e) is not None for e in node.value.elts):
            lists[node.targets[0].id] = _strs(node.value)

    def values(node):
        found, current = {}, parents.get(id(node))
        while current is not None:
            if isinstance(current, ast.For) and isinstance(current.target, ast.Name):
                items = _strs(current.iter) if isinstance(current.iter, (ast.List, ast.Tuple)) else \
                    lists.get(current.iter.id) if isinstance(current.iter, ast.Name) else None
                if items: found.setdefault(current.target.id, items)
            current = parents.get(id(current))
        return found
    return values


def langgraph(py, out):
    for rel, tree in py.trees.items():
        if not any((module or '').split('.')[0] == 'langgraph' for module, _ in py.imports.get(rel, {}).values()): continue
        graphs = {}
        for sub in ast.walk(tree):
            if isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Call) and _name(sub.value.func) in ('StateGraph', 'Graph', 'MessageGraph') \
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
            if any(_name(base) in ('Task', 'WrapperTask', 'ExternalTask') for base in node.bases) and \
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
            if isinstance(sub, ast.Call) and _name(sub.func) in tasks:
                found.edge(f'{found.id}/{slug(_name(sub.func))}', f'{found.id}/{slug(name)}', 'declared', site(rel, sub.lineno, py.line(rel, sub.lineno)))
    if found.edges: out.append(found)


def queues(py, out):
    produced, consumed = defaultdict(list), defaultdict(list)
    for rel, name, node in py.functions():
        modules = {(m or '').split('.')[0] for m, _ in py.imports.get(rel, {}).values()}
        if not modules & {'kafka', 'confluent_kafka', 'aiokafka', 'pika', 'aio_pika', 'nats', 'redis', 'google'}: continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call): continue
            callee = _name(sub.func) or ''
            first = _str(sub.args[0]) if sub.args else None
            keyword = {k.arg: _str(k.value) for k in sub.keywords}
            if callee in ('send', 'produce', 'publish', 'basic_publish', 'xadd') and (first or keyword.get('topic') or keyword.get('routing_key')):
                produced[first or keyword.get('topic') or keyword.get('routing_key')].append((rel, name, node, sub.lineno))
            elif callee in ('subscribe', 'KafkaConsumer', 'basic_consume', 'xread', 'consume') and (sub.args or keyword.get('queue')):
                topics = _strs(sub.args[0]) if sub.args else []
                for topic in topics or [keyword.get('queue')]:
                    if topic: consumed[topic].append((rel, name, node, sub.lineno))
    shared = sorted(set(produced) & set(consumed))
    if not shared: return
    first = produced[shared[0]][0]
    found = Found(f'{first[0]}:topics', 'topics', 'queue', site(first[0], first[3], py.line(first[0], first[3])))
    for topic in shared:
        for rel, name, node, line in produced[topic] + consumed[topic]:
            found.stage(name, site(rel, node.lineno, py.line(rel, node.lineno)), symbol=f"{rel[:-3].replace('/', '.')}.{name}")
        for a in produced[topic]:
            for b in consumed[topic]:
                found.edge(f'{found.id}/{slug(a[1])}', f'{found.id}/{slug(b[1])}', 'topic', site(b[0], b[3], py.line(b[0], b[3])), names=[topic])
    out.append(found)


def github_actions(rel, text, out):
    lines = text.splitlines()
    jobs_at = next((i for i, line in enumerate(lines) if re.match(r'^jobs:\s*$', line)), None)
    if jobs_at is None: return
    jobs, current, indent, needs_line = {}, None, None, None
    for number, line in enumerate(lines[jobs_at + 1:], start=jobs_at + 2):
        if not line.strip() or line.lstrip().startswith('#'): continue
        depth = len(line) - len(line.lstrip())
        if depth == 0: break
        match = re.match(r'^(\s*)([A-Za-z0-9_-]+):\s*(#.*)?$', line)
        if indent is None and match: indent = depth
        if match and depth == indent:
            current = match.group(2); jobs[current] = {'line': number, 'needs': [], 'needs_line': None}; needs_line = None; continue
        if current is None: continue
        need = re.match(r'^\s*needs:\s*(.*)$', line)
        if need and depth == indent + 2:
            value = need.group(1).split('#')[0].strip()
            jobs[current]['needs_line'] = number
            if value.startswith('['): jobs[current]['needs'] += [v.strip(' "\'') for v in value.strip('[]').split(',') if v.strip()]
            elif value: jobs[current]['needs'].append(value.strip('"\''))
            else: needs_line = depth
            continue
        if needs_line is not None:
            item = re.match(r'^\s*-\s*([A-Za-z0-9_-]+)', line)
            if item and depth > needs_line: jobs[current]['needs'].append(item.group(1)); continue
            needs_line = None
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


def make_targets(rel, text, out, kind):
    lines = text.splitlines()
    targets = {}
    pattern = re.compile(r'^([A-Za-z0-9_.\-/]+)\s*:(?!=)\s*([^#=]*)$' if kind == 'makefile' else r'^@?([A-Za-z0-9_-]+)(?:\s+[^:]*)?:\s*([^#=]*)$')
    for number, line in enumerate(lines, start=1):
        match = pattern.match(line)
        if match and not match.group(1).startswith('.'):
            targets[match.group(1)] = (number, [t for t in match.group(2).split() if not t.startswith(('$', '"', "'"))])
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
        found = Found(f'{rel}:states', f'{Path(rel).name} state machine', 'step_functions', site(rel, line_of('"StartAt"'), None))
        for name in data['States']: found.stage(name, site(rel, line_of(f'"{name}"'), None))
        for name, state in data['States'].items():
            if not isinstance(state, dict): continue
            for target in [state.get('Next'), state.get('Default')] + [c.get('Next') for c in state.get('Choices') or [] if isinstance(c, dict)]:
                if target in data['States']: found.edge(f'{found.id}/{slug(name)}', f'{found.id}/{slug(target)}', 'declared', site(rel, line_of(f'"{name}"'), None))
            if state.get('Type') == 'Choice':
                found.routers.append({'id': f'{found.id}:{slug(name)}', 'pipeline': found.id, 'stage': f'{found.id}/{slug(name)}', 'kind': 'switch',
                                      'table': name, 'on': name, 'entry': site(rel, line_of(f'"{name}"'), None),
                                      'branches': [{'condition': _unparse_choice(c), 'to': f"{found.id}/{slug(c.get('Next'))}",
                                                    'evidence': site(rel, line_of(f'"{name}"'), None)} for c in state.get('Choices') or [] if isinstance(c, dict)],
                                      'total': bool(state.get('Default')), 'default': state.get('Default'), 'unhandled': []})
            for catch in state.get('Catch') or []:
                if isinstance(catch, dict) and catch.get('Next'):
                    found.errors.append({'id': f'{found.id}:{slug(name)}:catch', 'pipeline': found.id, 'from': f'{found.id}/{slug(name)}',
                                         'to': catch['Next'], 'kind': 'catch', 'condition': ','.join(catch.get('ErrorEquals') or []),
                                         'evidence': site(rel, line_of(f'"{name}"'), None)})
        out.append(found)
    elif isinstance(data, dict) and isinstance(data.get('nodes'), list) and isinstance(data.get('connections'), dict):
        found = Found(f'{rel}:n8n', str(data.get('name') or Path(rel).stem), 'n8n', site(rel, line_of('"nodes"'), None))
        for node in data['nodes']:
            if isinstance(node, dict) and node.get('name'): found.stage(node['name'], site(rel, line_of(f'"{node["name"]}"'), None))
        for source, outputs in data['connections'].items():
            for lane in (outputs or {}).get('main') or []:
                for target in lane or []:
                    if isinstance(target, dict): found.edge(f'{found.id}/{slug(source)}', f"{found.id}/{slug(target.get('node'))}", 'declared', site(rel, line_of(f'"{source}"'), None))
        if found.edges: out.append(found)
    elif isinstance(data, list) and data and all(isinstance(n, dict) for n in data) and any('wires' in n for n in data):
        found = Found(f'{rel}:flow', Path(rel).stem, 'node_red', site(rel, 1, None))
        ids = {n.get('id'): n.get('name') or n.get('type') or n.get('id') for n in data if n.get('id')}
        for node in data:
            if node.get('id') and node.get('wires') is not None: found.stage(ids[node['id']], site(rel, line_of(f'"{node["id"]}"'), None))
        for node in data:
            for port in node.get('wires') or []:
                for target in port or []:
                    if target in ids: found.edge(f'{found.id}/{slug(ids[node["id"]])}', f'{found.id}/{slug(ids[target])}', 'declared', site(rel, line_of(f'"{node["id"]}"'), None))
        if found.edges: out.append(found)


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


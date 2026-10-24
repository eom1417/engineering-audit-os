"""Pipelines a project's own Python runs: functions announcing their phases in order, and orchestrators passing one
stage's result to the next (eaos/facts/pipeline.py)."""
import ast
import sys
from collections import defaultdict

from . import call_name
from .pipeline_read import (site, Found, _decorators, _literal_label, _unparse, describe, PIPELINE_WORDS, PHASE_CALLS,
                            FLOW_DECORATORS, MODEL_WORDS, SIGNATURES)


def phases(py, out):
    for rel, name, node in py.functions():
        calls = _phase_calls(node)
        if len({label for _, label in calls}) < 3: continue
        found = Found(f'{rel}:{name}', f'{name} ({rel})', 'orchestrator', site(rel, node.lineno, py.line(rel, node.lineno)),
                      [site(rel, calls[0][0], py.line(rel, calls[0][0]))], confidence=0.8)
        found.functions.add((rel, name))
        _phase_stages(py, found, (rel, name, node), calls)
        _catches(py, found, rel, node, 'blocked')
        out.append(found)


def _phase_calls(node):
    """(line, label) of each phase a function announces (phase('Reading:')), in line order."""
    calls = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and (call_name(sub.func) or '') in PHASE_CALLS and sub.args:
            label = _literal_label(sub.args[0])
            if label: calls.append((sub.lineno, label.rstrip(' :.-')))
    return sorted(calls, key=lambda row: row[0])


def _phase_stages(py, found, function, calls):
    """A stage per announced phase, described from its statements up to the next phase, each after the one before."""
    rel, name, node = function
    previous = None
    bounds = [line for line, _ in calls] + [node.end_lineno or calls[-1][0]]
    for index, (line, label) in enumerate(calls):
        where = site(rel, line, py.line(rel, line))
        key = found.stage(label, where, symbol=f"{rel[:-3].replace('/', '.')}.{name}")
        segment = _segment(node, bounds[index], bounds[index + 1])
        stage = found.stages[key]
        for statement in segment: describe(py, rel, statement, stage)
        if _calls_model(py, segment): stage['marks'] = sorted(set(stage['marks']) | {'ai', 'slow'}); stage['kind'] = 'ai'
        if previous and previous != key: found.edge(previous, key, 'order', where, kind='control')
        previous = key


def _segment(node, start, end):
    """The statements of a function from line `start` to before `end`: its own when some start there, else nested ones."""
    return [s for s in node.body if start <= getattr(s, 'lineno', 0) < end] or \
        [s for s in ast.walk(node) if isinstance(s, ast.stmt) and start <= s.lineno < end]


def _catches(py, found, rel, node, to):
    """An error lane to `to` for each except handler of the function."""
    for handler in (s for s in ast.walk(node) if isinstance(s, ast.ExceptHandler)):
        found.errors.append({'id': f'{found.id}:error:{handler.lineno}', 'pipeline': found.id, 'from': '*', 'to': to,
                             'kind': 'catch', 'condition': _unparse(handler.type) if handler.type else 'any exception',
                             'evidence': site(rel, handler.lineno, py.line(rel, handler.lineno))})


def _calls_model(py, statements):
    """Whether these statements call a project function or method whose body reaches a model provider."""
    names = {(call_name(s.func) or '') for st in statements for s in ast.walk(st) if isinstance(s, ast.Call)}
    for rel, defs in py.defs.items():
        for qualified, node in defs.items():
            if qualified.split('.')[-1] in names and _reaches_model(node): return True
    return False


def _reaches_model(node):
    """Whether a function's body names a model provider (MODEL_WORDS)."""
    return any(MODEL_WORDS.search(call_name(s) or '') for s in ast.walk(node) if isinstance(s, (ast.Name, ast.Attribute)))


def _stage_call(py, rel, call, tasks):
    """The function a call runs as a stage: a project function by name, a task's signature, or an activity."""
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in ('execute_activity', 'start_activity') and call.args:
        target = call_name(call.args[0])
        return (target, py.resolve(rel, target)) if target else None
    if isinstance(func, ast.Attribute) and func.attr in SIGNATURES and isinstance(func.value, ast.Name):
        target = py.resolve(rel, func.value.id)
        return (func.value.id, target) if target or func.value.id in tasks else None
    return _function_call(py, rel, func)


def _function_call(py, rel, func):
    """A project function called by name or as module.function, neither a class nor a helper (_name): (name, target)."""
    if isinstance(func, ast.Name): name, target = func.id, py.resolve(rel, func.id)
    else:
        where = py.resolve_module(rel, func.value.id) if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) else None
        if not where: return None
        name, target = func.attr, (where, py.defs[where][func.attr]) if func.attr in py.defs.get(where, {}) else None
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
        if not _chained(found, declared): continue
        found.kind = _framework(decorators, str(py.imports.get(rel, {}))) or found.kind
        found.confidence = 0.85 if declared else 0.7
        out.append(found)


def _chained(found, declared):
    """Whether a function's chain is real: three top stages, two edges, and a path through three (any, when declared)."""
    stages = [k for k in found.order if found.stages[k].get('top')]
    return len(stages) >= 3 and len(found.edges) >= 2 and (_longest(found, set(stages)) >= 3 or declared)


def _framework(decorators, imports):
    """The framework an orchestrator's decorators (and its module's imports) declare it in, or None."""
    if decorators & {'flow'}: return 'prefect'
    if decorators & {'job', 'graph'} and 'dagster' in imports: return 'dagster'
    if decorators & {'dag'}: return 'airflow'
    if decorators & {'workflow', 'run'} and 'temporal' in imports: return 'temporal'
    return None


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


def _collects(statement):
    """`values.append(x)` and its kind: a statement that adds to a named collection."""
    call = statement.value if isinstance(statement, ast.Expr) else None
    return (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr in ('append', 'extend', 'add', 'update')
            and isinstance(call.func.value, ast.Name))


class _Chain:
    """One function's data flow: the stages each name's value comes from, so a value passed to a stage draws an edge."""

    def __init__(self, py, rel, tasks, found):
        self.py, self.rel, self.tasks, self.found = py, rel, tasks, found
        self.origins, self.depth = {}, 0

    def flow(self, expr):
        """The stages the value of `expr` comes from."""
        if expr is None: return set()
        if isinstance(expr, ast.Name): return set(self.origins.get(expr.id, set()))
        if isinstance(expr, ast.Call): return self._call(expr)
        out = set()
        nested = isinstance(expr, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Lambda))
        self.depth += nested
        for child in ast.iter_child_nodes(expr):
            if isinstance(child, ast.expr): out |= self.flow(child)
            elif isinstance(child, ast.comprehension): out |= self.flow(child.iter)
        self.depth -= nested
        return out

    def _call(self, expr):
        """A call: the stage it runs, else the stages its arguments (and its object) come from."""
        stage = _stage_call(self.py, self.rel, expr, self.tasks)
        inputs = {}
        for arg in [*expr.args, *[k.value for k in expr.keywords]]:
            for source in self.flow(arg):
                inputs.setdefault(source, set()).update(n.id for n in ast.walk(arg) if isinstance(n, ast.Name) and n.id in self.origins)
        if not stage:
            return set(inputs) | (self.flow(expr.func.value) if isinstance(expr.func, ast.Attribute) else set())
        return {self._stage(expr, stage, inputs)}

    def _stage(self, expr, stage, inputs):
        """The stage a call runs, and an edge from each stage a value it takes comes from; its key."""
        found, (label, target) = self.found, stage
        where = site(self.rel, expr.lineno, self.py.line(self.rel, expr.lineno))
        key = found.stage(label, where, symbol=f"{target[0][:-3].replace('/', '.')}.{target[1].name}" if target else None)
        if self.depth == 0: found.stages[key]['top'] = True
        if target: self._describe(found.stages[key], expr, target)
        for source, names in inputs.items():
            found.edge(source, key, 'value', where, names=sorted(names))
            for value in sorted(names):
                if value not in {i['name'] for i in found.stages[key]['inputs']}:
                    found.stages[key]['inputs'].append({'name': value, 'kind': 'value', 'shape': None})
        return key

    def _describe(self, stage_row, expr, target):
        """A stage first seen at this call starts at its function, described from its body."""
        if stage_row['entry']['line'] == expr.lineno and stage_row['entry']['path'] == self.rel:
            stage_row['entry'] = site(target[0], target[1].lineno, self.py.line(target[0], target[1].lineno))
            describe(self.py, target[0], target[1], stage_row)

    def bind(self, target, values):
        if isinstance(target, ast.Name): self.origins[target.id] = set(values)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts: self.bind(item, values)
        elif isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
            self.origins[target.value.id] = self.origins.get(target.value.id, set()) | set(values)

    def walk(self, statements):
        for statement in statements:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)): continue
            if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Expr, ast.Return)): self._assign(statement)
            else: self._block(statement)

    def _assign(self, statement):
        """A statement that gives a name a value, or adds to a collection."""
        if isinstance(statement, ast.Assign):
            values = self.flow(statement.value)
            for target in statement.targets: self.bind(target, values)
        elif isinstance(statement, (ast.AnnAssign, ast.AugAssign)) and statement.value is not None:
            self.bind(statement.target, self.flow(statement.value) | (self.flow(statement.target) if isinstance(statement, ast.AugAssign) else set()))
        elif isinstance(statement, (ast.Expr, ast.Return)):
            values = self.flow(statement.value)
            if _collects(statement): self.bind(ast.Subscript(value=statement.value.func.value), values)

    def _block(self, statement):
        """A statement holding others: a loop, a branch, a with, a try."""
        if isinstance(statement, (ast.For, ast.AsyncFor)):
            self.bind(statement.target, self.flow(statement.iter))
            self._loop(statement)
        elif isinstance(statement, ast.While):
            self.flow(statement.test)
            self._loop(statement)
        elif isinstance(statement, ast.If): self.flow(statement.test); self.walk(statement.body); self.walk(statement.orelse)
        elif isinstance(statement, (ast.With, ast.AsyncWith)):
            for item in statement.items:
                values = self.flow(item.context_expr)
                if item.optional_vars is not None: self.bind(item.optional_vars, values)
            self.walk(statement.body)
        elif isinstance(statement, ast.Try):
            self.walk(statement.body)
            for handler in statement.handlers: self.walk(handler.body)
            self.walk(statement.orelse); self.walk(statement.finalbody)

    def _loop(self, statement):
        """A loop's body runs one level deeper: a stage there is not a top stage."""
        self.depth += 1
        self.walk(statement.body)
        self.depth -= 1
        self.walk(statement.orelse)


def _chain(py, rel, name, node, tasks):
    found = Found(f'{rel}:{name}', f'{name} ({rel})', 'orchestrator', site(rel, node.lineno, py.line(rel, node.lineno)),
                  [site(rel, node.lineno, py.line(rel, node.lineno))])
    found.functions.add((rel, name))
    _Chain(py, rel, tasks, found).walk(node.body)
    _catches(py, found, rel, node, 'raised')
    return found


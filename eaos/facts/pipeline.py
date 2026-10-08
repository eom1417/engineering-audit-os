"""Pipelines and flowcharts: whether the project, or a part of it, is a pipeline, and its stages, edges and routers.

A pipeline is found only from what the code declares or does, never guessed from names alone:
  - a declared DAG: a list of stage records whose `requires` name other stages, run through a registry of runners;
  - a declared sequence: a list of steps holding the functions a driver calls one after the other;
  - a registry loop: a loop over stage names dispatching through a table, each stage's inputs taken from what the
    earlier stages put in an accumulator;
  - an orchestrator: a function announcing its phases in order, or one whose calls pass one stage's result to the next;
  - the frameworks' own declarations (Airflow, Prefect, Dagster, Luigi, Celery canvas, LangGraph, Temporal), queue
    topologies (a topic both produced and consumed), and the build and CI chains (GitHub Actions `needs`, Make and just
    targets, npm script chains, n8n / Node-RED / Step Functions exports).
Every stage, edge and branch carries the file and line it was read from. A dispatch EAOS cannot follow is written as an
unresolved step, never as an edge. The project is not run: Python is read with the standard `ast`, the rest as text.
"""
import ast
import json
import re
from collections import defaultdict
from pathlib import Path

from . import digest, make

NAME = 'pipeline'
VERSION = '1'
LIMITATIONS = [
    'Read from the code, never by running it: a graph built at run time from data is an unresolved step, not an edge.',
    'Python is read with its own parser; JavaScript and other languages only through their build files (package.json, CI).',
    'An orchestrator counts only where the code passes one stage\'s result to the next, or announces its phases in order.',
    'A side channel is found where a stage writes a shared context key, global or environment variable another reads.',
]

# Every kind looked for, in the order the page lists them: (kind, label).
KINDS = (('declared_dag', 'Declared stages with requires, run through a registry'),
         ('registry_loop', 'A loop over stage names dispatching through a table'),
         ('orchestrator', 'A function passing one stage\'s output to the next, or announcing its phases'),
         ('airflow', 'Airflow DAGs (operators, >>, TaskFlow, branch operators)'),
         ('prefect', 'Prefect flows calling tasks'),
         ('dagster', 'Dagster jobs and assets'),
         ('luigi', 'Luigi tasks and their requires()'),
         ('celery', 'Celery canvas (chain, group, chord), task routes and retries'),
         ('langgraph', 'LangGraph graphs (add_node, add_edge, add_conditional_edges)'),
         ('n8n', 'n8n workflow exports'),
         ('node_red', 'Node-RED flow exports'),
         ('temporal', 'Temporal workflows running activities'),
         ('step_functions', 'AWS Step Functions state machines'),
         ('github_actions', 'GitHub Actions jobs and their needs'),
         ('makefile', 'Makefile targets and prerequisites'),
         ('justfile', 'justfile recipes and dependencies'),
         ('npm_scripts', 'npm script chains (a && b)'),
         ('queue', 'Queue or stream topologies: a topic both produced and consumed'),
         ('cli_chain', 'Command-line subcommands that chain'))
HOW = {'cli_chain': 'not read yet: subcommands are listed by the entry points, their chaining is not followed'}
TOOLING = {'github_actions', 'makefile', 'justfile', 'npm_scripts'}
CONFIDENCE = {'declared_dag': 0.95, 'registry_loop': 0.9, 'airflow': 0.95, 'prefect': 0.9, 'dagster': 0.9, 'luigi': 0.9,
              'celery': 0.9, 'langgraph': 0.95, 'n8n': 0.95, 'node_red': 0.95, 'temporal': 0.9, 'step_functions': 0.95,
              'github_actions': 0.95, 'makefile': 0.85, 'justfile': 0.85, 'npm_scripts': 0.9, 'queue': 0.7,
              'orchestrator': 0.7}
DETECTED_AT = 0.6
REQUIRES = {'requires', 'depends_on', 'needs', 'after', 'upstream', 'deps', 'dependencies'}
PRODUCES = {'produces', 'outputs', 'outs', 'provides'}
CONSUMES = {'consumes', 'inputs', 'ins'}
PIPELINE_WORDS = re.compile(r'(^|_)(pipelines?|etl|workflows?|orchestrators?|orchestrate|dags?)($|_)', re.I)
PHASE_CALLS = {'phase', 'stage', 'step'}
FLOW_DECORATORS = {'flow', 'dag', 'job', 'graph', 'pipeline', 'workflow'}
TASK_DECORATORS = {'task', 'op', 'asset', 'shared_task', 'activity'}
ERROR_STATES = {'failed': 'fail', 'failure': 'fail', 'error': 'fail', 'unavailable': 'skip', 'skipped': 'skip',
                'not_reached': 'block', 'blocked': 'block', 'dead_letter': 'fail'}
CONTEXT_PARAMS = {'context', 'ctx', 'state'}
DICT_METHODS = {'get', 'items', 'keys', 'values', 'setdefault', 'update', 'pop', 'copy'}
MODEL_WORDS = re.compile(r'provider|llm|openai|anthropic|claude|codex|gpt|prompt|completion', re.I)
NETWORK = {'requests', 'httpx', 'urllib', 'aiohttp', 'boto3', 's3fs', 'praw', 'smtplib', 'socket'}
PROCESS = {'subprocess', 'os.system', 'popen'}
DB_CALLS = {'execute', 'executemany', 'save', 'get_or_create', 'update_or_create', 'bulk_create', 'commit', 'insert', 'upsert'}
TIMEOUT_WORDS = {'timeout', 'execution_timeout', 'soft_time_limit', 'time_limit', 'budget', 'deadline'}
SIGNATURES = {'s', 'si', 'signature', 'delay', 'apply_async'}


def slug(text):
    return re.sub(r'[^A-Za-z0-9_.:/-]+', '-', str(text)).strip('-') or 'x'


def site(path, line, text=None):
    return {'path': path, 'line': line if isinstance(line, int) else None, 'text': (text or '').strip()[:160] or None}


# ---------------------------------------------------------------- one pipeline as it is found

class Found:
    """One pipeline: its stages, edges, routers and the rest, each with its evidence."""

    def __init__(self, key, title, kind, entry, evidence=(), role=None, confidence=None):
        self.id, self.title, self.kind = slug(key), title, kind
        self.role = role or ('tooling' if kind in TOOLING else 'product')
        self.confidence = confidence if confidence is not None else CONFIDENCE.get(kind, 0.7)
        self.entry, self.evidence = entry, list(evidence)
        self.stages, self.order, self.edges = {}, [], {}
        self.routers, self.fans, self.control, self.errors, self.hidden, self.unresolved = [], [], [], [], [], []
        self.parent = None
        self.functions = set()   # (path, name) of the functions this pipeline accounts for

    def stage(self, label, where, kind='stage', symbol=None, **extra):
        key = f'{self.id}/{slug(label)}'
        if key not in self.stages:
            self.stages[key] = {'id': key, 'pipeline': self.id, 'label': str(label), 'kind': kind, 'entry': where,
                                'symbol': symbol, 'tools': [], 'inputs': [], 'outputs': [], 'side_effects': [],
                                'optional': False, 'marks': [], 'sub_pipeline': None, 'timeout': False, **extra}
            self.order.append(key)
        return key

    def edge(self, a, b, matched_by, where, names=(), shape=None, kind='data', condition=None):
        if a == b or a not in self.stages or b not in self.stages: return None
        row = self.edges.get((a, b))
        if row is None:
            row = self.edges[(a, b)] = {'id': f'{a}->{b.rsplit("/", 1)[-1]}', 'pipeline': self.id, 'from': a, 'to': b,
                                        'kind': kind, 'data': {'names': [], 'shape': shape}, 'matched_by': matched_by,
                                        'condition': condition, 'evidence': where}
        for name in names:
            if name not in row['data']['names']: row['data']['names'].append(name)
        return row

    def record(self):
        return {'id': self.id, 'title': self.title, 'kind': self.kind, 'role': self.role, 'confidence': self.confidence,
                'entry': self.entry, 'evidence': self.evidence[:8], 'parent': self.parent,
                'stages': [self.stages[k] for k in self.order], 'edges': list(self.edges.values()),
                'routers': self.routers, 'fans': self.fans, 'control': self.control, 'error_lanes': self.errors,
                'hidden': self.hidden, 'unresolved': self.unresolved,
                'functions': sorted(f'{path}::{name}' for path, name in self.functions)}


# ---------------------------------------------------------------- the Python index

class Py:
    """Every Python file of the project parsed once: its functions, module-level values, imports and the names used."""

    def __init__(self, files):
        self.trees, self.lines, self.defs, self.classes, self.assigns, self.imports = {}, {}, {}, {}, {}, {}
        self.modules, self.used = {}, defaultdict(int)
        for rel, text in files:
            try: tree = ast.parse(text)
            except (SyntaxError, ValueError): continue
            self.trees[rel], self.lines[rel] = tree, text.splitlines()
            module = rel[:-3].replace('/', '.')
            if module.endswith('.__init__'): module = module[:-9]
            self.modules[module] = rel
            defs, classes, assigns, imports = {}, {}, {}, {}
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)): defs[node.name] = node
                elif isinstance(node, ast.ClassDef):
                    classes[node.name] = node
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)): defs.setdefault(f'{node.name}.{item.name}', item)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name): assigns[target.id] = node
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
                    assigns[node.target.id] = node
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    base = self._absolute(module, node.module, node.level, rel)
                    for alias in node.names: imports[alias.asname or alias.name] = (base, alias.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names: imports[alias.asname or alias.name.split('.')[0]] = (alias.name, None)
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load): self.used[node.id] += 1
                elif isinstance(node, ast.Attribute): self.used[node.attr] += 1
                elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.isidentifier():
                    self.used[node.value] += 1
            self.defs[rel], self.classes[rel], self.assigns[rel], self.imports[rel] = defs, classes, assigns, imports

    @staticmethod
    def _absolute(module, name, level, rel):
        if not level: return name or ''
        parts = module.split('.')
        package = parts if rel.endswith('__init__.py') else parts[:-1]
        base = package[:len(package) - (level - 1)] if level > 1 else package
        return '.'.join([*base, *([name] if name else [])])

    def line(self, rel, number):
        lines = self.lines.get(rel) or []
        return lines[number - 1] if isinstance(number, int) and 0 < number <= len(lines) else ''

    def module_rel(self, dotted):
        return self.modules.get(dotted)

    def resolve(self, rel, name):
        """(rel, FunctionDef) of a function named here or imported from a project module, else None."""
        node = self.defs.get(rel, {}).get(name)
        if node is not None: return rel, node
        target = self.imports.get(rel, {}).get(name)
        if not target: return None
        module, attr = target
        if attr is None: return None
        where = self.module_rel(module)
        if where and attr in self.defs.get(where, {}): return where, self.defs[where][attr]
        sub = self.module_rel(f'{module}.{attr}')
        return None if sub is None else None

    def resolve_module(self, rel, name):
        """The project file a name refers to when it is an imported project module."""
        target = self.imports.get(rel, {}).get(name)
        if not target: return None
        module, attr = target
        return self.module_rel(f'{module}.{attr}' if attr else module)

    def value(self, rel, name):
        """The module-level value assigned to a name here, or in the project module it is imported from: (rel, node)."""
        node = self.assigns.get(rel, {}).get(name)
        if node is not None: return rel, node.value
        target = self.imports.get(rel, {}).get(name)
        if target and target[1]:
            where = self.module_rel(target[0])
            if where and target[1] in self.assigns.get(where, {}): return where, self.assigns[where][target[1]].value
        return None

    def functions(self):
        for rel, defs in self.defs.items():
            for name, node in defs.items(): yield rel, name, node


def _str(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _strs(node):
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)): return [s for s in map(_str, node.elts) if s is not None]
    single = _str(node)
    return [single] if single is not None else []


def _name(node):
    """The last name of a callee: f, mod.f, obj.method."""
    if isinstance(node, ast.Name): return node.id
    if isinstance(node, ast.Attribute): return node.attr
    return None


def _root(node):
    while isinstance(node, (ast.Attribute, ast.Call, ast.Subscript)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


def _decorators(node):
    out = []
    for item in getattr(node, 'decorator_list', []):
        target = item.func if isinstance(item, ast.Call) else item
        out.append(_name(target) or '')
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Attribute): out.append(target.value.attr)
    return out


def _literal_label(node):
    """The leading literal of a phase label: 'x', 'x ' + y, f'x {y}'."""
    if _str(node) is not None: return _str(node).strip()
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add): return _literal_label(node.left)
    if isinstance(node, ast.JoinedStr) and node.values and _str(node.values[0]) is not None: return _str(node.values[0]).strip()
    return None


def _unparse(node, limit=80):
    try: return ast.unparse(node)[:limit]
    except Exception: return ''


# ---------------------------------------------------------------- what a stage function touches

def describe(py, rel, node, found_stage):
    """Fill a stage's tools, side effects and marks from its entry function's body (one level, no guessing)."""
    if node is None: return
    imports = py.imports.get(rel, {})
    tools, effects, marks = [], [], set(found_stage['marks'])
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            root = _root(sub.func)
            if root and root in imports:
                module = imports[root][0] or ''
                top = (module or root).split('.')[0]
                if top and not py.module_rel(module) and not any(m.startswith(top + '.') or m == top for m in py.modules):
                    if top not in tools: tools.append(top)
                    if top in NETWORK or root in NETWORK: marks.add('external'); marks.add('slow')
                    if top in ('subprocess',): marks.add('slow'); marks.add('risky'); effects.append(('process', top, sub.lineno))
            callee = _name(sub.func) or ''
            if callee in ('write_text', 'write_bytes', 'dump', 'to_csv', 'to_parquet', 'savefig'):
                effects.append(('file', _unparse(sub.func, 60), sub.lineno))
            if callee == 'open' and len(sub.args) > 1 and (_str(sub.args[1]) or '').startswith(('w', 'a')):
                effects.append(('file', _unparse(sub.args[0], 60), sub.lineno))
            if callee in DB_CALLS and root not in ('self',) and isinstance(sub.func, ast.Attribute):
                effects.append(('db', _unparse(sub.func, 60), sub.lineno)); marks.add('risky')
            if callee in ('setdefault', 'putenv') and _unparse(sub.func).startswith('os.environ'):
                effects.append(('env', _unparse(sub, 60), sub.lineno))
            if callee in ('post', 'put', 'get', 'request', 'urlopen') and root in NETWORK:
                effects.append(('network', _unparse(sub.func, 60), sub.lineno))
            for keyword in sub.keywords:
                if keyword.arg in TIMEOUT_WORDS: found_stage['timeout'] = True
        elif isinstance(sub, ast.Global):
            for name in sub.names: effects.append(('global', name, sub.lineno))
        elif isinstance(sub, (ast.Name, ast.Attribute)):
            word = sub.id if isinstance(sub, ast.Name) else sub.attr
            if MODEL_WORDS.search(word): marks.add('ai')
    for kind, name, line in effects[:12]:
        found_stage['side_effects'].append({'kind': kind, 'name': name, 'path': rel, 'line': line, 'text': None})
    found_stage['tools'] = sorted(set(found_stage['tools']) | set(tools))[:12]
    if 'ai' in marks: marks.add('slow')
    found_stage['marks'] = sorted(marks)
    if 'ai' in marks and found_stage['kind'] == 'stage': found_stage['kind'] = 'ai'


# ---------------------------------------------------------------- declared lists: DAGs and sequences

def _registry_for(py, names):
    """A dict of stage name -> function whose keys are mostly these names: (rel, assignment, {key: (rel, def)})."""
    best = None
    for rel, assigns in py.assigns.items():
        for var, node in assigns.items():
            value = node.value
            if not isinstance(value, ast.Dict) or len(value.keys) < 3: continue
            keys = {}
            for key, item in zip(value.keys, value.values):
                label = _str(key) if key is not None else None
                if label is None or not isinstance(item, ast.Name): continue
                keys[label] = (item, key.lineno)
            for sub in ast.walk(py.trees[rel]):   # REGISTRY.update(a=a, b=b)
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == 'update'
                        and isinstance(sub.func.value, ast.Name) and sub.func.value.id == var):
                    for keyword in sub.keywords:
                        if keyword.arg and isinstance(keyword.value, ast.Name): keys[keyword.arg] = (keyword.value, sub.lineno)
            share = len(set(keys) & set(names)) / max(len(names), 1)
            if share >= 0.6 and (best is None or share > best[0]):
                best = (share, rel, var, node, keys)
    return best


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
                rows.append({'label': label, 'line': element.lineno, 'requires': requires, 'produces': produces,
                             'consumes': consumes, 'functions': functions, 'optional': optional})
            else:
                names = [r['label'] for r in rows]
                if len(set(names)) != len(names): continue
                dag = sum(bool(set(r['requires']) & set(names)) for r in rows) >= 2
                drivers = _drivers(py, rel, var)
                called = any(isinstance(call, ast.Call) and isinstance(call.func, (ast.Subscript, ast.Attribute))
                             and _root(call.func) == target
                             for _, _, fn, _, target in drivers for call in ast.walk(fn) if target)
                sequence = not dag and all(r['functions'] for r in rows) and called
                if dag: _declared_dag(py, rel, var, node, rows, drivers, out)
                elif sequence: _declared_sequence(py, rel, var, node, rows, drivers, out)


def _declared_dag(py, rel, var, node, rows, drivers, out):
    names = [r['label'] for r in rows]
    driver = drivers[0] if drivers else None
    entry = site(driver[0], driver[2].lineno, py.line(driver[0], driver[2].lineno)) if driver else site(rel, node.lineno, py.line(rel, node.lineno))
    found = Found(f'{rel}:{var}', f'{var} ({rel})', 'declared_dag', entry, [site(rel, node.lineno, py.line(rel, node.lineno))])
    registry = _registry_for(py, names)
    by_label = {}
    for row in rows:
        where = site(rel, row['line'], py.line(rel, row['line']))
        target = None
        if registry and row['label'] in registry[4]:
            function = py.resolve(registry[1], registry[4][row['label']][0].id)
            if function: target = function
        if target:
            where = site(target[0], target[1].lineno, py.line(target[0], target[1].lineno))
        key = found.stage(row['label'], where, symbol=f"{target[0][:-3].replace('/', '.')}.{target[1].name}" if target else None,
                          optional=row['optional'])
        stage = found.stages[key]
        stage['outputs'] = [{'name': name, 'kind': 'artifact', 'shape': None} for name in row['produces']]
        by_label[row['label']] = (key, row, target)
        if target:
            found.functions.add((target[0], target[1].name))
            describe(py, target[0], target[1], stage)
    for label, (key, row, _) in by_label.items():
        for need in row['requires']:
            if need not in by_label: continue
            source = by_label[need]
            artifacts = source[1]['produces']
            found.stages[key]['inputs'] += [{'name': a, 'kind': 'artifact', 'shape': None} for a in artifacts[:3]
                                            if a not in {i['name'] for i in found.stages[key]['inputs']}]
            found.edge(source[0], key, 'declared', site(rel, row['line'], py.line(rel, row['line'])), names=artifacts[:3],
                       shape='files' if artifacts else None)
    for fn_rel, fn_name, fn_node, loop, _ in drivers:
        found.functions.add((fn_rel, fn_name))
        found.control.append({'id': f'{found.id}:loop', 'pipeline': found.id, 'stage': found.order[0], 'kind': 'loop',
                              'condition': _unparse(loop.iter if isinstance(loop, ast.For) else loop, 60),
                              'evidence': site(fn_rel, loop.lineno, py.line(fn_rel, loop.lineno))})
        if isinstance(loop, ast.For):
            for sub in loop.body:
                if isinstance(sub, ast.If) and any(isinstance(s, ast.Continue) for s in sub.body):
                    found.control.append({'id': f'{found.id}:skip:{sub.lineno}', 'pipeline': found.id, 'stage': found.order[0],
                                          'kind': 'conditional_skip', 'condition': _unparse(sub.test),
                                          'evidence': site(fn_rel, sub.lineno, py.line(fn_rel, sub.lineno))})
        _error_lanes(py, fn_rel, fn_node, found)
        break
    if registry:
        share, reg_rel, reg_var, reg_node, keys = registry
        router_key = found.stage(reg_var, site(reg_rel, reg_node.lineno, py.line(reg_rel, reg_node.lineno)), kind='router',
                                 symbol=f"{reg_rel[:-3].replace('/', '.')}.{reg_var}")
        lookup = _lookup(py, reg_var)
        if lookup: _error_lanes(py, lookup[0], lookup[1], found); found.functions.add((lookup[0], lookup[1].name))
        branches = []
        for label, (item, line) in keys.items():
            to = by_label.get(label, (None,))[0]
            branches.append({'condition': label, 'to': to, 'evidence': site(reg_rel, line, py.line(reg_rel, line))})
            if to is None:
                found.hidden.append({'id': f'{found.id}:dead:{slug(label)}', 'pipeline': found.id, 'kind': 'dead_stage',
                                     'channel': None, 'name': label, 'stages': [router_key],
                                     'evidence': site(reg_rel, line, py.line(reg_rel, line))})
        has_default = bool(lookup) and any(isinstance(s, ast.Compare) and any(isinstance(o, (ast.Is, ast.Eq)) for o in s.ops)
                                           and any(isinstance(c, ast.Constant) and c.value is None for c in s.comparators)
                                           for s in ast.walk(lookup[1]))
        missing = [name for name in names if name not in keys]
        found.routers.append({'id': f'{found.id}:{slug(reg_var)}', 'pipeline': found.id, 'stage': router_key, 'kind': 'registry',
                              'table': reg_var, 'on': 'stage name',
                              'entry': site(lookup[0], lookup[2], py.line(lookup[0], lookup[2])) if lookup else
                              site(reg_rel, reg_node.lineno, py.line(reg_rel, reg_node.lineno)),
                              'branches': branches, 'total': not missing, 'default': 'failed' if has_default else None,
                              'unhandled': missing})
        found.functions.add((reg_rel, reg_var))
    else:
        for label, (key, _, _) in by_label.items():
            found.unresolved.append({'id': f'{key}:runner', 'pipeline': found.id, 'stage': key, 'call': label,
                                     'reason': 'no registry maps this stage to the function that runs it',
                                     'evidence': found.stages[key]['entry']})
    _context_channels(py, found, [(t[0], t[1]) for _, _, t in by_label.values() if t])
    out.append(found)


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
            elif _str(sub) is not None and _str(sub).lower() in ERROR_STATES and isinstance(sub, ast.Constant): pass

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
    writes, reads = defaultdict(set), defaultdict(set)
    lines = {}
    stage_of = {(rel, node.name): key for key in found.order for rel, node in functions
                if found.stages[key]['entry']['path'] == rel and found.stages[key]['entry']['line'] == node.lineno}
    for (rel, name), key in stage_of.items():
        node = py.defs[rel].get(name)
        params = [a.arg for a in node.args.args]
        param = next((p for p in params if p in CONTEXT_PARAMS), None)
        if not param: continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name) and sub.value.id == param and _str(sub.slice):
                (writes if isinstance(sub.ctx, ast.Store) else reads)[_str(sub.slice)].add(key)
                lines.setdefault((_str(sub.slice), key), (rel, sub.lineno))
            elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and isinstance(sub.func.value, ast.Name) \
                    and sub.func.value.id == param and sub.func.attr == 'get' and sub.args and _str(sub.args[0]):
                reads[_str(sub.args[0])].add(key); lines.setdefault((_str(sub.args[0]), key), (rel, sub.lineno))
            elif isinstance(sub, ast.Compare) and any(isinstance(o, (ast.In, ast.NotIn)) for o in sub.ops) and _str(sub.left) \
                    and any(isinstance(c, ast.Name) and c.id == param for c in sub.comparators):
                reads[_str(sub.left)].add(key)
            elif isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == param \
                    and isinstance(sub.ctx, ast.Load) and sub.attr not in DICT_METHODS:
                reads[sub.attr].add(key); lines.setdefault((sub.attr, key), (rel, sub.lineno))
    for name in sorted(writes):
        writers = writes[name]
        readers = {r for r in reads.get(name, set()) if any(r != w for w in writers)}
        first = sorted(writers, key=found.order.index)[0]
        rel, line = lines.get((name, first), (found.stages[first]['entry']['path'], found.stages[first]['entry']['line']))
        if readers:
            found.hidden.append({'id': f'{found.id}:ctx:{slug(name)}', 'pipeline': found.id, 'kind': 'side_channel',
                                 'channel': 'context', 'name': f"context['{name}']",
                                 'stages': sorted(writers | readers, key=found.order.index), 'evidence': site(rel, line, py.line(rel, line))})
        elif not reads.get(name):
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


# ---------------------------------------------------------------- registry loops

def registry_loops(py, out):
    for rel, name, node in py.functions():
        for loop in ast.walk(node):
            if not isinstance(loop, ast.For) or not isinstance(loop.target, ast.Name): continue
            var = loop.target.id
            table = None
            for sub in ast.walk(loop):
                key = None
                if isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name) and isinstance(sub.slice, ast.Name) and sub.slice.id == var:
                    key = sub.value.id
                elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == 'get' and sub.args \
                        and isinstance(sub.args[0], ast.Name) and sub.args[0].id == var and isinstance(sub.func.value, ast.Name):
                    key = sub.func.value.id
                if key and isinstance(sub.ctx if isinstance(sub, ast.Subscript) else ast.Load(), ast.Load):
                    found_value = py.value(rel, key)
                    if found_value and isinstance(found_value[1], ast.Dict) and len(found_value[1].keys) >= 3 and \
                            all(_str(k) is not None and isinstance(v, ast.Name) for k, v in zip(found_value[1].keys, found_value[1].values)):
                        table = (key, sub.lineno, found_value)
                        break
            if table: _registry_loop(py, rel, name, node, loop, var, table, out)


def _registry_loop(py, rel, fn_name, fn, loop, var, table, out):
    key, line, (table_rel, table_node) = table
    keys = [_str(k) for k in table_node.keys]
    values = dict(zip(keys, table_node.values))
    accumulators = set()
    for sub in ast.walk(loop):
        if isinstance(sub, ast.Assign):
            for target in sub.targets:
                if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Name) and target.slice.id == var \
                        and isinstance(target.value, ast.Name):
                    accumulators.add(target.value.id)
    if not accumulators: return
    order = keys
    for candidate in py.assigns.get(table_rel, {}).values():
        items = _strs(candidate.value) if isinstance(candidate.value, (ast.List, ast.Tuple)) else []
        if len(items) >= 3 and set(items) <= set(keys) and len(items) >= 0.8 * len(keys): order = items; break
    found = Found(f'{rel}:{fn_name}', f'{key} ({rel})', 'registry_loop', site(rel, fn.lineno, py.line(rel, fn.lineno)),
                  [site(table_rel, table_node.lineno, py.line(table_rel, table_node.lineno)), site(rel, loop.lineno, py.line(rel, loop.lineno))])
    found.functions.add((rel, fn_name))
    for label in order:
        target = values[label]
        module_rel = py.resolve_module(table_rel, target.id)
        function = py.resolve(table_rel, target.id)
        if module_rel and 'run' in py.defs.get(module_rel, {}):
            run = py.defs[module_rel]['run']
            where, symbol = site(module_rel, run.lineno, py.line(module_rel, run.lineno)), f"{module_rel[:-3].replace('/', '.')}.run"
        elif function:
            where, symbol = site(function[0], function[1].lineno, py.line(function[0], function[1].lineno)), f"{function[0][:-3].replace('/', '.')}.{function[1].name}"
        else:
            where, symbol = site(table_rel, target.lineno, py.line(table_rel, target.lineno)), None
        stage_key = found.stage(label, where, symbol=symbol)
        found.stages[stage_key]['outputs'] = [{'name': f"{sorted(accumulators)[0]}[{label!r}]", 'kind': 'value', 'shape': None}]
    by_label = {found.stages[k]['label']: k for k in found.order}
    router = found.stage(key, site(table_rel, table_node.lineno, py.line(table_rel, table_node.lineno)), kind='router',
                         symbol=f"{table_rel[:-3].replace('/', '.')}.{key}")
    found.routers.append({'id': f'{found.id}:{slug(key)}', 'pipeline': found.id, 'stage': router, 'kind': 'dict_dispatch',
                          'table': key, 'on': var, 'entry': site(rel, line, py.line(rel, line)),
                          'branches': [{'condition': label, 'to': by_label.get(label),
                                        'evidence': site(table_rel, k.lineno, py.line(table_rel, k.lineno))}
                                       for label, k in zip(keys, table_node.keys)],
                          'total': set(order) <= set(keys), 'default': None, 'unhandled': [l for l in order if l not in keys]})
    for label in keys:
        if label not in order:
            found.hidden.append({'id': f'{found.id}:dead:{slug(label)}', 'pipeline': found.id, 'kind': 'dead_stage', 'channel': None,
                                 'name': label, 'stages': [router], 'evidence': site(table_rel, table_node.lineno, None)})
    found.control.append({'id': f'{found.id}:loop', 'pipeline': found.id, 'stage': router, 'kind': 'loop',
                          'condition': f'for {var} in {_unparse(loop.iter, 40)}', 'evidence': site(rel, loop.lineno, py.line(rel, loop.lineno))})

    def reads(body):
        for sub in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == 'get' \
                    and isinstance(sub.func.value, ast.Name) and sub.func.value.id in accumulators and sub.args and _str(sub.args[0]):
                yield _str(sub.args[0]), sub.lineno, sub.func.value.id
            elif isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name) and sub.value.id in accumulators and _str(sub.slice):
                yield _str(sub.slice), sub.lineno, sub.value.id
            elif isinstance(sub, ast.Compare) and _str(sub.left) and any(isinstance(c, ast.Name) and c.id in accumulators for c in sub.comparators):
                yield _str(sub.left), sub.lineno, next(c.id for c in sub.comparators if isinstance(c, ast.Name))

    def flow(read_list, targets, condition):
        for label, line, acc in read_list:
            where = site(rel, line, py.line(rel, line))
            if label not in by_label:
                if not any(u['call'] == f"{acc}[{label!r}]" for u in found.unresolved):
                    found.unresolved.append({'id': f'{found.id}:unresolved:{slug(label)}', 'pipeline': found.id,
                                             'stage': by_label.get(targets[0]) if targets else router, 'call': f"{acc}[{label!r}]",
                                             'reason': 'read here, but no stage of this loop writes it', 'evidence': where})
                continue
            for target in targets:
                if target in by_label:
                    found.edge(by_label[label], by_label[target], 'value', where, names=[f"{acc}[{label!r}]"], condition=condition)
                    found.stages[by_label[target]]['inputs'].append({'name': f"{acc}[{label!r}]", 'kind': 'value', 'shape': None})

    for statement in loop.body:
        if isinstance(statement, ast.If) and _tests(statement, var):
            branches, node, covered = [], statement, set()
            while True:
                labels = _tests(node, var)
                if not labels: break
                covered |= set(labels)
                for label in labels:
                    branches.append({'condition': label, 'to': by_label.get(label), 'evidence': site(rel, node.lineno, py.line(rel, node.lineno))})
                flow(list(reads(node.body)), labels, _unparse(node.test))
                if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If): node = node.orelse[0]; continue
                if node.orelse:
                    line = node.orelse[0].lineno
                    rest = [l for l in order if l not in covered]
                    branches.append({'condition': 'else', 'to': None, 'evidence': site(rel, line, py.line(rel, line))})
                    flow(list(reads(node.orelse)), rest, 'else')
                break
            if branches:
                router_key = found.stage(f'if {var} ==', site(rel, statement.lineno, py.line(rel, statement.lineno)), kind='router')
                found.routers.append({'id': f'{found.id}:{slug(var)}-chain', 'pipeline': found.id, 'stage': router_key, 'kind': 'if_chain',
                                      'table': var, 'on': var, 'entry': site(rel, statement.lineno, py.line(rel, statement.lineno)),
                                      'branches': branches, 'total': any(b['condition'] == 'else' for b in branches),
                                      'default': None, 'unhandled': []})
        elif not isinstance(statement, ast.If):
            flow([r for r in reads([statement]) if not isinstance(statement, ast.Assign) or True], order, None) \
                if any(True for _ in reads([statement])) and not _writes_acc(statement, accumulators, var) else None
    out.append(found)


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


# ---------------------------------------------------------------- orchestrators: phases, and value passed between calls

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
    import sys
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


# ---------------------------------------------------------------- frameworks

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
    returns = [(_strs(s.value) or [], s.lineno) for s in ast.walk(target[1]) if isinstance(s, ast.Return) and s.value is not None]
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


def langgraph(py, out):
    for rel, tree in py.trees.items():
        graphs = {}
        for sub in ast.walk(tree):
            if isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Call) and _name(sub.value.func) in ('StateGraph', 'Graph', 'MessageGraph') \
                    and len(sub.targets) == 1 and isinstance(sub.targets[0], ast.Name):
                graphs[sub.targets[0].id] = Found(f'{rel}:{sub.targets[0].id}', f'{sub.targets[0].id} ({rel})', 'langgraph',
                                                   site(rel, sub.lineno, py.line(rel, sub.lineno)), [site(rel, sub.lineno, py.line(rel, sub.lineno))])
        if not graphs: continue
        calls = sorted((s for s in ast.walk(tree) if isinstance(s, ast.Call) and isinstance(s.func, ast.Attribute)
                        and isinstance(s.func.value, ast.Name) and s.func.value.id in graphs), key=lambda s: s.lineno)
        for call in calls:
            found, method, where = graphs[call.func.value.id], call.func.attr, site(rel, call.lineno, py.line(rel, call.lineno))
            node_key = lambda label: found.stage(label, where, kind='source' if label == 'START' else 'sink' if label == 'END' else 'stage')
            label_of = lambda expr: _str(expr) or (expr.id if isinstance(expr, ast.Name) else None)
            if method == 'add_node' and call.args:
                label = label_of(call.args[0])
                key = node_key(label)
                fn = call.args[1] if len(call.args) > 1 else call.args[0]
                target = py.resolve(rel, fn.id) if isinstance(fn, ast.Name) else None
                if target:
                    found.stages[key]['symbol'] = f"{target[0][:-3].replace('/', '.')}.{target[1].name}"
                    describe(py, target[0], target[1], found.stages[key])
            elif method == 'add_edge' and len(call.args) >= 2:
                for a in (call.args[0].elts if isinstance(call.args[0], (ast.List, ast.Tuple)) else [call.args[0]]):
                    found.edge(node_key(label_of(a)), node_key(label_of(call.args[1])), 'declared', where, kind='data')
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
                router_fn = label_of(call.args[1]) or 'router'
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


# ---------------------------------------------------------------- build and CI files, and JSON exports

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


# ---------------------------------------------------------------- the scan

def _files(project, source=None):
    """(rel, text) of every file the scan reads: the project's in-scope, non-test files."""
    from ..vocabulary import classify
    if source is None:
        from .scope import declared_exclusions
        from .source import Source
        source = Source(project, exclude=list(declared_exclusions(project)) + ['node_modules', '.venv', 'venv', 'dist', 'build'])
    for item in source.readable():
        rel = item['path']
        if classify(rel) == 'test': continue
        name = Path(rel).name
        wanted = rel.endswith('.py') or name in ('package.json', 'Makefile', 'makefile', 'GNUmakefile', 'justfile', 'Justfile') \
            or ('.github/workflows/' in rel and rel.endswith(('.yml', '.yaml'))) or rel.endswith(('.asl.json', '.json'))
        if not wanted: continue
        text = source.text(rel)
        if text is not None: yield rel, text


def scan(project, source=None):
    """The pipelines of a project, as one record (see the module's docstring). Never runs the project."""
    found, flows = [], set()
    python, others = [], []
    for rel, text in _files(project, source):
        (python if rel.endswith('.py') else others).append((rel, text))
    py = Py(python)
    declared_lists(py, found)
    registry_loops(py, found)
    phases(py, found)
    airflow(py, found, flows)
    tasks = celery(py, found) or {}
    langgraph(py, found)
    luigi(py, found)
    queues(py, found)
    covered = {pair for f in found for pair in f.functions} | {(rel, '<dag>') for rel in ()}
    orchestrators(py, found, tasks, flows, covered)
    for rel, text in others:
        name = Path(rel).name
        if '.github/workflows/' in rel: github_actions(rel, text, found)
        elif name.lower() in ('makefile', 'gnumakefile'): make_targets(rel, text, found, 'makefile')
        elif name.lower() == 'justfile': make_targets(rel, text, found, 'justfile')
        elif name == 'package.json': npm_scripts(rel, text, found)
        elif rel.endswith('.json'): json_exports(rel, text, found)
    _link_sub_pipelines(found)
    for f in found:
        if not f.fans: _fans_from_edges(f)
        _globals_and_env(py, f)
    return _record(found, py)


def _link_sub_pipelines(found):
    """A stage whose function is another pipeline's orchestrator opens that pipeline: its sub-pipeline."""
    by_function = {}
    for f in found:
        entry = f.entry
        for path_name in f.functions: by_function.setdefault(path_name, f)
    for f in found:
        for stage in f.stages.values():
            target = stage.pop('callable', None)
            symbol = stage.get('symbol') or ''
            candidates = [target] if target else []
            if symbol and '.' in symbol:
                module, name = symbol.rsplit('.', 1)
                candidates.append((module.replace('.', '/') + '.py', name))
            for candidate in candidates:
                child = by_function.get(candidate)
                if child is not None and child is not f and child.parent is None:
                    stage['sub_pipeline'], child.parent = child.id, stage['id']
                    break


def _fans_from_edges(found):
    if found.kind in ('declared_dag', 'registry_loop', 'orchestrator', 'airflow', 'langgraph', 'prefect', 'dagster'):
        real = {k for k, s in found.stages.items() if s['kind'] not in ('router', 'fork', 'join')}
        outgoing, incoming = defaultdict(list), defaultdict(set)
        for a, b in found.edges:
            if a in real and b in real: outgoing[a].append(b); incoming[b].add(a)
        for fork, branches in sorted(outgoing.items()):
            if len(branches) < 2: continue
            joins = [s for s, sources in incoming.items() if set(branches) <= sources]
            if found.kind in ('declared_dag', 'registry_loop'):
                # A declared DAG's stages read the snapshot and earlier artifacts; a fan is a fork whose branches meet again.
                if not joins: continue
            found.fans.append({'id': f'{fork}:fan', 'pipeline': found.id, 'fork': fork, 'join': joins[0] if joins else None,
                               'branches': sorted(branches, key=found.order.index), 'matched': bool(joins),
                               'kind': 'parallel' if found.kind == 'airflow' else 'collect', 'evidence': found.stages[fork]['entry']})


def _globals_and_env(py, found):
    """Module globals and environment variables one stage writes and another reads, beside the declared flow."""
    writes, reads = defaultdict(set), defaultdict(set)
    where = {}
    for key, stage in found.stages.items():
        symbol = stage.get('symbol') or ''
        if '.' not in symbol: continue
        module, name = symbol.rsplit('.', 1)
        rel = module.replace('.', '/') + '.py'
        node = py.defs.get(rel, {}).get(name)
        if node is None or rel != stage['entry']['path']: continue
        declared = {n for s in ast.walk(node) if isinstance(s, ast.Global) for n in s.names}
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and sub.id in declared:
                (writes if isinstance(sub.ctx, ast.Store) else reads)[('global', sub.id)].add(key); where.setdefault(('global', sub.id), (rel, sub.lineno))
            elif isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load) and sub.id in py.assigns.get(rel, {}) and sub.id.isupper() is False \
                    and sub.id.islower():
                reads[('global', sub.id)].add(key)
            elif isinstance(sub, ast.Subscript) and _unparse(sub.value) == 'os.environ' and _str(sub.slice):
                (writes if isinstance(sub.ctx, ast.Store) else reads)[('env', _str(sub.slice))].add(key); where.setdefault(('env', _str(sub.slice)), (rel, sub.lineno))
            elif isinstance(sub, ast.Call) and _unparse(sub.func) in ('os.environ.get', 'os.getenv') and sub.args and _str(sub.args[0]):
                reads[('env', _str(sub.args[0]))].add(key)
    for (channel, name), writers in writes.items():
        readers = reads.get((channel, name), set()) - writers
        if not readers: continue
        rel, line = where[(channel, name)]
        found.hidden.append({'id': f'{found.id}:{channel}:{slug(name)}', 'pipeline': found.id, 'kind': 'side_channel', 'channel': channel,
                             'name': name, 'stages': sorted(writers | readers, key=found.order.index), 'evidence': site(rel, line, py.line(rel, line))})


def _record(found, py):
    pipelines = [f.record() for f in found if f.stages]
    product = [p for p in pipelines if p['role'] == 'product']
    confidence = max((p['confidence'] for p in product), default=None)
    detected = bool(product) and confidence >= DETECTED_AT
    kinds = sorted({p['kind'] for p in pipelines}, key=[k for k, _ in KINDS].index)
    counts = defaultdict(int)
    for p in pipelines: counts[p['kind']] += 1
    looked = [{'kind': kind, 'label': label, 'found': counts.get(kind, 0),
               'how': HOW.get(kind, 'read from the code without running it')} for kind, label in KINDS]
    evidence = [p['evidence'][0] if p['evidence'] else p['entry'] for p in product][:8]
    return {'detected': detected, 'confidence': confidence, 'kinds': kinds, 'evidence': evidence, 'looked_for': looked,
            'pipelines': pipelines, 'read': {'python_files': len(py.trees)}}


# ---------------------------------------------------------------- facts in and out

def run(target, source, **_):
    """The extractor: one fact per pipeline element, each located at its evidence, so a card or a page can cite it."""
    record = scan(target, source)
    facts = facts_of(record, source.content_fingerprint if hasattr(source, 'content_fingerprint') else '')
    return {'facts': facts, 'input_sha': digest(json.dumps(record, sort_keys=True, default=str).encode('utf-8')),
            'summary': {'detected': record['detected'], 'pipelines': len(record['pipelines']),
                        'stages': sum(len(p['stages']) for p in record['pipelines']), 'kinds': record['kinds']},
            'available': True, 'reason': None}


ELEMENTS = (('stages', 'pipeline_stage', 'entry'), ('edges', 'pipeline_edge', 'evidence'), ('routers', 'pipeline_router', 'entry'),
            ('fans', 'pipeline_fan', 'evidence'), ('control', 'pipeline_control', 'evidence'), ('error_lanes', 'pipeline_error', 'evidence'),
            ('hidden', 'pipeline_hidden', 'evidence'), ('unresolved', 'pipeline_unresolved', 'evidence'))


def facts_of(record, sha=''):
    def located(where):
        return {'path': where.get('path'), 'start_line': where.get('line')}
    rows = [make('pipeline_scan', NAME, VERSION, sha, {'path': '.', 'start_line': None},
                 {k: record[k] for k in ('detected', 'confidence', 'kinds', 'evidence', 'looked_for', 'read')})]
    for pipeline in record['pipelines']:
        head = {k: v for k, v in pipeline.items() if k not in dict((e[0], 1) for e in ELEMENTS)}
        rows.append(make('pipeline', NAME, VERSION, sha, located(pipeline['entry']), head))
        for field, kind, at in ELEMENTS:
            for index, item in enumerate(pipeline[field]):
                rows.append(make(kind, NAME, VERSION, sha, located(item.get(at) or {}), {**item, 'index': index}))
    return rows


def record_of(facts):
    """The record back from facts/pipeline.json's facts, each element with the id of its fact."""
    record = {'detected': False, 'confidence': None, 'kinds': [], 'evidence': [], 'looked_for': [], 'pipelines': []}
    by_id = {}
    for row in facts:
        if row.get('kind') == 'pipeline_scan': record.update(row['value'])
        elif row.get('kind') == 'pipeline':
            pipeline = {**row['value'], 'fact': row['id'], **{field: [] for field, _, _ in ELEMENTS}}
            by_id[pipeline['id']] = pipeline
            record['pipelines'].append(pipeline)
    kinds = {kind: field for field, kind, _ in ELEMENTS}
    for row in facts:
        field = kinds.get(row.get('kind'))
        if not field: continue
        item = {k: v for k, v in row['value'].items() if k != 'index'}
        pipeline = by_id.get(item.get('pipeline'))
        if pipeline is None: continue
        item['fact'] = row['id']
        pipeline[field].append((row['value'].get('index', 0), item))
    for pipeline in record['pipelines']:
        for field, _, _ in ELEMENTS:
            pipeline[field] = [item for _, item in sorted(pipeline[field], key=lambda pair: pair[0])]
    return record


def write(report, record):
    """facts/pipeline.json of a report, as the facts stage writes it; returns its index entry."""
    from .store import facts_dir, write_set
    facts_dir(report)
    rows = facts_of(record)
    return write_set(report, NAME, NAME, VERSION, rows, digest(json.dumps(record, sort_keys=True, default=str).encode('utf-8')),
                     LIMITATIONS, {'detected': record['detected'], 'pipelines': len(record['pipelines'])})


def read(report):
    """The record of a report's facts/pipeline.json, or None when the check did not write it."""
    path = Path(report) / 'facts' / 'pipeline.json'
    if not path.is_file(): return None
    try: return record_of(json.loads(path.read_text(encoding='utf-8')).get('facts') or [])
    except (OSError, ValueError): return None

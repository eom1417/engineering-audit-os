"""The pipeline map's reading model: one pipeline as it is found, the Python index of a project, and what a stage
function touches. Shared by the readers of eaos/facts/pipeline_code.py and eaos/facts/pipeline_frameworks.py."""
import ast
import re

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


class Py:
    """Every Python file of the project parsed once: its functions, classes, module-level values and imports."""

    def __init__(self, files):
        self.trees, self.lines, self.defs, self.classes, self.assigns, self.imports = {}, {}, {}, {}, {}, {}
        self.modules = {}
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
        return None

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


def describe(py, rel, node, found_stage):
    """Fill a stage's tools, side effects and marks from its entry function's body (one level, no guessing)."""
    if node is None: return
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        params = [a for a in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs] if a.arg not in ('self', 'cls')]
        found_stage['annotated'] = node.returns is not None and all(a.annotation is not None for a in params)
        found_stage['shared_context'] = len(params) == 1 and params[0].arg in CONTEXT_PARAMS
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


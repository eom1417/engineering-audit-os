"""Domain constants, data models and rule duplication — the source-of-truth view, from facts only.

The question this answers is the one that matters when a number differs between two screens:
where does this rule live, and does it live in more than one place?
"""
import ast
from collections import defaultdict
from pathlib import PurePosixPath
import re
from . import digest, make
from .source import language_of

NAME = 'domain'
VERSION = '2'
LIMITATIONS = [
    'Only literal module-level constants are captured; values computed at runtime are not.',
    'Two identical values are a duplication signal, not proof that they encode the same rule.',
    'Table and model detection is pattern-based; an unrecognised ORM is missed, not absent.',
    'Ownership of a rule is not asserted here; that requires semantic review.',
    'A mutable module-level value is a shared-state signal, not proof of a concurrency defect.',
    'Writes into third-party or standard-library modules are not reported; only modules this snapshot defines.',
    'Row-level security and access policies are read from .sql files in path order, which is migration order when '
    'names carry a timestamp; a policy created from a dashboard and never written to SQL is not seen.',
]
JS_CONST = re.compile(r'^[ \t]*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Z][A-Z0-9_]{2,})\s*=\s*(?P<value>[^;\n]+)', re.M)
# The name is never the keyword: `CREATE TABLE IF NOT EXISTS ${name}` (a name built at run time) is no table called "IF".
SQL_TABLE = re.compile(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"\[]?(?!IF\b)(?P<name>[\w.]+)', re.I)
# Prose that quotes a schema (a plan, a README) declares no table.
PROSE = ('.md', '.mdx', '.markdown', '.txt', '.rst')
ORM_MODEL = re.compile(r'^[ \t]*class\s+(?P<name>\w+)\s*\(([^)]*(?:Model|Base|Document|Entity)[^)]*)\)', re.M)
TS_MODEL = re.compile(r'^[ \t]*(?:export\s+)?(?:interface|type)\s+(?P<name>\w+)\s*[={]', re.M)
MIGRATION = re.compile(r'(migrations?|alembic|flyway|liquibase)/', re.I)
SQL_NAME = r'(?P<table>(?:"?\w+"?\.)?"?\w+"?)'
SQL_RLS = re.compile(r'ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?' + SQL_NAME + r'\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY', re.I)
SQL_POLICY = re.compile(r'CREATE\s+POLICY\s+(?P<quote>"?)(?P<name>.+?)(?P=quote)\s+ON\s+' + SQL_NAME + r'(?P<body>[^;]*)', re.I | re.S)
SQL_DROP_POLICY = re.compile(r'DROP\s+POLICY\s+(?:IF\s+EXISTS\s+)?(?P<quote>"?)(?P<name>.+?)(?P=quote)\s+ON\s+' + SQL_NAME, re.I)
SQL_DROP_TABLE = re.compile(r'DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?' + SQL_NAME, re.I)
SQL_OPEN = re.compile(r'\b(USING|WITH\s+CHECK)\s*\(\s*true\s*\)', re.I)
# Per-module metadata, not shared domain rules: repeating these names says nothing about rule ownership.
CONVENTIONAL = {'NAME', 'VERSION', 'SCHEMA_VERSION', 'LIMITATIONS', 'LOGGER', 'LOG', 'DEBUG', 'TAG', 'AUTHOR',
                'LICENSE', 'ORDER', 'DEFAULT', 'PREFIX', 'SUFFIX', 'ENCODING', 'TIMEOUT_DEFAULT'}


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


def _plain_literal(node):
    try: literal = ast.literal_eval(node)
    except (ValueError, SyntaxError): return None
    return literal if isinstance(literal, (int, float, str, bool)) else None


def python_constants(text):
    tree = _parse(text)
    if tree is None: return []
    found = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None: continue
        for target in _assign_targets(node):
            if not (isinstance(target, ast.Name) and target.id.isupper()): continue
            literal = _plain_literal(node.value)
            if literal is not None: found.append((target.id, literal, node.lineno))
    return found


def table_key(name):
    """One spelling per table: quotes dropped, lower case, and the default schema made explicit."""
    name = name.replace('"', '').replace('`', '').lower()
    return name if '.' in name else 'public.' + name


def sql_access(files):
    """Net row-level security and policies after every migration has run, in path order.

    A policy dropped and created again counts once; one dropped and not recreated does not count.
    """
    state = {'rls': set(), 'dropped': set(), 'policies': {}}
    for rel, text in sorted(files):
        for event in _sql_events(text): _apply_sql_event(state, rel, text, event)
    policies = {key: value for key, value in state['policies'].items() if key[0] not in state['dropped']}
    return {'rls': state['rls'], 'dropped': state['dropped'], 'policies': policies}


def _sql_events(text):
    events = [(m.start(), 'rls', m) for m in SQL_RLS.finditer(text)]
    events += [(m.start(), 'policy', m) for m in SQL_POLICY.finditer(text)]
    events += [(m.start(), 'drop_policy', m) for m in SQL_DROP_POLICY.finditer(text)]
    events += [(m.start(), 'drop_table', m) for m in SQL_DROP_TABLE.finditer(text)]
    return sorted(events, key=lambda event: event[0])


def _policy(rel, text, offset, match):
    body = ' '.join(match.group('body').split())
    command = re.search(r'\bFOR\s+(ALL|SELECT|INSERT|UPDATE|DELETE)\b', body, re.I)
    roles = re.search(r'\bTO\s+([\w\s,]+?)(?:\s+USING|\s+WITH|$)', body, re.I)
    return {'path': rel, 'line': text.count('\n', 0, offset) + 1,
            'command': (command.group(1).upper() if command else 'ALL'),
            'roles': [role.strip() for role in roles.group(1).split(',')] if roles else ['public'],
            'open': bool(SQL_OPEN.search(body))}


def _apply_sql_event(state, rel, text, event):
    offset, kind, match = event
    table = table_key(match.group('table'))
    if kind == 'rls': state['rls'].add(table); state['dropped'].discard(table)
    elif kind == 'drop_table': state['dropped'].add(table); state['rls'].discard(table)
    elif kind == 'drop_policy': state['policies'].pop((table, match.group('name')), None)
    else: state['policies'][(table, match.group('name'))] = _policy(rel, text, offset, match)


def _owned_modules(source):
    # A module is "ours" when a file in the snapshot defines it.
    owned = set()
    for item in source.readable():
        if not item['path'].endswith('.py'): continue
        parts = PurePosixPath(item['path']).parts
        owned.add(PurePosixPath(item['path']).stem)
        if len(parts) > 1: owned.add(parts[-2])
    return owned


def _line(text, match): return text.count('\n', 0, match.start()) + 1


def _add_mutables(found, rel, text, language, rows):
    found['mutable_globals'] += [(rel, name, shape, line, how, where, scope, encapsulated(name, text, language))
                                 for name, shape, line, how, where, scope in rows]


def _scan_python(found, rel, text, owned):
    for name, value, line in python_constants(text): found['constants'][name].append((rel, line, value))
    _add_mutables(found, rel, text, 'python', python_mutable_globals(text))
    found['external_writes'] += [(rel, module, attribute, line) for module, attribute, line in python_external_writes(text, owned)]
    found['models'] += [(match.group('name'), rel, _line(text, match), 'python_class') for match in ORM_MODEL.finditer(text)]


def _js_value(raw):
    try: return ast.literal_eval(raw)
    except (ValueError, SyntaxError): return raw[:40]


def _scan_js(found, rel, text, language):
    _add_mutables(found, rel, text, language, js_mutable_globals(text))
    for match in JS_CONST.finditer(text):
        found['constants'][match.group('name')].append((rel, _line(text, match), _js_value(match.group('value').strip().rstrip(','))))
    found['models'] += [(match.group('name'), rel, _line(text, match), 'ts_type') for match in TS_MODEL.finditer(text)]


def _scan_tables(found, rel, text):
    if rel.endswith('.sql') or ('CREATE TABLE' in text.upper() and not rel.lower().endswith(PROSE)):
        found['tables'] += [(match.group('name'), rel, _line(text, match)) for match in SQL_TABLE.finditer(text)]
    if MIGRATION.search(rel): found['migrations'].append(rel)
    if rel.endswith('.sql'): found['sql_files'].append((rel, text))


def _scan_file(found, rel, text, owned):
    language = language_of(rel)
    if language == 'python': _scan_python(found, rel, text, owned)
    elif language == 'go': _add_mutables(found, rel, text, language, go_mutable_globals(text))
    elif language in {'javascript', 'typescript', 'tsx'}: _scan_js(found, rel, text, language)
    _scan_tables(found, rel, text)


def _excluded_reason(name, per_module_identifier):
    if name in CONVENTIONAL: return 'conventional module metadata'
    if per_module_identifier: return 'per-module identifier: every site holds a different string'
    return None


def _constant_fact(name, places):
    values = {repr(value) for _, _, value in places}
    # A name whose every site holds a different *string* is a per-module identifier (module name, version).
    # Numbers that differ between sites are the opposite: one rule with two answers, which is the case we care about.
    per_module_identifier = (len(places) > 1 and len(values) == len(places)
                             and all(isinstance(value, str) for _, _, value in places))
    duplicate = len(places) > 1 and name not in CONVENTIONAL and not per_module_identifier
    return make('domain_constant', NAME, VERSION, digest(name.encode('utf-8')), {'path': places[0][0], 'start_line': places[0][1]},
                {'name': name, 'definitions': [{'path': path, 'line': line} for path, line, _ in places],
                 'distinct_values': len(values), 'duplicated': duplicate,
                 'same_value_everywhere': len(values) == 1 and duplicate,
                 'excluded_reason': _excluded_reason(name, per_module_identifier)},
                limitations=LIMITATIONS)


def _table_value(name, rel, access):
    key = table_key(name)
    value = {'name': name}
    if rel.endswith('.sql'):
        value.update(rls_enabled=key in access['rls'], policies=sum(table == key for table, _ in access['policies']),
                     dropped=key in access['dropped'])
    return value


def _policy_fact(table, name, policy):
    return make('db_policy', NAME, VERSION, digest((table + '/' + name).encode('utf-8')),
                {'path': policy['path'], 'start_line': policy['line']},
                {'table': table, 'name': name, 'command': policy['command'], 'roles': policy['roles'],
                 'open': policy['open']}, limitations=LIMITATIONS)


def _mutable_fact(row):
    rel, name, shape, line, how, where, scope, private = row
    return make('mutable_global', NAME, VERSION, digest((rel + name).encode('utf-8')),
                {'path': rel, 'start_line': line},
                {'name': name, 'shape': shape, 'mutated_by': how, 'mutated_at_line': where,
                 'mutation_scope': scope, 'encapsulated': private,
                 'note': 'Built at import time in its own module.' if scope == 'module'
                         else 'Changed while the program runs.'},
                limitations=LIMITATIONS)


def _facts(found):
    constants = found['constants']
    facts = [_constant_fact(name, sorted(constants[name])) for name in sorted(constants)]
    facts += [make('data_model', NAME, VERSION, digest((name + rel).encode('utf-8')), {'path': rel, 'start_line': line},
                   {'name': name, 'kind': kind}, limitations=LIMITATIONS) for name, rel, line, kind in sorted(found['models'])]
    access = sql_access(found['sql_files'])
    facts += [make('data_table', NAME, VERSION, digest((name + rel).encode('utf-8')), {'path': rel, 'start_line': line},
                   _table_value(name, rel, access), limitations=LIMITATIONS) for name, rel, line in sorted(found['tables'])]
    facts += [_policy_fact(table, name, policy) for (table, name), policy in sorted(access['policies'].items())]
    facts += [_mutable_fact(row) for row in sorted(found['mutable_globals'])]
    facts += [make('external_state_write', NAME, VERSION, digest((rel + module + attribute).encode('utf-8')),
                   {'path': rel, 'start_line': line},
                   {'module': module, 'attribute': attribute}, limitations=LIMITATIONS)
              for rel, module, attribute, line in sorted(found['external_writes'])]
    return facts


def _summary(facts, found):
    constants, mutable_globals = found['constants'], found['mutable_globals']
    flagged = {fact['value']['name'] for fact in facts if fact['kind'] == 'domain_constant' and fact['value']['duplicated']}
    distinct = lambda name: len({repr(v) for _, _, v in constants[name]})
    return {'constants': len(constants), 'duplicated_constants': len(flagged),
            'duplicated_with_same_value': sorted(name for name in flagged if distinct(name) == 1),
            'duplicated_with_different_values': sorted(name for name in flagged if distinct(name) > 1),
            'excluded_from_duplication': sorted({fact['value']['name'] for fact in facts
                                                 if fact['kind'] == 'domain_constant' and fact['value'].get('excluded_reason')}),
            'mutable_globals': len(mutable_globals),
            'mutable_globals_changed_at_runtime': sum(1 for row in mutable_globals if row[6] == 'function'),
            'external_state_writes': len(found['external_writes']),
            'data_models': len(found['models']), 'data_tables': len(found['tables']),
            'migration_paths': sorted(set(found['migrations']))[:20],
            'interpretation': 'A constant repeated in two modules is a question about rule ownership, not yet a defect.'}


def run(target, source, **options):
    owned = _owned_modules(source)
    found = {'constants': defaultdict(list), 'models': [], 'tables': [], 'migrations': [], 'sql_files': [],
             'mutable_globals': [], 'external_writes': []}
    fingerprints = []
    for item in source.readable():
        rel, text = item['path'], source.text(item['path'])
        if text is None: continue
        fingerprints.append(item['sha256'])
        _scan_file(found, rel, text, owned)
    facts = _facts(found)
    facts.sort(key=lambda f: (f['kind'], f['value'].get('name', ''), f['location']['path']))
    return {'facts': facts, 'summary': _summary(facts, found), 'available': True,
            'input_sha': digest(''.join(sorted(set(fingerprints))).encode('utf-8')), 'reason': None}

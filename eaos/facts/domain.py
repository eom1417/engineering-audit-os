"""Domain constants, data models and rule duplication — the source-of-truth view, from facts only.

The question this answers is the one that matters when a number differs between two screens:
where does this rule live, and does it live in more than one place? The module state a program changes while it
runs, and its writes into another module, are read by eaos/facts/domain_state.py.
"""
import ast
from collections import defaultdict
from pathlib import PurePosixPath
import re
from . import digest, make
from .domain_state import (_assign_targets, _parse, encapsulated, go_mutable_globals, js_mutable_globals,
                           python_external_writes, python_mutable_globals)
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
    return {'constants': len(constants), **_duplicates(facts, constants),
            'excluded_from_duplication': sorted({fact['value']['name'] for fact in facts
                                                 if fact['kind'] == 'domain_constant' and fact['value'].get('excluded_reason')}),
            'mutable_globals': len(mutable_globals),
            'mutable_globals_changed_at_runtime': sum(1 for row in mutable_globals if row[6] == 'function'),
            'external_state_writes': len(found['external_writes']),
            'data_models': len(found['models']), 'data_tables': len(found['tables']),
            'migration_paths': sorted(set(found['migrations']))[:20],
            'interpretation': 'A constant repeated in two modules is a question about rule ownership, not yet a defect.'}


def _duplicates(facts, constants):
    """How many constants are written in more than one place, and which of them hold the same value or differ."""
    flagged = {fact['value']['name'] for fact in facts if fact['kind'] == 'domain_constant' and fact['value']['duplicated']}
    distinct = lambda name: len({repr(v) for _, _, v in constants[name]})
    return {'duplicated_constants': len(flagged),
            'duplicated_with_same_value': sorted(name for name in flagged if distinct(name) == 1),
            'duplicated_with_different_values': sorted(name for name in flagged if distinct(name) > 1)}


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

"""Domain constants, data models and rule duplication — the source-of-truth view, from facts only.

The question this answers is the one that matters when a number differs between two screens:
where does this rule live, and does it live in more than one place?
"""
import ast
from collections import defaultdict
import re
from . import digest, make
from .source import language_of

NAME = 'domain'
VERSION = '1'
LIMITATIONS = [
    'Only literal module-level constants are captured; values computed at runtime are not.',
    'Two identical values are a duplication signal, not proof that they encode the same rule.',
    'Table and model detection is pattern-based; an unrecognised ORM is missed, not absent.',
    'Ownership of a rule is not asserted here; that requires semantic review.',
]
JS_CONST = re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Z][A-Z0-9_]{2,})\s*=\s*(?P<value>[^;\n]+)', re.M)
SQL_TABLE = re.compile(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"\[]?(?P<name>[\w.]+)', re.I)
ORM_MODEL = re.compile(r'^\s*class\s+(?P<name>\w+)\s*\(([^)]*(?:Model|Base|Document|Entity)[^)]*)\)', re.M)
TS_MODEL = re.compile(r'^\s*(?:export\s+)?(?:interface|type)\s+(?P<name>\w+)\s*[={]', re.M)
MIGRATION = re.compile(r'(migrations?|alembic|flyway|liquibase)/', re.I)
# Per-module metadata, not shared domain rules: repeating these names says nothing about rule ownership.
CONVENTIONAL = {'NAME', 'VERSION', 'SCHEMA_VERSION', 'LIMITATIONS', 'LOGGER', 'LOG', 'DEBUG', 'TAG', 'AUTHOR',
                'LICENSE', 'ORDER', 'DEFAULT', 'PREFIX', 'SUFFIX', 'ENCODING', 'TIMEOUT_DEFAULT'}


def python_constants(text):
    try: tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError): return []
    found = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id.isupper() and node.value is not None:
                    try: literal = ast.literal_eval(node.value)
                    except (ValueError, SyntaxError): continue
                    if isinstance(literal, (int, float, str, bool)):
                        found.append((target.id, literal, node.lineno))
    return found


def run(target, source, **options):
    facts, fingerprints = [], []
    constants = defaultdict(list)
    models, tables, migrations = [], [], []
    for item in source.readable():
        rel, text = item['path'], source.text(item['path'])
        if text is None: continue
        language = language_of(rel)
        fingerprints.append(item['sha256'])
        if language == 'python':
            for name, value, line in python_constants(text): constants[name].append((rel, line, value))
            for match in ORM_MODEL.finditer(text):
                models.append((match.group('name'), rel, text.count('\n', 0, match.start()) + 1, 'python_class'))
        elif language in {'javascript', 'typescript', 'tsx'}:
            for match in JS_CONST.finditer(text):
                raw = match.group('value').strip().rstrip(',')
                try: value = ast.literal_eval(raw)
                except (ValueError, SyntaxError): value = raw[:40]
                constants[match.group('name')].append((rel, text.count('\n', 0, match.start()) + 1, value))
            for match in TS_MODEL.finditer(text):
                models.append((match.group('name'), rel, text.count('\n', 0, match.start()) + 1, 'ts_type'))
        if rel.endswith('.sql') or 'CREATE TABLE' in text.upper():
            for match in SQL_TABLE.finditer(text):
                tables.append((match.group('name'), rel, text.count('\n', 0, match.start()) + 1))
        if MIGRATION.search(rel): migrations.append(rel)
    duplicated = 0
    for name in sorted(constants):
        places = sorted(constants[name])
        values = {repr(value) for _, _, value in places}
        fact_kind = 'domain_constant'
        # A name whose every site holds a different *string* is a per-module identifier (module name, version).
        # Numbers that differ between sites are the opposite: one rule with two answers, which is the case we care about.
        per_module_identifier = (len(places) > 1 and len(values) == len(places)
                                 and all(isinstance(value, str) for _, _, value in places))
        duplicate = len(places) > 1 and name not in CONVENTIONAL and not per_module_identifier
        if duplicate: duplicated += 1
        facts.append(make(fact_kind, NAME, VERSION, digest(name.encode('utf-8')), {'path': places[0][0], 'start_line': places[0][1]},
                          {'name': name, 'definitions': [{'path': path, 'line': line} for path, line, _ in places],
                           'distinct_values': len(values), 'duplicated': duplicate,
                           'same_value_everywhere': len(values) == 1 and duplicate,
                           'excluded_reason': ('conventional module metadata' if name in CONVENTIONAL
                                               else 'per-module identifier: every site holds a different string' if per_module_identifier
                                               else None)},
                          limitations=LIMITATIONS))
    for name, rel, line, kind in sorted(models):
        facts.append(make('data_model', NAME, VERSION, digest((name + rel).encode('utf-8')), {'path': rel, 'start_line': line},
                          {'name': name, 'kind': kind}, limitations=LIMITATIONS))
    for name, rel, line in sorted(tables):
        facts.append(make('data_table', NAME, VERSION, digest((name + rel).encode('utf-8')), {'path': rel, 'start_line': line},
                          {'name': name}, limitations=LIMITATIONS))
    facts.sort(key=lambda f: (f['kind'], f['value'].get('name', ''), f['location']['path']))
    flagged = {fact['value']['name'] for fact in facts if fact['kind'] == 'domain_constant' and fact['value']['duplicated']}
    summary = {'constants': len(constants), 'duplicated_constants': duplicated,
               'duplicated_with_same_value': sorted(name for name in flagged
                                                    if len({repr(v) for _, _, v in constants[name]}) == 1),
               'duplicated_with_different_values': sorted(name for name in flagged
                                                          if len({repr(v) for _, _, v in constants[name]}) > 1),
               'excluded_from_duplication': sorted({fact['value']['name'] for fact in facts
                                                    if fact['kind'] == 'domain_constant' and fact['value'].get('excluded_reason')}),
               'data_models': len(models), 'data_tables': len(tables), 'migration_paths': sorted(set(migrations))[:20],
               'interpretation': 'A constant repeated in two modules is a question about rule ownership, not yet a defect.'}
    return {'facts': facts, 'summary': summary, 'available': True,
            'input_sha': digest(''.join(sorted(set(fingerprints))).encode('utf-8')), 'reason': None}

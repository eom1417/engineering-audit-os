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
VERSION = '1'
LIMITATIONS = [
    'Only literal module-level constants are captured; values computed at runtime are not.',
    'Two identical values are a duplication signal, not proof that they encode the same rule.',
    'Table and model detection is pattern-based; an unrecognised ORM is missed, not absent.',
    'Ownership of a rule is not asserted here; that requires semantic review.',
    'A mutable module-level value is a shared-state signal, not proof of a concurrency defect.',
    'Writes into third-party or standard-library modules are not reported; only modules this snapshot defines.',
]
JS_CONST = re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Z][A-Z0-9_]{2,})\s*=\s*(?P<value>[^;\n]+)', re.M)
SQL_TABLE = re.compile(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"\[]?(?P<name>[\w.]+)', re.I)
ORM_MODEL = re.compile(r'^\s*class\s+(?P<name>\w+)\s*\(([^)]*(?:Model|Base|Document|Entity)[^)]*)\)', re.M)
TS_MODEL = re.compile(r'^\s*(?:export\s+)?(?:interface|type)\s+(?P<name>\w+)\s*[={]', re.M)
MIGRATION = re.compile(r'(migrations?|alembic|flyway|liquibase)/', re.I)
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
    try: tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError): return []
    bound = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and isinstance(node.value, MUTABLE):
                    bound[target.id] = (type(node.value).__name__, node.lineno)
    # A dict built up at module level is initialisation; the same write inside a function is
    # state that changes while the program runs, which is the case worth reporting.
    module_level = set()
    for statement in tree.body:
        for node in ast.walk(statement):
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)): continue
            module_level.add(id(node))
    mutated = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            for name in node.names: mutated[name] = ('global_statement', node.lineno, 'function')
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id in bound \
                and node.func.attr in MUTATORS:
            mutated[node.func.value.id] = ('method:' + node.func.attr, node.lineno,
                                           'module' if id(node) in module_level else 'function')
        elif isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id in bound:
                    mutated[target.value.id] = ('item_assignment', node.lineno,
                                                'module' if id(node) in module_level else 'function')
    found = []
    for name, (shape, line) in sorted(bound.items()):
        if name not in mutated: continue
        how, where, scope = mutated[name]
        found.append((name, shape, line, how, where, scope))
    for name, value in sorted(mutated.items()):
        how, where, scope = value
        if name not in bound and how == 'global_statement':
            found.append((name, 'rebound_global', where, how, where, scope))
    return found


def python_external_writes(text, owned=None):
    """Assignments into another module's namespace: state written by someone who does not own it.

    Only modules this project owns count. Setting sys.dont_write_bytecode is an idiom, not a
    violation of somebody's invariant, and flagging it buries the case that matters.
    """
    try: tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError): return []
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names: modules.add((alias.asname or alias.name).split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names: modules.add(alias.asname or alias.name)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AugAssign)): continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id in modules:
                if owned is not None and target.value.id not in owned: continue
                found.append((target.value.id, target.attr, node.lineno))
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
    mutable_globals, external_writes = [], []
    # A module is "ours" when a file in the snapshot defines it.
    owned_modules = set()
    for item in source.readable():
        parts = PurePosixPath(item['path']).parts
        if item['path'].endswith('.py'):
            owned_modules.add(PurePosixPath(item['path']).stem)
            if len(parts) > 1: owned_modules.add(parts[-2])
    for item in source.readable():
        rel, text = item['path'], source.text(item['path'])
        if text is None: continue
        language = language_of(rel)
        fingerprints.append(item['sha256'])
        if language == 'python':
            for name, value, line in python_constants(text): constants[name].append((rel, line, value))
            for name, shape, line, how, where, scope in python_mutable_globals(text):
                mutable_globals.append((rel, name, shape, line, how, where, scope))
            for module, attribute, line in python_external_writes(text, owned_modules):
                external_writes.append((rel, module, attribute, line))
            for match in ORM_MODEL.finditer(text):
                models.append((match.group('name'), rel, text.count('\n', 0, match.start()) + 1, 'python_class'))
        elif language == 'go':
            for name, shape, line, how, where, scope in go_mutable_globals(text):
                mutable_globals.append((rel, name, shape, line, how, where, scope))
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
    for rel, name, shape, line, how, where, scope in sorted(mutable_globals):
        facts.append(make('mutable_global', NAME, VERSION, digest((rel + name).encode('utf-8')),
                          {'path': rel, 'start_line': line},
                          {'name': name, 'shape': shape, 'mutated_by': how, 'mutated_at_line': where,
                           'mutation_scope': scope,
                           'note': 'Built at import time in its own module.' if scope == 'module'
                                   else 'Changed while the program runs.'},
                          limitations=LIMITATIONS))
    for rel, module, attribute, line in sorted(external_writes):
        facts.append(make('external_state_write', NAME, VERSION, digest((rel + module + attribute).encode('utf-8')),
                          {'path': rel, 'start_line': line},
                          {'module': module, 'attribute': attribute}, limitations=LIMITATIONS))
    facts.sort(key=lambda f: (f['kind'], f['value'].get('name', ''), f['location']['path']))
    flagged = {fact['value']['name'] for fact in facts if fact['kind'] == 'domain_constant' and fact['value']['duplicated']}
    summary = {'constants': len(constants), 'duplicated_constants': duplicated,
               'duplicated_with_same_value': sorted(name for name in flagged
                                                    if len({repr(v) for _, _, v in constants[name]}) == 1),
               'duplicated_with_different_values': sorted(name for name in flagged
                                                          if len({repr(v) for _, _, v in constants[name]}) > 1),
               'excluded_from_duplication': sorted({fact['value']['name'] for fact in facts
                                                    if fact['kind'] == 'domain_constant' and fact['value'].get('excluded_reason')}),
               'mutable_globals': len(mutable_globals),
               'mutable_globals_changed_at_runtime': sum(1 for row in mutable_globals if row[6] == 'function'), 'external_state_writes': len(external_writes),
               'data_models': len(models), 'data_tables': len(tables), 'migration_paths': sorted(set(migrations))[:20],
               'interpretation': 'A constant repeated in two modules is a question about rule ownership, not yet a defect.'}
    return {'facts': facts, 'summary': summary, 'available': True,
            'input_sha': digest(''.join(sorted(set(fingerprints))).encode('utf-8')), 'reason': None}

"""The domain data of the simulated users (M10.2): realistic sample data that fits the project, before any of them acts.

The external services the project calls are read by rules (eaos/rules/external-services.json) from the packages it
imports and the environment names it reads: each one is stubbed in the copy (the run's mail catcher, an address of its
own) or said as not covered, with why, when only a real account answers. The data models are the project's tables (the
domain facts, their columns read from the CREATE TABLE itself, the names a write sends); the assistant fills them once
with plain values: the values a persona types through the screens for a goal (`through_ui`), and the bulk history
seeded into the copy's own database (`seed`, eaos/live/experience/seed.py). Its answer is never trusted as it comes:
a row keeps only known tables and fields and plain values, an e-mail is example.com's, and nothing looks like a secret.
Without an assistant the rows are made by rules from the field types.

    <report>/experience/data.json   {"version": 1, "entities", "through_ui", "seed", "stubs", "not_covered"}
"""
import json
import re
from pathlib import Path

from ...facts.store import facts
from ...core.system.files import read_json

VERSION = 1
RULES = Path(__file__).resolve().parents[2] / 'rules/external-services.json'
LIMIT = {'entities': 30, 'fields': 25, 'rows': 10, 'seed': 50, 'goals': 30, 'values': 20, 'text': 200, 'sample': 3}
MANIFESTS = ('package.json', 'requirements.txt', 'requirements-dev.txt', 'pyproject.toml', 'Pipfile')
ENV_FILES = ('.env.example', '.env.sample', '.env.template', '.env.local.example')
ENV_NAME = re.compile(r'^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=', re.M)
PACKAGE = re.compile(r'(?:^|["\'])\s*([A-Za-z@][\w.@/-]*)', re.M)     # a requirement's name: a line's or a string's first word
# A column's type in a CREATE TABLE, first match wins: the plain kind a value of it takes.
KINDS = (('bool', 'boolean'), ('serial', 'number'), ('int', 'number'), ('numeric', 'number'), ('decimal', 'number'),
         ('real', 'number'), ('double', 'number'), ('float', 'number'), ('money', 'number'), ('timestamp', 'date'),
         ('date', 'date'), ('json', 'json'), ('uuid', 'id'))
CONSTRAINT = re.compile(r'^(constraint|primary|foreign|unique|check|exclude|like|index|key)\b', re.I)
MADE = re.compile(r'\b(default|serial|bigserial|identity|generated)\b', re.I)    # a column the database fills itself
EMAIL = re.compile(r'[\w.+-]+@[\w.-]+')
SECRET = re.compile(r'(sk_(live|test)_|pk_(live|test)_|AKIA[0-9A-Z]{12}|gh[pousr]_\w{20}|xox[abp]-|-----BEGIN|'
                    r'eyJ[\w-]{10,}\.|\b[A-Za-z0-9+/_-]{32,}\b)')
_TEXT = {'type': 'string'}
_ROWS = {'type': 'array', 'items': {'type': 'object'}}
SCHEMA = {'type': 'object', 'required': ['entities', 'through_ui', 'seed'],
          'properties': {'entities': {'type': 'array', 'items': {'type': 'object', 'required': ['table', 'rows'],
                                                                 'properties': {'table': _TEXT, 'rows': _ROWS}}},
                         'through_ui': {'type': 'array', 'items': {'type': 'object', 'required': ['goal', 'values'],
                                                                   'properties': {'goal': _TEXT, 'values': {'type': 'object'}}}},
                         'seed': {'type': 'array', 'items': {'type': 'object', 'required': ['table', 'rows'],
                                                             'properties': {'table': _TEXT, 'rows': _ROWS}}}}}
TASK = '''GOAL
You make the sample data of EAOS's simulated users: realistic, plain data that fits this app's business, so the people
who soon use its running copy meet screens that look lived in.

WHAT YOU ARE GIVEN
`entities`: the app's tables, each with its fields and their kinds (text, number, boolean, date, json, id, reference).
`goals`: what each simulated user comes to do (`persona.goal`). `stubs` and `not_covered`: the outside services the
copy stands in for, and those it cannot reach.

ANSWER
One JSON object of this schema: {schema}
`entities`: a few example rows per table ({rows} at most). `seed`: the history already in the database before anyone
comes (orders placed last month, posts written, customers known), {seed} rows per table at most, in an order that
fills a referenced table before the one pointing at it. `through_ui`: per goal, the values the persona types in the
screens, named by the label a person reads ("Email", "Title").
Use only the tables and fields given. Plain values only (text, numbers, true/false, dates as 2026-01-31). Every e-mail
ends in @example.com; no real person, no real card, no key, password or token. A goal through a service not covered
gets no values.'''


def _rules():
    return json.loads(RULES.read_text(encoding='utf-8'))['services']


def _declared(text):
    try: declared = json.loads(text)
    except ValueError: return {}
    return declared if isinstance(declared, dict) else {}


def _project_evidence(root):
    """(packages, environment names) a project's manifests and example environment files declare."""
    packages, names = set(), set()
    for name in MANIFESTS:
        path = Path(root) / name
        if not path.is_file(): continue
        text = path.read_text(encoding='utf-8', errors='replace')
        if name != 'package.json': packages |= {m.group(1).lower() for m in PACKAGE.finditer(text)}
        else: packages |= {p for key in ('dependencies', 'devDependencies') for p in _declared(text).get(key) or {}}
    for name in ENV_FILES:
        path = Path(root) / name
        if path.is_file(): names |= set(ENV_NAME.findall(path.read_text(encoding='utf-8', errors='replace')))
    return packages, names


def _imported(value):
    """The module an import fact names, and each name taken from it (`from google import genai`: google.genai)."""
    module = value.get('module')
    return {module, *(f'{module}.{name}' for name in value.get('names') or [])} if module else set()


def _facts_evidence(rows):
    """(packages, environment names) of the import and environment facts."""
    packages = set().union(*(_imported(row['value']) for row in rows if row.get('kind') == 'import_edge'))
    return packages, {row['value']['name'] for row in rows if row.get('kind') == 'env_read'}


def _evidence(where):
    """(packages, environment names) of a report (its facts), a project folder, or a list of facts."""
    if isinstance(where, list): return _facts_evidence(where)
    if (Path(where) / 'facts').is_dir(): return _facts_evidence(facts(where, 'import_edge', 'env_read'))
    return _project_evidence(where)


def _reveals(rule, packages, names):
    by_package = any(p == wanted or p.startswith((wanted + '/', wanted + '.')) for wanted in rule['packages'] for p in packages)
    return by_package or any(re.search(rule['env'], name) for name in names)


def services(where):
    """{stubs: [{service, kind, how}], not_covered: [{service, kind, why}]}: the external services the project uses
    (a report folder, a project folder or a list of facts), each stubbed in the copy or not covered, by the rules."""
    packages, names = _evidence(where)
    found = [rule for rule in _rules() if _reveals(rule, packages, names)]
    return {'stubs': [{'service': r['service'], 'kind': r['kind'], 'how': r['stub']} for r in found if r['stub']],
            'not_covered': [{'service': r['service'], 'kind': r['kind'], 'why': r['why']} for r in found if not r['stub']]}


def _kind(column):
    words = column.split()
    if len(words) > 1 and re.search(r'\breferences\b', column, re.I): return 'reference'
    declared = words[1].lower() if len(words) > 1 else ''
    return next((kind for key, kind in KINDS if key in declared), 'text')


def _parts(body):
    """The comma-separated parts of a CREATE TABLE's body, up to its closing parenthesis."""
    parts, depth, start = [], 0, 0
    for at, char in enumerate(body):
        if char == '(': depth += 1
        elif char == ')' and depth == 0: return parts + [body[start:at]]
        elif char == ')': depth -= 1
        elif char == ',' and depth == 0: parts, start = parts + [body[start:at]], at + 1
    return parts


def columns(text, line):
    """{column: kind} of the CREATE TABLE starting on `line` of an SQL text, without the columns the database fills."""
    offset = sum(len(row) for row in text.splitlines(keepends=True)[:max(line - 1, 0)])
    opening = text.find('(', offset)
    if opening < 0: return {}
    found = {}
    for part in _parts(text[opening + 1:]):
        part = ' '.join(part.split())
        if not part or CONSTRAINT.match(part) or MADE.search(part): continue
        found[part.split()[0].strip('"`[]')] = _kind(part)
    return dict(list(found.items())[:LIMIT['fields']])


def _target(report):
    try: return Path(json.loads((Path(report) / 'facts/run.json').read_text(encoding='utf-8'))['target'])
    except (OSError, ValueError, KeyError): return None


def _table_fields(root, location):
    """The columns of a table fact's CREATE TABLE, read from the project when it is there."""
    if root is None or not str(location.get('path', '')).endswith('.sql'): return {}
    path = (root / location['path']).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file(): return {}
    return columns(path.read_text(encoding='utf-8', errors='replace'), location.get('start_line') or 1)


def _named(table):
    last = table.split('.')[-1].strip('"')
    single = last[:-1] if len(last) > 3 and last.endswith('s') and not last.endswith('ss') else last
    return single.replace('_', ' ').title().replace(' ', '')


def _tables_of(rows, root):
    """{table in lower case: {name, table, fields}} of the table facts not dropped since."""
    found = {}
    for row in (r for r in rows if r['kind'] == 'data_table' and not r['value'].get('dropped')):
        table = row['value']['name'].replace('"', '').replace('`', '')
        entity = found.setdefault(table.lower(), {'name': _named(table), 'table': table, 'fields': {}})
        entity['fields'].update(_table_fields(root, row.get('location') or {}))
    return found


def entities(report):
    """[{name, table, fields}]: the project's tables, their columns, and the names its writes send to them."""
    rows = facts(report, 'data_table', 'data_access')
    found = _tables_of(rows, _target(report))
    for row in (r for r in rows if r['kind'] == 'data_access' and r['value'].get('keys')):
        entity = found.get(str(row['value'].get('target')).lower()) or {'fields': {}}
        for key in row['value']['keys']: entity['fields'].setdefault(key, 'text')
    return sorted(found.values(), key=lambda e: e['table'])[:LIMIT['entities']]


def _goals(scenario):
    return [{'goal': f"{persona['id']}.{goal['id']}", 'role': persona.get('role'), 'what': goal.get('goal')}
            for persona in (scenario or {}).get('personas') or [] for goal in persona.get('goals') or []][:LIMIT['goals']]


def _scenario(report):
    return read_json(Path(report) / 'experience/scenario.json')


def brief(report, scenario=None):
    """What the assistant reads: the tables and their fields, the goals of the scenario, the services stubbed or not."""
    known = services(report)
    return {'entities': entities(report), 'goals': _goals(scenario if scenario is not None else _scenario(report)),
            'stubs': [s['service'] for s in known['stubs']], 'not_covered': [s['service'] for s in known['not_covered']]}


def prompt(told):
    """The messages of the one question asked."""
    task = TASK.replace('{schema}', json.dumps(SCHEMA)).replace('{rows}', str(LIMIT['rows'])).replace('{seed}', str(LIMIT['seed']))
    return [{'role': 'system', 'content': task}, {'role': 'user', 'content': json.dumps(told, ensure_ascii=False)}]


def plain(value):
    """The value when it is plain and safe sample data, else None: short, no secret's shape, an e-mail of example.com."""
    if isinstance(value, bool) or (isinstance(value, (int, float)) and abs(value) < 1e12): return value
    if not isinstance(value, str) or len(value) > LIMIT['text'] or SECRET.search(value): return None
    mail = EMAIL.search(value)
    return None if mail and not mail.group(0).lower().endswith('@example.com') else value


def _row(row, fields):
    """The row's known fields with a plain value; None when nothing is left."""
    if not isinstance(row, dict): return None
    kept = {k: plain(v) for k, v in row.items() if k in fields}
    kept = {k: v for k, v in kept.items() if v is not None}
    return kept or None


def _rows(rows, fields, most):
    kept = [_row(row, fields) for row in (rows if isinstance(rows, list) else [])]
    return [row for row in kept if row][:most]


def _tables(answered, known, most):
    """[{table, rows}] of an answer's list, known tables only, each once, with its valid rows."""
    out, seen = [], set()
    for item in answered if isinstance(answered, list) else []:
        entity = known.get(str((item or {}).get('table', '')).lower()) if isinstance(item, dict) else None
        if entity is None or entity['table'] in seen: continue
        rows = _rows(item.get('rows'), entity['fields'], most)
        if rows: out.append({'table': entity['table'], 'rows': rows}); seen.add(entity['table'])
    return out


def _through_ui(answered, goals):
    out = []
    for item in answered if isinstance(answered, list) else []:
        if not isinstance(item, dict) or item.get('goal') not in goals or not isinstance(item.get('values'), dict): continue
        values = {str(k)[:60]: plain(v) for k, v in list(item['values'].items())[:LIMIT['values']]}
        values = {k: v for k, v in values.items() if v is not None}
        if values: out.append({'goal': item['goal'], 'values': values})
    return out


def checked(answer, told):
    """The parts of the assistant's answer that hold: known tables, fields and goals, plain values, bounded rows."""
    answer = answer if isinstance(answer, dict) else {}
    known = {e['table'].lower(): e for e in told['entities']}
    rows = {row['table']: row['rows'] for row in _tables(answer.get('entities'), known, LIMIT['rows'])}
    return {'entities': [{**e, 'rows': rows.get(e['table'], [])} for e in told['entities']],
            'through_ui': _through_ui(answer.get('through_ui'), {g['goal'] for g in told['goals']}),
            'seed': _tables(answer.get('seed'), known, LIMIT['seed'])}


def _sample(field, kind, n):
    """A plain value of a field's kind for the n-th sample row, or None for one the rules cannot make."""
    if kind == 'number': return n * 10
    if kind == 'boolean': return n % 2 == 1
    if kind == 'date': return f'2026-01-{n:02d}'
    if kind != 'text': return None
    return f'user{n}@example.com' if 'mail' in field.lower() else f"{field.replace('_', ' ').capitalize()} {n}"


def _samples(entity):
    """LIMIT['sample'] rows of the fields the rules can fill; none when they fill no field."""
    rows = [{f: _sample(f, kind, n) for f, kind in entity['fields'].items()} for n in range(1, LIMIT['sample'] + 1)]
    rows = [{k: v for k, v in row.items() if v is not None} for row in rows]
    return [row for row in rows if row]


def by_rules(told):
    """The data made without an assistant: a few rows per table from the field types; nothing typed through the UI."""
    made = [{**entity, 'rows': _samples(entity)} for entity in told['entities']]
    return {'entities': made, 'through_ui': [], 'seed': [{'table': e['table'], 'rows': e['rows']} for e in made if e['rows']]}


def plan(report, provider=None, scenario=None):
    """<report>/experience/data.json: the assistant asked once (deep) for the data, its answer checked, the services'
    stubs and what is not covered added by rules; made by rules alone without a provider. Returns the data."""
    told = brief(report, scenario)
    if provider is None: made = by_rules(told)
    else:
        answer, _ = provider.complete(prompt(told), deep=True, stage='experience_data', reads=_target(report))
        made = checked((answer.get('result') or answer) if isinstance(answer, dict) else answer, told)
    known = services(report)
    data = {'version': VERSION, **made, 'stubs': [{'service': s['service'], 'how': s['how']} for s in known['stubs']],
            'not_covered': [{'service': s['service'], 'why': s['why']} for s in known['not_covered']]}
    folder = Path(report) / 'experience'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'data.json').write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    return data

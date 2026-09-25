"""What the owner must protect and where they are going, asked once, with a declared default for every gap.

What must not break, how many users are coming, whether personal data is held: none of it can be read from
the code with certainty. The questions are fixed (eaos/rules/intake-questions.json). The owner answers
them in a JSON file of {id: answer} (`eaos audit --intake FILE`); a question they did not answer takes its
default, marked `default`, with the reason written next to it. Some defaults are read from the project
itself (the critical features, personal data, hosting), each citing where.

The answers become numbered quality scenarios (stimulus, response, measure) that k6, Toxiproxy and the
SLOs are later held to. Every scenario names the question it came from and whether its number was the
owner's answer or a default, so no threshold appears without a source. intake.json keeps the contract
schemas/artifacts/intake.schema.json; engagement.json reads its scenarios from there.
"""
import json
import re
from pathlib import Path

QUESTIONS = Path(__file__).resolve().parent / 'rules/intake-questions.json'
# Fields that identify a person wherever they appear, and fields that do so only on a person entity.
PERSONAL = re.compile(r'\b(e_?mail|phone(?:_?number)?|telefone|celular|mobile|cpf|cnpj|ssn|national_id)\b\s*[?]?\s*[:\s]', re.I)
NAMED = re.compile(r'\b(name|full_?name|first_?name|last_?name|nome)\b\s*[?]?\s*[:\s]', re.I)
PERSON = re.compile(r'user|profile|customer|client|member|employee|driver|operator|person|patient|student|contact', re.I)
END = re.compile(r'^\s*(\);|\}|class\s|create\s|export\s|interface\s|type\s)', re.I)
BLOCK = 60


def questions():
    return json.loads(QUESTIONS.read_text(encoding='utf-8'))['questions']


def _facts(out, kind):
    rows = []
    for path in sorted((Path(out) / 'facts').glob('*.json')):
        try: data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError): continue
        rows += [row for row in data.get('facts') or [] if isinstance(row, dict) and row.get('kind') == kind]
    return rows


def _block(target, location):
    """The lines of one table or model definition, from its first line to its end (at most BLOCK lines)."""
    try: lines = (Path(target) / location['path']).read_text(encoding='utf-8', errors='replace').splitlines()
    except (OSError, KeyError): return []
    start = max(int(location.get('start_line') or 1) - 1, 0)
    block = []
    for number in range(start, min(start + BLOCK, len(lines))):
        if block and END.match(lines[number]): break
        block.append((number + 1, lines[number]))
    return block


def personal_data(target, out):
    """(True, where) if a table or model holds a field that identifies a person, else (False, why not)."""
    seen = set()
    for row in _facts(out, 'data_table') + _facts(out, 'data_model'):
        location, name = row.get('location') or {}, (row.get('value') or {}).get('name') or ''
        if not location.get('path') or (location['path'], location.get('start_line')) in seen: continue
        seen.add((location['path'], location.get('start_line')))
        for number, line in _block(target, location):
            field = PERSONAL.search(line) or (NAMED.search(line) if PERSON.search(name) else None)
            if field:
                return True, f"{location['path']}:{number}: {name} has a {field.group(1)} field"
    return False, f'no email, phone or CPF field, and no name on a person, in {len(seen)} tables and models'


def hosting(target):
    if (Path(target) / 'vercel.json').is_file(): return 'Vercel', 'vercel.json is at the root'
    return 'unknown', 'no vercel.json at the root'


def critical_features(out):
    try: record = json.loads((Path(out) / 'features.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return [], 'features.json is absent'
    names = [feature['name'] for feature in record.get('features') or [] if feature.get('critical')]
    return names, f'{len(names)} of {len(record.get("features") or [])} features are on a critical path in features.json'


def run_command(target):
    """How the project starts, from package.json: preview, then start, then dev; None when it does not say."""
    try: scripts = json.loads((Path(target) / 'package.json').read_text(encoding='utf-8')).get('scripts') or {}
    except (OSError, ValueError): return None
    runner = next((tool for lock, tool in (('bun.lock', 'bun run'), ('bun.lockb', 'bun run'), ('pnpm-lock.yaml', 'pnpm run'),
                                          ('yarn.lock', 'yarn')) if (Path(target) / lock).is_file()), 'npm run')
    script = next((name for name in ('preview', 'start', 'dev') if name in scripts), None)
    return f'{runner} {script}' if script else None


def defaults(target, out):
    """{id: (answer, reason)} for the defaults read from the project; the rest come from the rules file."""
    return {'critical_features': critical_features(out), 'personal_data': personal_data(target, out),
            'hosting': hosting(target)}


def scenarios(rows):
    """Quality scenarios from the answers: every number names its question and whether it was answered."""
    by_id = {row['id']: row for row in rows}
    found = []

    def add(kind, question, stimulus, response, metric, threshold, unit):
        row = by_id[question]
        found.append({'id': f'QS-{len(found) + 1:03d}', 'kind': kind, 'stimulus': stimulus, 'response': response,
                      'measure': {'metric': metric, 'threshold': threshold, 'unit': unit},
                      'source': 'answer' if row['status'] == 'answered' else 'default', 'question_id': question})

    users = by_id['concurrent_users']['answer']
    critical = by_id['critical_features']['answer'] or ['every user-facing route']
    focus = ', '.join(critical[:5]) + (f' and {len(critical) - 5} more' if len(critical) > 5 else '')
    add('load', 'concurrent_users', f'{users} users at the same time use {focus}',
        'every request is answered within the threshold', 'p95_ms', 800, 'ms')
    add('latency', 'concurrent_users', f'{users} users at the same time use {focus}',
        'requests fail at no more than the threshold rate', 'error_rate', 0.01, 'ratio')
    if by_id['personal_data']['answer'] is True:
        add('privacy', 'personal_data', 'a user reads data through the application',
            'no user can read another user\'s personal data', 'personal_records_readable_by_others', 0, 'count')
    add('availability', 'availability_target', 'the service runs for a month',
        'it answers its health check', 'availability', float(by_id['availability_target']['answer']), 'percent')
    return found


def build(target, out, answers=None):
    """The intake record for one project: the owner's answers where given, declared defaults elsewhere."""
    answers = answers or {}
    derived = defaults(target, out)
    rows = []
    for question in questions():
        row = {'id': question['id'], 'question': question['question']}
        if question['id'] in answers:
            row.update(answer=answers[question['id']], status='answered')
        elif question['id'] in derived:
            answer, reason = derived[question['id']]
            row.update(answer=answer, status='default', default_reason=reason)
        else:
            row.update(answer=question['default'], status='default', default_reason=question['default_reason'])
        rows.append(row)
    return {'schema_version': 1, 'questions': rows, 'run_command': run_command(target), 'scenarios': scenarios(rows),
            'unknown_answers': sorted(set(answers) - {q['id'] for q in questions()})}


def read_answers(path):
    """The owner's answers file: a JSON object {question id: answer}."""
    if not path: return {}
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict): raise ValueError(f'{path}: the answers file is a JSON object {{question id: answer}}')
    return data


def write(target, out, answers_path=None):
    record = build(target, out, read_answers(answers_path))
    (Path(out) / 'intake.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return record

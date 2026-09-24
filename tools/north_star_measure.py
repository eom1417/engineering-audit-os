"""Measure the destination indicators from real reports on the pinned corpus.

Each indicator is computed by the definition written for it in docs/north-star.json, from what the
reports actually contain, never from what the code is able to produce. A report is reused only while
both the corpus commit and the tool's own source are unchanged.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINES = ['codegraph', 'enola', 'jscpd', 'reforge']
CORPUS = Path(os.environ.get('EAOS_CORPUS', '/tmp/eaos-corpus'))
REPORTS = Path(os.environ.get('EAOS_MEASURE', '/tmp/eaos-measure'))
# The two sentences the tool writes today for a structural clone and for a decision that changes nothing.
CLONE = 'share the same structure up to identifier names'
STRUCTURAL = ('move', 'split', 'merge', 'extract', 'introduce', 'layer', 'break the cycle', 'delete', 'rebuild')
DISPOSITIONS = {'retain': 'reuse', 'reuse': 'reuse', 'modify': 'restructure', 'restructure': 'restructure',
                'rebuild': 'rebuild', 'delete': 'delete', 'remove': 'delete'}
FOUR_REPORTS = (('CURRENT-STATE.md',), ('TARGET-STATE.md', 'TARGET-ARCHITECTURE.md'),
                ('GAP-AND-STRATEGY.md',), ('EXECUTION-PLAN.md', 'PLAN/WAVES.md'))
INFRASTRUCTURE_FREE = ('npm_script', 'public_api')


def git(*args, cwd=None):
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True)


def fetch(record):
    """Clone every corpus project at its pinned commit. Nothing inside a project is ever run."""
    CORPUS.mkdir(parents=True, exist_ok=True)
    for project in record['corpus']:
        where = CORPUS / project['name']
        if not (where / '.git').is_dir():
            if git('clone', '--quiet', '--no-checkout', project['repo'], str(where)).returncode:
                raise SystemExit(f"could not clone {project['repo']}")
        if not checked_out(where, project['commit']):
            if git('checkout', '--quiet', '--force', project['commit'], cwd=where).returncode:
                git('fetch', '--quiet', '--depth', '1', 'origin', project['commit'], cwd=where)
                if git('checkout', '--quiet', '--force', project['commit'], cwd=where).returncode:
                    raise SystemExit(f"{project['name']}: commit {project['commit']} is not reachable")
        print(f"{project['name']}: {project['commit'][:10]}")


def checked_out(where, commit):
    """At the pinned commit with every tracked file present: a clean HEAD over an empty tree is not a checkout."""
    return (git('rev-parse', 'HEAD', cwd=where).stdout.strip() == commit
            and not git('status', '--porcelain', cwd=where).stdout.strip())


def tool_digest():
    digest = hashlib.sha256()
    for path in sorted((ROOT / 'eaos').rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            digest.update(path.relative_to(ROOT).as_posix().encode()); digest.update(path.read_bytes())
    return digest.hexdigest()


def audit(name, target, commit):
    """Audit one target with the engines on, reusing the last report only if nothing it depends on moved."""
    out = REPORTS / name
    key = {'commit': commit, 'tool': tool_digest(), 'engines': ENGINES}
    stamp = out / '.north-star.json'
    if stamp.is_file():
        previous = json.loads(stamp.read_text())
        if previous.get('key') == key: return out, previous['exit']
    if out.exists(): subprocess.run(['rm', '-rf', str(out)])
    done = subprocess.run([sys.executable, '-m', 'eaos', 'audit', str(target), '--out', str(out), '--skip', 'site',
                           '--engines', *ENGINES], capture_output=True, text=True, cwd=ROOT)
    out.mkdir(parents=True, exist_ok=True)
    stamp.write_text(json.dumps({'key': key, 'exit': done.returncode}))
    return out, done.returncode


def load(out, name, default=None):
    path = out / name
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def facts(out, kind=None):
    rows = []
    for path in sorted((out / 'facts').glob('*.json')):
        data = load(out, 'facts/' + path.name, {})
        rows += [row for row in (data.get('facts') or []) if isinstance(row, dict)]
    return [row for row in rows if kind is None or row.get('kind') == kind]


class Project:
    def __init__(self, spec, out, code):
        self.name, self.truth, self.out, self.exit = spec['name'], spec['truth'], out, code
        self.dossier = load(out, 'dossier.json', {'claims': [], 'coverage': {}})
        self.plan = load(out, 'plan.json', {'tasks': []})
        self.target = load(out, 'target-architecture.json', {})
        self.claim_text = json.dumps(self.dossier.get('claims', []), ensure_ascii=False)

    def surfaces(self):
        rows = [row for row in facts(self.out, 'entry_point')
                if (row.get('value') or {}).get('surface') and (row.get('value') or {}).get('framework') not in INFRASTRUCTURE_FREE
                and not (row.get('value') or {}).get('test_only')]
        return len({(row['value'].get('surface'), row['value'].get('route'), (row.get('location') or {}).get('path')) for row in rows})


def ratio(part, whole):
    return round(part / whole, 3) if whole else None


def mean(values):
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values), 3) if values else None


def pooled(pairs):
    part, whole = sum(p for p, _ in pairs), sum(w for _, w in pairs)
    return ratio(part, whole)


def per(projects, fn):
    return [(project.name, fn(project)) for project in projects]


def text(rows, fmt=lambda v: v):
    return ' · '.join(f'{name} {fmt(value)}' for name, value in rows)


def indicator_values(projects, record):
    """Every automated indicator: (value, evidence) computed from the reports by its written definition."""
    values = {}
    rows = per(projects, lambda p: p.exit)
    values['R1'] = (ratio(sum(code == 0 for _, code in rows), len(rows)), 'exit codes: ' + text(rows))
    rows = per(projects, lambda p: p.surfaces())
    values['R2'] = (ratio(sum(count > 0 for _, count in rows), len(rows)), 'user surfaces found: ' + text(rows))
    rows = per(projects, lambda p: p.dossier.get('coverage', {}).get('parse_coverage'))
    values['U1'] = (mean([value for _, value in rows]), 'parse_coverage: ' + text(rows))
    rows = per(projects, lambda p: (min(p.surfaces(), p.truth['user_surfaces']), p.truth['user_surfaces']))
    values['U2'] = (mean([ratio(a, b) for _, (a, b) in rows]), 'found/true surfaces: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))
    with_db = [p for p in projects if p.truth.get('tables')]
    rows = per(with_db, lambda p: (len(facts(p.out, 'db_table')), p.truth['tables'], len(facts(p.out, 'db_policy')), p.truth['policies']))
    values['U3'] = (ratio(sum(t >= 0.9 * tt and q >= 0.9 * qq for _, (t, tt, q, qq) in rows), len(rows)),
                    'db_table/db_policy facts vs truth: ' + text(rows, lambda v: f'{v[0]}/{v[1]} tables, {v[2]}/{v[3]} policies'))
    rows = per(projects, lambda p: len((load(p.out, 'features.json', {}) or {}).get('features') or []))
    values['U4'] = (ratio(sum(count > 0 for _, count in rows), len(rows)), 'features in features.json: ' + text(rows))

    def answered(project):
        statuses = [answer.get('status') for entry in (load(project.out, 'load-model.json', {}) or {}).get('entry_points', [])
                    for answer in (entry.get('answers') or {}).values()]
        return sum(status == 'answered' for status in statuses), len(statuses)
    rows = per(projects, answered)
    values['U5'] = (mean([ratio(a, b) or 0 for _, (a, b) in rows]), 'answered load questions: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))

    def signal(project):
        claims = project.dossier.get('claims', [])
        return sum(CLONE not in claim.get('statement', '') for claim in claims), len(claims)
    rows = per(projects, signal)
    values['S1'] = (mean([ratio(a, b) for _, (a, b) in rows]), 'claims that are not structural clones: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))

    def mentioned(project, field, kind):
        items = project.truth.get(field) or []
        kinded = json.dumps(facts(project.out, kind), ensure_ascii=False)
        return sum(item in project.claim_text or item in kinded for item in items), len(items)
    rows = [(p.name, mentioned(p, 'leftovers', 'leftover')) for p in projects if p.truth.get('leftovers')]
    values['D2'] = (pooled([v for _, v in rows]), 'leftovers reported: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))
    rows = [(p.name, mentioned(p, 'secrets', 'committed_secret')) for p in projects if p.truth.get('secrets')]
    values['H1'] = (pooled([v for _, v in rows]), 'committed secrets reported: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))
    rows = per([p for p in projects if p.truth.get('policies')], lambda p: (len(facts(p.out, 'db_policy')), p.truth['policies']))
    values['H2'] = (ratio(sum(a >= 0.9 * b for _, (a, b) in rows), len(rows)), 'db_policy facts vs truth: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))

    rows = per(projects, lambda p: len(p.target.get('target_components') or []))
    values['T1'] = (ratio(sum(count > 0 for _, count in rows), len(rows)), 'target_components: ' + text(rows))
    rows = per(projects, lambda p: len(p.target.get('infrastructure') or []))
    values['T2'] = (ratio(sum(count > 0 for _, count in rows), len(rows)), 'infrastructure decisions: ' + text(rows))

    def structural(project):
        decisions = project.target.get('decisions') or []
        return sum(any(word in str(d.get('chosen', '')).lower() for word in STRUCTURAL) for d in decisions), len(decisions)
    rows = per(projects, structural)
    values['T3'] = (pooled([v for _, v in rows]), 'decisions that change structure: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))

    def decided(project):
        components = project.target.get('current_components') or []
        return sum(DISPOSITIONS.get(c.get('relation')) is not None and bool(c.get('reason')) for c in components), len(components)
    rows = per(projects, decided)
    seen = {DISPOSITIONS[c.get('relation')] for p in projects for c in (p.target.get('current_components') or [])
            if c.get('relation') in DISPOSITIONS}
    coverage = mean([ratio(a, b) for _, (a, b) in rows])
    values['T4'] = (round((coverage or 0) * len(seen) / 4, 3),
                    f"components with a disposition and reason: {text(rows, lambda v: f'{v[0]}/{v[1]}')}; dispositions the tool produced: {sorted(seen)} of 4")

    def mapped(project):
        features = (load(project.out, 'features.json', {}) or {}).get('features') or []
        return sum(bool(f.get('target_component')) for f in features), len(features)
    rows = per(projects, mapped)
    values['T5'] = (pooled([v for _, v in rows]) or 0.0, 'features placed in a target component: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))

    def gap_rows(project):
        matrix = project.target.get('gap_matrix') or []
        return sum(bool(row.get('target_component')) for row in matrix), len(matrix)
    rows = per(projects, gap_rows)
    values['G1'] = (pooled([v for _, v in rows]), 'gap rows tied to a target component: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))

    def sustainability(project):
        indicators = (load(project.out, 'sustainability.json', {}) or {}).get('indicators') or {}
        items = indicators.values() if isinstance(indicators, dict) else indicators
        measured = [(item.get('value') if isinstance(item, dict) else item) for item in items]
        return sum(value is not None for value in measured), len(measured)
    rows = per(projects, sustainability)
    values['G2'] = (mean([ratio(a, b) for _, (a, b) in rows]), 'sustainability indicators with a value: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))

    tasks = [task for p in projects for task in p.plan.get('tasks', [])]
    count = len(tasks)
    sized = sum(str(task.get('effort')) not in ('unknown', 'None', '') for task in tasks)
    ready = sum(task.get('kind') == 'remediate' and (task.get('decision') or {}).get('readiness') == 'ready' for task in tasks)
    runnable = sum(bool(task.get('acceptance')) and all('human review' not in str(row.get('command', ''))
                   for row in task.get('acceptance', [])) for task in tasks)

    def proportional(task):
        options = task.get('options') or []
        nothing = any('Do nothing' in (o.get('option_en') or '') or 'لا نفعل' in (o.get('option') or '') for o in options)
        return len(options) >= 2 and nothing and bool(task.get('rollback'))
    values['P1'] = (ratio(sized, count), f'cards with a known effort: {sized}/{count}')
    values['P2'] = (ratio(ready, count), f'ready remediate cards: {ready}/{count}')
    values['P3'] = (ratio(runnable, count), f'cards with a runnable acceptance command: {runnable}/{count}')
    rows = per(projects, lambda p: len([m for m in p.plan.get('milestones') or [] if m.get('goal') and m.get('exit')]))
    values['P4'] = (ratio(sum(n > 0 for _, n in rows), len(rows)), 'milestones with a goal and exit criterion: ' + text(rows))
    values['P5'] = (ratio(sum(proportional(t) for t in tasks), count), f'cards with options, do-nothing and rollback: {sum(proportional(t) for t in tasks)}/{count}')
    rows = per(projects, lambda p: bool(p.plan.get('tasks')) and all(t.get('section') for t in p.plan.get('tasks', [])))
    values['P6'] = (ratio(sum(ok for _, ok in rows), len(rows)), 'every card carries a team section: ' + text(rows))
    rows = per(projects, lambda p: sum(any((p.out / name).exists() for name in names) for names in FOUR_REPORTS))
    values['P7'] = (mean([n / 4 for _, n in rows]), 'of the four reports present: ' + text(rows, lambda v: f'{v}/4'))
    holdout = sum(bool(p.get('holdout')) for p in record['corpus'])
    # Ten real projects, three of them never read during development; without the three, at most 0.7.
    counted = min(len(record['corpus']), 10 if holdout >= 3 else 7)
    values['V4'] = (ratio(counted, 10), f"{len(record['corpus'])} real projects, {holdout} held out")
    return values


def self_truth(record):
    """D1 and S2 on this repository's own history, where every defect is known."""
    truth = record['self_truth']
    where = REPORTS / 'self-truth-tree'
    if not (where / '.git').exists() or git('rev-parse', 'HEAD', cwd=where).stdout.strip() != truth['commit']:
        subprocess.run(['rm', '-rf', str(where)])
        git('worktree', 'prune', cwd=ROOT)
        if git('worktree', 'add', '--detach', '--force', str(where), truth['commit'], cwd=ROOT).returncode:
            raise SystemExit('could not check out self_truth.commit')
    out, _ = audit('self-truth', where, truth['commit'])
    words = ('dead', 'unused', 'unreachable', 'undefined', 'never read', 'duplicate key', 'retired', 'no longer exist')
    findings = [json.dumps(row, ensure_ascii=False) for row in facts(out)
                if any(word in ((row.get('value') or {}).get('message') or '').lower() + str((row.get('value') or {}).get('kind'))
                       for word in words + ('dead_code',))]
    findings += [json.dumps(c, ensure_ascii=False) for c in load(out, 'dossier.json', {}).get('claims', [])
                 if any(word in c.get('statement', '').lower() for word in words)]
    found = [d['text'] for d in truth['defects'] if any(any(m in row for m in d['match']) for row in findings)]
    candidates = set()
    for row in facts(out):
        value = row.get('value') or {}
        if value.get('kind') == 'dead_code':
            message = value.get('message') or ''
            # One candidate is one place: ten functions named `detect` in ten modules are ten candidates.
            qualified = message.split('`')[1] if '`' in message else message.rsplit(' ', 1)[-1].strip()
            symbol = qualified.rsplit('.', 1)[-1].rsplit('/', 1)[-1]
            candidates.add(((row.get('location') or {}).get('path'), symbol))
    dead = sorted({symbol for _, symbol in candidates if symbol in truth['true_dead_symbols']})
    false = [c for c in candidates if c[1] not in truth['true_dead_symbols']]
    return {'D1': (ratio(len(found), len(truth['defects'])), f"{len(found)} of {len(truth['defects'])} known defects found: " + '; '.join(t.split(':')[0] for t in found)),
            'S2': (ratio(len(dead), len(dead) + len(false)),
                   f'{len(dead)} dead of {len(dead) + len(false)} distinct candidates (by path and symbol): ' + ', '.join(dead))}


def measure(record, only=None):
    projects = []
    for spec in record['corpus']:
        target = CORPUS / spec['name']
        if not checked_out(target, spec['commit']):
            raise SystemExit(f"{spec['name']} is not at {spec['commit'][:10]} with a clean tree; run python tools/north_star.py fetch")
        out, code = audit(spec['name'], target, spec['commit'])
        projects.append(Project(spec, out, code))
    values = indicator_values(projects, record)
    if only is None or only in ('D1', 'S2'): values.update(self_truth(record))
    return values

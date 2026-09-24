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
# Artifacts from runs of a project's own code. The audit report is deleted whenever the tool changes;
# these are not, because re-running a project needs the owner's authorization, not a new commit.
RUNTIME = REPORTS / 'runtime'
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
        self.runtime = RUNTIME / self.name

    def artifact(self, contract):
        """A plan artifact, only if it keeps its contract in schemas/artifacts/; otherwise it counts as absent."""
        from contracts import load_valid
        return load_valid(contract, self.out, self.runtime)

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
    # A table counts as read when its row-level security state is known, not merely its name.
    rows = per(with_db, lambda p: (sum('rls_enabled' in (f.get('value') or {}) for f in facts(p.out, 'data_table')), p.truth['tables'],
                                   len(facts(p.out, 'db_policy')), p.truth['policies']))
    values['U3'] = (ratio(sum(t >= 0.9 * tt and q >= 0.9 * qq for _, (t, tt, q, qq) in rows), len(rows)),
                    'data_table facts with RLS state, and db_policy facts, vs truth: ' + text(rows, lambda v: f'{v[0]}/{v[1]} tables, {v[2]}/{v[3]} policies'))
    rows = per(projects, lambda p: len((p.artifact('features') or {}).get('features') or []))
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
    def credentials(project):
        items = project.truth.get('credentials') or []
        found = facts(project.out, 'committed_credential')
        return sum(any(item['path'] in ((f.get('location') or {}).get('path') or '')
                       and (f.get('value') or {}).get('severity') == item['severity'] for f in found) for item in items), len(items)
    rows = [(p.name, credentials(p)) for p in projects if p.truth.get('credentials')]
    values['H1'] = (pooled([v for _, v in rows]), 'committed credentials reported with the right severity: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))
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
        features = (project.artifact('features') or {}).get('features') or []
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
    runnable_card = lambda task: bool(task.get('acceptance')) and all('human review' not in str(row.get('command', ''))
                                                                   for row in task.get('acceptance', []))
    removals = sum(t.get('pattern') == 'remove_dead' and t.get('kind') == 'remediate'
                   and (t.get('decision') or {}).get('readiness') == 'ready' and runnable_card(t) for t in tasks)
    dead = sum((c.get('render') or {}).get('key') in ('dead_code', 'leftover') for p in projects for c in p.dossier.get('claims', []))
    values['D3'] = (ratio(removals, dead) if dead else 0.0, f'ready remove_dead cards: {removals} for {dead} dead-code and leftover claims')
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
    values.update(orchestration_values(projects, record))
    values['R4'] = toolchain_value()
    return values


def applies(project, rule):
    """Whether an adopted adapter applies to a project, read from the project's own files."""
    root = CORPUS / project.name
    files = [p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '.git' not in p.parts]
    if rule == 'all': return True
    if rule == 'js': return any(f.endswith(('.ts', '.tsx', '.js', '.jsx')) for f in files)
    if rule == 'sql': return any(f.endswith('.sql') for f in files)
    if rule == 'ci_or_iac': return any(f.startswith('.github/workflows/') or f.endswith(('Dockerfile', '.tf')) for f in files)
    if rule == 'openapi': return any(f.split('/')[-1].startswith(('openapi.', 'swagger.')) for f in files)
    return False


def orchestration_values(projects, record):
    """Indicators for the stages the workflow blueprint adds: intake, supply chain, adapters, C4, ADR,
    report quality, behavior lock and runtime verification. Each reads one artifact by its contract."""
    values = {}
    adapters = record.get('adopted_adapters') or []

    def adapters_observed(project):
        observed = set(((load(project.out, 'facts/external.json', {}) or {}).get('summary') or {}).get('engines_observed') or [])
        wanted = [a['name'] for a in adapters if applies(project, a['applies'])]
        return sum(name in observed for name in wanted), len(wanted)
    rows = per(projects, adapters_observed)
    values['R3'] = (mean([ratio(a, b) for _, (a, b) in rows]) or 0.0, 'adopted adapters that ran / applicable: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))

    def intake(project):
        questions = (load(project.out, 'intake.json', {}) or {}).get('questions') or []
        return bool(questions) and all(q.get('status') in ('answered', 'default') for q in questions)
    rows = per(projects, intake)
    values['U6'] = (ratio(sum(ok for _, ok in rows), len(rows)), 'intake.json complete: ' + text(rows))

    def supply_chain(project):
        sbom = (load(project.out, 'sbom.cdx.json', {}) or {}).get('components') or []
        observed = ((load(project.out, 'facts/external.json', {}) or {}).get('summary') or {}).get('engines_observed') or []
        return bool(sbom) and 'osv-scanner' in observed
    rows = per(projects, supply_chain)
    values['H3'] = (ratio(sum(ok for _, ok in rows), len(rows)), 'SBOM with components and OSV-Scanner observed: ' + text(rows))

    def c4(project):
        current, target = project.out / 'architecture/current/workspace.dsl', project.out / 'architecture/target/workspace.dsl'
        if not (current.is_file() and target.is_file()): return False
        names = [c.get('name') for c in project.target.get('target_components') or [] if c.get('name')]
        text_ = target.read_text(encoding='utf-8')
        return bool(names) and all(name in text_ for name in names)
    rows = per(projects, c4)
    values['T6'] = (ratio(sum(ok for _, ok in rows), len(rows)), 'current and target C4 models naming every target component: ' + text(rows))

    def adr(project):
        sections = ('Context and Problem Statement', 'Considered Options', 'Decision Outcome')
        files = sorted((project.out / 'adr').glob('ADR-*.md')) if (project.out / 'adr').is_dir() else []
        valid = sum(all(section in f.read_text(encoding='utf-8') for section in sections) for f in files)
        return min(valid, len(project.target.get('decisions') or [])), len(project.target.get('decisions') or [])
    rows = per(projects, adr)
    values['T7'] = (pooled([v for _, v in rows]) or 0.0, 'MADR files for decisions: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))

    def quality(project):
        reports = (load(project.out, 'report-quality.json', {}) or {}).get('reports') or []
        four = {'CURRENT-STATE.md', 'TARGET-STATE.md', 'GAP-AND-STRATEGY.md', 'EXECUTION-PLAN.md'}
        return sum(r.get('name') in four and r.get('vale_errors') == 0 and r.get('markdownlint_errors') == 0 for r in reports)
    rows = per(projects, quality)
    values['P8'] = (mean([n / 4 for _, n in rows]), 'of the four reports passing Vale and markdownlint: ' + text(rows, lambda v: f'{v}/4'))

    def locked(project):
        features = [f.get('name') for f in (project.artifact('features') or {}).get('features') or []]
        specs = (project.artifact('behavior-lock-plan') or {}).get('specs') or []
        covered = {s.get('feature') for s in specs if s.get('path') and (project.out / 'behavior-lock' / s['path']).exists()}
        return sum(name in covered for name in features), len(features)
    rows = per(projects, locked)
    values['E4'] = (pooled([v for _, v in rows]) or 0.0, 'features with a behavior-lock spec: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))

    def passing(project):
        results = (project.artifact('behavior-lock-results') or {}).get('results') or []
        return sum(r.get('status') == 'passed' for r in results), len(results)
    rows = per(projects, passing)
    values['E5'] = (pooled([v for _, v in rows]) or 0.0, 'behavior-lock specs passing on current code: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))
    values.update(runtime_values(projects))
    values.update(plan_values(projects))
    return values


# The handover kit every project should receive, and when each file applies (see adopted_adapters rules).
# A trailing slash is a directory: at least one validated file under it is expected.
KIT = (('handover/.github/workflows/eaos.yml', 'all'), ('handover/.pre-commit-config.yaml', 'all'),
       ('handover/renovate.json', 'all'), ('handover/.dependency-cruiser.cjs', 'js'), ('handover/semgrep/', 'all'),
       ('handover/otel/collector.yaml', 'all'), ('handover/slo/', 'all'), ('handover/readiness/goss.yaml', 'all'),
       ('handover/mkdocs.yml', 'all'), ('nfr/k6/', 'all'), ('nfr/toxiproxy.json', 'all'), ('nfr/zap.yaml', 'all'))
MECHANICAL = ('remove_dead', 'dead_code', 'leftover', 'move_module', 'upgrade_dependency')


def plan_values(projects):
    """Indicators of the assessment stages added with the 15-stage pipeline: M1, S3, P9, K1."""
    values = {}

    def measured_files(project):
        rows = (project.artifact('measurements') or {}).get('files') or []
        complete = sum(all(row.get(field) is not None for field in ('loc', 'complexity_max', 'churn', 'fan_in')) for row in rows)
        # The denominator is what the audit parsed, so a short table cannot score well.
        parsed = (project.dossier.get('coverage') or {}).get('files_parsed') or 0
        return complete, max(parsed, len(rows))
    rows = per(projects, measured_files)
    values['M1'] = (mean([ratio(a, b) or 0 for _, (a, b) in rows]) or 0.0,
                    'source files with size, complexity, churn and fan-in: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))

    def corroborated(project):
        register = project.artifact('debt-register')
        if register is None: return None
        high = [item for item in register['items'] if item['severity'] in ('high', 'critical')]
        ok = sum(any(w['kind'] == 'deterministic' for w in item['witnesses'])
                 or len({w['tool'] for w in item['witnesses']}) >= 2 for item in high)
        return ok, len(high)
    rows = per(projects, corroborated)
    values['S3'] = (mean([0.0 if v is None else (ratio(*v) if v[1] else 1.0) for _, v in rows]) or 0.0,
                    'high and critical debt items with two independent witnesses: '
                    + text(rows, lambda v: 'no register' if v is None else f'{v[0]}/{v[1]}'))

    def codemods(project):
        cards = [t for t in project.plan.get('tasks', []) if t.get('pattern') in MECHANICAL]
        ok = sum(((t.get('codemod') or {}).get('dry_run') or {}).get('exit') == 0
                 and ((t.get('codemod') or {}).get('dry_run') or {}).get('files_changed', 0) > 0 for t in cards)
        return ok, len(cards)
    rows = per(projects, codemods)
    values['P9'] = (pooled([v for _, v in rows]) or 0.0, 'mechanical cards whose codemod ran dry without error: '
                    + text(rows, lambda v: f'{v[0]}/{v[1]}'))

    def kit(project):
        files = (project.artifact('handover-validation') or {}).get('files') or []
        expected = [path for path, rule in KIT if applies(project, rule)]
        def satisfied(path):
            rows_ = [f for f in files if (f['path'].startswith(path) if path.endswith('/') else f['path'] == path)]
            return bool(rows_) and all(f['ok'] for f in rows_)
        return sum(satisfied(path) for path in expected), len(expected)
    rows = per(projects, kit)
    values['K1'] = (mean([ratio(a, b) for _, (a, b) in rows]) or 0.0, 'handover kit files accepted by their own tool: '
                    + text(rows, lambda v: f'{v[0]}/{v[1]}'))
    return values


def runtime_values(projects):
    """Indicators of the execution contract (E6-E11). Their artifacts live under RUNTIME/<project>, written
    only by runs in an isolated environment the owner authorized; a project never run counts as zero."""
    from contracts import contracts, validate
    values = {}

    def load_after(project):
        path = project.runtime / 'behavior-lock/results-after.json'
        try: data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError): return None
        return data if not validate(data, contracts()['behavior-lock-results']) else None

    def load_test(project):
        scenarios = (project.artifact('runtime-performance') or {}).get('scenarios') or []
        return sum(bool(s.get('before')) and bool(s.get('after')) for s in scenarios), len(scenarios)
    rows = per(projects, load_test)
    values['E6'] = (pooled([v for _, v in rows]) or 0.0, 'load scenarios measured before and after: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))

    def parity(project):
        before = {r['path'] for r in (project.artifact('behavior-lock-results') or {}).get('results') or [] if r['status'] == 'passed'}
        after = {r['path'] for r in (load_after(project) or {}).get('results') or [] if r['status'] == 'passed'}
        return len(before & after), len(before)
    rows = per(projects, parity)
    values['E7'] = (pooled([v for _, v in rows]) or 0.0, 'specs passing before that still pass after: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))

    def executed_by_model(project):
        tasks = (project.artifact('execution-log') or {}).get('tasks') or []
        return any(t['tool'] == 'model' and t['status'] == 'VERIFIED_IN_ISOLATED_COPY' and t['acceptance_exit'] == 0 for t in tasks)
    rows = per(projects, executed_by_model)
    values['E1'] = (1.0 if any(ok for _, ok in rows) else 0.0, 'a card executed by a model, verified in an isolated copy, acceptance passing: ' + text(rows))

    def honest(project):
        report = project.artifact('runtime-guarantee')
        if not report or report['status'] != 'COMPARED': return 0, 0
        return sum(row['verdict'] == 'HONEST' for row in report['rows']), len(report['rows'])
    rows = per(projects, honest)
    values['E2'] = (pooled([v for _, v in rows]) or 0.0, 'predicted indicator deltas the change actually produced: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))

    executed = [p for p in projects if load_after(p) is not None]
    def secure(project):
        report = project.artifact('runtime-security')
        return report is not None and report['static']['critical'] == 0 and report['static']['high'] == 0 and report['dast']['high'] == 0
    rows = per(executed, secure)
    values['E8'] = (ratio(sum(ok for _, ok in rows), len(rows)) or 0.0,
                    ('executed projects with no open critical or high finding: ' + text(rows)) if rows else 'no project executed yet')

    def share(contract, key, test):
        def count(project):
            items = (project.artifact(contract) or {}).get(key) or []
            chosen = [item for item in items if test(item) is not None]
            return sum(bool(test(item)) for item in chosen), len(chosen)
        return count
    for indicator, contract, key, test, label in (
            ('E9', 'runtime-resilience', 'experiments', lambda e: e['ok'], 'fault experiments where the application behaved as expected'),
            ('E10', 'runtime-telemetry', 'surfaces', lambda s: s['spans'] > 0 if s['critical'] else None, 'critical surfaces with at least one span'),
            ('E11', 'production-readiness', 'items', lambda i: i['ok'], 'readiness items whose command passed')):
        rows = per(projects, share(contract, key, test))
        values[indicator] = (pooled([v for _, v in rows]) or 0.0, f'{label}: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))
    return values


def toolchain_value():
    """R4: adopted assessment tools present at their pinned version, from `eaos tools doctor --json`."""
    done = subprocess.run([sys.executable, '-m', 'eaos', 'tools', 'doctor', '--json'], capture_output=True, text=True, cwd=ROOT)
    try: tools = json.loads(done.stdout)['tools']
    except (ValueError, KeyError, TypeError): return 0.0, 'eaos tools doctor --json gave no tool list (the command does not exist yet, or failed)'
    from contracts import contracts, validate
    if validate({'tools': tools}, contracts()['tools-doctor']): return 0.0, 'eaos tools doctor --json breaks schemas/artifacts/tools-doctor.schema.json'
    wanted = [t for t in tools if t['role'] in ('read', 'validate') and any(s <= 'S07' for s in t.get('stages', []))]
    missing = [t['name'] for t in wanted if not t['ok']]
    return ratio(len(wanted) - len(missing), len(wanted)) or 0.0, f"{len(wanted) - len(missing)}/{len(wanted)} assessment tools at their pinned version" + (f"; missing: {', '.join(missing)}" if missing else '')
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

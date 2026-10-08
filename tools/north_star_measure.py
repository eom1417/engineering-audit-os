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

sys.path.append(str(Path(__file__).resolve().parent.parent))
from eaos.indicators import Report, facts, load, mean, per, pooled, ratio, text  # noqa: E402
from eaos.indicators import values as shared_values  # noqa: E402
import dev_paths  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ENGINES = ['codegraph', 'enola', 'jscpd', 'reforge', 'syft', 'osv-scanner', 'scc', 'semgrep', 'trivy', 'checkov', 'dependency-cruiser', 'sqlfluff', 'spectral', 'oasdiff', 'gitnexus']
CORPUS = dev_paths.CORPUS
REPORTS = dev_paths.MEASURE
# Artifacts from runs of a project's own code. The audit report is deleted whenever the tool changes;
# these are not, because re-running a project needs the owner's authorization, not a new commit.
RUNTIME = REPORTS / 'runtime'


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
    for project in record.get('live_corpus') or []:
        where = CORPUS / project['name']
        if not (where / '.git').is_dir() and git('clone', '--quiet', '--no-checkout', project['source'], str(where)).returncode:
            raise SystemExit(f"could not clone {project['source']}")
        if not checked_out(where, project['commit']) and git('checkout', '--quiet', '--force', project['commit'], cwd=where).returncode:
            raise SystemExit(f"{project['name']}: commit {project['commit']} is not reachable in {project['source']}")
        print(f"{project['name']} (live): {project['commit'][:10]}")


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


def applies(project, rule):
    """Whether an adopted adapter applies to a corpus project: a Project, or its record from docs/north-star.json."""
    from eaos.indicators import applies as shared
    name = project['name'] if isinstance(project, dict) else project.name
    return shared(project if isinstance(project, Report) else Report(REPORTS / name, root=CORPUS / name, name=name), rule)


class Project(Report):
    """A corpus project's report, with the truth recorded for it and the audit's exit code."""

    def __init__(self, spec, out, code):
        super().__init__(out, runtime=RUNTIME / spec['name'], root=CORPUS / spec['name'], name=spec['name'])
        self.truth, self.exit = spec['truth'], code


def indicator_values(projects, record):
    """Every automated indicator. What needs no truth comes from eaos.indicators (the same computation the
    stage gates use); what compares against the truth recorded for each corpus project is computed here."""
    values = {}
    rows = per(projects, lambda p: p.exit)
    values['R1'] = (ratio(sum(code == 0 for _, code in rows), len(rows)), 'exit codes: ' + text(rows))
    rows = per(projects, lambda p: (min(p.surfaces(), p.truth['user_surfaces']), p.truth['user_surfaces']))
    values['U2'] = (mean([ratio(a, b) for _, (a, b) in rows]), 'found/true surfaces: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))
    with_db = [p for p in projects if p.truth.get('tables')]
    # A table counts as read when its row-level security state is known, not merely its name.
    rows = per(with_db, lambda p: (sum('rls_enabled' in (f.get('value') or {}) for f in facts(p.out, 'data_table')), p.truth['tables'],
                                   len(facts(p.out, 'db_policy')), p.truth['policies']))
    values['U3'] = (ratio(sum(t >= 0.9 * tt and q >= 0.9 * qq for _, (t, tt, q, qq) in rows), len(rows)),
                    'data_table facts with RLS state, and db_policy facts, vs truth: ' + text(rows, lambda v: f'{v[0]}/{v[1]} tables, {v[2]}/{v[3]} policies'))
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

    values.update(shared_values(projects, record.get('adopted_adapters') or []))
    holdout = sum(bool(p.get('holdout')) for p in record['corpus'])
    # Ten real projects, three of them never read during development; without the three, at most 0.7.
    counted = min(len(record['corpus']), 10 if holdout >= 3 else 7)
    values['V4'] = (ratio(counted, 10), f"{len(record['corpus'])} real projects, {holdout} held out")
    values['R4'] = toolchain_value()
    return values


def toolchain_value():
    """R4: adopted assessment tools present at their pinned version, from `eaos tools doctor --json`."""
    done = subprocess.run([sys.executable, '-m', 'eaos', 'tools', 'doctor', '--json'], capture_output=True, text=True, cwd=ROOT)
    try: tools = json.loads(done.stdout)['tools']
    except (ValueError, KeyError, TypeError): return 0.0, 'eaos tools doctor --json gave no tool list (the command does not exist yet, or failed)'
    from eaos.indicators import toolchain
    return toolchain(tools)


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
    # A candidate adjudication refuted, or found to name no symbol, is not something EAOS asserts
    # (facts/deadcode.adjudicate): it neither finds a defect (D1) nor counts as a candidate (S2).
    asserted = lambda row: ((row.get('value') or {}).get('adjudication') or {}).get('verdict') not in ('refuted', 'not_a_symbol')
    findings = [json.dumps(row, ensure_ascii=False) for row in facts(out) if asserted(row)
                if any(word in ((row.get('value') or {}).get('message') or '').lower() + str((row.get('value') or {}).get('kind'))
                       for word in words + ('dead_code',))]
    findings += [json.dumps(c, ensure_ascii=False) for c in load(out, 'dossier.json', {}).get('claims', [])
                 if any(word in c.get('statement', '').lower() for word in words)]
    found = [d['text'] for d in truth['defects'] if any(any(m in row for m in d['match']) for row in findings)]
    candidates = set()
    for row in facts(out):
        value = row.get('value') or {}
        # S2 judges symbols: a module candidate is judged by D1, and a refuted candidate is not asserted.
        # A name only tests read is a review candidate (test_only), not something EAOS asserts is dead.
        if (value.get('kind') == 'dead_code' and asserted(row) and value.get('subject_kind') != 'module'
                and (value.get('adjudication') or {}).get('verdict') != 'test_only'):
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


def card_on_its_file(out):
    """S4 for one report: (cards standing on their own file and evidence, engine cards). A card stands when every fact
    it cites is of its kind and not a wide group finding, an agreement has two engines with a site at the card's place,
    and the card's place leads its paths."""
    from eaos.correlate import is_wide
    by_id = {row['id']: row for row in facts(out, 'engine_finding')}
    paths = {task.get('claim_id'): task.get('paths') or [] for task in load(out, 'plan.json', {}).get('tasks') or []}
    honest = total = 0
    for claim in load(out, 'dossier.json', {}).get('claims') or []:
        params = (claim.get('render') or {}).get('params') or {}
        if (claim.get('render') or {}).get('key') != 'engine_cluster': continue
        total += 1
        cited = [by_id[i] for i in claim.get('fact_ids') or [] if i in by_id]
        local = all(row['value'].get('kind') == params.get('kind') and not is_wide(row) for row in cited)
        at_place = {row['value'].get('engine') for row in cited
                    if params.get('place') in {site.get('path') for site in row['value'].get('sites') or []}
                    | {(row.get('location') or {}).get('path')}}
        agreed = params.get('verdict') != 'corroborated' or len(at_place) >= 2
        shown = paths.get(claim['id'])
        leads = shown is None or not shown or shown[0] == params.get('place')
        honest += bool(cited) and local and agreed and leads
    return honest, total


def card_values(projects, record):
    """S4 on the corpus and on EAOS's own history (the self-truth report)."""
    rows = per(projects, lambda p: card_on_its_file(p.out))
    self_out = REPORTS / 'self-truth'
    if (self_out / 'dossier.json').is_file(): rows.append(('eaos', card_on_its_file(self_out)))
    return {'S4': (pooled([v for _, v in rows]), 'engine cards on their own file and evidence: ' + text(rows, lambda v: f'{v[0]}/{v[1]}'))}


USABILITY = ('X1', 'X2', 'X3', 'X4', 'X5', 'X6', 'X8', 'X9', 'X10', 'X11', 'X12', 'X13', 'B1', 'B2', 'B3', 'B4', 'L1', 'L2', 'L3', 'L4', 'L5', 'L6')


STUDIO = ('F8', 'W2')


def measure(record, only=None):
    if only in USABILITY: return usability_values(only)   # read from this checkout, not from the corpus
    if only in STUDIO: return studio_values(only)
    projects = []
    for spec in record['corpus']:
        target = CORPUS / spec['name']
        if not checked_out(target, spec['commit']):
            raise SystemExit(f"{spec['name']} is not at {spec['commit'][:10]} with a clean tree; run python tools/north_star.py fetch")
        out, code = audit(spec['name'], target, spec['commit'])
        projects.append(Project(spec, out, code))
    values = indicator_values(projects, record)
    if only is None or only in ('D1', 'S2', 'S4'): values.update(self_truth(record))
    values.update(card_values(projects, record))
    values.update(live_values(record))
    values.update(usability_values(only))
    values.update(studio_values(only))
    return values


def studio_values(only=None):
    """F8 from the Studio's screen gates (studio/scripts/gates.mjs -> $EAOS_MEASURE/studio-gates/gates.json), counted
    only when they ran in full on the build shipped in this checkout; W2 from the adoption records (docs/adoption)."""
    values = {}
    shipped = ROOT / 'eaos/data/studio/SOURCE.json'
    if only in (None, 'F8'):
        gates = REPORTS / 'studio-gates/gates.json'
        run = json.loads(gates.read_text(encoding='utf-8')) if gates.is_file() else None
        built = json.loads(shipped.read_text(encoding='utf-8'))['source_sha256'] if shipped.is_file() else None
        if not run:
            values['F8'] = (None, 'no gate run yet: npm run build && node scripts/gates.mjs in studio/')
        elif not run.get('complete') or run.get('studio_source_sha256') != built:
            values['F8'] = (None, 'the last gate run is not of the shipped build, or not complete: run node scripts/gates.mjs again')
        else:
            rows = run['results']
            widths = sorted({v['width'] for v in run['viewports'].values()})
            variants = sorted({(r['lang'], r['theme']) for r in rows})
            failed = sorted({r['shot'] for r in rows if not r['pass']})
            values['F8'] = (ratio(len(rows) - len(failed), len(rows)) if rows else None,
                            f"Studio shots passing every gate (overflow, initial scroll, axe, 44px targets, Arabic tracking, offline, script errors) "
                            f"at {'/'.join(map(str, widths))} in {', '.join('-'.join(v) for v in variants)}: {len(rows) - len(failed)}/{len(rows)} "
                            f"({len({r['route'] for r in rows})} views of {run['data']['project']})" + (f"; failing: {', '.join(failed[:5])}" if failed else ''))
    if only in (None, 'W2'):
        values['W2'] = adoption_value()
    return values


def adoption_value():
    """The Studio's packages pinned by an adoption record with candidates, a decision and pins, committed no later than
    the Studio's first code (docs/adoption/README.md)."""
    import re
    package = json.loads((ROOT / 'studio/package.json').read_text(encoding='utf-8')) if (ROOT / 'studio/package.json').is_file() else {}
    wanted = {**package.get('dependencies', {}), **package.get('devDependencies', {})}
    if not wanted:
        return None, 'the Studio has no packages yet'
    first_code = git('log', '--reverse', '--format=%H', '--', 'studio/src', cwd=ROOT).stdout.split()
    covered = set()
    for path in sorted((ROOT / 'docs/adoption').glob('*.md')):
        if path.name == 'README.md': continue
        added = git('log', '--diff-filter=A', '--format=%H', '--', path.relative_to(ROOT).as_posix(), cwd=ROOT).stdout.split()
        if not added: continue  # not committed: it cannot show it came first
        if first_code and subprocess.run(['git', 'merge-base', '--is-ancestor', added[-1], first_code[0]], cwd=ROOT).returncode != 0: continue
        for section in path.read_text(encoding='utf-8').split('\n## ')[1:]:
            if not all(part in section for part in ('**Candidates**', '**Decision**', '**Pinned**')): continue
            pinned = section.split('**Pinned**', 1)[1]
            for name, version in re.findall(r'`(@?[\w./-]+)@(\d+\.\d+\.\d+)`', pinned):
                if wanted.get(name) == version: covered.add(name)
    missing = sorted(set(wanted) - covered)
    return (ratio(len(covered), len(wanted)), f'Studio packages pinned by an adoption record written before the code: {len(covered)}/{len(wanted)}'
            + (f"; without a record: {', '.join(missing)}" if missing else ''))


def usability_values(only=None):
    """X1-X3 from the trials from nothing (tools/ux_trial.py -> $EAOS_MEASURE/ux/<project>/trial.json), X4 and X5
    from the guided commands and the error catalog on this checkout (docs/USER-EXPERIENCE.md)."""
    from eaos import guided
    values = {}
    trials = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((REPORTS / 'ux').glob('*/trial.json'))]
    names = ', '.join(t['project'] for t in trials) or 'no trial run yet'
    for key, test, label in (
            ('X1', lambda t: t['manual_files'] == 0 and t['applied'], 'trials that reached an applied fix with no file written by hand'),
            ('X2', lambda t: t['finished'] and len(t['questions']) <= 3 and all(q['kind'] in ('yes_no', 'choice') for q in t['questions']),
             'trials finished with at most 3 yes/no or choice questions'),
            ('X3', lambda t: t['minutes_to_first_report'] is not None and t['minutes_to_first_report'] <= 30,
             'trials that reached the first report within 30 minutes')):
        if only in (None, key):
            ok = [t['project'] for t in trials if test(t)]
            values[key] = (ratio(len(ok), len(trials)) if trials else None,
                           f'{label}: {len(ok)}/{len(trials)} ({names})')
    if only in (None, 'X4'):
        sys.path.insert(0, str(ROOT / 'tests'))
        from test_guided import commands_ending_with_box
        ended = commands_ending_with_box()
        values['X4'] = (ratio(len(ended), len(guided.USER_COMMANDS)) or 0.0,
                        f"user commands ending with the next-step box: {len(ended)}/{len(guided.USER_COMMANDS)}"
                        + (f"; missing: {', '.join(sorted(set(guided.USER_COMMANDS) - ended))}" if set(guided.USER_COMMANDS) - ended else ''))
    if only in (None, 'X6'):
        sys.path.insert(0, str(ROOT / 'tests'))
        from test_intents import accuracy
        rows = accuracy()
        right, total = sum(r for r, _ in rows.values()), sum(t for _, t in rows.values())
        values['X6'] = (ratio(right, total) or 0.0, 'plain requests the intent table maps to the right command: '
                        + ', '.join(f'{name} {r}/{t}' for name, (r, t) in rows.items()) + f' ({right}/{total})')
    if only in (None, 'X8'):
        import asyncio
        from eaos.mcp_server import CAPABILITIES, build
        registered = {tool.name for tool in asyncio.run(build().list_tools())}
        exercised = (ROOT / 'tests/test_mcp.py').read_text(encoding='utf-8')
        ok = [c for c, tool in CAPABILITIES.items() if tool in registered and f"'{tool}'" in exercised]
        missing = sorted(set(CAPABILITIES) - set(ok))
        values['X8'] = (ratio(len(ok), len(CAPABILITIES)) or 0.0, f'capabilities of the guided way with a tested MCP tool: {len(ok)}/{len(CAPABILITIES)}'
                        + (f"; missing: {', '.join(missing)}" if missing else ''))
    if only in (None, 'X9'):
        runs = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((REPORTS / 'mcp').glob('*/trial.json'))]
        ok = [t['project'] for t in runs if t['delivered'] and t['person_turns'] <= 2 and t['manual_files'] == 0]
        values['X9'] = (ratio(len(ok), len(runs)) if runs else None,
                        f"trials an assistant drove from a plain request to a delivered branch, with at most one agreement: {len(ok)}/{len(runs)} "
                        f"({', '.join(t['project'] for t in runs) or 'no trial run yet'})")
    for key, who, shown in (('X11', 'claude', 'as an arrow-key choice in Claude Code after /eaos alone'),
                            ('X12', 'codex', 'as a numbered list in Codex after $eaos alone')):
        if only in (None, key):
            tries = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((REPORTS / 'menu').glob('*/trial.json'))]
            ok = [t['project'] for t in tries if all((t.get(who) or {}).get(k) for k in
                                                     ('shown', 'as_choice', 'labels_in_order', 'recommended_first', 'menu_called', 'did_it'))]
            values[key] = (ratio(len(ok), len(tries)) if tries else None,
                           f"menu trials where the first page of menu() showed {shown}, every label in order and the recommended one "
                           f"first, and the option chosen by its number reached its tools: {len(ok)}/{len(tries)} "
                           f"({', '.join(t['project'] for t in tries) or 'no trial run yet'})")
    if only in (None, 'X10'):
        from eaos.human_report import readability_problems
        pages = sorted(p for p in REPORTS.glob('*/human/index.html') if p.parent.parent.name not in ('runtime', 'ux', 'mcp'))
        clean = [p.parent.parent.name for p in pages if not readability_problems(p.read_text(encoding='utf-8'))]
        values['X10'] = (ratio(len(clean), len(pages)) if pages else None,
                         f"reports for people with the four reports, a severity legend and no number without its meaning: {len(clean)}/{len(pages)} "
                         f"({', '.join(p.parent.parent.name for p in pages) or 'no report yet'})")
    if only in (None, 'X13'): values['X13'] = field_report_value()
    values.update(blueprint_values(only))
    values.update(continuity_values(only))
    if only in (None, 'X5'):
        done, total = guided.complete_entries()
        values['X5'] = (ratio(done, total) or 0.0, f'known errors with a plain message, a fix and a command in Arabic and English: {done}/{total}')
    return values


def field_report_value():
    """X13: the scenarios of the field report (2026-10-07) that work now, from the locked acceptance/test_field_report.py
    run on this checkout: each test is one scenario."""
    import importlib.util
    import unittest
    # Loaded from its file: on this script's path, `acceptance` is tools/acceptance.py, not the folder of locked tests.
    spec = importlib.util.spec_from_file_location('field_report_acceptance', ROOT / 'acceptance/test_field_report.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    flat = lambda s: [t for item in s for t in (flat(item) if isinstance(item, unittest.TestSuite) else [item])]
    names = [test.id().rsplit('.', 1)[-1] for test in flat(suite)]
    with open(os.devnull, 'w') as quiet:
        result = unittest.TextTestRunner(stream=quiet, verbosity=0).run(suite)
    broken = {test.id().rsplit('.', 1)[-1] for test, _ in result.failures + result.errors}
    ok = [name for name in names if name not in broken]
    return (ratio(len(ok), len(names)) if names else None,
            f'field-report scenarios that work: {len(ok)}/{len(names)}' + (f"; failing: {', '.join(sorted(broken))}" if broken else ''))


def blueprint_values(only=None):
    """B1-B4, building from a plan (docs/BUILD-FROM-PLAN.md): the plan fixtures read in every format, the fixture
    specs laid out whole, and the build trials ($EAOS_MEASURE/build/<project>/trial.json) audited clean."""
    from eaos import blueprint
    values, plans = {}, ROOT / 'tests/fixtures/plans'
    if only in (None, 'B1'):
        files = sorted(plans.glob('clinic.*'))
        files = [f for f in files if f.suffix in blueprint.SOURCE_SUFFIXES and not f.name.endswith('.spec.json')]
        read = [f.suffix for f in files if 'Staff register patients and book their visits' in ' '.join(blueprint.read_source(f).split())]
        values['B1'] = (ratio(len(read), len(files)) if files else None, f"plan formats read to their text: {len(read)}/{len(files)} ({', '.join(read)})")
    if only in (None, 'B2'):
        checks, passed = 0, 0
        for path in sorted(plans.glob('*.spec.json')):
            spec = json.loads(path.read_text(encoding='utf-8'))
            stack = blueprint.choose_stack(spec)
            built = blueprint.design(spec, stack)
            cards = built['plan']['tasks']
            order = {m['id']: index for index, m in enumerate(built['plan']['milestones'])}
            by_id = {c['id']: c for c in cards}
            rows = [any(c.get('feature') == f['id'] and c['acceptance'] and c['tests'] for c in cards) for f in spec['features']]
            rows += [sum(e['module'] == m['id'] for m in spec['modules']) == 1 for e in spec.get('entities') or []]
            rows += [concern in built['policy']['vendors'] for concern in blueprint.ISOLATED if stack[concern]['id'] != 'none']
            rows += [all(order[by_id[d]['milestone']] <= order[c['milestone']] for d in c['depends_on']) for c in cards]
            checks, passed = checks + len(rows), passed + sum(rows)
        values['B2'] = (ratio(passed, checks) if checks else None, f'blueprint checks held (every feature a card with acceptance and tests, '
                        f'every entity one owner, every vendor one home, every card after what it needs): {passed}/{checks}')
    runs = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((REPORTS / 'build').glob('*/trial.json'))]
    names = ', '.join(t['project'] for t in runs) or 'no trial run yet'
    if only in (None, 'B3'):
        clean = [t['project'] for t in runs if t['delivered'] and t.get('final_audit') and
                 not any(t['final_audit'][key] for key in ('cycles', 'policy_violations', 'copies', 'dead_code', 'broken'))]
        values['B3'] = (ratio(len(clean), len(runs)) if runs else None,
                        f'projects built from a plan that their own audit finds clean (no cycle, layer break, copy, dead code, broken reference): {len(clean)}/{len(runs)} ({names})')
    if only in (None, 'B4'):
        built = sum(len(t['features_built']) for t in runs)
        total = sum(len(t['features']) for t in runs)
        values['B4'] = (ratio(built, total) if total else None, f'features of the plans built through their gates, with tests: {built}/{total} ({names})')
    return values


PARTS = ('cards', 'arch-map', 'arch-drill', 'flows', 'system-map', 'target-map', 'target-mapping', 'progress-history', 'work-log', 'stamp')


def continuity_values(only=None):
    """L1-L3 from the handover trials (tools/handover_trial.py -> $EAOS_MEASURE/handover/<project>/trial.json), L4 from
    the reports for people: every part a person asked for (the cards, the maps, the target, the progress) is there."""
    values = {}
    runs = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((REPORTS / 'handover').glob('*/trial.json'))]
    names = ', '.join(t['project'] for t in runs) or 'no trial run yet'
    for key, test, label in (
            ('L1', lambda t: t['progress_true'], "trials whose ledger counts exactly the cards merged into the person's branch, out of the plan's"),
            ('L2', lambda t: t['merged'] and t['branch_deleted'] and t['report_updated'], 'trials where merging deleted the branch and rebuilt the report in the same step'),
            ('L3', lambda t: t['cut'] and t['claude_first_tool'] == 'status' and not t['asked_again'] and not t['redone'] and t['delivered'],
             'trials where Claude Code finished the batch Codex was cut off in: status first, no question asked again, no card redone')):
        if only in (None, key):
            ok = [t['project'] for t in runs if test(t)]
            values[key] = (ratio(len(ok), len(runs)) if runs else None, f'{label}: {len(ok)}/{len(runs)} ({names})')
    if only in (None, 'L5'):
        tries = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((REPORTS / 'branch').glob('*/trial.json'))]
        ok = [t['project'] for t in tries if all(t[k] for k in ('asked_branch', 'checked_on_branch', 'merged_into_branch', 'main_untouched',
                                                                  'checkout_untouched', 'report_names_branch'))]
        values['L5'] = (ratio(len(ok), len(tries)) if tries else None,
                        f"trials on a project open on main with its work on a branch ahead: asked which branch, checked it, merged into it, "
                        f"main and the checkout untouched, the report names it: {len(ok)}/{len(tries)} ({', '.join(t['project'] for t in tries) or 'no trial run yet'})")
    if only in (None, 'L6'):
        stamps = sorted([*(REPORTS / 'handover').glob('*/EAOS/*/.report.json'), *(REPORTS / 'branch').glob('*/EAOS/*/.report.json')])
        good = []
        for path in stamps:
            made, trial = json.loads(path.read_text(encoding='utf-8')), path.parents[2] / 'trial.json'
            merged = json.loads(trial.read_text(encoding='utf-8')).get('merged_at') if trial.is_file() else None
            if made.get('digest') and made.get('version') and not made.get('errors') and (not merged or made.get('built', '') >= merged):
                good.append(path.parts[-4])
        values['L6'] = (ratio(len(good), len(stamps)) if stamps else None,
                        f"reports of the assistant trials stamped with the EAOS that made them, with no part that failed, built after the last merge: "
                        f"{len(good)}/{len(stamps)} ({', '.join(p.parts[-4] for p in stamps) or 'no trial run yet'})")
    if only in (None, 'L4'):
        pages = sorted(p for p in REPORTS.glob('*/human/index.html') if p.parent.parent.name not in ('runtime', 'ux', 'mcp'))
        pages += sorted((REPORTS / 'handover').glob('*/EAOS/*/REPORT.html'))
        whole = [p for p in pages if all(f'data-part="{part}"' in p.read_text(encoding='utf-8') for part in PARTS)]
        values['L4'] = (ratio(len(whole), len(pages)) if pages else None,
                        f"reports for people with every card, the current map, its drill-down and flows, the target and its mapping, and the progress over time: "
                        f"{len(whole)}/{len(pages)} ({', '.join(p.relative_to(REPORTS).parts[0] if p.name == 'index.html' else p.parts[-4] for p in pages) or 'no report yet'})")
    return values


def live_values(record):
    """E1, E2, E5-E11 over the live corpus: projects whose owner authorised running them. The public corpus
    above is audited, never run: its owners gave no such authorisation."""
    from eaos.indicators import execution_values
    live = []
    for spec in record.get('live_corpus') or []:
        target = CORPUS / spec['name']
        if not checked_out(target, spec['commit']):
            raise SystemExit(f"{spec['name']} is not at {spec['commit'][:10]} with a clean tree; run python tools/north_star.py fetch")
        out, _ = audit(spec['name'], target, spec['commit'])
        live.append(Report(out, runtime=RUNTIME / spec['name'], root=target, name=spec['name']))
    return execution_values(live) if live else {}

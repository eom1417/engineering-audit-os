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

ROOT = Path(__file__).resolve().parent.parent
ENGINES = ['codegraph', 'enola', 'jscpd', 'reforge', 'syft', 'osv-scanner', 'scc', 'semgrep', 'trivy', 'checkov', 'dependency-cruiser', 'sqlfluff', 'spectral', 'oasdiff', 'gitnexus']
CORPUS = Path(os.environ.get('EAOS_CORPUS', '/workspace/eaos-corpus'))
REPORTS = Path(os.environ.get('EAOS_MEASURE', '/workspace/eaos-measure'))
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


USABILITY = ('X1', 'X2', 'X3', 'X4', 'X5', 'X6', 'X8', 'X9')


def measure(record, only=None):
    if only in USABILITY: return usability_values(only)   # read from this checkout, not from the corpus
    projects = []
    for spec in record['corpus']:
        target = CORPUS / spec['name']
        if not checked_out(target, spec['commit']):
            raise SystemExit(f"{spec['name']} is not at {spec['commit'][:10]} with a clean tree; run python tools/north_star.py fetch")
        out, code = audit(spec['name'], target, spec['commit'])
        projects.append(Project(spec, out, code))
    values = indicator_values(projects, record)
    if only is None or only in ('D1', 'S2'): values.update(self_truth(record))
    values.update(live_values(record))
    values.update(usability_values(only))
    return values


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
    if only in (None, 'X5'):
        done, total = guided.complete_entries()
        values['X5'] = (ratio(done, total) or 0.0, f'known errors with a plain message, a fix and a command in Arabic and English: {done}/{total}')
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

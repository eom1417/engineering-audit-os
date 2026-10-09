"""F11-F14: the exit gate of the "Studio first" phase (NS46, docs/STUDIO.md D7), measured from what was run.

    F11  routes      the routes of docs/studio-routes.json shot by the last screen-gate runs of the shipped build, every
                     shot passing, and every data section the route reads either written or explained in coverage.json
    F12  coverage    rows of studio/coverage.json measured (or measured empty), over the corpus reports; the rest is the
                     count of "not measured yet" states, which may only fall
    F13  projects    the projects of docs/studio-routes.json on which a complete run of the shipped build shot every
                     route and passed every gate
    F14  budgets     Lighthouse mobile on every page it ran on, the 5,000-card filter and Home's time to interactive,
                     each against STUDIO-COMPLETE's budget
    F15  command     the real trials of the command centre (tools/studio_trial.py -> $EAOS_MEASURE/studio/<project>/
                     trial.json) that went from the check to an accepted branch from the Studio alone, by a real assistant,
                     every state understood; none counts until FleetManageWeb has one; with the live owner-control,
                     branch-control (NS46.T18) and scan-freshness (NS46.T19) trials

A screen-gate run is a gates.json under $EAOS_MEASURE/studio-gates (tools/studio_gates.py --studio, or the removed
studio/scripts/gates.mjs for older runs); it counts only when it is complete and of the build shipped in this checkout
(eaos/data/studio/SOURCE.json). Both layouts of gates.json are read: `results` with `route` and `pass`, and `rows`
with `page` and `failures`.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / 'docs/studio-routes.json'
SHIPPED = ROOT / 'eaos/data/studio/SOURCE.json'
COUNTED = ('measured', 'empty')


def registry():
    return json.loads(REGISTRY.read_text(encoding='utf-8'))


def _load(path):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


def shipped():
    data = _load(SHIPPED) or {}
    return data.get('source_sha256')


def runs(reports):
    """Every gate run under reports/studio-gates, normalised: {file, project, current, rows: [(page, passed)], lighthouse,
    folder}. `current` is true only for a complete run of the shipped build."""
    built, out = shipped(), []
    for path in sorted((Path(reports) / 'studio-gates').rglob('gates.json')):
        run = _load(path)
        if not isinstance(run, dict): continue
        studio = run.get('studio') if isinstance(run.get('studio'), dict) else {}
        data = studio.get('data') or run.get('data') or {}
        complete = studio.get('complete', run.get('complete'))
        source = studio.get('source_sha256', run.get('studio_source_sha256'))
        if 'rows' in run:
            rows = [(row.get('page'), not row.get('failures') and row.get('status', 'observed') == 'observed') for row in run['rows']]
        else:
            rows = [(row.get('route'), bool(row.get('pass'))) for row in run.get('results') or []]
        project = str(data.get('project') or '')
        folder = Path(data['folder']) if data.get('folder') else Path(reports) / project / 'studio'
        out.append({'file': path, 'project': project, 'current': bool(complete) and bool(built) and source == built,
                    'rows': rows, 'lighthouse': run.get('lighthouse') or {}, 'folder': folder})
    return out


def explained(folder):
    """{section: why} for every section the run's data folder writes or explains: the manifest's sections, and the
    coverage rows that carry a reason, a detail and a step (or say it was measured)."""
    manifest = _load(Path(folder) / 'manifest.json') or {}
    out = {entry.get('name'): 'written' for entry in manifest.get('sections') or []}
    for row in (_load(Path(folder) / 'coverage.json') or {}).get('sections') or []:
        if row.get('section') in out: continue
        if row.get('state') in COUNTED or (row.get('detail') and row.get('reason') and row.get('step')):
            out[row['section']] = f"coverage: {row.get('state')}"
    return out


def route_status(reports, routes=None):
    """{route id: (ok, why)} over the current runs: a route holds when at least one current run shot it, every shot of
    it passed, and in each such run every section it needs is written or explained."""
    routes = registry()['routes'] if routes is None else routes
    current = [run for run in runs(reports) if run['current']]
    status = {}
    for route in routes:
        shot = [(run, [ok for page, ok in run['rows'] if page == route['id']]) for run in current]
        shot = [(run, oks) for run, oks in shot if oks]
        if not current: status[route['id']] = (False, 'no complete screen-gate run of the shipped build'); continue
        if not shot: status[route['id']] = (False, 'not shot by any current gate run'); continue
        failed = [run['project'] for run, oks in shot if not all(oks)]
        if failed: status[route['id']] = (False, f"a gate fails on {', '.join(failed)}"); continue
        missing = sorted({need for run, _ in shot for need in route['needs'] if need not in explained(run['folder'])})
        status[route['id']] = (not missing, 'ok' if not missing else f"data neither written nor explained: {', '.join(missing)}")
    return status


def routes_value(reports):
    """F11."""
    routes = registry()['routes']
    status = route_status(reports, routes)
    ok = [route['id'] for route in routes if status[route['id']][0]]
    if not any(run['current'] for run in runs(reports)):
        return None, f'no complete screen-gate run of the shipped build under {Path(reports).name}/studio-gates; 0/{len(routes)} routes shown'
    missing = [f"{route['id']} ({status[route['id']][1]})" for route in routes if not status[route['id']][0]]
    return (round(len(ok) / len(routes), 3), f"Studio routes of C-experience 2.2 shown with real data or a coverage state, every gate passing: "
            f"{len(ok)}/{len(routes)}" + (f"; missing: {', '.join(missing[:8])}" + (' …' if len(missing) > 8 else '') if missing else ''))


def coverage_value(reports, names):
    """F12 over the reports of the named projects: rows measured ÷ rows. A report with no coverage.json counts as
    nothing measured, over the sections the coverage contract plans."""
    import sys
    sys.path.insert(0, str(ROOT))
    from eaos.studio.coverage import PLANNED
    counted = total = 0
    seen, absent, waiting = [], [], []
    for name in names:
        data = _load(Path(reports) / name / 'studio/coverage.json')
        if not data:
            absent.append(name)
            total += len(PLANNED)
            continue
        rows = data.get('sections') or []
        good = [row for row in rows if row.get('state') in COUNTED]
        counted, total = counted + len(good), total + len(rows)
        seen.append(f'{name} {len(good)}/{len(rows)}')
        waiting += [row['section'] for row in rows if row.get('state') not in COUNTED]
    if not seen: return None, 'no report has studio/coverage.json yet: ' + ', '.join(absent)
    common = sorted(set(waiting), key=lambda s: -waiting.count(s))
    return (round(counted / total, 3) if total else None,
            f'Studio sections measured: {counted}/{total}; {total - counted} "not measured yet" states (' + '; '.join(seen)
            + (f"; no coverage.json: {', '.join(absent)}" if absent else '') + ')' + (f"; waiting: {', '.join(common[:8])}" if common else ''))


def projects_value(reports):
    """F13."""
    spec = registry()
    ids = {route['id'] for route in spec['routes']}
    current = [run for run in runs(reports) if run['current']]
    ok, notes = [], []
    for project in spec['projects']:
        mine = [run for run in current if run['project'].lower().startswith(project['match'])]
        good = [run for run in mine if run['rows'] and all(passed for _, passed in run['rows']) and ids <= {page for page, _ in run['rows']}]
        if good: ok.append(project['name'])
        elif not mine: notes.append(f"{project['name']}: no current run")
        else:
            run = mine[-1]
            notes.append(f"{project['name']}: {sum(not passed for _, passed in run['rows'])} failing shots, "
                         f"{len(ids - {page for page, _ in run['rows']})} routes not shot")
    return (round(len(ok) / len(spec['projects']), 3) if current else None,
            f"projects where the shipped Studio passed every gate on every route: {len(ok)}/{len(spec['projects'])}"
            + (f"; {'; '.join(notes)}" if notes else ''))


def budgets_value(reports):
    """F14: each budget met ÷ budgets; a budget never measured is not met."""
    spec = registry()['budgets']
    floors = spec['lighthouse_mobile']
    current = [run for run in runs(reports) if run['current']]
    rows = []
    for run in current:
        for page, result in run['lighthouse'].items():
            scores = (result or {}).get('scores') or {}
            rows.append((f"lighthouse {run['project']}/{page}",
                         all((scores.get(key) or 0) >= floor for key, floor in floors.items()),
                         ' '.join(f"{key} {scores.get(key)}" for key in floors)))
    timing = _load(Path(reports) / 'studio-gates/budgets.json') or {}
    timed = timing if timing.get('studio_source_sha256') == shipped() else {}
    for key in ('filter_5000_ms', 'home_interactive_ms'):
        value = timed.get(key)
        rows.append((key, isinstance(value, (int, float)) and value <= spec[key], f'{value} ms (budget {spec[key]})' if value is not None else 'not measured'))
    if not current and not timed:
        return None, 'no Lighthouse or timing run of the shipped build yet'
    met = [name for name, ok, _ in rows if ok]
    failing = [f'{name}: {why}' for name, ok, why in rows if not ok]
    return (round(len(met) / len(rows), 3), f'Studio budgets met: {len(met)}/{len(rows)}' + (f"; not met: {'; '.join(failing[:6])}" if failing else ''))


def trial_passed(trial):
    """One command-centre trial, as NS46.T11's acceptance judges it: (passed, why not)."""
    checks = [('a real assistant', trial.get('assistant') in ('Claude Code', 'Codex')), ('audited', bool(trial.get('audited'))),
              ('a selection of 2+ cards', len((trial.get('selection') or {}).get('cards') or []) >= 2),
              ('a card fixed', bool(trial.get('cards_fixed'))), ('a question answered in the inbox', (trial.get('questions_answered_in_inbox') or 0) >= 1),
              ('accepted', bool(trial.get('accepted'))), ('nothing typed to the assistant', trial.get('typed_to_assistant') == 0),
              ('every state understood', bool(trial.get('understood')) and all((trial.get('understood') or {}).values()))]
    missing = [name for name, ok in checks if not ok]
    return not missing, ', '.join(missing)


OWNER_CONTROL_CASES = (
    'report_save_queue_reload_restart', 'waiting_custom_exact_text', 'binary_custom_no_consent',
    'authoritative_ids_language_identity', 'refresh_reconciliation_project_isolation',
    'idempotency_concurrent_answers', 'failure_retry_draft_retention', 'auth_origin_csrf',
    'recommendation_separate_selection', 'keyboard_accessibility',
    'scan_explain_plan_fix_queue_controls', 'diff_tests_accept_undo_guards',
)
OWNER_CONTROL_VIEWS = {(viewport, lang, theme) for viewport in ('phone', 'desktop')
                       for lang in ('ar', 'en') for theme in ('light', 'dark')}


def owner_controls_value(reports):
    """NS46.T17: current live proof, never mocked answers or button presence."""
    passed, notes = [], []
    for name in ('EAOS', 'FleetManageWeb'):
        trial = _load(Path(reports) / 'owner-controls' / name / 'trial.json') or {}
        cases = {row.get('id'): row for row in trial.get('cases', []) if isinstance(row, dict)}
        views = {(row.get('viewport'), row.get('lang'), row.get('theme')) for row in trial.get('views', [])
                 if isinstance(row, dict) and row.get('pass') is True and row.get('screenshot')}
        missing = [case for case in OWNER_CONTROL_CASES if not (cases.get(case, {}).get('pass') is True
                   and cases[case].get('evidence') and cases[case].get('kind') == 'live')]
        if trial.get('assistant') not in ('Codex', 'Claude Code') or trial.get('mocked') is not False:
            missing.append('a real assistant, explicitly not mocked')
        if trial.get('studio_source_sha256') != shipped(): missing.append('current shipped digest')
        if not OWNER_CONTROL_VIEWS <= views: missing.append('phone/desktop × ar/en × light/dark screenshots')
        if not trial.get('completed_at'): missing.append('completed timestamp')
        if missing: notes.append(name + ': ' + ', '.join(missing))
        else: passed.append(name)
    return len(passed) / 2, f'live owner controls: {len(passed)}/2' + ('; ' + '; '.join(notes) if notes else '')


def live_trial_value(reports, folder, module):
    """NS46.T18/T19: a live trial judged by its locked acceptance module (acceptance/test_<module>.py): (1.0 or 0.0, why)."""
    import importlib
    import sys
    sys.path.insert(0, str(ROOT / 'acceptance'))
    accepted = importlib.import_module(f'test_{module}')
    missing = accepted.judge(Path(reports) / folder / 'trial.json', accepted.CASES)
    return (0.0 if missing else 1.0), f'{folder}: ' + ('live trial passed' if not missing else f'{len(missing)} requirement(s) missing, first: ' + '; '.join(missing[:3]))


def command_value(reports):
    """F15."""
    trials = [(path.parent.name, _load(path)) for path in sorted((Path(reports) / 'studio').glob('*/trial.json'))]
    trials = [(name, trial) for name, trial in trials if isinstance(trial, dict)]
    if not trials: return None, 'no command-centre trial yet (tools/studio_trial.py)'
    judged = [(name, *trial_passed(trial)) for name, trial in trials]
    ok = [name for name, passed, _ in judged if passed]
    fleet = any(name.lower().startswith('fleetmanageweb') for name in ok)
    notes = [f'{name}: missing {why}' for name, passed, why in judged if not passed]
    control_value, control_notes = owner_controls_value(reports)
    branch_value, branch_notes = live_trial_value(reports, 'branch-control', 'branch_control')
    fresh_value, fresh_notes = live_trial_value(reports, 'scan-freshness', 'scan_freshness')
    control_notes = '; '.join((control_notes, branch_notes, fresh_notes))
    value = min(round(len(ok) / len(trials), 3) if fleet else 0.0, control_value, branch_value, fresh_value)
    return value, (f'command-centre trials from the check to an accepted branch, from the Studio alone: {len(ok)}/{len(trials)}'
                   + ('' if fleet else '; FleetManageWeb has not passed yet') + (f"; {'; '.join(notes)}" if notes else '') + '; ' + control_notes)


def values(reports, record, only=None):
    names = [spec['name'] for spec in record['corpus']] + [spec['name'] for spec in record.get('live_corpus') or []]
    out = {}
    if only in (None, 'F11'): out['F11'] = routes_value(reports)
    if only in (None, 'F12'): out['F12'] = coverage_value(reports, names)
    if only in (None, 'F13'): out['F13'] = projects_value(reports)
    if only in (None, 'F14'): out['F14'] = budgets_value(reports)
    if only in (None, 'F15'): out['F15'] = command_value(reports)
    return out

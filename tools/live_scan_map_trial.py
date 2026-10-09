"""The live scan map trial (owner request 2026-10-09): a real check of a real project, watched in the shipped Studio.

    python tools/live_scan_map_trial.py replay PROGRESS REPORT [--speed 4]
        Write a recorded run-progress.jsonl into REPORT again, line by line at its own pace (sped up), as a new run:
        the Studio serving REPORT follows it as if the check ran now. For the pages' work and their tests; it is never
        evidence for the trial.
    python tools/live_scan_map_trial.py judge --report REPORT --browser BROWSER_JSON [--out TRIAL_JSON]
        Read what the real check wrote (run-progress.jsonl, run-manifest.json) and what the browser saw
        (tools/live_scan_map_trial.mjs) and write the trial file the acceptance reads
        ($EAOS_MEASURE/live-scan-map/trial.json by default).

The check itself is `eaos start` of the project, run by the person's EAOS (no mock), with the Studio's `eaos studio`
serving the same project; the browser half waits for the check to start and takes the early, middle and done moments.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))

CASES = (
    'progress_file_written_by_the_pipeline', 'every_stage_ends_exactly_once', 'folded_state_equals_the_manifest',
    'stages_come_from_the_declaration', 'engines_steps_from_the_tool_registry', 'facts_steps_per_extractor',
    'absent_stages_carry_their_reason', 'studio_followed_the_run_live', 'page_opened_mid_run_shows_the_full_state',
    'glow_and_moving_light_mid_run', 'reduced_motion_stops_all_motion', 'banner_on_other_pages_while_running',
    'record_kept_after_the_run',
)
MOMENTS = ('early', 'middle', 'done')
VIEWS = [(width, lang, theme) for width in (390, 768, 1440) for lang in ('ar', 'en') for theme in ('light', 'dark')]


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def replay(source, report, speed=4.0):
    from eaos.pipeline import progress
    lines = Path(source).read_text(encoding='utf-8').splitlines() if Path(source).is_file() else []
    rows = [json.loads(line) for line in lines if line.strip()] if lines else progress.read(source)
    if not rows: raise SystemExit(f'{source}: no progress rows')
    log = progress.ProgressLog(report)
    times = [datetime.fromisoformat(r['at']) for r in rows]
    for row, at, before in zip(rows, times, [times[0]] + times[:-1]):
        time.sleep(max(0.0, (at - before).total_seconds() / speed))
        fields = {k: v for k, v in row.items() if k not in ('seq', 'at', 'event', 'run')}
        if row['event'] == 'run.started': fields['pid'] = __import__('os').getpid()
        log.emit(row['event'], **fields)
    print(f'replayed {len(rows)} rows as run {log.run}')


def _case(cases, name, ok, evidence):
    cases[name] = {'id': name, 'pass': bool(ok), 'kind': 'live', 'evidence': str(evidence)[:1500]}


def judge(report, browser_json, out):
    from eaos.engines import ADAPTERS
    from eaos.facts.run import ORDER as EXTRACTORS
    from eaos.pipeline import progress
    from eaos.pipeline.stages import ORDER
    import north_star_studio as studio
    report = Path(report)
    rows = progress.read(report)
    manifest = json.loads((report / 'run-manifest.json').read_text(encoding='utf-8'))
    seen = json.loads(Path(browser_json).read_text(encoding='utf-8'))
    state = progress.fold(rows)
    by = {s['name']: s for s in state['stages']}
    cases = {}
    events = [r['event'] for r in rows]
    _case(cases, 'progress_file_written_by_the_pipeline', rows and events[0] == 'run.started' and events[-1] == 'run.ended'
          and [r['seq'] for r in rows] == list(range(1, len(rows) + 1)),
          f'{len(rows)} lines, run {state["run"]}, first {events[:1]}, last {events[-1:]}, status {state["status"]}')
    ends = sorted(r['stage'] for r in rows if r['event'] == 'stage.ended')
    _case(cases, 'every_stage_ends_exactly_once', ends == sorted(ORDER), f'{len(ends)} ends for {len(ORDER)} declared stages')
    differ = [s['name'] for s in state['stages'] if (s['state'], s['reason'], s['seconds'], s['artifacts']) !=
              tuple(manifest['stages'][s['name']][k] for k in ('status', 'reason', 'seconds', 'artifacts'))]
    _case(cases, 'folded_state_equals_the_manifest', not differ and state['status'] == manifest['status'] and state['counts'] == manifest['counts'],
          f'differ: {differ}; status {state["status"]} = {manifest["status"]}; counts {state["counts"]}')
    _case(cases, 'stages_come_from_the_declaration', [s['name'] for s in rows[0]['stages']] == list(ORDER),
          f'run.started lists {len(rows[0]["stages"])} stages in the order of eaos/pipeline/stages.py')
    engines = by.get('engines', {})
    names = [s['name'] for s in engines.get('steps', [])]
    _case(cases, 'engines_steps_from_the_tool_registry', engines.get('state') == 'ok' and sorted(names) == sorted(ADAPTERS),
          f"{len(names)} steps for {len(ADAPTERS)} registered tools: " + ', '.join(f"{s['name']}={s['status']}" for s in engines.get('steps', [])))
    facts = [s['name'] for s in by.get('facts', {}).get('steps', [])]
    _case(cases, 'facts_steps_per_extractor', facts == list(EXTRACTORS), f'{len(facts)} steps: {", ".join(facts)}')
    absent = [s for s in state['stages'] if s['state'] not in ('ok',)]
    _case(cases, 'absent_stages_carry_their_reason', all(s['reason'].strip() for s in absent),
          '; '.join(f"{s['name']} {s['state']}: {s['reason']}" for s in absent) or 'every stage ran')

    views = seen.get('rows') or []
    at = lambda moment, **kw: [r for r in views if r['moment'] == moment and r['route'] == '/scan' and not r['reduced']
                               and all(r.get(k) == v for k, v in kw.items())]
    early_running = [r for r in at('early') if r['run_state'] == 'running']
    mid_running = [r for r in at('middle') if r['run_state'] == 'running']
    done_rows = at('done')
    _case(cases, 'studio_followed_the_run_live', early_running and mid_running and done_rows and all(r['run_state'] == 'done' for r in done_rows),
          f"early: {len(early_running)} views saw it running; middle: {len(mid_running)}; done: "
          f"{sum(r['run_state'] == 'done' for r in done_rows)}/{len(done_rows)} saw it done; moments {seen.get('moments')}")
    full = [r for r in mid_running if r['ended_on_page'] >= r['ended_in_api'] - 1 and r['ended_in_api'] > 0]
    _case(cases, 'page_opened_mid_run_shows_the_full_state', mid_running and len(full) == len(mid_running),
          '; '.join(f"{r['viewport']}-{r['lang']}-{r['theme']}: page {r['ended_on_page']} ended, api {r['ended_in_api']}" for r in mid_running[:12]))
    lit = [r for r in mid_running if r['glow'] >= 1 and r['flows'] >= 1 and (r.get('light') or {}).get('moved')]
    _case(cases, 'glow_and_moving_light_mid_run', bool(lit),
          f"{len(lit)} mid-run views with the glow and a light that moved: " + '; '.join(f"{r['screenshot']} {r['light']}" for r in lit[:3]))
    reduced = [r for r in views if r['reduced']]
    still = [r for r in reduced if r['flows'] == 0 and r['motion'] == 'reduced' and (r['halo_animation'] in (None, 'none'))]
    _case(cases, 'reduced_motion_stops_all_motion', reduced and len(still) == len(reduced),
          '; '.join(f"{r['screenshot']}: flows {r['flows']}, halo animation {r['halo_animation']}, glow {r['glow']}" for r in reduced))
    banner = [r for r in views if r['route'] != '/scan']
    _case(cases, 'banner_on_other_pages_while_running', banner and all(r.get('banner') for r in banner),
          '; '.join(f"{r['route']} {r['viewport']}: banner {r.get('banner')} {r['screenshot']}" for r in banner))
    _case(cases, 'record_kept_after_the_run', done_rows and all(r['ended_on_page'] == len(ORDER) for r in done_rows),
          f"{len(done_rows)} views after the run show {sorted({r['ended_on_page'] for r in done_rows})} ended stages of {len(ORDER)}")

    view_rows = [{**r, 'pass': bool(r['pass'] and r.get('screenshot') and Path(r['screenshot']).is_file())} for r in views]
    trial = {'kind': 'live', 'mocked': False, 'completed_at': now(), 'studio_source_sha256': studio.shipped(),
             'project': manifest.get('target', '').rsplit('/', 1)[-1], 'run': state['run'], 'status': state['status'],
             'seconds': state['seconds'], 'moments': seen.get('moments'), 'browser_errors': seen.get('errors') or [],
             'cases': [cases[name] for name in CASES], 'views': view_rows}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(trial, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    failed = [c['id'] for c in trial['cases'] if not c['pass']] + [f"view {r['moment']} {r['viewport']} {r['lang']} {r['theme']}" for r in view_rows if not r['pass']]
    print(json.dumps({'trial': str(out), 'cases': len(CASES), 'views': len(view_rows), 'failed': failed}, ensure_ascii=False))
    return 0 if not failed else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    one = sub.add_parser('replay')
    one.add_argument('progress')
    one.add_argument('report')
    one.add_argument('--speed', type=float, default=4.0)
    two = sub.add_parser('judge')
    two.add_argument('--report', required=True)
    two.add_argument('--browser', required=True)
    import north_star_measure as measure
    two.add_argument('--out', default=str(measure.REPORTS / 'live-scan-map' / 'trial.json'))
    args = parser.parse_args(argv)
    if args.command == 'replay': return replay(args.progress, args.report, args.speed) or 0
    return judge(args.report, args.browser, args.out)


if __name__ == '__main__':
    sys.exit(main())

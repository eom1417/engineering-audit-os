"""The live map's real acceptance (PLAN-v2 section 7, phase 5), judged from what real runs left.

    python tools/live_scan_map_acceptance.py kill --base URL --token-file FILE --project DIR --json OUT
        7.4: `eaos start` of DIR (whose Studio serves URL), killed with SIGKILL once `plan` has run 20 s; the Studio is
        read every 0.5 s until it says `interrupted`; then `eaos start` again, which resumes; the stages it kept, as the
        Studio says.
    python tools/live_scan_map_acceptance.py flows RUNTIME --json OUT
        7.5: the steps of the last setup, safety and fix runs in a project's runtime folder.
    python tools/live_scan_map_acceptance.py judge --evidence DIR [--out FILE]
        Every item of section 7 from DIR (the phase's runs, below); writes $EAOS_MEASURE/live-scan-map/acceptance.json
        by default, which acceptance/test_live_scan_map.py RealAcceptance reads.

DIR holds: 71/watch/browser.json (tools/live_scan_map_trial.mjs TRIAL_MODE=watch over the develop check),
71/report (that check's report folder), 71/start.log (`eaos start` of it), 71/start-look/browser.json (the address it
printed, opened), 71/trial.json (the three moments of the same check, judged by tools/live_scan_map_trial.py),
73/watch.json (tools/watch_trial.py), 73/button/browser.json, 74/kill.json and
74/look/browser.json, 75/flows.json (tools/live_scan_map_acceptance.py flows) and 75/look-*/browser.json, and 72/routed.json
when the routed run through the Remote sign-in was made (else 7.2 is pending the owner).
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))

COUNT = re.compile(r'(\d+)\D+(\d+)')
ADDRESS = re.compile(r'https?://\S+#/scan\?token=[A-Za-z0-9_-]+')


def read(path):
    path = Path(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


def check_of(base, token):
    """The check's flow as the Studio at `base` serves it (/api/progress), or {} when it does not answer."""
    request = urllib.request.Request(f'{base}/api/progress', headers={'X-EAOS-Token': token})
    try:
        with urllib.request.urlopen(request, timeout=10) as answer: return json.loads(answer.read())['flows']['check']
    except OSError: return {}


def start(project):
    return subprocess.Popen([sys.executable, '-m', 'eaos', 'start', str(project), '--yes', '--lang', 'ar', '--no-watch'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def wait_running(run, base, token, stage, seconds):
    """Returns once `stage` of the check has run `seconds`, as the Studio says."""
    since = None
    while since is None or time.monotonic() - since < seconds:
        if run.poll() is not None: raise SystemExit('the check ended before the kill')
        state = next((s['state'] for s in check_of(base, token).get('stages', []) if s['name'] == stage), None)
        since = since or (time.monotonic() if state == 'running' else None)
        time.sleep(1)


def wait_stopped(base, token, killed):
    """(state, seconds after the kill) once the Studio says the check stopped; (None, None) after 60 s."""
    while time.monotonic() - killed < 60:
        state = check_of(base, token).get('state')
        if state in ('interrupted', 'stalled'): return state, round(time.monotonic() - killed, 2)
        time.sleep(0.5)
    return None, None


def kill(args):
    """7.4, see the module's docstring."""
    token = Path(args.token_file).read_text(encoding='utf-8').strip()
    run = start(args.project)
    wait_running(run, args.base, token, args.stage, args.after)
    kept_before = [s['name'] for s in check_of(args.base, token)['stages'] if s['state'] == 'ok']
    os.killpg(run.pid, signal.SIGKILL)
    killed = time.monotonic()
    run.wait()
    shown = wait_stopped(args.base, token, killed)
    resumed = start(args.project)
    resumed.wait()
    after = check_of(args.base, token)
    record = {'stage': args.stage, 'after_seconds': args.after, 'ok_at_kill': kept_before,
              'shown': shown[0], 'seconds_to_shown': shown[1], 'restart_exit': resumed.returncode,
              'after': {'run': after.get('run'), 'state': after.get('state'), 'status': after.get('status'),
                        'kept': [s['name'] for s in after.get('stages', []) if s.get('resumed')]}}
    Path(args.json).write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(record, ensure_ascii=False))
    return 0


def _item(checks, **evidence):
    """An item of section 7: it passes when every named check holds; the checks are kept with the evidence."""
    checks = {name: bool(held) for name, held in checks.items()}
    return {'pass': all(checks.values()), 'checks': checks, **evidence}


def overhead(report, seconds):
    """I7 on the real run: the progress file's size, and the bound of tools/progress_trial.py (lines written times
    the measured cost of one, plus one `ps` sample every 2 s times the measured cost of one) against the run's time."""
    from progress_trial import line_cost, sample_cost
    path = Path(report) / 'run-progress.jsonl'
    lines = len(path.read_text(encoding='utf-8').splitlines())
    bound = lines * line_cost() + int(seconds / 2) * sample_cost()
    return {'file_bytes': path.stat().st_size, 'lines': lines, 'bound_seconds': round(bound, 2),
            'bound_share': round(bound / seconds, 4)}


def counted(seen, stage):
    """The counted texts the page showed for a stage: "n/N" on its card or its steps, or its "n of N" steps."""
    row = seen.get(stage) or {}
    texts = [t for t in row.get('card', []) + row.get('counted', []) if re.search(r'\d+/\d+', t)]
    texts += [t for t in row.get('steps_of', []) if (m := COUNT.search(t)) and int(m.group(1)) > 0]
    return texts


def photo_gaps(watch):
    """The seconds between consecutive photos of the watched check."""
    times = [datetime.fromisoformat(p['at'].replace('Z', '+00:00')).timestamp() for p in watch.get('photos', [])]
    return [b - a for a, b in zip(times, times[1:])]


def real_check(evidence):
    """7.1: the watched check of develop."""
    from progress_trial import judge
    watch = read(evidence / '71/watch/browser.json').get('checks', {}).get('watch') or {}
    report = evidence / '71/report'
    manifest = read(report / 'run-manifest.json')
    i2, i7 = judge(report), overhead(report, manifest['seconds'])
    seen = watch.get('seen') or {}
    gaps = photo_gaps(watch)
    shown = {stage: counted(seen, stage)[:3] for stage in ('plan', 'transform', 'engines')}
    programs = (seen.get('engines') or {}).get('programs', [])
    return _item({'complete': manifest['status'] == 'COMPLETE', 'I2': i2['equal'],
                  'I7_file_under_1MB': i7['file_bytes'] < 1_000_000, 'I7_under_2_percent': i7['bound_share'] < 0.02,
                  'I9_nothing_unmatched': not watch.get('unmatched'), 'I9_glows_seen': watch.get('glows', 0) >= 20,
                  'counted_in_plan': shown['plan'], 'counted_in_transform': shown['transform'], 'counted_in_engines': shown['engines'],
                  'program_in_engines': programs, 'light_leaves_facts': 'facts' in watch.get('lights_from', []),
                  'photos_every_30s': len(gaps) >= 9 and max(gaps) <= 45},
                 status=manifest['status'], seconds=manifest['seconds'], I2=i2, I7=i7,
                 I9={k: watch.get(k) for k in ('glows', 'lights', 'lines', 'unmatched')}, counted_shown=shown,
                 programs_in_engines=programs[:10], lights_from=watch.get('lights_from'),
                 photos=len(gaps) + 1, longest_gap_seconds=round(max(gaps, default=0), 1),
                 first_photo=(watch.get('photos') or [{}])[0].get('desk'))


def failing(rows, name):
    return [name(row) for row in rows if not row['pass']]


def visual(evidence):
    """7.6: the gated views of the three moments of the same check (with reduced motion) and the trial's cases."""
    trial = read(evidence / '71/trial.json')
    views, cases, checks = trial.get('views', []), trial.get('cases', []), list((trial.get('front_end') or {}).items())
    failed = {'views': failing(views, lambda v: f"{v['moment']} {v['viewport']} {v['lang']} {v['theme']} {v.get('kind')}"),
              'cases': failing(cases, lambda c: c['id']), 'page_checks': [name for name, check in checks if not check['pass']]}
    return _item({'views_gated': len(views) >= 40, 'cases_and_checks_present': cases and checks, 'nothing_fails': not any(failed.values())},
                 views=len(views), failed=failed)


def performance(evidence):
    """7.7: the page left open for the whole check, measured by Chrome: main thread idle > 95%, heap growth < 20 MB."""
    usages = ((read(evidence / '71/watch/browser.json').get('checks') or {}).get('watch') or {}).get('usages') or []
    if len(usages) < 2: return _item({'measured': False})
    first, last = usages[0], usages[-1]
    wall = (last['at'] - first['at']) / 1000
    idle = 1 - (last['task_seconds'] - first['task_seconds']) / wall
    growth = (last['heap_bytes'] - first['heap_bytes']) / 2 ** 20
    return _item({'ten_minutes_or_more': wall >= 600, 'idle_over_95_percent': idle > 0.95, 'heap_growth_under_20MB': growth < 20},
                 minutes=round(wall / 60, 1), main_thread_idle=round(idle, 4), heap_growth_mb=round(growth, 2), heap_mb=[round(u['heap_bytes'] / 2 ** 20, 1) for u in usages])


def map_page(look):
    return bool(look) and look.get('run_state') in ('running', 'done') and look.get('flow') == 'check' and look.get('journey') == 4


def entries(evidence):
    """7.3: the live map reached from a real Claude Code `audit`, from `eaos start`, and from the Studio's button."""
    mcp = read(evidence / '73/watch.json')
    mcp_look = mcp.get('page')
    said = (evidence / '71/start.log').read_text(encoding='utf-8') if (evidence / '71/start.log').is_file() else ''
    start_look = (read(evidence / '71/start-look/browser.json').get('checks') or {}).get('look')
    pressed = (read(evidence / '73/button/browser.json').get('checks') or {}).get('button') or {}
    printed = [re.sub(r'token=[A-Za-z0-9_-]+', 'token=<redacted>', a) for a in ADDRESS.findall(said)]
    return _item({'audit_answers_watch': mcp.get('watch'), 'watch_studio_answers': (mcp.get('progress') or {}).get('status') == 200,
                  'watch_page_is_the_map': map_page(mcp_look), 'eaos_start_prints_it': printed, 'printed_page_is_the_map': map_page(start_look),
                  'button_opens_the_map': pressed.get('hash', '').startswith('#/scan'), 'button_started_a_check': pressed.get('run_started'),
                  'button_map_is_the_check': pressed.get('flow') == 'check'},
                 mcp={'session': mcp.get('session'), 'watch': mcp.get('watch'), 'page': mcp_look},
                 eaos_start={'printed': printed, 'page': start_look}, button=pressed)


def resume_after_kill(evidence):
    """7.4: interrupted within 30 s of SIGKILL; the restart kept every stage that had ended ok, and the page says so."""
    record = read(evidence / '74/kill.json')
    look = (read(evidence / '74/look/browser.json').get('checks') or {}).get('look') or {}
    after = record.get('after') or {}
    panel = look.get('panel', '')                   # the page in Arabic: "kept as it was from an earlier run"
    return _item({'interrupted': record.get('shown') == 'interrupted', 'within_30s': (record.get('seconds_to_shown') or 99) <= 30,
                  'every_finished_stage_kept': record.get('ok_at_kill') and set(record['ok_at_kill']) <= set(after.get('kept', [])),
                  'resumed_run_complete': after.get('status') == 'COMPLETE', 'page_says_kept': 'أُخذت كما هي' in panel},
                 **{k: record.get(k) for k in ('stage', 'shown', 'seconds_to_shown', 'ok_at_kill')}, after=after,
                 page={k: look.get(k) for k in ('screenshot', 'run_state')})


def later_flows(evidence):
    """7.5: setup, safety and fix run for real on a corpus web app: each screen a step with its picture on the page,
    the fix card by card."""
    flows = read(evidence / '75/flows.json')
    safety = (read(evidence / '75/look-safety/browser.json').get('checks') or {}).get('look') or {}
    fix = (read(evidence / '75/look-fix/browser.json').get('checks') or {}).get('look') or {}
    screens = [s for s in (flows.get('safety') or {}).get('record', []) if s.get('artifact', '').endswith('.png')]
    cards = (flows.get('fix') or {}).get('change', [])
    return _item({'setup_ran': (flows.get('setup') or {}).get('status'), 'screens_are_steps': screens,
                  'screen_pictures_on_the_page': safety.get('shots', 0) >= 1, 'fix_card_by_card': len(cards) >= 2,
                  'fix_map_on_the_page': fix.get('flow') == 'fix'}, flows=flows, safety_page=safety, fix_page=fix)


def flow_steps(runtime):
    """{flow: {status, <stage>: [steps]}} of the last run of each later flow in a runtime folder."""
    from eaos import progress
    out = {}
    for flow in ('setup', 'safety', 'fix'):
        state = progress.fold(progress.read(runtime, flow))
        out[flow] = {'status': state['status'], 'run': state['run'],
                     **{s['name']: [{k: step.get(k) for k in ('name', 'status', 'artifact')} for step in s['steps']]
                        for s in state['stages']}}
    return out


def judge(args):
    evidence = Path(args.evidence)
    routed = read(evidence / '72/routed.json')
    items = {'7.1': real_check(evidence),
             '7.2': routed or {'pass': None, 'pending': 'owner', 'why': 'the shared browser was not signed in to remote.e-m.sa'},
             '7.3': entries(evidence), '7.4': resume_after_kill(evidence), '7.5': later_flows(evidence),
             '7.6': visual(evidence), '7.7': performance(evidence)}
    record = {'kind': 'live', 'mocked': False, 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'items': items}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: v['pass'] for k, v in items.items()}))
    return 0 if all(v['pass'] is not False for v in items.values()) else 1


def main(argv=None):
    import dev_paths
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    one = sub.add_parser('kill')
    one.add_argument('--base', required=True); one.add_argument('--token-file', required=True)
    one.add_argument('--project', required=True); one.add_argument('--json', required=True)
    one.add_argument('--stage', default='plan'); one.add_argument('--after', type=float, default=20.0)
    two = sub.add_parser('judge')
    two.add_argument('--evidence', required=True)
    two.add_argument('--out', default=str(dev_paths.MEASURE / 'live-scan-map' / 'acceptance.json'))
    three = sub.add_parser('flows')
    three.add_argument('runtime'); three.add_argument('--json', required=True)
    args = parser.parse_args(argv)
    if args.command == 'flows':
        Path(args.json).write_text(json.dumps(flow_steps(args.runtime), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        return 0
    return {'kill': kill, 'judge': judge}[args.command](args)


if __name__ == '__main__':
    sys.exit(main())

"""Real-run measures of the progress record (live scan map v2, phase 2): I2, I7 and I8 on real checks.

    python tools/progress_trial.py overhead <project> <workdir> [--json out.json] [--no-engines]
    python tools/progress_trial.py kill <project> <workdir> [--stage engines] [--after 8] [--json out.json]
    python tools/progress_trial.py judge <report>
    python tools/progress_trial.py collect --determinism D.json --determinism-engines E.json --kill K.json \
        --overhead O.json --corpus-report R

overhead (I7, and I2 on the same run): the whole check of <project> twice, each in its own process and fresh report
folder, first with progress on (`on/`), then with EAOS_PROGRESS=off (`off/`). It records each run's wall seconds,
the overhead (on - off) / off, the progress file's size and lines (with the history copy), the counted steps each
stage showed, and whether the folded progress equals run-manifest.json stage by stage (judge). Two runs of one check
also differ by the machine's own noise; so the record also gives a bound that does not depend on it: the lines
written times the measured cost of writing one, plus the `ps` samples times the measured cost of one sample.

kill (I8): starts the check, waits until <stage> has run <after> seconds, kills the check's whole process group
with SIGKILL, reaps it, then reads the report every 0.25 s the way the Studio does (eaos/api/read.py:scan_state) and
records how many seconds after the kill it says `interrupted` (same machine: the process is gone) and when a reader
that cannot see the process (another machine) would say `stalled` (progress.judge with living=None).

judge (I2): the folded progress of a finished report against its run-manifest.json, stage by stage.

collect: the records of one real round (determinism from tools/progress_determinism.py, kill, overhead) joined into
$EAOS_MEASURE/live-scan-map/backend.json, which acceptance/test_live_scan_map.py BackendCoverage reads.

Every run is started from a folder outside the project with PYTHONSAFEPATH=1, so a check of EAOS itself runs this
EAOS, never the checked code.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
if str(ROOT / 'tools') not in sys.path: sys.path.insert(0, str(ROOT / 'tools'))

COMPARED = ('status', 'reason', 'seconds', 'artifacts')


def check_command(project, out, engines=True):
    code = ('from eaos.pipeline import execute\n'
            f'm = execute({str(project)!r}, {str(out)!r}, language="ar", engines={[] if engines else None!r})\n'
            'print(m["status"], m["seconds"])\n')
    return [sys.executable, '-c', code]


def environment(progress_on=True):
    env = {**os.environ, 'PYTHONSAFEPATH': '1'}
    if progress_on: env.pop('EAOS_PROGRESS', None)
    else: env['EAOS_PROGRESS'] = 'off'
    return env


def fresh(folder):
    folder = Path(folder)
    if folder.exists(): subprocess.run(['rm', '-rf', str(folder)], check=True)
    return folder


def judge(report):
    """I2: {'equal': bool, 'differences': [...]} between the folded progress and run-manifest.json."""
    from eaos import progress
    report = Path(report)
    manifest = json.loads((report / 'run-manifest.json').read_text(encoding='utf-8'))
    state = progress.fold(progress.read(report))
    differences = []
    names = [s['name'] for s in state['stages']]
    if sorted(names) != sorted(manifest['stages']): differences.append({'stages': [names, sorted(manifest['stages'])]})
    for row in state['stages']:
        kept = manifest['stages'].get(row['name']) or {}
        got = {'status': row['state'], 'reason': row['reason'], 'seconds': row['seconds'], 'artifacts': row['artifacts']}
        want = {key: kept.get(key) for key in COMPARED}
        if got != want: differences.append({'stage': row['name'], 'fold': got, 'manifest': want})
        if (kept.get('reason_code') or '') != row['reason_code']:
            differences.append({'stage': row['name'], 'reason_code': [row['reason_code'], kept.get('reason_code')]})
    whole = (state['state'], state['status'], state['counts'])
    if whole != ('done', manifest['status'], manifest['counts']):
        differences.append({'run': [list(whole), ['done', manifest['status'], manifest['counts']]]})
    return {'equal': not differences, 'stages': len(names), 'differences': differences}


def counted(report):
    """{stage: [(step, done, total, status)]} of the counted steps the run showed."""
    from eaos import progress
    out = {}
    for stage in progress.fold(progress.read(report))['stages']:
        steps = [[s['name'], s['done'], s['total'], s['status']] for s in stage['steps'] if s.get('kind') == 'count']
        if steps: out[stage['name']] = steps
    return out


def line_cost(samples=2000):
    """Seconds to write one progress line (a running counted step, the most frequent), measured here."""
    from eaos.progress import ProgressLog
    from eaos.pipeline.stages import STAGES
    with tempfile.TemporaryDirectory() as folder:
        log = ProgressLog(folder, pulse=False, sampler=None)
        log.started(STAGES, [s.name for s in STAGES], {})
        log.stage_started('plan')
        step = log.stepper('plan')
        began = time.perf_counter()
        for done in range(samples): step(f'item {done}', done, samples, 'running')
        return (time.perf_counter() - began) / samples


def sample_cost(samples=20):
    """Seconds one `ps` sample of the running programs takes, measured here."""
    from eaos.progress.sampler import Sampler
    sampler = Sampler()
    began = time.perf_counter()
    for _ in range(samples): sampler.sample()
    return (time.perf_counter() - began) / samples


def overhead(args):
    project, work = Path(args.project).resolve(), Path(args.workdir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    runs = {}
    for name, on in (('on', True), ('off', False)):
        out = fresh(work / name)
        out.mkdir(parents=True)
        began = time.monotonic()
        done = subprocess.run(check_command(project, out, not args.no_engines), cwd=str(work), env=environment(on),
                              capture_output=True, text=True)
        runs[name] = {'wall_seconds': round(time.monotonic() - began, 1), 'exit': done.returncode,
                      'said': done.stdout.strip()[-200:], 'error': done.stderr.strip()[-1500:] if done.returncode else ''}
        manifest = out / 'run-manifest.json'
        if manifest.is_file(): runs[name]['manifest_seconds'] = json.loads(manifest.read_text(encoding='utf-8'))['seconds']
    report = work / 'on'
    progress_file = report / 'run-progress.jsonl'
    history = sorted((report / 'progress').rglob('*.jsonl')) if (report / 'progress').is_dir() else []
    rows = [json.loads(line) for line in progress_file.read_text(encoding='utf-8').splitlines()] if progress_file.is_file() else []
    events = {}
    for row in rows: events[row['event']] = events.get(row['event'], 0) + 1
    on, off = runs['on'].get('manifest_seconds'), runs['off'].get('manifest_seconds')
    per_line, per_sample = line_cost(), sample_cost()
    samples = max(int((on or 0) / 2.0), 0)                         # SAMPLE_EVERY: one ps every 2 s while a stage runs
    bound = len(rows) * per_line + samples * per_sample
    record = {
        'project': str(project), 'engines': not args.no_engines, 'runs': runs,
        'overhead_measured': round((on - off) / off, 4) if on and off else None,
        'overhead_bound': round(bound / on, 4) if on else None,
        'bound_parts': {'lines': len(rows), 'seconds_per_line': round(per_line, 6), 'ps_samples_at_most': samples,
                        'seconds_per_sample': round(per_sample, 4), 'seconds': round(bound, 2)},
        'file_bytes': progress_file.stat().st_size if progress_file.is_file() else None,
        'history_bytes': sum(p.stat().st_size for p in history), 'lines': len(rows), 'events': events,
        'counted_steps': counted(report) if progress_file.is_file() else {},
        'fold_equals_manifest': judge(report) if (report / 'run-manifest.json').is_file() else None,
        'off_wrote_no_progress': not (work / 'off' / 'run-progress.jsonl').exists(),
    }
    record['pass'] = bool(record['overhead_bound'] is not None and record['overhead_bound'] < 0.02
                          and record['file_bytes'] is not None and record['file_bytes'] < 1_000_000
                          and (record['fold_equals_manifest'] or {}).get('equal') and record['off_wrote_no_progress']
                          and all(r['exit'] == 0 for r in runs.values()))
    return record


def kill(args):
    from eaos import progress
    from eaos.api.read import scan_state
    project, work = Path(args.project).resolve(), Path(args.workdir).resolve()
    out = fresh(work / 'killed')
    out.mkdir(parents=True)
    process = subprocess.Popen(check_command(project, out), cwd=str(work), env=environment(True),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    began, stage_seen = time.monotonic(), None
    try:
        while time.monotonic() - began < args.timeout:
            state = progress.fold(progress.read(out))
            running = next((s for s in state['stages'] if s['name'] == args.stage and s['state'] == 'running'), None)
            if running and stage_seen is None: stage_seen = time.monotonic()
            if stage_seen and time.monotonic() - stage_seen >= args.after: break
            if process.poll() is not None: break
            time.sleep(0.2)
        before = scan_state(out)['state']
        os.killpg(process.pid, signal.SIGKILL)
        killed = time.monotonic()
        process.wait()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    path = progress.path_for(out)
    seen = {'interrupted': None, 'stalled': None}
    while time.monotonic() - killed < 45 and None in seen.values():
        if seen['interrupted'] is None and scan_state(out)['state'] == 'interrupted':
            seen['interrupted'] = round(time.monotonic() - killed, 2)
        folded = progress.fold(progress.read(out))
        if seen['stalled'] is None and progress.judge(folded, progress.heard_at(path), time.time(), None) == 'stalled':
            seen['stalled'] = round(time.monotonic() - killed, 2)
        time.sleep(0.25)
    folded = progress.fold(progress.read(out))
    return {'project': str(project), 'stage': args.stage, 'after_seconds': args.after,
            'state_before_kill': before, 'running_stage_at_kill': next((s['name'] for s in folded['stages'] if s['state'] == 'running'), None),
            'seconds_to_interrupted_same_machine': seen['interrupted'], 'seconds_to_stalled_other_machine': seen['stalled'],
            'pass': bool(before == 'running' and seen['interrupted'] is not None and seen['interrupted'] <= 30
                         and seen['stalled'] is not None and seen['stalled'] <= 30)}


def collect(args):
    """$EAOS_MEASURE/live-scan-map/backend.json from one real round: what each guarantee measured, and its verdict."""
    import dev_paths
    read = lambda path: json.loads(Path(path).read_text(encoding='utf-8'))
    determinism, engines, killed, cost = read(args.determinism), read(args.determinism_engines), read(args.kill), read(args.overhead)
    counted_steps = cost.get('counted_steps') or {}
    stages = {}
    if args.overhead_dir:
        for name in ('on', 'off'):
            manifest = Path(args.overhead_dir) / name / 'run-manifest.json'
            if manifest.is_file(): stages[name] = {k: v['seconds'] for k, v in read(manifest)['stages'].items()}
    outside = {name: round(sum(s for k, s in rows.items() if k != 'engines'), 2) for name, rows in stages.items()}
    record = {
        'contract': 1, 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'I2_corpus': judge(args.corpus_report), 'I2_develop': cost.get('fold_equals_manifest'),
        'I6': {'project': determinism['project'], 'engines': determinism['engines'], 'identical': determinism['identical'],
               'compared': determinism['on_vs_off']['compared'], 'differ': determinism['on_vs_off']['differ'],
               'only_on': determinism['on_vs_off']['only_left'], 'only_off': determinism['on_vs_off']['only_right']},
        'I6_engines': {'project': engines['project'], 'engines': engines['engines'], 'compared': engines['on_vs_off']['compared'],
                       'progress_adds_no_difference': engines['progress_adds_no_difference'],
                       'differ_only_with_progress_switched': engines['differ_only_with_progress_switched'],
                       'differ_between_two_runs_with_progress': len(engines['on_vs_on']['differ'])},
        'I7': {'project': cost['project'], 'overhead_measured': cost['overhead_measured'], 'overhead_bound': cost['overhead_bound'],
               'bound_parts': cost['bound_parts'], 'file_bytes': cost['file_bytes'], 'lines': cost['lines'],
               'engines_seconds': {name: rows.get('engines') for name, rows in stages.items()},
               'seconds_outside_engines': outside,
               'overhead_measured_outside_engines': round((outside['on'] - outside['off']) / outside['off'], 4)
               if outside.get('on') and outside.get('off') else None,
               'runs': {k: {'manifest_seconds': v.get('manifest_seconds'), 'exit': v['exit']} for k, v in cost['runs'].items()}},
        'I8': {k: killed[k] for k in ('project', 'stage', 'state_before_kill', 'running_stage_at_kill',
                                      'seconds_to_interrupted_same_machine', 'seconds_to_stalled_other_machine')},
        'counted_steps': {stage: counted_steps.get(stage, []) for stage in ('plan', 'transform', 'executive', 'claims',
                                                                            'sustainability', 'compose', 'bundles', 'emit')},
    }
    folder = dev_paths.MEASURE / 'live-scan-map'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'backend.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    record['written'] = str(folder / 'backend.json')
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    one = sub.add_parser('overhead')
    one.add_argument('project'); one.add_argument('workdir'); one.add_argument('--json'); one.add_argument('--no-engines', action='store_true')
    two = sub.add_parser('kill')
    two.add_argument('project'); two.add_argument('workdir'); two.add_argument('--json')
    two.add_argument('--stage', default='engines'); two.add_argument('--after', type=float, default=8.0)
    two.add_argument('--timeout', type=float, default=1800.0)
    three = sub.add_parser('judge')
    three.add_argument('report')
    four = sub.add_parser('collect')
    for name in ('--determinism', '--determinism-engines', '--kill', '--overhead', '--corpus-report'):
        four.add_argument(name, required=True)
    four.add_argument('--overhead-dir', help='the overhead workdir, for each run\'s stage seconds')
    args = parser.parse_args(argv)
    run = {'overhead': overhead, 'kill': kill, 'collect': collect, 'judge': lambda a: judge(a.report)}[args.command]
    record = run(args)
    if args.command == 'collect': record['pass'] = True
    text = json.dumps(record, ensure_ascii=False, indent=1)
    if getattr(args, 'json', None): Path(args.json).write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0 if record.get('pass', record.get('equal')) else 1


if __name__ == '__main__':
    sys.exit(main())

"""A trial from nothing: a project, a fresh EAOS home, and only the commands a person types (docs/USER-EXPERIENCE.md).

    python tools/ux_trial.py <project folder> [--name NAME] [--lang ar|en] [--until safety|applied]

The trial answers every question with yes, as a person agreeing would, and types `eaos next` until the journey
reaches --until or a step fails. It writes ${EAOS_MEASURE:-/tmp/eaos-measure}/ux/<name>/trial.json:

    {project, commit, manual_files, questions[{id, kind}], minutes_to_first_report, reached, applied,
     commands[{argv, exit, seconds}], finished}

manual_files is what a person had to write by hand: always 0 here, because this script only types commands; a
trial run by a person records the files they wrote with --manual-file. X1, X2 and X3 are read from these files
(tools/north_star_measure.py usability_values).
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEASURE = Path(os.environ.get('EAOS_MEASURE', '/workspace/eaos-measure'))
ORDER = ('scan', 'ready', 'safety', 'fix', 'review')


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('project')
    parser.add_argument('--name', default=None)
    parser.add_argument('--lang', choices=['ar', 'en'], default='ar')
    parser.add_argument('--until', choices=ORDER, default='safety')
    parser.add_argument('--manual-file', action='append', default=[], help='a file a person had to write by hand')
    args = parser.parse_args(argv)
    project = Path(args.project).resolve()
    name = args.name or project.name
    where = MEASURE / 'ux' / name
    home = where / 'home'
    subprocess.run(['rm', '-rf', str(home)])
    for stale in list(where.glob('out-*.txt')) + [where / 'trial.json']:   # a trial reads only its own outputs
        if stale.exists(): stale.unlink()
    env = {**os.environ, 'EAOS_HOME': str(home), 'PYTHONPATH': str(ROOT)}
    commit = subprocess.run(['git', '-C', str(project), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    trial = {'schema_version': 1, 'project': name, 'commit': commit, 'manual_files': len(args.manual_file),
             'manual_file_names': args.manual_file, 'started': datetime.now(timezone.utc).isoformat(timespec='seconds'),
             'commands': [], 'minutes_to_first_report': None, 'reached': None, 'applied': False, 'finished': False}
    began = time.monotonic()

    def run(*command):
        started = time.monotonic()
        done = subprocess.run([sys.executable, '-m', 'eaos', *command], cwd=project, env=env, capture_output=True, text=True)
        trial['commands'].append({'argv': ['eaos', *command], 'exit': done.returncode, 'seconds': round(time.monotonic() - started)})
        (where / f"out-{len(trial['commands'])}.txt").write_text(done.stdout + done.stderr, encoding='utf-8')
        return done.returncode

    where.mkdir(parents=True, exist_ok=True)
    code = run('start', '.', '--yes', '--lang', args.lang)
    trial['minutes_to_first_report'] = round((time.monotonic() - began) / 60, 1)
    for _ in range(12):
        state = next((json.loads(p.read_text()) for p in home.glob('projects/*/state.json')), {})
        trial['reached'] = _reached(state)
        if code != 0: break
        if trial['reached'] and ORDER.index(trial['reached']) >= ORDER.index(args.until): break
        code = run('next', '--yes')
    state = next((json.loads(p.read_text()) for p in home.glob('projects/*/state.json')), {})
    trial['reached'] = _reached(state)
    trial['questions'] = [{'id': q['id'], 'kind': q.get('kind', 'yes_no')} for q in state.get('questions') or []]
    trial['applied'] = bool(state.get('applied'))
    trial['finished'] = trial['reached'] is not None and ORDER.index(trial['reached']) >= ORDER.index(args.until)
    trial['minutes_total'] = round((time.monotonic() - began) / 60, 1)
    (where / 'trial.json').write_text(json.dumps(trial, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: trial[k] for k in ('project', 'reached', 'finished', 'questions', 'minutes_to_first_report',
                                            'minutes_total', 'manual_files', 'applied')}, ensure_ascii=False))
    return 0 if trial['finished'] else 1


def _reached(state):
    """The furthest step the guided state records as done."""
    reached = None
    if state.get('scanned'): reached = 'scan'
    if (state.get('setup') or {}).get('commit'): reached = 'ready'
    if (state.get('safety') or {}).get('commit'): reached = 'safety'
    if state.get('fixed'): reached = 'fix'
    if state.get('applied'): reached = 'review'
    return reached


if __name__ == '__main__':
    raise SystemExit(main())

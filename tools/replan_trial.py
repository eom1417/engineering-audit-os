"""Re-plan a target already built (NS46.T16, docs/STUDIO.md D10): a fresh check of the project with this EAOS, then
a real planning run of its ideal on top of the rules, recorded beside the check.

    python tools/replan_trial.py chief-ops [--target <the project's folder>] [--assistant claude|codex] [--fresh]

The target defaults to the pinned corpus copy ($EAOS_CORPUS/<project>); for EAOS itself, pass a checkout of this
repository. The check (`eaos audit`, the engines on and the site skipped, as `tools/north_star_measure.py` runs it) is
written to $EAOS_MEASURE/replan/<project>/report and reused unless --fresh; none of the project's code runs. Then
`tools/ideal_trial.py --into replan` plans it and writes $EAOS_MEASURE/replan/<project>/run.json and comparison.md.
audit.json beside them records the check: {target, commit, exit, seconds, eaos}.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT))
import dev_paths  # noqa: E402
import ideal_trial  # noqa: E402
from north_star_measure import ENGINES  # noqa: E402


def check(target, report):
    """The fresh check of `target` into `report`: (exit code, seconds)."""
    if report.exists(): shutil.rmtree(report)
    started = time.monotonic()
    done = subprocess.run([sys.executable, '-m', 'eaos', 'audit', str(target), '--out', str(report), '--skip', 'site',
                           '--engines', *ENGINES], cwd=ROOT)
    return done.returncode, round(time.monotonic() - started, 1)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('project')
    parser.add_argument('--target', help='the project\'s folder (default $EAOS_CORPUS/<project>)')
    parser.add_argument('--assistant', default='claude', choices=('claude', 'codex'))
    parser.add_argument('--lang', default='ar', choices=('ar', 'en'))
    parser.add_argument('--timeout', type=int, default=None)
    parser.add_argument('--commit', help='the EAOS commit a frozen copy (no .git) was made from, for the record')
    parser.add_argument('--fresh', action='store_true', help='check the project again even if a check is recorded')
    args = parser.parse_args(argv)
    target = Path(args.target).resolve() if args.target else dev_paths.CORPUS / args.project
    if not target.is_dir():
        print(f'no project folder at {target}', file=sys.stderr)
        return 2
    folder = dev_paths.MEASURE / 'replan' / args.project
    folder.mkdir(parents=True, exist_ok=True)
    report = folder / 'report'
    if args.fresh or not (report / 'target-architecture.json').is_file():
        print(f'checking {target} into {report}', flush=True)
        code, seconds = check(target, report)
        commit = subprocess.run(['git', '-C', str(target), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
        (folder / 'audit.json').write_text(json.dumps({'target': str(target), 'commit': commit or None, 'exit': code,
                                                       'seconds': seconds, 'eaos': args.commit}, indent=1) + '\n', encoding='utf-8')
        print(f'check exit {code} in {seconds} s', flush=True)
        if not (report / 'target-architecture.json').is_file():
            print('the check wrote no target-architecture.json: nothing to plan', file=sys.stderr)
            return 1
    plan = [args.project, '--report', str(report), '--into', 'replan', '--project-dir', str(target),
            '--assistant', args.assistant, '--lang', args.lang]
    if args.timeout: plan += ['--timeout', str(args.timeout)]
    if args.commit: plan += ['--commit', args.commit]
    return ideal_trial.main(plan)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

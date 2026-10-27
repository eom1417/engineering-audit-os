"""The detection baseline (docs/STANDARDS.md §5, M0.2): how far a check of tests/fixtures/baseline-app found each problem
planted in it (tests/fixtures/baseline-problems.json). Refuses a check that found any of them less than recorded, or
found any example planted to stay (`must_stay`: a placeholder, the program's own configuration).

    python tools/detection_baseline.py <check output> [--record]

tools/golden_trial.sh runs the check (the app run, no assistant) and then this; --record writes what the check found,
after a change that found more.
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

PROBLEMS = Path(__file__).resolve().parents[1] / 'tests' / 'fixtures' / 'baseline-problems.json'
LEVELS = ('missed', 'finding', 'card')    # a finding is recorded by an engine or a screen; a card is shown to the person
NEAR = 3                                  # lines between a finding and the planted line that still name it


def _read(path):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}


def _route(url):
    """'#/reports' for a hash route, else the URL's path."""
    return '#' + url.split('#', 1)[1] if '#' in url else urlsplit(url).path or '/'


def evidence(technical):
    """(level, text, place, line) for everything the check recorded: its cards, engine findings, screen errors and
    whether the pages need a sign-in (place '*': the app as a whole)."""
    rows = _cards(technical) + _engine_findings(technical) + _screen_errors(technical)
    return rows + ([('finding', 'sign_in', '*', None)] if _read(technical / 'live' / 'sign-in.json').get('needed') else [])


def _cards(technical):
    return [('card', f"{task.get('pattern')} {task.get('title')}".lower(), path, None)
            for task in _read(technical / 'plan.json').get('tasks') or [] for path in task.get('paths') or []]


def _engine_findings(technical):
    return [('finding', f"{row['kind']} {row['rule']} {row['message']}".lower(), path, line)
            for report in (_read(technical / 'engines' / 'engines.json').get('engines') or {}).values()
            for row in report.get('findings') or [] for path, line in row['sites']]


def _screen_errors(technical):
    return [('finding', ' '.join(row['page_errors']).lower(), _route(row.get('landed') or row['url']), None)
            for row in _read(technical / 'live' / 'screens.json').get('rows') or [] if row.get('page_errors')]


def level(problem, rows):
    """How far the rows reach the problem: the best level of a row at its place (and near its line) naming its kind."""
    place, line = problem.get('path') or problem.get('route'), problem.get('line')
    reached = [LEVELS.index(row_level) for row_level, text, where, at in rows if where in (place, '*')
               and not (at and line and abs(at - line) > NEAR) and any(kind.lower() in text for kind in problem['kinds'])]
    return LEVELS[max(reached, default=0)]


def _found_what_must_stay(baseline, rows):
    """Whether the check found an example planted to stay (said when it did)."""
    kept = [example['id'] for example in baseline.get('must_stay') or [] if level(example, rows) != 'missed']
    if kept: print('REFUSED, found what must stay: ' + ', '.join(kept))
    return bool(kept)


def main(output, record=False):
    technical = next(Path(output).rglob('run-manifest.json')).parent
    rows, baseline = evidence(technical), _read(PROBLEMS)
    worse = []
    for problem in baseline['problems']:
        problem['now'] = level(problem, rows)
        print(f"{problem['id']:20} {problem['now']:8} (recorded {problem['found']})")
        if LEVELS.index(problem['now']) < LEVELS.index(problem['found']): worse.append(problem['id'])
    found = sum(problem['now'] != 'missed' for problem in baseline['problems'])
    print(f"detection baseline: {found} of {len(baseline['problems'])} planted problems found")
    if worse: print('REFUSED, found less than recorded: ' + ', '.join(worse))
    if _found_what_must_stay(baseline, rows) or worse: return 1
    if record:
        for problem in baseline['problems']: problem['found'] = problem.pop('now')
        PROBLEMS.write_text(json.dumps(baseline, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    sys.exit(main(sys.argv[1], '--record' in sys.argv))

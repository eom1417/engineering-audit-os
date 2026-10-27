"""The simulated users proved on corpus apps (M10.10): for each app, the whole simulation (`eaos check --path experience`),
a full check with the short simulation (`--path complete experience`), and a full check without it (`--path complete`)
whose saved journeys are replayed by the behaviour lock with no assistant. Each step's time, assistant calls and cost,
and what the simulated users met (personas, goals, tickets, difficulties by verdict, each confirmed one's pictures and
steps on disk and its card) are measured right after it, before the next check clears its records.

    python tools/experience_proof.py <scratch> <corpus app> [...]

Each app runs in <scratch>/<app>/ with an EAOS home of its own (tools/journeys_proof.py Journey); its results go into
<scratch>/results/<app>.json. Run it in a transient unit.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
os.environ['EAOS_HEADLESS'] = '1'
os.environ.setdefault('EAOS_SIGN_IN_WAIT', '30')

import corpus  # noqa: E402  (beside this file)
from journeys_proof import Journey, cost, eaos, report_of  # noqa: E402

STEPS = (('whole', ('experience',)), ('short', ('complete', 'experience')), ('replays', ('complete',)))
LIMIT = 90 * 60


def _read(path):
    try: body = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}
    return body if isinstance(body, dict) else {}


def _rows(path, key):
    return [row for row in _read(path).get(key) or [] if isinstance(row, dict)]


def _cards(report):
    """{fact id: card id} of the plan's cards."""
    return {fact: task['id'] for task in _rows(report / 'plan.json', 'tasks') for fact in (task.get('evidence') or {}).get('fact_ids') or ()}


def _confirmed(report, row, cards):
    """One confirmed difficulty: its pictures and journey on disk, its steps to reproduce, its card."""
    pictures, journey = row.get('pictures') or [], row.get('journey')
    facts = [f['id'] for f in _rows(report / 'facts' / 'experience.json', 'facts') if f['value'].get('id') == row['id']]
    return {'id': row['id'], 'goal': row['goal'], 'kind': row['kind'], 'title': row.get('title'), 'pictures': len(pictures),
            'pictures_on_disk': sum((report / p).exists() for p in pictures), 'journey_on_disk': bool(journey and (report / journey).exists()),
            'repro_steps': len(row.get('repro') or []), 'card': next((cards[f] for f in facts if f in cards), None)}


def _goals(folder):
    goals, personas = _rows(folder / 'run.json', 'goals'), _rows(folder / 'scenario.json', 'personas')
    status = [g.get('status') for g in goals]
    return {'personas': len(personas), 'roles': [p.get('role') for p in personas], 'goals': len(goals),
            'reached': status.count('reached'), 'stuck': status.count('stuck'), 'goal_status': {g.get('name'): g.get('status') for g in goals}}


def measured(report):
    """What the simulated users of this report did and met, and the lock's replays."""
    report, folder = Path(report), Path(report) / 'experience'
    run, rows = _read(folder / 'run.json'), _rows(folder / 'difficulties.json', 'difficulties')
    verdicts = [r.get('verdict') for r in rows]
    return {**_goals(folder), 'run_seconds': run.get('seconds'), 'run_calls': run.get('calls'),
            'tickets': len(_rows(folder / 'tickets.json', 'tickets')),
            'difficulties': {v: verdicts.count(v) for v in ('confirm', 'doubt', 'reject')},
            'confirmed': [_confirmed(report, r, _cards(report)) for r in rows if r.get('verdict') == 'confirm'],
            'replays': _read(folder / 'replays.json').get('summary'), 'lock_rows': len(_rows(report / 'behavior-lock' / 'results.json', 'results')),
            'story_cards': [d.get('card') for d in _read(folder / 'story.json').get('difficulties', {}).get('ranked', [])]}


def manifest(report):
    """The check's time, the stages not ok, and what its assistant used (eaos/core/system/usage.py), by stage."""
    from eaos.core.system.usage import of_check
    record, use = _read(report / 'run-manifest.json'), of_check(report) or {}
    stages, used = record.get('stages') or {}, use.get('stages') or {}
    return {'check_seconds': round(record.get('seconds') or 0),
            'not_ok': {n: f"{r['status']}: {str(r.get('reason'))[:200]}" for n, r in stages.items() if r.get('status') != 'ok'},
            'experience_stage': stages.get('experience'), 'cost_usd': cost(use.get('total')), 'calls': (use.get('total') or {}).get('calls'),
            'calls_by_stage': {name: row.get('calls') for name, row in used.items()}, 'experience_cost_usd': _experience_cost(used)}


def _experience_cost(used):
    """What the simulated users' own calls cost (their stages are named experience_*)."""
    return round(sum(row.get('cost_usd') or 0 for name, row in used.items() if name.startswith('experience')), 3)


def step(app, paths):
    def work():
        code, said = eaos('check', '--project', str(app), '--path', *paths, '--run-app', '--assistant', 'claude',
                          '--sign-in', 'test_user', '--lang', 'en', '--watch', timeout=LIMIT)
        report = report_of(app)
        found = {**manifest(report), **measured(report)}
        return {'passed': code == 0 and not [n for n, why in found['not_ok'].items() if not why.startswith(('skipped', 'unavailable'))],
                'exit': code, **found, **({} if code == 0 else {'reason': said[-600:]})}
    return work


def prove(scratch, name):
    journey = Journey(scratch, name)
    entry = next(a for a in json.loads(corpus.CATALOG.read_text(encoding='utf-8'))['apps'] if a['name'] == name)
    if not (journey.folder / 'app').exists(): corpus.fetch(entry, journey.folder)
    for label, paths in STEPS: journey.step(label, step(journey.folder / 'app', paths))
    return journey


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    for app_name in sys.argv[2:]: prove(Path(sys.argv[1]).resolve(), app_name)

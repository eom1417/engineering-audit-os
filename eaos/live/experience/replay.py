"""Save and replay (M10.4): every journey a simulated user finished (eaos/live/experience/actor.py saved it) is done
again in every full check with no assistant at all, on the browser agent's replay (eaos/live/agent.py), and joins the
behaviour lock: a journey that no longer replays is a behaviour that broke, shown in red.

    replay_all(base, sessions, report)   experience/replays.json: {version, replays: [...], summary: {green, red, skipped}}
    as_lock(replays)                     its rows in the behaviour lock's shape (behavior-lock/results.json `results`)
    saved(report)                        whether any journey is saved to replay
    join_lock(runtime, lock, replays)    the lock's record (run_lock's answer) with the replays as its rows, written to
                                         <runtime>/behavior-lock/results.json: every full check, after the lock's run

A journey that never reached its goal is skipped: it is not a behaviour to keep. One replay's pictures go to
experience/replays/<name>/, replaced each time, so they never pile up.
"""
import json
import shutil
import time
from pathlib import Path

from ..agent import Browser, replay
from .actor import JOURNEYS, load

VERSION = 1
REPLAYS = 'replays'
LOCK_STATUS = {'green': 'passed', 'red': 'failed', 'skipped': 'quarantined'}


def _landed(journey):
    """The last address the saved journey's working steps landed on, or its start."""
    landed = [s.get('landed') for s in journey.get('steps') or [] if not s.get('error') and s.get('landed')]
    return landed[-1] if landed else journey.get('start') or '/'


def _verdict(journey, done):
    """green, or red with where and why, of a replay `done` (agent.replay's answer) of `journey`."""
    if 'broken_at' in done:
        return {'status': 'red', 'broken_at': done['broken_at'], 'error': str(done.get('error') or 'the step failed')[:300]}
    if _landed(journey) not in done['screens']:
        return {'status': 'red', 'error': f'the journey ended on {_landed(journey)}, the replay never reached it'}
    return {'status': 'green'}


def replay_one(base, journey, out, storage_state=None):
    """{goal, status, broken_at?, error?, screens, seconds}: `journey` done again with no assistant, pictures in `out`."""
    if not journey.get('reached'):
        return {'goal': journey.get('goal'), 'status': 'skipped', 'why': 'the journey never reached its goal', 'screens': [], 'seconds': 0}
    shutil.rmtree(out, ignore_errors=True)
    began = time.monotonic()
    with Browser(base, out, storage_state) as browser:
        done = replay(browser, journey)
    return {'goal': journey['goal'], **_verdict(journey, done), 'screens': done['screens'],
            'seconds': round(time.monotonic() - began, 1)}


def replay_all(base, sessions, report):
    """experience/replays.json in `report`, written and returned: every saved journey replayed on the app at `base`,
    signed in with its role's storage state (`sessions`: {role: path or None})."""
    folder = Path(report) / 'experience'
    replays = []
    for path in sorted((folder / JOURNEYS).glob('*.json')):
        journey = load(path)
        if not isinstance(journey, dict):
            replays.append({'goal': path.stem, 'status': 'skipped', 'why': 'the saved journey cannot be read', 'screens': [], 'seconds': 0})
            continue
        found = replay_one(base, journey, folder / REPLAYS / path.stem, (sessions or {}).get(journey.get('role')))
        replays.append({**found, 'file': f'{JOURNEYS}/{path.name}'})
    record = {'version': VERSION, 'replays': replays,
              'summary': {status: sum(r['status'] == status for r in replays) for status in LOCK_STATUS}}
    (folder / 'replays.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return record


def as_lock(replays):
    """[{path, status, reason?}]: each replay as a row of the behaviour lock's results (eaos/live/behavior/lock.py),
    path experience/journeys/<file>; green passed, red failed, skipped quarantined."""
    rows = []
    for found in (replays or {}).get('replays') or []:
        reason = found.get('error') or found.get('why') or ''
        if 'broken_at' in found: reason = f"step {found['broken_at']}: {reason}"
        rows.append({'path': 'experience/' + (found.get('file') or found['goal']), 'status': LOCK_STATUS[found['status']],
                     **({'reason': reason[:300]} if reason else {})})
    return rows


def saved(report):
    """Whether `report` holds a saved journey to replay."""
    return any((Path(report) / 'experience' / JOURNEYS).glob('*.json'))


def join_lock(runtime, lock, replays):
    """The behaviour lock's record `lock` with each replay a row (as_lock) in place of an earlier check's, written to
    <runtime>/behavior-lock/results.json, so a journey that no longer replays shows as a broken screen does."""
    rows = [r for r in lock.get('results') or [] if not r['path'].startswith('experience/')] + as_lock(replays)
    record = {**lock, 'results': rows}
    folder = Path(runtime) / 'behavior-lock'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'results.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return record

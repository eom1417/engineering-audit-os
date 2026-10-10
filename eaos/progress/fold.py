"""The single Python fold: a flow's progress lines turned into one state, one row per declared stage.

`apply(state, row)` is the step a reader takes for each new line; `fold(rows)` is all of them from the start. The
Studio's TypeScript fold (studio/src/data/scan.ts) applies the same rules to the same lines, and both are tested on the
same recorded runs (tests/fixtures/progress/): the page never invents a state the lines do not hold.

For the check, at the end of a run the folded statuses, reasons, seconds and artifacts are the ones in
run-manifest.json.
"""
import json
from pathlib import Path

from .log import path_for

WAITING, RUNNING = 'waiting', 'running'
ENDED = ('ok', 'skipped', 'unavailable', 'failed', 'not_reached')


def read(folder, flow='check'):
    """The rows of a flow's progress file, in order; [] when there is none. A line still being written is left."""
    try: raw = path_for(folder, flow).read_bytes()
    except OSError: return []
    rows = []
    for line in raw[:raw.rfind(b'\n') + 1].decode('utf-8', 'replace').splitlines():
        try: row = json.loads(line)
        except ValueError: continue
        if isinstance(row, dict): rows.append(row)
    return rows


def empty():
    return {'contract': 1, 'flow': None, 'run': None, 'state': 'none', 'status': None, 'reason': '', 'started_at': None,
            'ended_at': None, 'heard_at': None, 'alive_every': None, 'seconds': None, 'last_seq': 0, 'requested': [],
            'previous': {}, 'previous_steps': {}, 'counts': {}, 'stages': [], 'pid': None, 'host': None}


def declared(flow, stages):
    """The state of a flow that has not run yet: its declared stages (log.stage_rows), all waiting."""
    return {**empty(), 'flow': flow, 'stages': [_stage(row, ()) for row in stages]}


def _stage(declared, requested):
    return {**declared, 'requested': declared['name'] in requested, 'state': WAITING, 'started_at': None,
            'ended_at': None, 'seconds': None, 'reason': '', 'reason_code': '', 'artifacts': [], 'detail': {},
            'steps': [], 'programs': [], 'activity_note': '', 'resumed': False}


def _run_started(state, row):
    requested = row.get('requested') or []
    state.clear()
    state.update(empty(), flow=row.get('flow') or 'check', run=row.get('run'), state=RUNNING, started_at=row.get('at'),
                 requested=list(requested), previous=row.get('previous') or {}, previous_steps=row.get('previous_steps') or {},
                 alive_every=row.get('alive_every'), pid=row.get('pid'), host=row.get('host'))
    state['stages'] = [_stage(s, set(requested)) for s in row.get('stages') or [] if isinstance(s, dict) and s.get('name')]


def _stage_started(stage, row):
    stage.update(state=RUNNING, started_at=row.get('at'))


def _stage_step(stage, row):
    found = next((s for s in stage['steps'] if s['name'] == row.get('step')), None)
    if found is None:
        found = {'name': row.get('step'), 'kind': row.get('kind') or 'item', 'status': WAITING, 'done': 0, 'total': 0,
                 'seconds': None, 'reason': '', 'reason_code': ''}
        stage['steps'].append(found)
    found.update(status=row.get('status') or RUNNING, done=row.get('done', 0), total=row.get('total', 0))
    if 'seconds' in row: found['seconds'] = row['seconds']
    found.update({key: row[key] for key in ('reason', 'reason_code', 'artifact') if row.get(key)})


def _stage_activity(stage, row):
    stage['programs'] = [dict(p) for p in row.get('programs') or [] if isinstance(p, dict)]
    if row.get('reason'): stage['activity_note'] = row['reason']


def _stage_ended(stage, row):
    stage.update(state=row.get('status'), ended_at=row.get('at'), seconds=row.get('seconds'), reason=row.get('reason') or '',
                 reason_code=row.get('reason_code') or '', artifacts=list(row.get('artifacts') or []),
                 detail=row.get('detail') or {}, resumed=bool(row.get('resumed')), programs=[])


STAGE_EVENTS = {'stage.started': _stage_started, 'stage.step': _stage_step, 'stage.activity': _stage_activity,
                'stage.ended': _stage_ended}


def apply(state, row):
    """One event onto the folded state (in place); the state it returns. Unknown events and stages are ignored, and a
    line of another run than the one folded is left out."""
    event = row.get('event')
    if event == 'run.started': _run_started(state, row)
    elif state.get('run') is None or row.get('run') != state.get('run'): return state
    stage = next((s for s in state['stages'] if s['name'] == row.get('stage')), None) if event in STAGE_EVENTS else None
    if stage: STAGE_EVENTS[event](stage, row)
    elif event == 'run.ended':
        state.update(state='done', status=row.get('status'), reason=row.get('reason') or '', ended_at=row.get('at'),
                     seconds=row.get('seconds'), counts=row.get('counts') or {})
    state['heard_at'] = row.get('at') or state.get('heard_at')
    state['last_seq'] = max(state.get('last_seq') or 0, int(row.get('seq') or 0))
    return state


def fold(rows):
    """The whole state after `rows`: one row per declared stage, in the declaration's order."""
    state = empty()
    for row in rows: apply(state, row)
    return state


def fold_file(path):
    """The fold of one progress file given by its path (a recorded run, a history entry)."""
    rows = []
    try: text = Path(path).read_text(encoding='utf-8')
    except OSError: return empty()
    for line in text.splitlines():
        try: row = json.loads(line)
        except ValueError: continue
        if isinstance(row, dict): rows.append(row)
    return fold(rows)

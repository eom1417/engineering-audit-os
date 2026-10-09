"""The run's progress as it happens: one JSON line per event in `<report>/run-progress.jsonl`.

`execute()` writes it itself, so every way of starting a check (the terminal's `eaos start`, the assistant's job, the
Studio's run) leaves the same trace, and anything that can read the report folder can follow the run live:

    {"seq": 1, "event": "run.started", "run": "...", "stages": [...the declared stages...], "requested": [...]}
    {"seq": 2, "event": "stage.started", "stage": "facts"}
    {"seq": 3, "event": "stage.step", "stage": "facts", "step": "syntax", "done": 0, "total": 19, "status": "running"}
    {"seq": 9, "event": "stage.ended", "stage": "facts", "status": "ok", "seconds": 212.4, "artifacts": [...]}
    {"seq": 60, "event": "run.ended", "status": "INCOMPLETE", "counts": {...}}

Every stage of the declaration gets exactly one `stage.ended`, at the moment its fate is decided: a stage that ran, one
not requested, one blocked by a stage before it, one a resumed run kept. `run.started` carries the stages as data, so
a reader draws what this EAOS runs, and a stage added to `stages.py` appears with no change anywhere else.

The file is replaced (a new inode) when a run starts and appended to, one whole line per write, afterwards: a reader
that sees the inode change knows a new run began. Writing it never decides the fate of the run: a failure to write is
swallowed, and the manifest stays the record.

`fold(rows)` turns the lines into one state, one row per stage: the same state a reader builds by applying the events
one by one, and at the end of a run the same statuses, reasons, seconds and artifacts as run-manifest.json.
"""
import json
import os
import secrets
import socket
import threading
from datetime import datetime, timezone
from pathlib import Path

PROGRESS = 'run-progress.jsonl'
WAITING, RUNNING = 'waiting', 'running'
ENDED = ('ok', 'skipped', 'unavailable', 'failed', 'not_reached')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def _small(detail):
    """What a stage reported about itself, kept only when it is a short scalar: a count, a word."""
    out = {}
    for key, value in (detail or {}).items():
        if isinstance(value, bool) or value is None: continue
        if isinstance(value, (int, float)) or (isinstance(value, str) and len(value) <= 80):
            out[str(key)] = value
    return dict(list(out.items())[:8])


def stage_rows(stages):
    """The declaration as data, in its order: what a reader needs to draw the map and explain each stage."""
    return [{'name': s.name, 'requires': list(s.requires), 'produces': list(s.produces), 'necessity': s.necessity,
             'description': s.description, 'absent_when': s.absent_when} for s in stages]


class ProgressLog:
    """Append-only writer of one run's events. Thread-safe; never raises."""

    def __init__(self, out):
        self.path = Path(out) / PROGRESS
        self.seq = 0
        self.lock = threading.Lock()
        self.run = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + secrets.token_hex(3)
        self.broken = False

    def emit(self, event, **fields):
        with self.lock:
            self.seq += 1
            row = {'seq': self.seq, 'at': now(), 'event': event, 'run': self.run, **fields}
            if self.broken: return row
            line = json.dumps(row, ensure_ascii=False, default=str) + '\n'
            try:
                if self.seq == 1:
                    # a new run is a new file: written beside, then moved in, so a reader sees a new inode at once
                    temporary = self.path.with_name(f'.{PROGRESS}.{os.getpid()}.tmp')
                    temporary.write_text(line, encoding='utf-8')
                    os.replace(temporary, self.path)
                else:
                    with self.path.open('a', encoding='utf-8') as handle:
                        handle.write(line)
                        handle.flush()
            except OSError:
                self.broken = True
            return row

    def started(self, stages, requested, previous):
        return self.emit('run.started', stages=stage_rows(stages), requested=list(requested), previous=previous,
                         pid=os.getpid(), host=socket.gethostname())

    def stepper(self, stage):
        """`step(name, done, total, status='running', seconds=None)` for one stage: where a long stage is inside."""
        def step(name, done, total, status=RUNNING, seconds=None, reason=''):
            fields = {'stage': stage, 'step': str(name), 'done': int(done), 'total': int(total), 'status': str(status)}
            if seconds is not None: fields['seconds'] = round(float(seconds), 2)
            if reason: fields['reason'] = str(reason)[:200]
            self.emit('stage.step', **fields)
        return step

    def ended(self, row, **extra):
        self.emit('stage.ended', stage=row['stage'], status=row['status'], reason=row['reason'], seconds=row['seconds'],
                  necessity=row['necessity'], artifacts=list(row['artifacts']), detail=_small(row.get('detail')), **extra)


def previous_seconds(out):
    """{stage: seconds} of the last run of this report that reached an end, for a rough estimate; {} on a first run."""
    try: manifest = json.loads((Path(out) / 'run-manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}
    return {name: row.get('seconds') for name, row in (manifest.get('stages') or {}).items()
            if isinstance(row, dict) and row.get('status') == 'ok' and isinstance(row.get('seconds'), (int, float))}


def read(report):
    """The rows of the report's progress file, in order; [] when there is none. A line still being written is left."""
    try: raw = (Path(report) / PROGRESS).read_bytes()
    except OSError: return []
    rows = []
    for line in raw[:raw.rfind(b'\n') + 1].decode('utf-8', 'replace').splitlines():
        try: row = json.loads(line)
        except ValueError: continue
        if isinstance(row, dict): rows.append(row)
    return rows


def empty():
    return {'contract': 1, 'run': None, 'state': 'none', 'status': None, 'started_at': None, 'ended_at': None,
            'seconds': None, 'last_seq': 0, 'requested': [], 'previous': {}, 'counts': {}, 'stages': [], 'pid': None, 'host': None}


def apply(state, row):
    """One event onto the folded state (in place); the state it returns. Unknown events and stages are ignored."""
    event = row.get('event')
    if event == 'run.started':
        state.clear()
        state.update(empty())
        requested = set(row.get('requested') or [])
        state.update(run=row.get('run'), state=RUNNING, started_at=row.get('at'), requested=list(row.get('requested') or []),
                     previous=row.get('previous') or {}, pid=row.get('pid'), host=row.get('host'))
        state['stages'] = [{**s, 'requested': s['name'] in requested, 'state': WAITING, 'started_at': None, 'ended_at': None,
                            'seconds': None, 'reason': '', 'artifacts': [], 'detail': {}, 'steps': [], 'resumed': False}
                           for s in row.get('stages') or [] if isinstance(s, dict) and s.get('name')]
    elif state.get('run') is None or row.get('run') != state.get('run'):
        return state
    by = {s['name']: s for s in state['stages']}
    stage = by.get(row.get('stage'))
    if event == 'stage.started' and stage:
        stage.update(state=RUNNING, started_at=row.get('at'))
    elif event == 'stage.step' and stage:
        steps = stage['steps']
        found = next((s for s in steps if s['name'] == row.get('step')), None)
        if found is None:
            found = {'name': row.get('step'), 'status': WAITING, 'done': 0, 'total': 0, 'seconds': None, 'reason': ''}
            steps.append(found)
        found.update(status=row.get('status') or RUNNING, done=row.get('done', 0), total=row.get('total', 0))
        if 'seconds' in row: found['seconds'] = row['seconds']
        if row.get('reason'): found['reason'] = row['reason']
    elif event == 'stage.ended' and stage:
        stage.update(state=row.get('status'), ended_at=row.get('at'), seconds=row.get('seconds'), reason=row.get('reason') or '',
                     artifacts=list(row.get('artifacts') or []), detail=row.get('detail') or {}, resumed=bool(row.get('resumed')))
    elif event == 'run.ended':
        state.update(state='done', status=row.get('status'), ended_at=row.get('at'), seconds=row.get('seconds'),
                     counts=row.get('counts') or {})
    state['last_seq'] = max(state.get('last_seq') or 0, int(row.get('seq') or 0))
    return state


def fold(rows):
    """The whole state after `rows`: one row per declared stage, in the declaration's order."""
    state = empty()
    for row in rows: apply(state, row)
    return state


def alive(state):
    """False when a run that never ended was started by a process on this machine that is gone (it was stopped or
    crashed); True when it may still be running; None when it cannot be told (another machine, no process number)."""
    if state.get('state') != RUNNING: return None
    if not state.get('pid') or state.get('host') != socket.gethostname(): return None
    try: os.kill(int(state['pid']), 0)
    except ProcessLookupError: return False
    except PermissionError: return True
    except (OSError, ValueError): return None
    return True

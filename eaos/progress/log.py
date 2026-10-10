"""The writer of a flow's progress: one JSON line per event, appended as the work happens.

Every long piece of work EAOS does is a flow with declared stages: the check (`eaos/pipeline/stages.py`), and later
setting up the app, recording the screens and fixing. Each flow writes `<folder>/progress/<flow>.jsonl`; the check
keeps v1's `<report>/run-progress.jsonl`, so every reader written for v1 still finds it.

    {"seq": 1, "event": "run.started", "flow": "check", "schema": 1, "stages": [...], "requested": [...], ...}
    {"seq": 2, "event": "stage.started", "stage": "facts"}
    {"seq": 3, "event": "stage.step", "stage": "facts", "step": "syntax", "done": 0, "total": 19, "status": "running"}
    {"seq": 4, "event": "stage.activity", "stage": "engines", "programs": [{"name": "semgrep-core", ...}]}
    {"seq": 5, "event": "run.alive"}
    {"seq": 9, "event": "stage.ended", "stage": "facts", "status": "ok", "seconds": 212.4, "artifacts": [...]}
    {"seq": 60, "event": "run.ended", "status": "INCOMPLETE", "counts": {...}}

The events and their fields are declared in eaos/data/schemas/progress.json (versioned by `schema` in run.started).

Every declared stage gets exactly one `stage.ended`: the flow ends each stage when its fate is decided, a second end
of the same stage is left out, and `finish()` ends every stage the flow did not reach (a stop, a crash) before it
writes `run.ended`.

The file is replaced (a new inode) when a run starts and appended to, one whole line per write, afterwards: a reader
that sees the inode change knows a new run began. Writing it never decides the fate of the run: a failure to write is
swallowed, and the manifest stays the record.

The last runs of each flow are kept, whole, in `<folder>/progress/history/<flow>/<run>.jsonl` (HISTORY_KEEP of
them, newest by run id): a run is copied there when it ends, and the file a new run replaces is copied there first, so
a run that was killed is kept too. history.py reads them back.

Three things keep the file honest and small while a stage runs, all on one background thread per run:
- a counted step that only moves forward is written at most 4 times a second per step name (COALESCE), and its last
  value is always written, at the latest when the stage ends;
- a `run.alive` line is written whenever ALIVE_EVERY seconds pass with nothing else written, so a reader can tell a
  quiet stage from a dead run (liveness.py);
- every SAMPLE_EVERY seconds the external programs the run started are looked at (sampler.py) and a
  `stage.activity` line is written when the set changes.
"""
import json
import os
import secrets
import shutil
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .context import bounded
from .fold import fold_file
from .liveness import ALIVE_EVERY

PROGRESS = 'run-progress.jsonl'
FOLDER = 'progress'
SCHEMA = 1
RUNNING = 'running'
COALESCE = 0.25
SAMPLE_EVERY = 2.0
TICK = 0.5
HISTORY = 'history'
HISTORY_KEEP = 5


def enabled():
    """False when EAOS_PROGRESS is 0, off, no or false: then no flow writes its progress and `count()` and `step()`
    hear nothing. It exists to prove that progress never changes a result (tools/progress_determinism.py)."""
    return os.environ.get('EAOS_PROGRESS', '').strip().lower() not in ('0', 'off', 'no', 'false')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def path_for(folder, flow='check'):
    """Where a flow writes its progress: the check in `<report>/run-progress.jsonl`, any other flow in
    `<folder>/progress/<flow>.jsonl`."""
    return Path(folder) / PROGRESS if flow == 'check' else Path(folder) / FOLDER / f'{flow}.jsonl'


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


def history_folder(folder, flow='check'):
    """Where a flow's last runs are kept: `<folder>/progress/history/<flow>/`."""
    return Path(folder) / FOLDER / HISTORY / flow


def first_row(path):
    """The first line of a progress file, parsed ({} when it cannot be read)."""
    try:
        with Path(path).open('r', encoding='utf-8') as handle: return json.loads(handle.readline() or '{}')
    except (OSError, ValueError): return {}


def keep(path, folder, flow, limit=HISTORY_KEEP):
    """Copy the run held in the progress file at `path` into the flow's history, then keep only the newest `limit`
    runs there. Returns the copy's path, or None (no file, no run id, a failure: history never stops a run)."""
    try:
        run = first_row(path).get('run')
        if not run or not Path(path).is_file(): return None
        place = history_folder(folder, flow)
        place.mkdir(parents=True, exist_ok=True)
        copy = place / f'{run}.jsonl'
        shutil.copyfile(path, copy)
        for old in sorted(place.glob('*.jsonl'))[:-limit]: old.unlink()
        return copy
    except OSError:
        return None


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
    return [{'name': s.name, 'requires': list(s.requires), 'produces': list(getattr(s, 'produces', ()) or ()),
             'necessity': getattr(s, 'necessity', 'required'), 'description': getattr(s, 'description', ''),
             'absent_when': getattr(s, 'absent_when', ''), 'ai': getattr(s, 'ai', False)} for s in stages]


def previous_seconds(out):
    """{stage: seconds} of the last run of this report that reached an end, for a rough estimate; {} on a first run."""
    try: manifest = json.loads((Path(out) / 'run-manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}
    return {name: row.get('seconds') for name, row in (manifest.get('stages') or {}).items()
            if isinstance(row, dict) and row.get('status') == 'ok' and isinstance(row.get('seconds'), (int, float))}


def previous_steps(path):
    """{stage: {step: seconds}} of the steps that ended ok in the progress file at `path` (the last run), {} if none."""
    out = {}
    for stage in fold_file(path)['stages']:
        kept = {s['name']: s['seconds'] for s in stage['steps']
                if s.get('status') == 'ok' and isinstance(s.get('seconds'), (int, float))}
        if kept: out[stage['name']] = kept
    return out


class ProgressLog:
    """Append-only writer of one run's events. Thread-safe; never raises.

    `clock` (monotonic seconds) paces the coalescer, the heartbeat and the sampler; `pulse=False` keeps the background
    thread off (a test then calls `tick()` itself); `sampler` is what `tick()` asks for the running programs (None:
    nobody asks)."""

    def __init__(self, out, flow='check', *, clock=time.monotonic, pulse=True, sampler=True, alive_every=ALIVE_EVERY):
        self.flow = flow
        self.folder = Path(out)
        self.path = path_for(out, flow)
        self.seq = 0
        self.lock = threading.RLock()
        self.run = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + secrets.token_hex(3)
        self.enabled = enabled()
        self.broken = not self.enabled              # turned off: every line is left unwritten, as if it failed
        self.clock = clock
        self.pulse = pulse and self.enabled
        self.alive_every = alive_every
        if sampler is True and self.enabled:
            from .sampler import Sampler
            sampler = Sampler()
        self.sampler = (sampler or None) if self.enabled else None
        self.declared = {}          # name -> necessity, in the declaration's order
        self.ended_stages = set()
        self.current = None
        self.stage_began = self.sampled_at = self.wrote_at = clock()
        self.programs = []
        self.sampler_said = False
        self.pending = {}           # (stage, step) -> the newest fields not written yet
        self.written = {}           # (stage, step) -> (clock, status) of the last line written
        self.step_began = {}        # (stage, step) -> clock when it began running, for the seconds of its end
        self.finished = False
        self.stop = threading.Event()
        self.thread = None

    # writing

    def emit(self, event, **fields):
        with self.lock:
            self.seq += 1
            row = {'seq': self.seq, 'at': now(), 'event': event, 'run': self.run, **fields}
            self.wrote_at = self.clock()
            if event == 'stage.started':
                self.current, self.stage_began, self.sampled_at, self.programs = fields.get('stage'), self.wrote_at, self.wrote_at, []
            elif event == 'run.ended':
                self.finished = True
                self.stop.set()
            if self.broken: return row
            line = json.dumps(row, ensure_ascii=False, default=str) + '\n'
            try:
                if self.seq == 1:
                    # a new run is a new file: written beside, then moved in, so a reader sees a new inode at once;
                    # the run it replaces goes to the history first (it may have been killed before its end)
                    keep(self.path, self.folder, self.flow)
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = self.path.with_name(f'.{self.path.name}.{os.getpid()}.tmp')
                    temporary.write_text(line, encoding='utf-8')
                    os.replace(temporary, self.path)
                else:
                    with self.path.open('a', encoding='utf-8') as handle:
                        handle.write(line)
                        handle.flush()
            except OSError:
                self.broken = True
                self.stop.set()
            return row

    def started(self, stages, requested, previous, steps=None):
        """`run.started` with the declared stages as data; the step seconds of the last run come from the file this
        run replaces unless `steps` gives them. Starts the background thread."""
        rows = stage_rows(stages)
        with self.lock:
            self.declared = {row['name']: row['necessity'] for row in rows}
        if steps is None:
            try: steps = previous_steps(self.path)
            except Exception: steps = {}
        row = self.emit('run.started', flow=self.flow, schema=SCHEMA, stages=rows, requested=list(requested),
                        previous=previous or {}, previous_steps=steps, alive_every=self.alive_every,
                        pid=os.getpid(), host=socket.gethostname())
        if self.pulse and not self.broken:
            self.thread = threading.Thread(target=self._beat, name=f'eaos-progress-{self.flow}', daemon=True)
            self.thread.start()
        return row

    def stage_started(self, stage):
        return self.emit('stage.started', stage=stage)

    def stepper(self, stage):
        """`step(name, done, total, status='running', seconds=None, reason='', reason_code='', kind='', artifact='')`
        for one stage: where a long stage is inside. `done` is held between 0 and `total`."""
        def step(name, done, total, status=RUNNING, seconds=None, reason='', reason_code='', kind='', artifact=''):
            done, total = bounded(done, total)
            fields = {'stage': stage, 'step': str(name), 'done': done, 'total': total, 'status': str(status)}
            if kind: fields['kind'] = str(kind)
            if seconds is not None: fields['seconds'] = round(float(seconds), 2)
            if reason: fields['reason'] = str(reason)[:200]
            if reason_code: fields['reason_code'] = str(reason_code)[:80]
            if artifact: fields['artifact'] = str(artifact)[:300]
            self._step(fields)
        return step

    def _step(self, fields):
        """A step's line, coalesced. A step that ends without saying its seconds gets the time since it began
        running, so every step that ended ok has seconds the next run's estimate can use (`previous_steps`)."""
        key = (fields['stage'], fields['step'])
        with self.lock:
            moment = self.clock()
            last = self.written.get(key)
            if fields['status'] == RUNNING:
                if key not in self.step_began or (last and last[1] != RUNNING): self.step_began[key] = moment
            elif fields['status'] != 'waiting':
                began = self.step_began.pop(key, None)
                if 'seconds' not in fields and began is not None: fields['seconds'] = round(moment - began, 2)
            if fields['status'] == RUNNING and last and last[1] == RUNNING and moment - last[0] < COALESCE:
                self.pending[key] = fields           # moving forward too fast: keep the newest, write it soon
                return
            self.pending.pop(key, None)
            self.written[key] = (moment, fields['status'])
            self.emit('stage.step', **fields)

    def _flush(self, stage=None):
        """Write the newest value of each coalesced step whose 4-a-second window has passed (all of `stage`'s now)."""
        with self.lock:
            moment = self.clock()
            for key in list(self.pending):
                if key[0] == stage or moment - self.written[key][0] >= COALESCE:
                    fields = self.pending.pop(key)
                    self.written[key] = (moment, fields['status'])
                    self.emit('stage.step', **fields)

    def ended(self, row, **extra):
        """`stage.ended` for one stage; a second end of the same stage is left out (None)."""
        with self.lock:
            name = row['stage']
            if name in self.ended_stages or self.finished: return None
            self._flush(name)
            self.ended_stages.add(name)
            if self.current == name: self.current, self.programs = None, []
            fields = {'stage': name, 'status': row['status'], 'reason': row['reason'], 'seconds': row['seconds'],
                      'necessity': row['necessity'], 'artifacts': list(row['artifacts']), 'detail': _small(row.get('detail'))}
            if row.get('reason_code'): fields['reason_code'] = row['reason_code']
            return self.emit('stage.ended', **fields, **extra)

    def finish(self, status, reason='', seconds=None, counts=None):
        """`run.ended`, after ending every declared stage that has no end yet: the one running is `failed`, the ones
        never reached are `not_reached`, each with the reason the run ended. A second call is left out (None)."""
        with self.lock:
            if self.finished: return None
            why = (reason or status)[:200]
            for name, necessity in self.declared.items():
                if name in self.ended_stages: continue
                if name == self.current:
                    self.ended({'stage': name, 'status': 'failed', 'reason': f'the run ended ({status}) while this stage ran: {why}',
                                'reason_code': 'run_ended', 'seconds': round(self.clock() - self.stage_began, 2),
                                'necessity': necessity, 'artifacts': []})
                else:
                    self.ended({'stage': name, 'status': 'not_reached', 'reason': f'the run ended ({status}) before this stage: {why}',
                                'reason_code': 'run_ended', 'seconds': 0.0, 'necessity': necessity, 'artifacts': []})
            fields = {'status': status}
            if reason: fields['reason'] = reason[:300]
            if seconds is not None: fields['seconds'] = seconds
            if counts is not None: fields['counts'] = counts
            row = self.emit('run.ended', **fields)
            if not self.broken and self.enabled: keep(self.path, self.folder, self.flow)
            return row

    def close(self):
        """Stop the background thread without ending the run (a reader will judge it by its silence)."""
        self.stop.set()

    # the background thread

    def tick(self):
        """One beat: flush the coalesced steps whose window passed, look at the running programs when due, and write
        `run.alive` after ALIVE_EVERY seconds of silence. False once the run is over or the file cannot be written."""
        with self.lock:
            if self.finished or self.broken: return False
            self._flush()
            stage = self.current
            due = bool(stage and self.sampler and not self.sampler_said and self.clock() - self.sampled_at >= SAMPLE_EVERY)
        if due: self._look(stage)
        with self.lock:
            if self.finished or self.broken: return False
            if self.clock() - self.wrote_at >= self.alive_every: self.emit('run.alive')
        return True

    def _look(self, stage):
        """The running programs of `stage`, written when they changed (or once why they cannot be seen)."""
        found = self.sampler.sample()                   # outside the lock: ps takes a moment
        with self.lock:
            if self.current != stage or self.finished: return
            self.sampled_at = self.clock()
            if found is None:
                self.sampler_said = True
                self.emit('stage.activity', stage=stage, programs=[], reason=self.sampler.reason)
            elif [(p['pid'], p['name']) for p in found] != [(p['pid'], p['name']) for p in self.programs]:
                self.programs = found
                self.emit('stage.activity', stage=stage, programs=found)

    def _beat(self):
        while not self.stop.wait(TICK):
            try:
                if not self.tick(): return
            except Exception:                           # the heartbeat must never take the run with it
                return

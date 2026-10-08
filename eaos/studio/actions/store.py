"""Where the command centre keeps its runs: on disk, so a run outlives the server, the tab and a restart.

    ~/.eaos/projects/<project>/runs/
        queue.json                  the order of the queued runs (the person may change it)
        dispatch.lock               held by the one server that starts runs for this project
        <run>/run.json              the run: action, verb, selection, state, attempt, session, result, question
        <run>/events.jsonl          its events, append-only, hash-chained (the envelope of D-platform 2.5)
        <run>/stream.jsonl          the assistant's raw output, which a restarted server can go on reading
        <run>/stderr.log            the assistant's error output, shown only in part

A run's events carry a gapless `seq` (the SSE id), and each its `prev` and `hash` = sha256(prev + canonical JSON of
the event without `hash`), so a reader can tell a log that was edited. Nothing secret is written: every string goes
through `scrub` first.
"""
import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

ZERO = '0' * 64
STATES = ('queued', 'running', 'paused', 'waiting_for_person', 'done', 'failed', 'stopped')
TERMINAL = ('done', 'failed', 'stopped')
ACTIVE = ('running', 'paused', 'waiting_for_person')
DIFF_LIMIT = 64 * 1024
SECRET = re.compile(r'(sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}'
                    r'|AKIA[0-9A-Z]{16}|xox[abpr]-[A-Za-z0-9-]{10,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'
                    r'|(?i:bearer)\s+[A-Za-z0-9._~+/-]{16,}=*|-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----)')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


class Scrubber:
    """Strings as they may be shown and stored: no secret, no home folder, the project as `.`."""

    def __init__(self, project, extra=()):
        self.project = str(Path(project).resolve())
        self.home = str(Path.home())
        self.extra = [value for value in extra if value]

    def __call__(self, value):
        if isinstance(value, str):
            for secret in self.extra: value = value.replace(secret, '[hidden]')
            value = SECRET.sub('[hidden]', value)
            value = value.replace(self.project + os.sep, '').replace(self.project, '.')
            return value.replace(self.home, '~') if len(self.home) > 1 else value
        if isinstance(value, dict): return {key: self(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)): return [self(item) for item in value]
        return value


def _write_json(path, data):
    path.parent.mkdir(exist_ok=True)                  # a run's folder, never the runs folder: a deleted project stays deleted
    temporary = path.with_name(path.name + f'.{os.getpid()}.{threading.get_ident()}.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    temporary.replace(path)


def _read_json(path, default=None):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


class Store:
    """The runs of one project, their events and the queue. Thread-safe within one process; across processes the
    dispatcher lock (`dispatch.lock`) keeps a single writer of states, and events are appended under a file lock."""

    def __init__(self, folder, scrub):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.scrub = scrub
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)

    # runs
    def path(self, run):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', str(run or '')): raise KeyError(run)
        return self.folder / run

    def load(self, run):
        data = _read_json(self.path(run) / 'run.json')
        if not data: raise KeyError(run)
        return data

    def save(self, record):
        with self.lock:
            record['updated'] = now()
            _write_json(self.path(record['id']) / 'run.json', record)
            self.changed.notify_all()
        return record

    def update(self, run, **fields):
        with self.lock:
            record = self.load(run)
            record.update(fields)
            return self.save(record)

    def all(self):
        rows = []
        for path in self.folder.glob('*/run.json'):
            data = _read_json(path)
            if data: rows.append(data)
        return sorted(rows, key=lambda row: row.get('created') or '', reverse=True)

    # the queue
    def queue(self):
        order = _read_json(self.folder / 'queue.json', []) or []
        queued = {row['id']: row for row in self.all() if row.get('state') == 'queued'}
        known = [run for run in order if run in queued]
        rest = sorted((run for run in queued if run not in known), key=lambda run: queued[run].get('queued_at') or '')
        return known + rest

    def set_queue(self, order):
        with self.lock:
            _write_json(self.folder / 'queue.json', list(order))
            self.changed.notify_all()

    # events
    def events(self, run, after=0):
        path = self.path(run) / 'events.jsonl'
        if not path.is_file(): return []
        out = []
        for line in path.read_text(encoding='utf-8').splitlines():
            try: event = json.loads(line)
            except ValueError: continue
            if event.get('seq', 0) > after: out.append(event)
        return out

    def append(self, run, kind, text, data=None, detail=None):
        """One event, after the last; returns it. `text` is {"en", "ar"} (a plain string stands for both)."""
        import fcntl
        if isinstance(text, str): text = {'en': text, 'ar': text}
        data = data or {}
        if kind == 'edit' and len(data.get('diff') or '') > DIFF_LIMIT:
            data = {**data, 'diff': data['diff'][:DIFF_LIMIT] + '\n[the rest of the diff is cut]', 'cut': True}
        with self.lock:
            path = self.path(run) / 'events.jsonl'
            path.parent.mkdir(exist_ok=True)
            with path.open('a+', encoding='utf-8') as out:
                fcntl.flock(out, fcntl.LOCK_EX)
                out.seek(0)
                lines = [line for line in out.read().splitlines() if line.strip()]
                last = json.loads(lines[-1]) if lines else {'seq': 0, 'hash': ZERO}
                event = {'seq': last['seq'] + 1, 'id': f"{run}-{last['seq'] + 1}", 'run': run, 'at': now(), 'kind': kind,
                         'text': self.scrub(text), 'data': self.scrub(data), 'detail': self.scrub(detail), 'prev': last['hash']}
                event['hash'] = hashlib.sha256((event['prev'] + canonical(event)).encode('utf-8')).hexdigest()
                out.write(json.dumps(event, ensure_ascii=False) + '\n')
                out.flush()
                fcntl.flock(out, fcntl.LOCK_UN)
            self.changed.notify_all()
            return event

    def verify(self, run):
        """Problems with the run's hash chain: [] when every event follows the one before it unchanged."""
        problems, prev = [], ZERO
        for index, event in enumerate(self.events(run), 1):
            body = {key: value for key, value in event.items() if key != 'hash'}
            if event.get('seq') != index: problems.append(f'event {index}: seq {event.get("seq")}')
            if event.get('prev') != prev: problems.append(f'event {index}: prev does not match')
            if hashlib.sha256((prev + canonical(body)).encode('utf-8')).hexdigest() != event.get('hash'):
                problems.append(f'event {index}: hash does not match')
            prev = event.get('hash')
        return problems

    def wait_change(self, timeout):
        with self.changed:
            self.changed.wait(timeout)

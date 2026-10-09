"""The live feed: what changed in a project's Studio data, as numbered events a stream replays from any point.

The source is the project's event log (`events.jsonl`, NS39.T2) when it exists. Until that log is written, the feed
watches the Studio manifest (studio/manifest.json, written last by eaos/studio/export.py, so a new digest means a
whole new set) and names what changed by comparing the sections before and after:

    scan.done           the manifest's scan (its commit or time) changed: a new check landed
    batch.delivered     cards moved to in_batch or on_branch: a batch of fixes is on its branch
    branch.merged       cards moved to done: a batch was taken into the person's branch
    decision.asked      a decision is waiting that was not
    decision.answered   a decision that was waiting is not any more
    studio.updated      sections changed with none of the above (a new EAOS, a rebuilt report)

Every event says its source (`manifest` or `events`) and the sections whose digest changed, so the Studio reloads
only those. The numbers (`seq`) only grow; an event's id is `<epoch>-<seq>`, where the epoch is made per feed, so a
client that reconnects with a Last-Event-ID from an earlier server is told to reload everything (`reset`) instead of
being replayed someone else's numbers. The feed keeps the last `KEEP` events; an older id also gets a reset.

The action API (docs/studio-actions.json) publishes its own events through `publish`, into the same numbering.

Beside either source, the feed tails the running check's progress file (`run-progress.jsonl`, eaos/progress/log.py)
and publishes each new line as one `scan.stage` event whose data is the line itself, into the same numbering and the
same replay. It reads the file, not a process, so a check started from the terminal, the assistant or the Studio is
followed alike. What the file held when the feed started is the state the server starts from, not an event: a page
reads it whole from /api/scan-progress (read.py) and then applies the events after it. A new run replaces the file;
the feed sees the new inode and reads the new file from its start.
"""
import json
import secrets
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from ..progress import PROGRESS

KEEP = 2000
EVENT_LOG = 'events.jsonl'
TEXT = {
    'scan.done': ('A new check landed', 'وصل فحص جديد'),
    'batch.delivered': ('A batch of fixes is on its branch', 'دفعة إصلاحات جاهزة على فرعها'),
    'branch.merged': ('Fixes were taken into your branch', 'دخلت الإصلاحات فرعك'),
    'decision.asked': ('A decision is waiting for you', 'قرار ينتظرك'),
    'decision.answered': ('A decision was answered', 'تمت الإجابة على قرار'),
    'studio.updated': ('The Studio data was updated', 'تحدّثت بيانات الاستوديو'),
    'scan.stage': ('The check moved on', 'تقدّم الفحص'),
}
STEP_TEXT = {
    'run.started': ('The check started', 'بدأ الفحص'),
    'stage.started': ('Stage {stage} started', 'بدأت مرحلة {stage}'),
    'stage.step': ('{stage}: {step}', '{stage}: {step}'),
    'stage.activity': ('{stage}: programs running', '{stage}: البرامج الشغّالة'),
    'run.alive': ('The check is still running', 'الفحص ما زال شغّالًا'),
    'stage.ended': ('Stage {stage}: {status}', 'مرحلة {stage}: {status}'),
    'run.ended': ('The check ended: {status}', 'انتهى الفحص: {status}'),
}
BATCH, MERGED = {'in_batch', 'on_branch'}, {'done'}


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def _read(path):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


class Feed:
    def __init__(self, report, keep=KEEP):
        self.report = Path(report)
        self.folder = self.report / 'studio'
        self.epoch = secrets.token_hex(4)
        self.seq = 0
        self.events = deque(maxlen=keep)
        self.lock = threading.Lock()
        self.seen = None            # what the manifest said last time: digest, scan, sections, card and decision states
        self.log_at = 0             # bytes of events.jsonl already read
        self.source = 'events' if self.event_log().is_file() else 'manifest'
        # the progress file as it is now is the starting state (read whole by /api/scan-progress), not events
        self.progress_inode, self.progress_at = self._progress_stat()

    # ------------------------------------------------------------------ reading
    def event_log(self):
        return self.report / EVENT_LOG

    def last_id(self):
        with self.lock:
            return f'{self.epoch}-{self.seq}'

    def since(self, last_id):
        """(events after `last_id`, reset): reset is True when the id is not this feed's or is older than it keeps."""
        with self.lock:
            events = list(self.events)
            if not last_id: return [], False
            epoch, _, number = str(last_id).rpartition('-')
            if epoch != self.epoch or not number.isdigit() or int(number) > self.seq: return [], True
            after = int(number)
            if after < self.seq and (not events or events[0]['seq'] > after + 1): return [], True
            return [e for e in events if e['seq'] > after], False

    # ------------------------------------------------------------------ writing
    def publish(self, kind, data=None, text=None, source='action', sections=()):
        """Add one event and return it. `text` is {en, ar}; known kinds have their own."""
        en, ar = TEXT.get(kind, (kind, kind))
        with self.lock:
            self.seq += 1
            event = {'seq': self.seq, 'id': f'{self.epoch}-{self.seq}', 'at': now(), 'kind': kind, 'source': source,
                     'sections': sorted(sections), 'text': text or {'en': en, 'ar': ar}, 'data': data or {}}
            self.events.append(event)
            return event

    # ------------------------------------------------------------------ watching
    def poll(self):
        """Look once for what changed and publish it; returns the events added. Safe to call from any thread."""
        progress = self._poll_progress()
        if self.event_log().is_file():
            self.source = 'events'
            return progress + self._poll_log()
        self.source = 'manifest'
        return progress + self._poll_manifest()

    def progress_file(self):
        return self.report / PROGRESS

    def _progress_stat(self):
        try: found = self.progress_file().stat()
        except OSError: return None, 0
        return found.st_ino, found.st_size

    def _poll_progress(self):
        inode, size = self._progress_stat()
        if inode is None: return []
        if inode != self.progress_inode or size < self.progress_at:      # a new run: its file from the start
            self.progress_inode, self.progress_at = inode, 0
        if size == self.progress_at: return []
        try:
            with self.progress_file().open('rb') as handle:
                handle.seek(self.progress_at)
                chunk = handle.read()
        except OSError:
            return []
        complete = chunk[:chunk.rfind(b'\n') + 1]       # a line still being written waits for the next look
        self.progress_at += len(complete)
        added = []
        for line in complete.decode('utf-8', 'replace').splitlines():
            try: row = json.loads(line)
            except ValueError: continue
            if not isinstance(row, dict) or not row.get('event'): continue
            en, ar = STEP_TEXT.get(row['event'], (row['event'], row['event']))
            words = {k: row.get(k, '') for k in ('stage', 'step', 'status')}
            added.append(self.publish('scan.stage', data=row, source='progress',
                                      text={'en': en.format(**words), 'ar': ar.format(**words)}))
        return added

    def _poll_log(self):
        added = []
        try:
            with self.event_log().open('rb') as handle:
                handle.seek(self.log_at)
                chunk = handle.read()
        except OSError:
            return added
        complete = chunk[:chunk.rfind(b'\n') + 1]       # a line still being written waits for the next look
        self.log_at += len(complete)
        for line in complete.decode('utf-8', 'replace').splitlines():
            try: row = json.loads(line)
            except ValueError: continue
            if not isinstance(row, dict): continue
            added.append(self.publish(str(row.get('kind') or row.get('type') or 'event'), data=row, source='events'))
        self._poll_manifest(quiet=True)                 # the manifest still tells the Studio which sections to reload
        return added

    def snapshot(self):
        manifest = _read(self.folder / 'manifest.json')
        if not isinstance(manifest, dict) or not isinstance(manifest.get('sections'), list): return None
        sections = {s.get('name'): s.get('sha256') for s in manifest['sections'] if isinstance(s, dict)}
        before = self.seen or {}
        def states(name, key):
            if before.get('sections', {}).get(name) == sections.get(name) and name in before.get('states', {}):
                return before['states'][name]
            body = _read(self.folder / f'{name}.json') if name in sections else None
            rows = (body or {}).get(key) if isinstance(body, dict) else None
            return {str(r.get('id')): r.get('state') for r in rows or [] if isinstance(r, dict)}
        return {'digest': '|'.join(f'{k}:{v}' for k, v in sorted(sections.items(), key=lambda kv: str(kv[0]))),
                'scan': manifest.get('scanned'), 'sections': sections,
                'states': {'cards': states('cards', 'cards'), 'decisions': states('decisions', 'decisions')}}

    def _poll_manifest(self, quiet=False):
        current = self.snapshot()
        if current is None: return []
        before, self.seen = self.seen, current
        if before is None or before['digest'] == current['digest'] or quiet: return []
        changed = sorted({*before['sections'], *current['sections']} - {
            name for name in current['sections'] if before['sections'].get(name) == current['sections'][name]})
        events = []
        if before['scan'] != current['scan']:
            events.append(('scan.done', {'scanned': current['scan']}))
        cards_then, cards_now = before['states']['cards'], current['states']['cards']
        moved = {cid: (cards_then.get(cid), state) for cid, state in cards_now.items() if cards_then.get(cid) != state}
        batch = sorted(c for c, (was, state) in moved.items() if state in BATCH and was not in BATCH)
        merged = sorted(c for c, (was, state) in moved.items() if state in MERGED and was not in MERGED)
        if batch: events.append(('batch.delivered', {'cards': batch[:500], 'count': len(batch)}))
        if merged: events.append(('branch.merged', {'cards': merged[:500], 'count': len(merged)}))
        waiting = lambda states: {d for d, state in states.items() if state == 'waiting'}
        asked = sorted(waiting(current['states']['decisions']) - waiting(before['states']['decisions']))
        answered = sorted(waiting(before['states']['decisions']) - waiting(current['states']['decisions']))
        if asked: events.append(('decision.asked', {'decisions': asked}))
        if answered: events.append(('decision.answered', {'decisions': answered}))
        if not events: events.append(('studio.updated', {}))
        return [self.publish(kind, data=data, source='manifest', sections=changed) for kind, data in events]

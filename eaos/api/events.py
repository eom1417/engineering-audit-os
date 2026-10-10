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

Beside either source, the feed tails every progress file (eaos/progress/log.py): the check's (`run-progress.jsonl`
in the report) and each other flow's (`<runtime>/progress/<flow>.jsonl`: setting up, recording the screens, fixing).
The install of the tools (`<tools home>/progress/tools.jsonl`) is tailed the same way.
Each new line is published as one `progress` event whose data is the line itself plus its `flow`, into the same
numbering and the same replay. It reads files, not processes, so work started from the terminal, the assistant or the
Studio is followed alike. What the files held when the feed started is the state the server starts from, not events:
a page reads it whole from /api/progress (read.py) and then applies the events after it. A new run replaces its file;
the feed sees the new inode, or a file it did not know, and reads it from its start.
"""
import json
import secrets
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from .. import toolchain
from ..progress import PROGRESS, path_for
from ..progress.log import FOLDER

KEEP = 2000
EVENT_LOG = 'events.jsonl'
TEXT = {
    'scan.done': ('A new check landed', 'وصل فحص جديد'),
    'batch.delivered': ('A batch of fixes is on its branch', 'دفعة إصلاحات جاهزة على فرعها'),
    'branch.merged': ('Fixes were taken into your branch', 'دخلت الإصلاحات فرعك'),
    'decision.asked': ('A decision is waiting for you', 'قرار ينتظرك'),
    'decision.answered': ('A decision was answered', 'تمت الإجابة على قرار'),
    'studio.updated': ('The Studio data was updated', 'تحدّثت بيانات الاستوديو'),
    'progress': ('The work moved on', 'تقدّم العمل'),
}
FLOW_TEXT = {'check': ('The check', 'الفحص'), 'setup': ('Setting up your app', 'تجهيز برنامجك'),
             'safety': ('Recording the screens', 'تصوير الشاشات'), 'fix': ('The fix', 'الإصلاح'),
             'tools': ('Preparing the tools', 'تجهيز الأدوات')}
STEP_TEXT = {
    'run.started': ('{flow} started', 'بدأ {flow}'),
    'stage.started': ('Stage {stage} started', 'بدأت مرحلة {stage}'),
    'stage.step': ('{stage}: {step}', '{stage}: {step}'),
    'stage.activity': ('{stage}: programs running', '{stage}: البرامج الشغّالة'),
    'run.alive': ('{flow} is still running', '{flow} ما زال شغّالًا'),
    'stage.ended': ('Stage {stage}: {status}', 'مرحلة {stage}: {status}'),
    'run.ended': ('{flow} ended: {status}', 'انتهى {flow}: {status}'),
}
BATCH, MERGED = {'in_batch', 'on_branch'}, {'done'}


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def _stat(path):
    """(inode, size) of a file, or (None, 0) when it is not there."""
    try: found = path.stat()
    except OSError: return None, 0
    return found.st_ino, found.st_size


def _rows(chunk):
    """The progress events in whole lines of bytes; a line that is not one is left out."""
    rows = []
    for line in chunk.decode('utf-8', 'replace').splitlines():
        try: row = json.loads(line)
        except ValueError: continue
        if isinstance(row, dict) and row.get('event'): rows.append(row)
    return rows


def _read(path):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


class Feed:
    def __init__(self, report, keep=KEEP, runtime=None):
        self.report = Path(report)
        self.runtime = Path(runtime) if runtime else None
        self.folder = self.report / 'studio'
        self.epoch = secrets.token_hex(4)
        self.seq = 0
        self.events = deque(maxlen=keep)
        self.lock = threading.Lock()
        self.seen = None            # what the manifest said last time: digest, scan, sections, card and decision states
        self.log_at = 0             # bytes of events.jsonl already read
        self.source = 'events' if self.event_log().is_file() else 'manifest'
        # the progress files as they are now are the starting state (read whole by /api/progress), not events
        self.tails = {path: _stat(path) for _, path in self.progress_files()}

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

    def progress_files(self):
        """(flow, path) of every progress file: the check's, each other flow's in the runtime folder, and the install of
        the tools, shared by every project on this computer (eaos/toolchain.py)."""
        files = [('check', self.report / PROGRESS)]
        if self.runtime: files += [(path.stem, path) for path in sorted((self.runtime / FOLDER).glob('*.jsonl'))]
        return files + [(toolchain.FLOW, path_for(toolchain.home(), toolchain.FLOW))]

    def _poll_progress(self):
        return [event for flow, path in self.progress_files() for event in self._tail(flow, path)]

    def _tail(self, flow, path):
        inode, size = _stat(path)
        if inode is None: return []
        known, at = self.tails.get(path, (None, 0))
        if inode != known or size < at: at = 0         # a new run, or a file that appeared since: from its start
        self.tails[path] = (inode, at)
        if size == at: return []
        try:
            with path.open('rb') as handle:
                handle.seek(at)
                chunk = handle.read()
        except OSError:
            return []
        complete = chunk[:chunk.rfind(b'\n') + 1]       # a line still being written waits for the next look
        self.tails[path] = (inode, at + len(complete))
        return [self._publish_progress(flow, row) for row in _rows(complete)]

    def _publish_progress(self, flow, row):
        en, ar = STEP_TEXT.get(row['event'], (row['event'], row['event']))
        words = {k: row.get(k, '') for k in ('stage', 'step', 'status')}
        named = FLOW_TEXT.get(flow, (flow, flow))
        return self.publish('progress', data={**row, 'flow': flow}, source='progress',
                            text={'en': en.format(flow=named[0], **words), 'ar': ar.format(flow=named[1], **words)})

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

"""The assistant handoff: a run for which no assistant can be started here (docs/studio-actions.json `assistants`).

The request waits in the project's EAOS workspace (`studio-requests.json`, never inside the project). The next `status`
call of any assistant returns it (eaos/mcp_server.py), which marks it taken; the assistant closes it with a `note` that
starts with `studio-request <id> done`. The Studio also shows the request as text to copy, for an assistant that is not
connected to EAOS at all.
"""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

_lock = threading.Lock()
DONE = 'studio-request {id} done'


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _path(project):
    from ... import guided
    return guided.workspace(Path(project).resolve()) / 'studio-requests.json'


def _read(project):
    try: return json.loads(_path(project).read_text(encoding='utf-8'))
    except (OSError, ValueError): return []


def _write(project, rows, create=False):
    path = _path(project)
    if create: path.parent.mkdir(parents=True, exist_ok=True)
    elif not path.parent.is_dir(): return                 # the project's workspace is gone: nothing to update
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    temporary.replace(path)


def request_text(prompt, run):
    """What the person copies to an assistant, and what `status` hands over: the run's prompt and how to close it."""
    close = DONE.format(id=run)
    return {'en': f'{prompt}\n\nWhen you are done, call the eaos `note` tool with a text that starts with "{close}:" and says what you did.',
            'ar': f'{prompt}\n\nلما تخلص، استدعِ أداة eaos `note` بنص يبدأ بـ "{close}:" ويقول وش سويت.'}


def add(project, run, prompt, label):
    with _lock:
        rows = [row for row in _read(project) if row.get('run') != run]
        rows.append({'id': run, 'run': run, 'label': label, 'request': request_text(prompt, run), 'state': 'waiting',
                     'created': _now(), 'taken_by': None, 'taken_at': None, 'done': None})
        _write(project, rows, create=True)


def exists(project):
    return _path(project).is_file()


def pending(project):
    """The requests no assistant has taken yet."""
    return [row for row in _read(project) if row.get('state') == 'waiting']


def get(project, run):
    return next((row for row in _read(project) if row.get('run') == run), None)


def take(project, by):
    """The oldest waiting request, now marked taken by `by` (the `status` tool's part of the handoff); None if none."""
    with _lock:
        rows = _read(project)
        row = next((r for r in rows if r.get('state') == 'waiting'), None)
        if row is None: return None
        row.update(state='taken', taken_by=by, taken_at=_now())
        _write(project, rows)
        return row


def close(project, text):
    """A note that closes a request (`studio-request <id> done: ...`): returns the run id it closed, or None."""
    with _lock:
        rows = _read(project)
        for row in rows:
            if row.get('state') in ('waiting', 'taken') and str(text or '').strip().startswith(DONE.format(id=row['id'])):
                row.update(state='done', done=str(text)[len(DONE.format(id=row['id'])):].lstrip(' :')[:4000], closed_at=_now())
                _write(project, rows)
                return row['run']
    return None


def drop(project, run):
    with _lock:
        _write(project, [row for row in _read(project) if row.get('run') != run])


def for_status(project, by):
    """What `status` adds for the assistant: the request it now takes, in the words it needs; {} when none waits."""
    try: row = take(project, by)
    except Exception: return {}
    if not row: return {}
    return {'studio_request': {'id': row['id'], 'label': row['label'], 'request': row['request']['en'],
                               'what_now': 'The person asked for this from the EAOS Studio: do it now, before anything else, then close it with note as it says.'}}

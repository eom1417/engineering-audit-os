"""The person's sign-in to the app EAOS checks: whether its pages need one, the one session every page stage opens them
with, and the check waiting for the person to sign in by hand (docs/GUIDE.md "Signing in to your app").

    session(runtime)           <runtime>/session.json: the run's one browser session (Playwright storage state), made by
                               the seed script (a test user) or by the person on the sign-in page (by_hand); only its
                               owner reads it, and nothing copies it into the report, a branch or what the assistant reads
    from_code(report)          the sign-in the code shows (the surfaces of its `auth` feature, eaos/features.py)
    from_pages(page)           the pages a probe (eaos/live_setup.py probe) saw sent to a sign-in, with where they went
    works(live, base, state)   whether `state` opens those pages signed in
    ask / asked / wait         the check asks the person to sign in (<workspace>/sign-in.json) and waits for them while
                               the stages that open no page go on; the sign-in page (eaos/api/sign_in.py, the Studio's
                               Waiting for you, `eaos sign-in`) answers it
    renew(live, base, state)   a session made by hand checked before use; the person asked again only when it expired
    forget(workspace)          the project's sessions removed (Forget my sign-in, eaos clean)
"""
import json
import os
import re
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

SESSION = 'session.json'                     # in the run's folder: the session of the app in its isolated copy
PUBLISHED = 'published-session.json'         # in the project's workspace: the published address's, for one check only
ASKED = 'sign-in.json'                       # in the project's workspace: the check waits for the person to sign in
WAIT = int(os.environ.get('EAOS_SIGN_IN_WAIT') or 900)   # seconds the check waits for the person before going on signed out
SIGNED_IN, SIGNED_OUT = 'signed_in', 'signed_out'


def session(runtime):
    return Path(runtime) / SESSION


def _write(path, record):
    """`record` as JSON readable by its owner only, written whole or not at all."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.tmp')
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w', encoding='utf-8') as out:
        json.dump(record, out, ensure_ascii=False)
    os.replace(temporary, path)


def _read(path):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


def by_hand(state):
    """Whether the session file was saved by the person on the sign-in page (never replaced by a seed script's)."""
    return bool(((_read(state) or {}).get('eaos') or {}).get('by') == 'hand')


def seeding(state):
    """The file a seed script signs in to: the run's session itself, or, the person's being theirs, a copy of it that
    the script switches into each view (eaos/test_users.py BY_HAND); the caller removes the copy after the seed."""
    if not by_hand(state): return state
    copy = state.with_name('.seeded.json')
    shutil.copyfile(state, copy)
    copy.chmod(0o600)                                    # a signed-in session: its owner's alone
    return copy


def mark(state):
    """The session the browser just saved, marked as the person's and made readable by its owner only."""
    record = _read(state) or {}
    _write(state, {**record, 'eaos': {'by': 'hand', 'at': datetime.now(timezone.utc).isoformat(timespec='seconds')}})


def from_code(report):
    """The routes of the code's sign-in feature (eaos/features.py groups login, signin, auth... as `auth`)."""
    features = (_read(Path(report) / 'features.json') or {}).get('features') or []
    return [f'{surface}: a sign-in route of the code' for feature in features if feature.get('name') == 'auth'
            for surface in (feature.get('surfaces') or [])[:5]]


def from_pages(page):
    """Each page the probe saw sent to a sign-in, or showing a password field, with where it went."""
    from .live_setup import signed_out
    seen = [page, *(page.get('others') or [])] if page else []
    return [f"{row.get('path') or '/'} showed the sign-in page {row.get('url')}" for row in seen if signed_out(row)]


def page_of(page, base):
    """The sign-in page the probe's pages were sent to, at `base` (the app's address this run), else `base` itself."""
    from urllib.parse import urlsplit
    from .live_setup import signed_out
    sent = next((row.get('url') for row in ([page, *(page.get('others') or [])] if page else []) if signed_out(row) and row.get('url')), None)
    if not sent: return base
    parts = urlsplit(sent)
    return base.rstrip('/') + parts.path + (f'?{parts.query}' if parts.query else '')


def works(live, base, state, report=None):
    """Whether the session `state` opens the app's first page and a few screens without being sent to a sign-in."""
    from .live_setup import probe
    if not Path(state).is_file(): return False
    page = probe(live, base, Path(state), report)
    return 200 <= (page.get('status') or 0) < 400 and not from_pages(page)


# ---------------------------------------------------------------- the check asks, the person answers

def ask(workspace, base, state, why, log=None, mail=None, published=False):
    """The check asks the person to sign in to the app at `base`; the browser of the sign-in page saves to `state`."""
    now = datetime.now(timezone.utc)
    _write(Path(workspace) / ASKED, {'asked': now.isoformat(timespec='seconds'), 'until': (now + timedelta(seconds=WAIT)).isoformat(timespec='seconds'),
                                     'base': base, 'session': str(state), 'why': why, 'log': str(log) if log else None, 'mail': mail,
                                     'published': published, 'state': 'waiting'})


def asked(workspace):
    """What the check asks the person now, or None (nothing asked, answered, or no longer waited for)."""
    record = _read(Path(workspace) / ASKED)
    if not record or record.get('state') != 'waiting' or record['until'] < datetime.now(timezone.utc).isoformat(timespec='seconds'): return None
    return record


def answer(workspace, outcome):
    """The person's answer: SIGNED_IN once the browser saved the session, SIGNED_OUT to go on without signing in."""
    record = asked(workspace)
    if record is None: raise LookupError('the check does not wait for a sign-in now')
    if outcome == SIGNED_IN: mark(record['session'])
    _write(Path(workspace) / ASKED, {**record, 'state': outcome})
    return record


def wait(workspace, seconds=None):
    """SIGNED_IN, SIGNED_OUT (the person said so) or 'timeout'; the question is removed either way. A stopped check
    stops waiting (assistants.command.check_cancelled)."""
    from . import progress
    from .assistants.command import check_cancelled
    path, end = Path(workspace) / ASKED, time.monotonic() + (WAIT if seconds is None else seconds)
    progress.step('your sign-in', 0, 1, 'waiting', reason='waiting for you to sign in to the app: the Studio\'s Waiting for you, '
                  'or eaos sign-in', reason_code='sign_in_waiting')
    try:
        while time.monotonic() < end:
            check_cancelled()
            outcome = (_read(path) or {}).get('state')
            if outcome in (SIGNED_IN, SIGNED_OUT): return outcome
            time.sleep(1)
        return 'timeout'
    finally:
        path.unlink(missing_ok=True)


def renew(live, base, state, report=None, workspace=None):
    """A session saved by hand, checked before a stage or a batch opens pages with it: kept when it works, else the
    person is asked once to sign in again and waited for. True when it works now."""
    if not by_hand(state): return Path(state).is_file()
    if works(live, base, state, report): return True
    workspace = workspace or Path(live.runtime).parent
    ask(workspace, base, state, 'expired', log=service_log(live), mail=live.mail())
    return wait(workspace) == SIGNED_IN and works(live, base, state, report)


def lend(live, base, target):
    """The person's session in place of `target` (the lock's browser state) when one was saved by hand and still works
    (renewed when it expired): the lock and the screens before and after a fix open the pages signed in as they do."""
    state = session(live.runtime)
    if by_hand(state) and renew(live, base, state):
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_bytes(Path(state).read_bytes())


def service_log(live):
    """The file the running app writes its output to (where a development sign-in prints its code)."""
    started = getattr(getattr(live, 'sandbox', None), 'started', None)
    return started[0][3].name if started else None


def codes(record, lines=40):
    """What the app sent the person while they sign in: the last lines of its own output, and the mail it sent to the
    run's mail catcher (Mailpit), newest first. Nothing typed on the sign-in page is ever kept."""
    said = []
    try: said = Path(record['log']).read_text(encoding='utf-8', errors='replace').splitlines()[-lines:] if record.get('log') else []
    except OSError: pass
    return {'output': [line for line in said if line.strip()], 'mail': _mail(record.get('mail'))}


def _mail(address):
    """The newest mails Mailpit caught (its API at `address`): who to, the subject and the text."""
    if not address: return []
    import urllib.request
    try:
        with urllib.request.urlopen(f'{address}/api/v1/messages?limit=5', timeout=3) as response: listed = json.loads(response.read())
        found = []
        for row in listed.get('messages') or []:
            with urllib.request.urlopen(f"{address}/api/v1/message/{row['ID']}", timeout=3) as response: whole = json.loads(response.read())
            found.append({'to': ', '.join(t.get('Address', '') for t in whole.get('To') or []), 'subject': whole.get('Subject'),
                          'text': (whole.get('Text') or '')[:2000], 'at': row.get('Created')})
        return found
    except (OSError, ValueError, KeyError):
        return []


def published(address):
    """The published address the person named, checked: an http(s) address of a site, never this computer."""
    if not address: return None
    match = re.fullmatch(r'(https?)://([A-Za-z0-9.-]+)(:\d+)?(/[^\s]*)?', str(address).strip())
    if not match or match[2] in ('localhost', '127.0.0.1', '0.0.0.0'):
        raise ValueError(f'{address}: a published address is the http(s) address of the site, as people open it')
    return match[0].rstrip('/')


def forget(workspace):
    """The project's sessions (of every branch's run, and the published address's) removed; a check asks again."""
    workspace = Path(workspace)
    found = [*workspace.glob(f'runtime*/{SESSION}'), workspace / PUBLISHED]
    for path in found: path.unlink(missing_ok=True)
    return [str(path) for path in found]


def step(state, otherwise):
    """For the assistant's status while a job runs: ('sign_in', why) when the check waits for the person to sign in,
    else `otherwise`."""
    if not asked(state['workspace']): return otherwise
    return ('sign_in', 'the check waits for the person to sign in to their app: tell them to open Waiting for you in the Studio, '
                       'or to run eaos sign-in in a terminal; the stages that open no page go on meanwhile')

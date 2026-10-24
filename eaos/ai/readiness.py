"""Whether the person's AI assistant can really answer, asked before a check counts on it.

`which claude` is not enough: an assistant can be installed and signed out, or signed in with a sign-in that can no
longer be refreshed (Codex: "refresh token was already used"), or not answering at all. So the probe does what the
check will do, on a question of one word:

    1. installed: the command is on the PATH;
    2. it runs: `<command> --version` answers (its first line is the version);
    3. signed in: `claude auth status` / `codex login status`, when the command says it is not;
    4. answering: one tiny real call, with no tool and nothing kept, the same way the check's adapters call it
       (eaos/ai/claude_adapter.py, codex_adapter.py), under a short timeout.

The answer is {id, name, installed, version, ready, code, reason: {ar, en}, command, checked_at, seconds}: `code` is
`<assistant>_<problem>` (`codex_sign_in_expired`), whose words, with how to fix it, are the `reasons` of
eaos/data/errors.json, the same words the live map and the report show for an AI stage that did not run. A result
is cached in ~/.eaos/assistants/readiness.json for a few minutes (`fresh=True` asks again); the cache is keyed by the
command's place and the environment that decides its sign-in (HOME, CLAUDE_CONFIG_DIR, CODEX_HOME), which the probe
inherits as it is and never sets. Only codes, versions and times are written: the probe's raw output can hold an
account, so it never leaves this module.
"""
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone

from ..core.places import home

NAMES = {'claude': 'Claude Code', 'codex': 'Codex'}
TIMEOUT = 30            # seconds the tiny real call may take
QUICK = 15              # seconds for --version and the sign-in status
KEEP_READY = 600        # seconds a ready answer is reused
KEEP_NOT_READY = 60     # seconds a not-ready answer is reused (the person may be fixing it)
QUESTION = 'Reply with the single word: ready'

# What a failed call says, in the assistants' own words, and the problem it means (first match wins).
PATTERNS = (
    ('sign_in_expired', r'refresh token (?:was )?already (?:been )?used|refresh_token_reused|refresh token.{0,40}(?:expired|invalid)'),
    ('not_signed_in', r'not logged in|please run /login|please log ?in|run `?codex login|invalid api key|authentication_error|unauthori[sz]ed|\b401\b'),
    ('limit', r'usage limit|rate limit|(?:session|weekly|daily|opus) limit|hit your (?:\w+ )?limit|limit reached|quota|'
              r'credit balance|too many requests|\b429\b'),
)
# When a spent limit comes back, as the assistant says it ("resets 7:10pm (UTC)", "try again at 5 PM").
RESETS = re.compile(r'(?:resets?|try again)(?: at| in)? ([0-9][0-9:]*\s*(?:[ap]m\b|hours?\b|minutes?\b)?(?:\s*\([A-Za-z0-9+:-]+\))?)', re.IGNORECASE)


class NoAssistant:
    """Falsy stand-in for the check's provider when the assistant's stages do not run, carrying why in a stable code
    (the `reasons` of eaos/data/errors.json) and EAOS's own sentence: the live map and the report say exactly why."""

    def __init__(self, code, reason):
        self.code, self.reason = code, reason

    def __bool__(self):
        return False

    def __repr__(self):
        return f'NoAssistant({self.code!r})'


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def words(code):
    """{ar, en} of `code` from the catalog, or None."""
    from ..core.progress.reasons import reasons
    found = reasons().get(code)
    return {'ar': found.get('ar') or found.get('en'), 'en': found.get('en')} if found else None


def classify(text):
    """The problem a failed call's words mean: sign_in_expired, not_signed_in, limit, or failed."""
    low = str(text or '').lower()
    return next((problem for problem, pattern in PATTERNS if re.search(pattern, low)), 'failed')


def resets_at(text):
    """When a spent usage limit comes back, in the assistant's own words, or None."""
    found = RESETS.search(str(text or ''))
    return found.group(1).strip() if found else None


def _run(argv, timeout, stdin=None, cwd=None):
    """(returncode, stdout, stderr) or (None, '', why) when it could not run or did not end in time: then its whole
    process group is ended, so a child it started cannot hold the probe."""
    try:
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd,
                                   start_new_session=(os.name == 'posix'))
    except (OSError, subprocess.SubprocessError) as problem:
        return None, '', type(problem).__name__
    try:
        out, err = process.communicate(stdin, timeout=timeout)
        return process.returncode, out or '', err or ''
    except subprocess.TimeoutExpired:
        try: os.killpg(process.pid, signal.SIGKILL)
        except OSError: process.kill()
        process.communicate()
        return None, '', 'timeout'


def _claude_status(path):
    code, out, _ = _run([path, 'auth', 'status'], QUICK)
    if code is None: return None
    try: return bool(json.loads(out).get('loggedIn'))
    except (ValueError, AttributeError): return None      # an older CLI without the command: the real call decides


def _codex_status(path):
    code, out, err = _run([path, 'login', 'status'], QUICK)
    if code is None: return None
    if 'not logged in' in (out + err).lower(): return False
    return True if code == 0 else None


def _claude_call(path, timeout):
    """(answered, problem, what it said): the check's way of asking (no tool, no MCP server, nothing kept), on one word."""
    with tempfile.TemporaryDirectory(prefix='eaos-probe-') as empty:
        code, out, err = _run([path, '-p', '--tools', '', '--strict-mcp-config', '--no-session-persistence', '--output-format', 'json',
                               '--system-prompt', 'Answer in one word.', QUESTION], timeout, cwd=empty)
    if code is None: return False, 'no_answer' if err == 'timeout' else 'failed', ''
    try: envelope = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
    except ValueError: envelope = {}
    if code == 0 and isinstance(envelope, dict) and not envelope.get('is_error') and str(envelope.get('result') or '').strip():
        return True, None, ''
    said = (str(envelope.get('result') or '') if isinstance(envelope, dict) else '') + '\n' + out + '\n' + err
    return False, classify(said), said


def _codex_call(path, timeout):
    """(answered, problem, what it said): `codex exec` as the check's adapter runs it (read-only, in an empty folder, nothing kept)."""
    with tempfile.TemporaryDirectory(prefix='eaos-probe-') as empty:
        answer = os.path.join(empty, 'answer.txt')
        code, out, err = _run([path, 'exec', '--skip-git-repo-check', '--ephemeral', '--ignore-rules', '--ignore-user-config',
                               '-s', 'read-only', '--color', 'never', '-C', empty, '-o', answer, '-'], timeout, stdin=QUESTION, cwd=empty)
        text = open(answer, encoding='utf-8').read() if os.path.exists(answer) else ''
    if code is None: return False, 'no_answer' if err == 'timeout' else 'failed', ''
    if code == 0 and text.strip(): return True, None, ''
    return False, classify(out + '\n' + err), out + '\n' + err


CHECKS = {'claude': (_claude_status, _claude_call), 'codex': (_codex_status, _codex_call)}


def check(name, timeout=TIMEOUT):
    """The probe itself, never cached: the readiness of assistant `name` (claude or codex) on this computer now."""
    began = time.monotonic()
    row = {'id': name, 'name': NAMES[name], 'installed': False, 'version': None, 'ready': False, 'code': None,
           'command': name, 'checked_at': _now(), 'seconds': 0.0}

    def done(problem=None, said=''):
        row['ready'] = problem is None
        row['code'] = f'{name}_{problem}' if problem else f'{name}_ready'
        row['reason'] = words(row['code'])
        back = resets_at(said) if problem == 'limit' else None
        if back and row['reason']:
            row['resets'] = back
            row['reason'] = {'ar': f"{row['reason']['ar']} يتجدد حدّه: {back}.", 'en': f"{row['reason']['en']} It resets: {back}."}
        row['seconds'] = round(time.monotonic() - began, 1)
        return row

    path = shutil.which(name)
    if not path: return done('not_installed')
    row['installed'] = True
    code, out, err = _run([path, '--version'], QUICK)
    if code != 0: return done('no_answer' if err == 'timeout' else 'not_working')
    row['version'] = (out.strip().splitlines() or [''])[0][:80] or None
    status, call = CHECKS[name]
    if status(path) is False: return done('not_signed_in')
    answered, problem, said = call(path, timeout)
    return done(None if answered else problem, said)


# ---------------------------------------------------------------- the short cache

def _cache_file():
    return home() / 'assistants' / 'readiness.json'


def _key(name):
    """What decides an assistant's readiness here: where its command is and the environment its sign-in lives in."""
    return json.dumps([name, shutil.which(name), *(os.environ.get(v) for v in ('HOME', 'CLAUDE_CONFIG_DIR', 'CODEX_HOME'))])


def _read_cache():
    try: return json.loads(_cache_file().read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}


def cached(name):
    """The last probe of `name` while it still holds, else None."""
    row = _read_cache().get(_key(name))
    if not isinstance(row, dict) or 'at' not in row: return None
    keep = KEEP_READY if row['probe'].get('ready') else KEEP_NOT_READY
    return row['probe'] if time.time() - row['at'] < keep else None


def probe(name, fresh=False, timeout=TIMEOUT):
    """The readiness of `name` (claude or codex), from the short cache unless `fresh`."""
    if name not in NAMES: raise ValueError(f'no assistant named {name}: claude or codex')
    if not fresh:
        found = cached(name)
        if found: return {**found, 'cached': True}
    row = check(name, timeout)
    path = _cache_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path.with_suffix('.lock'), 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)       # one writer at a time, of this process or another: no answer is lost
            saved = _read_cache()
            saved[_key(name)] = {'at': time.time(), 'probe': row}
            temporary = path.with_suffix(f'.{os.getpid()}.tmp')
            temporary.write_text(json.dumps(saved, ensure_ascii=False, indent=1), encoding='utf-8')
            temporary.replace(path)
    except OSError:
        pass                                       # a read-only home: the answer still stands for this call
    return {**row, 'cached': False}


def probe_all(fresh=False, timeout=TIMEOUT, names=None):
    """Every assistant's readiness, probed side by side: [{...}] in the order EAOS prefers them."""
    names = [n for n in (names or NAMES) if n in NAMES]
    out = {}
    threads = [threading.Thread(target=lambda n=n: out.__setitem__(n, probe(n, fresh, timeout)), daemon=True) for n in names]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    return [out[n] for n in names]

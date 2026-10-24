"""Who may talk to a Studio, checked in one place (M3.3) for its server (eaos/interfaces/api/guard.py) and its actions
(docs/studio-actions.json `security`):
- the server listens on 127.0.0.1 only (`LOOPBACK`), or 0.0.0.0 behind one exact Remote origin;
- every request names the server by its Host (127.0.0.1:<port>, localhost:<port>, the Remote one), which defeats DNS
  rebinding; a page outside /api/ is read only;
- every /api/ call carries the launch token in X-EAOS-Token (a run's event stream on the actions' own server, which an
  EventSource opens, may carry it as `token=`); every write also carries X-EAOS-CSRF and comes from the Studio's origin;
- irreversible actions and runs that change code need a confirm token from their preview: single-use, ten minutes,
  bound to the action, the selection and the project.
Every compare is constant-time; a refusal says why, never with the token.
"""
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from urllib.parse import parse_qs, urlsplit

LOOPBACK = '127.0.0.1'
HOSTS = ('127.0.0.1', 'localhost')
TOKEN_HEADER, CSRF_HEADER = 'x-eaos-token', 'x-eaos-csrf'
READS = frozenset({'GET', 'HEAD', 'OPTIONS'})
CONFIRM_SECONDS = 600


def new_token():
    return secrets.token_urlsafe(32)


def same(a, b):
    """Constant-time comparison of two tokens; a missing one never matches."""
    return isinstance(a, str) and isinstance(b, str) and bool(a) and hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))


def header(headers, name):
    """A header by name, any case; headers may be a dict or a list of pairs."""
    pairs = headers.items() if hasattr(headers, 'items') else headers or []
    for key, value in pairs:
        if str(key).lower() == name.lower(): return value
    return None


def _token_of(method, path, headers, query):
    """The launch token a call carries: its header, or with `query` for a GET (an EventSource cannot set headers) `token=`."""
    token = header(headers, TOKEN_HEADER)
    if token is None and query and method == 'GET':
        token = (parse_qs(urlsplit(path).query).get('token') or [None])[0]
    return token


def origins(keys, port):
    return {f'http://{host}:{port}' for host in HOSTS} | ({keys.remote_origin} if getattr(keys, 'remote_origin', None) else set())


def hosts(keys, port):
    """The Host values a Studio answers: this computer on its port, and the Remote address it was given."""
    return {f'{name}:{port}' for name in HOSTS} | ({urlsplit(keys.remote_origin).netloc} if getattr(keys, 'remote_origin', None) else set())


def refusal(keys, method, path, headers, port=None):
    """None when the call may go on, else (status, reason, what to do). `keys` holds the token, the CSRF token, the port
    and the Remote origin (a Locks, or the server's Keys); `port` the one the server listens on when the keys name none."""
    port = getattr(keys, 'port', 0) or port
    if (header(headers, 'Host') or '').strip().lower() not in hosts(keys, port):
        return 421, 'host', 'this server answers only to 127.0.0.1 and localhost'
    if not urlsplit(path).path.startswith('/api/'):
        return None if method in READS else (405, 'method', 'the Studio pages are read only')
    if not same(_token_of(method, path, headers, getattr(keys, 'query_token', False)), keys.token):
        return 401, 'token', 'the launch token is missing or wrong: open the address `eaos studio` printed'
    if method in READS: return None
    if not same(header(headers, CSRF_HEADER), keys.csrf):
        return 403, 'csrf', 'the CSRF token is missing or wrong: reload the Studio'
    if _origin_of(headers) not in origins(keys, port):
        return 403, 'origin', 'the request does not come from this Studio'
    return None


def _origin_of(headers):
    """The page a call comes from: its Origin, else the scheme and host of its Referer; '' when neither says."""
    origin = header(headers, 'Origin')
    if origin: return origin
    parts = urlsplit(header(headers, 'Referer') or '')
    return f'{parts.scheme}://{parts.netloc}' if parts.scheme and parts.netloc else ''


class Locks:
    """The keys of a Studio's actions, and their confirm tokens. `query_token`: the actions' own server, whose event
    streams an EventSource opens with `token=`."""
    query_token = True

    def __init__(self, port, token=None, remote_origin=None):
        self.port = int(port)
        self.remote_origin = remote_origin
        if remote_origin and not re.fullmatch(r'https://[a-z0-9]+(?:-[a-z0-9]+)*--[1-9][0-9]{0,4}\.dev\.remote\.e-m\.sa', remote_origin):
            raise ValueError('remote_origin must be one exact Remote HTTPS project hostname')
        if remote_origin and int(urlsplit(remote_origin).hostname.split('--')[-1].split('.')[0]) != self.port:
            raise ValueError('Remote hostname port must match the listening port')
        self.token = token or new_token()
        self.csrf = new_token()
        self._key = hashlib.sha256(('confirm:' + self.token).encode('utf-8')).digest()
        self._spent = set()
        self._lock = threading.Lock()

    def check(self, method, path, headers):
        """None when the call may go on, else (status, why): the one refusal (`refusal`)."""
        refused = refusal(self, method, path, headers)
        return refused and (refused[0], refused[2])

    # confirm tokens
    def _bound(self, action, selection, project):
        return json.dumps([action, selection, str(project)], sort_keys=True, ensure_ascii=False)

    def confirm(self, action, selection, project):
        expires = int(time.time()) + CONFIRM_SECONDS
        nonce = secrets.token_urlsafe(12)
        mac = hmac.new(self._key, f'{nonce}.{expires}.{self._bound(action, selection, project)}'.encode('utf-8'), 'sha256').hexdigest()
        return {'token': f'{nonce}.{expires}.{mac}', 'expires': expires}

    def spend(self, token, action, selection, project):
        """True once for a valid, unexpired confirm token of this action, selection and project."""
        try: nonce, expires, mac = str(token).split('.')
        except ValueError: return False
        expected = hmac.new(self._key, f'{nonce}.{expires}.{self._bound(action, selection, project)}'.encode('utf-8'), 'sha256').hexdigest()
        if not same(mac, expected) or not expires.isdigit() or int(expires) < time.time(): return False
        with self._lock:
            if nonce in self._spent: return False
            self._spent.add(nonce)
        return True

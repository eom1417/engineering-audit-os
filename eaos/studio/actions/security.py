"""The command centre's locks (docs/studio-actions.json `security`).

The server listens on 127.0.0.1 only. Every call carries the launch token; every POST also carries the CSRF token and
comes from the Studio's own origin; the Host is the loopback one, which defeats DNS rebinding. Irreversible actions and
runs that change code need a confirm token from their preview: single-use, ten minutes, bound to the action, the
selection and the project. Every compare is constant-time.
"""
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from urllib.parse import parse_qs, urlsplit

LOOPBACK = ('127.0.0.1', 'localhost')
CONFIRM_SECONDS = 600


def same(a, b):
    return isinstance(a, str) and isinstance(b, str) and hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))


def header(headers, name):
    """A header by name, any case; headers may be a dict or a list of pairs."""
    pairs = headers.items() if hasattr(headers, 'items') else headers or []
    for key, value in pairs:
        if str(key).lower() == name.lower(): return value
    return None


class Locks:
    def __init__(self, port, token=None, remote_origin=None):
        self.port = int(port)
        self.remote_origin = remote_origin
        if remote_origin and not re.fullmatch(r'https://[a-z0-9]+(?:-[a-z0-9]+)*--[1-9][0-9]{0,4}\.dev\.remote\.e-m\.sa', remote_origin):
            raise ValueError('remote_origin must be one exact Remote HTTPS project hostname')
        if remote_origin and int(urlsplit(remote_origin).hostname.split('--')[-1].split('.')[0]) != self.port:
            raise ValueError('Remote hostname port must match the listening port')
        self.token = token or secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)
        self._key = hashlib.sha256(('confirm:' + self.token).encode('utf-8')).digest()
        self._spent = set()
        self._lock = threading.Lock()

    def origins(self):
        return {f'http://{host}:{self.port}' for host in LOOPBACK} | ({self.remote_origin} if self.remote_origin else set())

    def check(self, method, path, headers):
        """None when the call may go on, else (status, reason). GET needs the token (in the header, or `token=` in the
        query for an EventSource, which cannot set headers); POST also the CSRF token and the Studio's origin."""
        host = (header(headers, 'Host') or '').strip().lower()
        if host not in {f'{name}:{self.port}' for name in LOOPBACK} | ({urlsplit(self.remote_origin).netloc} if self.remote_origin else set()):
            return 403, 'the Host is not this computer\'s Studio'
        token = header(headers, 'X-EAOS-Token')
        if token is None and method == 'GET':
            token = (parse_qs(urlsplit(path).query).get('token') or [None])[0]
        if not same(token, self.token): return 401, 'the launch token is missing or wrong'
        if method == 'GET': return None
        if method != 'POST': return 405, 'only GET and POST'
        if not same(header(headers, 'X-EAOS-CSRF'), self.csrf): return 403, 'the CSRF token is missing or wrong'
        origin = header(headers, 'Origin')
        if not origin:
            referer = header(headers, 'Referer') or ''
            parts = urlsplit(referer)
            origin = f'{parts.scheme}://{parts.netloc}' if parts.scheme and parts.netloc else ''
        if origin not in self.origins(): return 403, 'the request does not come from the Studio\'s own page'
        return None

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

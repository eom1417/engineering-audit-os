"""Who may talk to the Studio's server: the page EAOS opened, on this computer, and nothing else.

- The server listens on 127.0.0.1 only (`LOOPBACK`); `serve` refuses any other address.
- Every request names the server by its Host (127.0.0.1:<port> or localhost:<port>), so a web page that rebinds its
  own name to 127.0.0.1 is refused (DNS rebinding).
- Every /api/ request carries the launch token in the X-EAOS-Token header, compared in constant time. The token is in
  the address EAOS opens (#token=, never sent to a server, never in a log) and the Studio keeps it for the tab.
- Every request that is not a read (POST, PUT, PATCH, DELETE) also carries X-EAOS-CSRF, equal to the CSRF token
  GET /api/session returned, and an Origin (or a Referer) of this server. The read API has no such route; the action
  API mounted beside it (docs/studio-actions.json) gets the checks for free.
- A refusal says why in the server's log, never with the token.
"""
import hmac
import logging
import secrets
from urllib.parse import urlsplit

from starlette.responses import JSONResponse

LOOPBACK = '127.0.0.1'
TOKEN_HEADER = 'x-eaos-token'
CSRF_HEADER = 'x-eaos-csrf'
READS = frozenset({'GET', 'HEAD', 'OPTIONS'})
log = logging.getLogger('eaos.studio.server')


def new_token():
    return secrets.token_urlsafe(32)


def same(given, expected):
    """Constant-time comparison of two tokens; a missing one never matches."""
    return bool(given) and bool(expected) and hmac.compare_digest(given.encode('utf-8'), expected.encode('utf-8'))


class Guard:
    """ASGI middleware: the Host check on every request, the token on /api/, CSRF and Origin on every write."""

    def __init__(self, app, keys):
        self.app, self.keys = app, keys

    def allowed_hosts(self):
        port = self.keys.port
        return {f'127.0.0.1:{port}', f'localhost:{port}'}

    def refusal(self, scope):
        headers = {k.decode('latin-1').lower(): v.decode('latin-1') for k, v in scope.get('headers') or []}
        if headers.get('host') not in self.allowed_hosts():
            return 421, 'host', 'this server answers only to 127.0.0.1 and localhost'
        path, method = scope.get('path') or '/', scope.get('method') or 'GET'
        if not path.startswith('/api/'):
            return (None if method in READS else (405, 'method', 'the Studio pages are read only'))
        if not same(headers.get(TOKEN_HEADER), self.keys.token):
            return 401, 'token', 'the launch token is missing or wrong: open the address `eaos studio` printed'
        if method in READS: return None
        if not same(headers.get(CSRF_HEADER), self.keys.csrf):
            return 403, 'csrf', 'the CSRF token is missing or wrong: reload the Studio'
        origin = headers.get('origin') or _origin(headers.get('referer'))
        if origin not in {f'http://{host}' for host in self.allowed_hosts()}:
            return 403, 'origin', 'the request does not come from this Studio'
        return None

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        refused = self.refusal(scope)
        if refused is None:
            return await self.app(scope, receive, send)
        status, reason, text = refused
        log.warning('refused %s %s: %s', scope.get('method'), scope.get('path'), reason)
        response = JSONResponse({'error': reason, 'message': text}, status_code=status, headers={'Cache-Control': 'no-store'})
        await response(scope, receive, send)


def _origin(referer):
    if not referer: return None
    parts = urlsplit(referer)
    return f'{parts.scheme}://{parts.netloc}' if parts.scheme and parts.netloc else None

"""The Studio server's guard (eaos/core/system/studio_access.py holds the checks, the same the actions pass): an ASGI middleware that
refuses a request from anywhere but the page EAOS opened, says why in the server's log, never with the token."""
import logging

from starlette.responses import JSONResponse

from ...core.system.studio_access import refusal

log = logging.getLogger('eaos.studio.server')


class Guard:
    """The Host check on every request, the token on /api/, CSRF and Origin on every write."""

    def __init__(self, app, keys):
        self.app, self.keys = app, keys

    def refusal(self, scope):
        headers = [(k.decode('latin-1'), v.decode('latin-1')) for k, v in scope.get('headers') or []]
        # an app made without keys answers on the port it listens on (as a check runs it)
        return refusal(self.keys, scope.get('method') or 'GET', scope.get('path') or '/', headers,
                       port=(scope.get('server') or ('', 0))[1])

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

"""Serving the action API: mounted on NS37.T2's Starlette server, or on its own with the standard library.

NS37.T2 (the read server) mounts the actions next to its read API with two lines:

    from eaos.interfaces.studio import Actions, mount
    mount(app.router, Actions(project, port=port, token=launch_token))    # the same launch token as the read API

`starlette_routes` gives the routes (`/api/session`, `/api/actions…`, `/api/assistants`, `/api/runs…`,
`/api/questions…`); the events of a run are a streaming response. `serve` is the same API on Python's own HTTP
server, for the trial and for a computer without Starlette: it binds 127.0.0.1 and nothing else.
"""
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from . import plan

LOOPBACK = '127.0.0.1'
HEADERS = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer'}
# A stream goes out as it is written: no proxy in front (Caddy, nginx) holds it back to fill a buffer.
STREAM = {**HEADERS, 'X-Accel-Buffering': 'no'}


def tagged(payload):
    """(the body of a read, its ETag): the Studio polls the runs every few seconds, and an unchanged list costs a 304
    instead of the whole list again (1 MB on a phone over 4G starved the run's own event stream, 2026-10-24)."""
    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return body, '"' + hashlib.sha256(body).hexdigest()[:32] + '"'


def _events_of(path):
    """(run, last id from the query) when the path is a run's event stream, else None."""
    parts = urlsplit(path).path.strip('/').split('/')
    if len(parts) == 4 and parts[:2] == ['api', 'runs'] and parts[3] == 'events':
        return parts[2], (parse_qs(urlsplit(path).query).get('after') or [None])[-1]
    return None


def starlette_routes(actions, prefix=''):
    from starlette.responses import JSONResponse, Response, StreamingResponse
    from starlette.routing import Route

    async def endpoint(request):
        path = request.url.path[len(prefix):] + (('?' + request.url.query) if request.url.query else '')
        headers = dict(request.headers)
        body = None
        if request.method == 'POST':
            try: body = await request.json()
            except ValueError: return JSONResponse({'error': 'the body must be JSON'}, 400, headers=HEADERS)
        stream = _events_of(path) if request.method == 'GET' else None
        from starlette.concurrency import run_in_threadpool
        status, payload = await run_in_threadpool(actions.handle, request.method, path, headers, body)   # a probe takes seconds
        if stream and status == 200:
            run, after = stream
            last = headers.get('last-event-id') or after
            from starlette.concurrency import iterate_in_threadpool
            return StreamingResponse(iterate_in_threadpool(actions.sse(run, last, follow=True)), media_type='text/event-stream', headers=STREAM)
        if request.method == 'GET' and status == 200:
            body, etag = tagged(payload)
            if headers.get('if-none-match') == etag: return Response(status_code=304, headers={**HEADERS, 'ETag': etag})
            return Response(body, 200, media_type='application/json', headers={**HEADERS, 'ETag': etag})
        return JSONResponse(payload, status, headers=HEADERS)

    return [Route(prefix + '/api/{rest:path}', endpoint, methods=['GET', 'POST'])]


class _Handler(BaseHTTPRequestHandler):
    actions = None
    server_version = 'EAOS-Studio'

    def log_message(self, *arguments):                 # the actions log themselves; no request line on the terminal
        pass

    def _send(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        for key, value in HEADERS.items(): self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        status, payload = self.actions.handle('GET', self.path, dict(self.headers.items()), None)
        stream = _events_of(self.path)
        if not stream or status != 200: return self._send(status, payload)
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        for key, value in STREAM.items(): self.send_header(key, value)
        self.end_headers()
        try:
            for frame in self.actions.sse(stream[0], self.headers.get('Last-Event-ID') or stream[1], follow=True):
                self.wfile.write(frame.encode('utf-8'))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        length = int(self.headers.get('Content-Length') or 0)
        if length > (plan.MAX_BYTES if self.path.split('?')[0] == '/api/plan' else 4 * 1024 * 1024): return self._send(413, {'error': 'too large'})
        try: body = json.loads(self.rfile.read(length) or b'{}')
        except ValueError: return self._send(400, {'error': 'the body must be JSON'})
        self._send(*self.actions.handle('POST', self.path, dict(self.headers.items()), body))


def serve(actions, port=None):
    """The action API alone on 127.0.0.1:<port> (the Actions' port); returns the running server (serve_forever is
    the caller's)."""
    handler = type('Handler', (_Handler,), {'actions': actions})
    return ThreadingHTTPServer((LOOPBACK, int(port or actions.locks.port)), handler)

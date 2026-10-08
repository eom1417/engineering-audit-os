"""Serving the action API: mounted on NS37.T2's Starlette server, or on its own with the standard library.

NS37.T2 (the read server) mounts the actions next to its read API with two lines:

    from eaos.studio.actions import Actions, mount
    mount(app.router, Actions(project, port=port, token=launch_token))    # the same launch token as the read API

`starlette_routes` gives the routes (`/api/session`, `/api/actions…`, `/api/assistants`, `/api/runs…`,
`/api/questions…`); the events of a run are a streaming response. `serve` is the same API on Python's own HTTP
server, for the trial and for a computer without Starlette: it binds 127.0.0.1 and nothing else.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

LOOPBACK = '127.0.0.1'
HEADERS = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer'}


def _events_of(path):
    """(run, last id from the query) when the path is a run's event stream, else None."""
    parts = urlsplit(path).path.strip('/').split('/')
    if len(parts) == 4 and parts[:2] == ['api', 'runs'] and parts[3] == 'events':
        return parts[2], (parse_qs(urlsplit(path).query).get('after') or [None])[-1]
    return None


def starlette_routes(actions, prefix=''):
    from starlette.responses import JSONResponse, StreamingResponse
    from starlette.routing import Route

    async def endpoint(request):
        path = request.url.path[len(prefix):] + (('?' + request.url.query) if request.url.query else '')
        headers = dict(request.headers)
        body = None
        if request.method == 'POST':
            try: body = await request.json()
            except ValueError: return JSONResponse({'error': 'the body must be JSON'}, 400, headers=HEADERS)
        stream = _events_of(path) if request.method == 'GET' else None
        status, payload = actions.handle(request.method, path, headers, body)
        if stream and status == 200:
            run, after = stream
            last = headers.get('last-event-id') or after
            from starlette.concurrency import iterate_in_threadpool
            return StreamingResponse(iterate_in_threadpool(actions.sse(run, last, follow=True)), media_type='text/event-stream', headers=HEADERS)
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
        for key, value in HEADERS.items(): self.send_header(key, value)
        self.end_headers()
        try:
            for frame in self.actions.sse(stream[0], self.headers.get('Last-Event-ID') or stream[1], follow=True):
                self.wfile.write(frame.encode('utf-8'))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        length = int(self.headers.get('Content-Length') or 0)
        if length > 4 * 1024 * 1024: return self._send(413, {'error': 'too large'})
        try: body = json.loads(self.rfile.read(length) or b'{}')
        except ValueError: return self._send(400, {'error': 'the body must be JSON'})
        self._send(*self.actions.handle('POST', self.path, dict(self.headers.items()), body))


def serve(actions, port=None):
    """The action API alone on 127.0.0.1:<port> (the Actions' port); returns the running server (serve_forever is
    the caller's)."""
    handler = type('Handler', (_Handler,), {'actions': actions})
    return ThreadingHTTPServer((LOOPBACK, int(port or actions.locks.port)), handler)

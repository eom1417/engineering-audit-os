"""The Studio's local server: the built Studio (eaos/data/studio), the read API, the live stream, on 127.0.0.1.

    app = create_app(report)          # report: the technical report folder, with studio/ in it
    serve(app)                        # blocks; the address with its token is app.state.ctx.url

The Studio pages themselves hold no project data and are served to any request that names this server; everything
under /api/ needs the launch token (guard.py). The page is served with `connect-src 'self'` in place of the snapshot's
`'none'`, so it may call this server and nothing else; opened from a file it stays offline as before.

The action API (docs/studio-actions.json, NS46.T9) mounts next to the read API. The command centre's own package
(`eaos.studio.actions`: `Actions` and `mount(router, actions)`) is mounted by itself when the project is known
(`command_centre`): it shares this launch token and CSRF token, its routes come after the read API's, and its
session (the assistants found) is merged into /api/session. Anything else mounts with `mounts`:

    def mount(ctx):                   # ctx: Context below (report, project, keys, feed, publish)
        return [Route('/api/runs', runs, methods=['GET', 'POST']), ...]   # Starlette routes, or
        return [('POST', '/api/runs', handler), ...]                      # plain handlers (see `plain`)

    create_app(report, mounts=[mount])

Every mounted route is under the same guard: the token on every call, and CSRF plus the Origin check on every write.
`ctx.feed.publish(kind, data, text)` puts an action's event into the same numbered stream the Studio already reads.
"""
import asyncio
import contextlib
import inspect
import json
import logging
import os
import signal
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path

import anyio
from sse_starlette.sse import EventSourceResponse
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from .. import guided
from . import guard, launch, read
from .events import Feed

ASSETS = Path(__file__).resolve().parent.parent / 'data' / 'studio'
POLL = 0.4               # seconds between two looks at the manifest or the event log
HEARTBEAT = 15           # seconds between two keep-alive comments on an idle stream
SNAPSHOT_CSP = "connect-src 'none'"
LIVE_CSP = "connect-src 'self'"
log = logging.getLogger('eaos.studio.server')


@dataclass
class Keys:
    token: str = field(default_factory=guard.new_token)
    csrf: str = field(default_factory=guard.new_token)
    port: int = 0


@dataclass
class Context:
    report: Path
    feed: Feed
    keys: Keys
    project: Path | None = None
    name: str = ''
    assets: Path = ASSETS
    actions_mounted: bool = False
    session_extra: object = None      # a callable whose dict joins /api/session (the command centre's)
    closers: list = field(default_factory=list)

    @property
    def url(self):
        return f'http://127.0.0.1:{self.keys.port}/#token={self.keys.token}'

    def publish(self, kind, data=None, text=None):
        return self.feed.publish(kind, data=data, text=text)


def plain(method, path, handler):
    """A Starlette route over a framework-free handler: handler(request: dict) -> (status, payload) or payload.
    request = {method, path, params, query, body, headers, last_event_id}. A payload that is an iterator of dicts is
    streamed as server-sent events (each dict may carry id, event and data)."""
    async def endpoint(request):
        body = None
        if request.method not in guard.READS:
            raw = await request.body()
            try: body = json.loads(raw) if raw else None
            except ValueError: return JSONResponse({'error': 'body', 'message': 'the body is not JSON'}, status_code=400)
        call = {'method': request.method, 'path': request.url.path, 'params': dict(request.path_params),
                'query': dict(request.query_params), 'body': body, 'headers': {k.lower(): v for k, v in request.headers.items()
                                                                               if k.lower() not in (guard.TOKEN_HEADER, guard.CSRF_HEADER)},
                'last_event_id': request.headers.get('last-event-id')}
        result = await handler(call) if inspect.iscoroutinefunction(handler) else await run_in_threadpool(handler, call)
        status, payload = result if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], int) else (200, result)
        if hasattr(payload, '__next__'):
            return EventSourceResponse(_drain(payload), ping=HEARTBEAT)
        return JSONResponse(payload, status_code=status, headers=read.NO_STORE)
    return Route(path, endpoint, methods=[method])


async def _drain(iterator):
    while True:
        item = await run_in_threadpool(next, iterator, None)
        if item is None: return
        yield {k: (json.dumps(v, ensure_ascii=False) if k == 'data' and not isinstance(v, str) else v) for k, v in item.items()}


def stream(ctx):
    async def events(request):
        last = request.headers.get('last-event-id') or request.query_params.get('after')

        async def generate():
            nonlocal last
            missed, reset = ctx.feed.since(last)
            if reset:
                last = ctx.feed.last_id()
                yield {'event': 'reset', 'id': last, 'data': json.dumps({'last': last, 'source': ctx.feed.source})}
            elif not last:
                last = ctx.feed.last_id()
                yield {'event': 'hello', 'id': last, 'data': json.dumps({'last': last, 'source': ctx.feed.source})}
            for event in missed:
                last = event['id']
                yield {'event': 'studio', 'id': event['id'], 'data': json.dumps(event, ensure_ascii=False)}
            while True:
                if await request.is_disconnected(): return
                fresh, reset = ctx.feed.since(last)
                if reset:
                    last = ctx.feed.last_id()
                    yield {'event': 'reset', 'id': last, 'data': json.dumps({'last': last, 'source': ctx.feed.source})}
                for event in fresh:
                    last = event['id']
                    yield {'event': 'studio', 'id': event['id'], 'data': json.dumps(event, ensure_ascii=False)}
                await asyncio.sleep(POLL / 2)
        return EventSourceResponse(generate(), ping=HEARTBEAT, headers={'Cache-Control': 'no-store'})
    return [Route('/api/events', events)]


def pages(ctx):
    root = Path(ctx.assets).resolve()

    async def index(request):
        page = root / 'index.html'
        if not page.is_file():
            return Response('The Studio is not built in this EAOS (eaos/data/studio is missing).', status_code=503)
        html = page.read_text(encoding='utf-8').replace(SNAPSHOT_CSP, LIVE_CSP)
        return Response(html, media_type='text/html', headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                                                                'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY'})

    async def asset(request):
        name = request.path_params['path']
        target = (root / name).resolve()
        if not target.is_relative_to(root) or not target.is_file() or target.name == 'index.html':
            return Response(status_code=404)
        return FileResponse(target, headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-cache'})

    return [Route('/', index), Route('/index.html', index), Route('/{path:path}', asset)]


def command_centre(ctx):
    """The command centre's action API (eaos/studio/actions, NS46.T9) on this server, when it is installed and the
    project is known; [] otherwise. It gets this server's launch token and gives its CSRF token to the guard, so both
    layers of checks agree."""
    try:
        from ..studio import actions as centre
    except ImportError:
        return []
    if ctx.project is None or not hasattr(centre, 'Actions') or not hasattr(centre, 'mount'):
        return []
    from starlette.routing import Router
    engine = centre.Actions(ctx.project, port=ctx.keys.port, token=ctx.keys.token)
    ctx.keys.csrf = engine.csrf
    ctx.session_extra = getattr(engine, 'session', None)
    if hasattr(engine, 'close'): ctx.closers.append(engine.close)
    router = Router()
    centre.mount(router, engine)
    return list(router.routes)


def _routes(entries):
    out = []
    for entry in entries or []:
        out.append(plain(*entry) if isinstance(entry, tuple) else entry)
    return out


def create_app(report, project=None, name=None, keys=None, mounts=None, assets=None, watch=True):
    report = Path(report)
    ctx = Context(report=report, feed=Feed(report), keys=keys or Keys(), project=Path(project) if project else None,
                  name=name or (Path(project).name if project else report.name), assets=Path(assets or ASSETS))
    mounted = command_centre(ctx) if mounts is None else [route for mount in mounts for route in _routes(mount(ctx))]
    ctx.actions_mounted = bool(mounted)
    ctx.feed.poll()                                   # the state the server starts from, not an event

    @contextlib.asynccontextmanager
    async def lifespan(app):
        async def watch_loop():
            while True:
                try: await anyio.to_thread.run_sync(ctx.feed.poll)
                except Exception as problem: log.warning('feed: %s', problem)
                await asyncio.sleep(POLL)
        task = asyncio.create_task(watch_loop()) if watch else None
        yield
        if task: task.cancel()
        for close in ctx.closers:
            try: close()
            except Exception as problem: log.warning('close: %s', problem)

    async def not_found(request, exc):
        return JSONResponse({'error': 'not_found'}, status_code=404, headers=read.NO_STORE)

    api = read.routes(ctx) + stream(ctx) + mounted
    app = Starlette(routes=api + [Route('/api/{rest:path}', lambda r: JSONResponse({'error': 'not_found'}, status_code=404,
                                                                                     headers=read.NO_STORE),
                                        methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])] + pages(ctx),
                    middleware=[Middleware(guard.Guard, keys=ctx.keys)], lifespan=lifespan,
                    exception_handlers={404: not_found})
    app.state.ctx = ctx
    return app


def bind(port=0, host=guard.LOOPBACK):
    """A listening socket on 127.0.0.1 (any other address is refused), on `port` or a free one."""
    if host != guard.LOOPBACK:
        raise ValueError(f'the Studio server listens on {guard.LOOPBACK} only, not {host}')
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(128)
    sock.set_inheritable(True)
    return sock


def serve(app, sock=None, ready=None):
    """Run until stopped. `sock` from bind(); the port is put in the app's keys before the first request."""
    import uvicorn
    sock = sock or bind(app.state.ctx.keys.port)
    app.state.ctx.keys.port = sock.getsockname()[1]
    config = uvicorn.Config(app, log_level='warning', access_log=False, lifespan='on', timeout_graceful_shutdown=2)
    server = uvicorn.Server(config)
    if ready: ready(server)
    server.run(sockets=[sock])


def run_foreground(project=None, port=0, show=True, out=lambda text: print(text, flush=True)):
    """`eaos studio`: serve until stopped, with the record launch.py reuses. Returns the exit code."""
    state, report = launch.prepare(project)
    found = launch.running(state)
    if found:
        out(f'The Studio of this project is already open: {launch.url_of(found)}')
        launch._open(launch.url_of(found), show)
        return 0
    sock = bind(port)
    app = create_app(report, project=state['project'], keys=Keys(port=sock.getsockname()[1]))
    ctx = app.state.ctx
    launch._write_record(state, {'pid': os.getpid(), 'port': ctx.keys.port, 'token': ctx.keys.token, 'report': str(report),
                                 'project': state['project'], 'started': time.time()})
    try:
        out(f"EAOS Studio, live: {ctx.url}\n(only this computer can open it; press Ctrl-C to stop)")
        if not guided.scan_done(state):
            out('This project has not been checked yet: the Studio opens empty until `eaos start` checks it.')
        launch._open(ctx.url, show)
        # Uvicorn re-raises the signal it stopped on; a stop (SIGTERM) then ends here like Ctrl-C, and the record goes
        signal.signal(signal.SIGTERM, _interrupt)
        serve(app, sock)
    except KeyboardInterrupt:
        pass
    finally:
        launch.record_path(state).unlink(missing_ok=True)
    return 0


def _interrupt(number, frame):
    raise KeyboardInterrupt

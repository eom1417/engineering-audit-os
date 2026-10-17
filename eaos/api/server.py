"""The Studio's local server: the built Studio (eaos/data/studio), the read API, the live stream, on 127.0.0.1.

    app = create_app(report)          # report: the technical report folder, with studio/ in it
    serve(app)                        # blocks; launch.url_of gives the address with its token

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
import re
import secrets
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
from ..agent_tools import project_state
from . import guard, launch, projects, read
from .events import Feed

ASSETS = Path(__file__).resolve().parent.parent / 'data' / 'studio'
POLL = 0.4               # seconds between two looks at the manifest or the event log
HEARTBEAT = 5            # seconds between two keep-alive comments on an idle stream (the page polls after 8 s of silence)
IDLE = 600               # seconds a Studio server stays with no run and no client; the switcher or launcher starts it again
SNAPSHOT_CSP = "connect-src 'none'"
LIVE_CSP = "connect-src 'self'"
log = logging.getLogger('eaos.studio.server')


@dataclass
class Keys:
    token: str = field(default_factory=guard.new_token)
    csrf: str = field(default_factory=guard.new_token)
    port: int = 0
    remote_origin: str | None = None

    def __post_init__(self):
        if self.remote_origin:
            from ..studio.actions.security import Locks
            Locks(self.port, remote_origin=self.remote_origin)


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
    busy: object = None               # a callable: whether a run is active or queued (the command centre's)
    seen: float = field(default_factory=time.monotonic)      # the last request or stream beat of a client

    def idle(self, now):
        """No client for IDLE seconds and no run active or queued: the server may go (each costs about 220 MB)."""
        return now - self.seen > IDLE and not (self.busy and self.busy())

    @property
    def url(self):
        return f'http://127.0.0.1:{self.keys.port}/'

    def publish(self, kind, data=None, text=None):
        return self.feed.publish(kind, data=data, text=text)

    def state(self):
        """The project's guided state as it is now (eaos/guided.py), or None when no project is known."""
        return guided.load(self.project) if self.project else None


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
                ctx.seen = time.monotonic()
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
        if _remote_login_trusted(ctx):
            # The owner's remote address sits behind the Remote sign-in, which loses the token in the address on some
            # redirects. The page reads it from a script whose address changes on every load, so no cache in front of
            # the server can hand back an old answer. On this computer the address carries the token (#token=).
            html = html.replace('<script src="./boot.js"></script>',
                                f'<script src="./live-token.js?n={secrets.token_hex(8)}"></script><script src="./boot.js"></script>', 1)
        return Response(html, media_type='text/html', headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                                                                'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY'})

    async def asset(request):
        name = request.path_params['path']
        target = (root / name).resolve()
        if not target.is_relative_to(root) or not target.is_file() or target.name == 'index.html':
            return Response(status_code=404)
        return FileResponse(target, headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-cache'})

    async def live_token(request):
        if not _remote_login_trusted(ctx) or _this_computer((request.scope.get('client') or ('',))[0]):
            return Response(status_code=404)
        given = f"window.EAOS_BOOT_TOKEN={json.dumps(ctx.keys.token)};try{{sessionStorage.setItem('eaos.token',window.EAOS_BOOT_TOKEN)}}catch(e){{}}\n"
        return Response(given, media_type='text/javascript', headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store, private'})

    return [Route('/', index), Route('/index.html', index), Route('/live-token.js', live_token), Route('/{path:path}', asset)]


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
    engine = centre.Actions(ctx.project, port=ctx.keys.port, token=ctx.keys.token, studio=ctx.report / 'studio', remote_origin=ctx.keys.remote_origin)
    ctx.keys.csrf = engine.csrf
    ctx.session_extra = getattr(engine, 'session', None)
    from ..studio.actions.store import ACTIVE
    ctx.busy = lambda: any(row.get('state') in (*ACTIVE, 'queued') and not row.get('read') for row in engine.store.all())
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
    ctx = Context(report=report, feed=Feed(report, runtime=_runtime(project)), keys=keys or Keys(),
                  project=Path(project) if project else None, name=name or (Path(project).name if project else report.name),
                  assets=Path(assets or ASSETS))
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

    api = read.routes(ctx) + stream(ctx) + _routes(projects.routes(ctx)) + mounted
    app = Starlette(routes=api + [Route('/api/{rest:path}', lambda r: JSONResponse({'error': 'not_found'}, status_code=404,
                                                                                     headers=read.NO_STORE),
                                        methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])] + pages(ctx),
                    middleware=[Middleware(_Seen, ctx=ctx), Middleware(guard.Guard, keys=ctx.keys)], lifespan=lifespan,
                    exception_handlers={404: not_found})
    app.state.ctx = ctx
    return app


class _Seen:
    """Every request is a client's: the server stays while one comes (Context.idle)."""

    def __init__(self, app, ctx):
        self.app, self.ctx = app, ctx

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http': self.ctx.seen = time.monotonic()
        await self.app(scope, receive, send)


def _exit_when_idle(ctx, every=30):
    """Stop this server (as `launch.stop` does) once it is idle."""
    while not ctx.idle(time.monotonic()): time.sleep(every)
    os.kill(os.getpid(), signal.SIGTERM)


def _runtime(project):
    """The project's runtime folder, where the flows after the check write their progress; None without a project."""
    known = guided.load(Path(project)) if project else None
    return guided.runtime_of(known) if known else None


def bind(port=0, host=guard.LOOPBACK, remote_origin=None, routed=False):
    """A loopback socket, or 0.0.0.0 with an exact authenticated Remote origin (or `routed`: one made from the port once
    bound, launch.remote_template), on `port` or a free one."""
    if remote_origin:
        from ..studio.actions.security import Locks
        Locks(port, remote_origin=remote_origin)
    if host != guard.LOOPBACK and not (host == '0.0.0.0' and (remote_origin or routed)):
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


def prepare(project=None):
    """The project's state and its report folder, with the Studio data rebuilt from the ledger when it was checked."""
    state = project_state(project)
    report = guided.report_of(state)
    if guided.scan_done(state):
        guided.reconcile(state)
        guided.publish(state)
        guided.save(state)
    return state, report


def run_foreground(project=None, port=0, show=True, remote_origin=None, out=lambda text: print(text, flush=True)):
    """`eaos studio`: serve until stopped, with the record launch.py reuses. Returns the exit code."""
    state, report = prepare(project)
    found = launch.running(state)
    if found and (remote_origin or found.get('remote_origin')) and not launch.remote_template():
        out('The Studio is already running; use its protected launch record to open it.')
        return 0
    if found:
        out(f'The Studio of this project is already open: {launch.url_of(found)}')
        launch._open(launch.url_of(found), show)
        return 0
    template = None if remote_origin else launch.remote_template()
    sock = _bind_kept(state, port, remote_origin, remote=bool(template))
    if template: remote_origin = template.format(port=sock.getsockname()[1])
    keys = Keys(port=sock.getsockname()[1], remote_origin=remote_origin)
    launch.records_folder().mkdir(parents=True, exist_ok=True)
    keys.token = _kept_token(os.environ.get('EAOS_STUDIO_TOKEN_FILE') or launch.token_path(state))
    launch.keep_port(state, keys.port)
    app = create_app(report, project=state['project'], keys=keys)
    ctx = app.state.ctx
    launch._write_record(state, {'pid': os.getpid(), 'port': ctx.keys.port, 'token': ctx.keys.token, 'report': str(report),
                                 'project': state['project'], 'started': time.time(), 'remote_origin': remote_origin,
                                 'page_reads_token': _remote_login_trusted(ctx)})
    try:
        if template: out(f"EAOS Studio, live: {launch.url_of({'port': keys.port, 'remote_origin': remote_origin, 'page_reads_token': True})}")
        elif remote_origin:
            out(f"EAOS Studio, live on {remote_origin}. Launch token is stored in the protected project launch record; no token is printed.")
        else: out(f"EAOS Studio, live: {launch.url_of({'port': keys.port, 'token': keys.token})}\n"
                  '(only this computer can open it; press Ctrl-C to stop)')
        if not guided.scan_done(state):
            out('This project has not been checked yet: the Studio opens empty until `eaos start` checks it.')
        if not remote_origin: launch._open(launch.url_of({'port': keys.port, 'token': keys.token}), show)
        # Uvicorn re-raises the signal it stopped on; a stop (SIGTERM) then ends here like Ctrl-C, and the record goes
        signal.signal(signal.SIGTERM, _interrupt)
        if not remote_origin:     # a Remote address has nothing to start its server again: it stays (it is the owner's link)
            import threading
            threading.Thread(target=_exit_when_idle, args=(ctx,), name='eaos-studio-idle', daemon=True).start()
        serve(app, sock)
    except KeyboardInterrupt:
        pass
    finally:
        launch.record_path(state).unlink(missing_ok=True)
    return 0


def _bind_kept(state, port, remote_origin, remote=False):
    """The socket of `port`, or the port the project's Studio used last when it is free, so its address stays the same;
    else a free one. `remote`: a server whose Remote address is made from its port (launch.remote_template), so it
    listens beyond loopback like one given --remote-origin."""
    host = '0.0.0.0' if remote_origin or remote else guard.LOOPBACK
    if not port and not remote_origin and launch.kept_port(state):
        try: return bind(launch.kept_port(state), host=host, routed=remote)
        except OSError: pass
    return bind(port, host=host, remote_origin=remote_origin, routed=remote)


def _this_computer(address):
    """Whether a request's TCP peer is this computer (loopback or one of its own addresses: one it can bind to). The
    Remote sign-in's proxy reaches the server from another machine; a program here (another project's code, a forged
    Host and Sec-Fetch header) never gets the token from live-token.js. The peer is the socket's, never a header's."""
    try:
        with socket.socket(socket.AF_INET6 if ':' in address else socket.AF_INET) as probe: probe.bind((address, 0))
    except (OSError, ValueError):
        return False
    return True


def _remote_login_trusted(ctx):
    """EAOS_STUDIO_TRUST_REMOTE_LOGIN=1 on a server started with --remote-origin: the sign-in in front of it guards the
    Studio, so the launch token travels in live-token.js rather than in the address. Never on a local Studio."""
    return bool(ctx.keys.remote_origin) and (os.environ.get('EAOS_STUDIO_TRUST_REMOTE_LOGIN') == '1' or bool(launch.remote_template()))


def _kept_token(path):
    """A remote Studio's launch token kept across restarts, so the owner's address keeps working: read from (or first
    written to) a file only its owner can read. None without a path."""
    if not path: return None
    file = Path(path)
    try:
        token = file.read_text(encoding='utf-8').strip()
        if re.fullmatch(r'[A-Za-z0-9_-]{32,128}', token) and (file.stat().st_mode & 0o077) == 0: return token
    except OSError:
        pass
    token = guard.new_token()
    fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as out: out.write(token + '\n')
    os.chmod(file, 0o600)
    return token


def _interrupt(number, frame):
    raise KeyboardInterrupt

"""Where the Studio's server listens and for how long: its socket (loopback, or beyond it for an exact Remote origin),
uvicorn on it, the port and launch token it keeps across restarts, and its exit once idle (eaos/interfaces/studio_server/server.py
builds the app it serves)."""
import json
import os
import re
import signal
import socket
import time
from pathlib import Path

from ...core.system import launch, studio_access as security
from ...core.system.studio_access import Locks


def _exit_when_idle(ctx, every=30):
    """Stop this server (as `launch.stop` does) once it is idle."""
    while not ctx.idle(time.monotonic()): time.sleep(every)
    os.kill(os.getpid(), signal.SIGTERM)


def bind(port=0, host=security.LOOPBACK, remote_origin=None, routed=False):
    """A loopback socket, or 0.0.0.0 with an exact authenticated Remote origin (or `routed`: one made from the port once
    bound, launch.remote_template), on `port` or a free one."""
    if remote_origin:
        Locks(port, remote_origin=remote_origin)
    if host != security.LOOPBACK and not (host == security.EVERY_NETWORK and (remote_origin or routed)):
        raise ValueError(f'the Studio server listens on {security.LOOPBACK} only, not {host}')
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
    # No forwarding header is believed (uvicorn trusts X-Forwarded-For from 127.0.0.1 by default): the peer the token
    # checks (live-token.js) is always the socket's, so a program here cannot pass for the Remote sign-in's proxy.
    config = uvicorn.Config(app, log_level='warning', access_log=False, lifespan='on', timeout_graceful_shutdown=2,
                            proxy_headers=False, forwarded_allow_ips='')
    server = uvicorn.Server(config)
    if ready: ready(server)
    server.run(sockets=[sock])


def _drop_record(state):
    """This server's record goes as it ends; the record of the Studio that replaced it (an updated EAOS) stays."""
    path = launch.record_path(state)
    try:
        if json.loads(path.read_text(encoding='utf-8')).get('pid') == os.getpid(): path.unlink()
    except (OSError, ValueError): pass


def _bind_kept(state, port, remote_origin, remote=False):
    """The socket of `port`, or the port the project's Studio used last when it is free, so its address stays the same;
    else a free one. `remote`: a server whose Remote address is made from its port (launch.remote_template), so it
    listens beyond loopback like one given --remote-origin."""
    host = security.EVERY_NETWORK if remote_origin or remote else security.LOOPBACK
    if not port and not remote_origin and launch.kept_port(state):
        try: return bind(launch.kept_port(state), host=host, routed=remote)
        except OSError: pass
    return bind(port, host=host, remote_origin=remote_origin, routed=remote)


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
    token = security.new_token()
    fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as out: out.write(token + '\n')
    os.chmod(file, 0o600)
    return token


def _interrupt(number, frame):
    raise KeyboardInterrupt

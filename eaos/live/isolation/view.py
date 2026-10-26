"""The launcher that gives a sandboxed command a view of the disk of its own run only (eaos/live/isolation/sandbox.py).

    python -I live/isolation/view.py '<spec>' argv...     spec: {"offline": bool, "cwd": path, "mounts": [...]}

It enters a user and a mount namespace of its own (and a network one when `offline`), applies `mounts` in order, each
["hide", folder] (an empty tmpfs over it) or ["show", target, source, read_only] (source bound at target), moves to
`cwd` and becomes the command. Inside, the command runs as an ordinary user: it cannot undo a mount, so what is hidden
stays hidden. The standard library only, as a script: it runs before the command, in its place.
"""
import ctypes
import json
import os
import stat
import sys

CLONE_NEWNS, CLONE_NEWUSER, CLONE_NEWNET = 0x00020000, 0x10000000, 0x40000000
MS_RDONLY, MS_REMOUNT, MS_BIND, MS_REC, MS_PRIVATE = 1, 32, 4096, 16384, 1 << 18
INSIDE = 1000           # the user inside when the caller is root: root inside could unmount what hides the rest


def _call(libc, name, *args):
    if getattr(libc, name)(*args) != 0:
        number = ctypes.get_errno()
        raise OSError(number, f'{name}: {os.strerror(number)}')


def _mount(libc, source, target, kind, flags):
    _call(libc, 'mount', source and source.encode(), target.encode(), kind and kind.encode(), ctypes.c_ulong(flags), None)


def _place(target, folder):
    """An empty folder or file at `target` to mount on (inside a tmpfs already mounted above it)."""
    if folder: return os.makedirs(target, exist_ok=True)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if not os.path.exists(target): open(target, 'a').close()


def _map_user(uid, gid):
    """The caller's user and group (taken before unshare) as the namespace's own; root becomes INSIDE."""
    for name, text in (('setgroups', 'deny'), ('uid_map', f'{uid or INSIDE} {uid} 1'), ('gid_map', f'{gid or INSIDE} {gid} 1')):
        with open(f'/proc/self/{name}', 'w') as out: out.write(text)


def _opened(mounts):
    """({source: descriptor}, the sources that are folders) of the mounts that show a source."""
    # Each source is opened in this namespace before anything hides it, then bound from its descriptor.
    sources = {mount[2]: os.open(mount[2], os.O_PATH) for mount in mounts if mount[0] == 'show'}
    return sources, {source for source, descriptor in sources.items() if stat.S_ISDIR(os.fstat(descriptor).st_mode)}


def enter(spec):
    libc = ctypes.CDLL(None, use_errno=True)
    uid, gid = os.getuid(), os.getgid()
    _call(libc, 'unshare', CLONE_NEWUSER | CLONE_NEWNS | (CLONE_NEWNET if spec['offline'] else 0))
    _map_user(uid, gid)
    _mount(libc, None, '/', None, MS_REC | MS_PRIVATE)
    sources, folders = _opened(spec['mounts'])
    for mount in spec['mounts']:
        if mount[0] == 'hide':
            _mount(libc, 'tmpfs', mount[1], 'tmpfs', 0)
            continue
        _, target, source, read_only = mount
        _place(target, source in folders)
        _mount(libc, f'/proc/self/fd/{sources[source]}', target, None, MS_BIND | MS_REC)
        if read_only: _mount(libc, None, target, None, MS_REMOUNT | MS_BIND | MS_RDONLY)
    for descriptor in sources.values(): os.close(descriptor)
    os.chdir(spec['cwd'])


if __name__ == '__main__':
    try:
        enter(json.loads(sys.argv[1]))
        os.execvp(sys.argv[2], sys.argv[2:])  # nosemgrep: python.lang.security.audit.dangerous-os-exec-audit, python.lang.security.audit.dangerous-os-exec-tainted-env-args -- the sandbox's own launcher: it runs, once its view is entered, the argv the sandbox built
    except (OSError, ValueError, AttributeError, IndexError) as problem:
        print(f'eaos sandbox: {problem}', file=sys.stderr)
        raise SystemExit(127)

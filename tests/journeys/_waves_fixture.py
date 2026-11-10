"""Shared by the wave tests: git helpers and a repository to fix in waves."""
import subprocess
from pathlib import Path
from shared_fixture import scratch


def git(where, *args):
    return subprocess.run(['git', '-C', str(where), *args], capture_output=True, text=True, check=True).stdout.strip()


def repository():
    root = Path(scratch()) / 'shop'
    root.mkdir()
    (root / 'a.txt').write_text('a\n')
    git(root, 'init', '-q'); git(root, 'add', '-A')
    git(root, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'first')
    return root


def commit_file(root, name, text):
    (root / name).write_text(text)
    git(root, 'add', '-A'); git(root, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', name)
    return git(root, 'rev-parse', 'HEAD')

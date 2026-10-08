"""Where the development-only material lives on this machine, and how to fetch it again.

Nothing here is part of EAOS the product; it is what measuring and developing it needs: the pinned
sample corpus, the source checkouts of the engines EAOS runs, and the measurement reports. They share
one root, $EAOS_DEV_HOME (default ~/.eaos/dev), and each part can still be moved with its own variable.
None of them is ever committed: the corpus and the engines are fetched at their pinned commits, the
reports are rebuilt by the measurements and trials.

    python tools/dev_paths.py            # print where each part is
    python tools/dev_paths.py upstreams  # clone every engine source in upstreams/registry.yaml at its commit
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get('EAOS_DEV_HOME') or '~/.eaos/dev').expanduser()


def place(env, name):
    return Path(os.environ.get(env) or HOME / name).expanduser()


CORPUS = place('EAOS_CORPUS', 'corpus')
MEASURE = place('EAOS_MEASURE', 'measure')
UPSTREAMS = place('EAOS_UPSTREAMS', 'upstream-src')
# The hand-written labels of the precision set (tools/precision.py): kept outside the repository and the
# projects, written from the source before any report of the project is read.
TRUTH = place('EAOS_TRUTH', 'truth')
ENOLA = UPSTREAMS / 'enola'


def pinned_upstreams(registry=ROOT / 'upstreams/registry.yaml'):
    """(checkout name, repository, commit) for every upstream the registry pins to a commit."""
    rows, current = [], {}
    for line in registry.read_text(encoding='utf-8').splitlines():
        if line.startswith('  - name:'):
            current = {}
        for key in ('repository', 'commit'):
            if line.startswith(f'    {key}:'):
                current[key] = line.split(':', 1)[1].split('#')[0].strip()
        if 'repository' in current and 'commit' in current:
            rows.append((current['repository'].rstrip('/').rsplit('/', 1)[1].removesuffix('.git'),
                         current['repository'], current['commit']))
            current = {}
    return rows


def fetch_upstreams():
    UPSTREAMS.mkdir(parents=True, exist_ok=True)
    for name, repository, commit in pinned_upstreams():
        where = UPSTREAMS / name
        if not (where / '.git').is_dir():
            subprocess.run(['git', 'clone', '--quiet', repository, str(where)], check=True)
        subprocess.run(['git', 'checkout', '--quiet', '--force', commit], cwd=where, check=True)
        print(f'{name}: {commit[:10]}')


if __name__ == '__main__':
    if sys.argv[1:] == ['upstreams']:
        fetch_upstreams()
    elif not sys.argv[1:]:
        for label, path in (('corpus', CORPUS), ('measure', MEASURE), ('upstream-src', UPSTREAMS), ('truth', TRUTH)):
            print(f'{label:13} {path}{"" if path.exists() else "  (absent)"}')
    else:
        raise SystemExit(__doc__)

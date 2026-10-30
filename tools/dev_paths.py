"""Where the development-only material lives on this machine, and how to fetch it again.

Nothing here is part of EAOS the product; it is what measuring and developing it needs: the pinned
sample corpus, the source checkouts of the engines EAOS runs, and the measurement reports. They share
one root, $EAOS_DEV_HOME (default ~/.eaos/dev), and each part can still be moved with its own variable.
None of them is ever committed: the corpus and the engines are fetched at their pinned commits, the
reports are rebuilt by the measurements and trials.

    python tools/dev_paths.py            # print where each part is
    python tools/dev_paths.py upstreams  # clone every engine source eaos/data/toolchain.json pins (source_commit)
    python tools/dev_paths.py map        # GitNexus's map of EAOS (docs/EXTENDING.md "The map"), about 35 s, no token
    python tools/dev_paths.py map-where  # the command that asks it who calls a symbol and what a change breaks
"""
import json
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
# Public pipeline projects pinned for the pipeline map's truth files (evaluations/pipelines/, tools/pipeline_truth.py).
PIPELINES = place('EAOS_PIPELINES', 'pipelines')
# GitNexus writes where it reads (its index of about 300 MB, skills, a block in AGENTS.md and CLAUDE.md), so it reads a
# copy of the tracked files here, never the checkout; `--skip-agents-md` keeps its block out of the context files.
MAP = place('EAOS_MAP', 'map')
SKILLS = ROOT / '.claude' / 'skills'          # its skills are copied here, a folder git ignores


def pinned_upstreams(registry=ROOT / 'eaos/data/toolchain.json'):
    """(checkout name, repository, commit) for every tool the registry pins to a source commit (`source_commit`)."""
    return [(tool['repository'].rstrip('/').rsplit('/', 1)[1].removesuffix('.git'), tool['repository'], tool['source_commit'])
            for tool in json.loads(registry.read_text(encoding='utf-8'))['tools'] if tool.get('source_commit')]


def fetch_upstreams():
    UPSTREAMS.mkdir(parents=True, exist_ok=True)
    for name, repository, commit in pinned_upstreams():
        where = UPSTREAMS / name
        if not (where / '.git').is_dir():
            subprocess.run(['git', 'clone', '--quiet', repository, str(where)], check=True)
        subprocess.run(['git', 'checkout', '--quiet', '--force', commit], cwd=where, check=True)
        print(f'{name}: {commit[:10]}')


def map_where():
    return f'GITNEXUS_HOME={MAP / "registry"} gitnexus impact <symbol> -r {ROOT.name} > /tmp/impact.json   (copy: {MAP / ROOT.name})'


def build_map():
    """GitNexus's graph, area skills and MCP of EAOS: built on a copy in MAP, its skills copied into .claude/skills."""
    sys.path.insert(0, str(ROOT))
    from eaos.core.toolchain import home
    from eaos.engines.code.gitnexus import make_map
    if (home() / 'bin' / 'gitnexus').exists(): os.environ['PATH'] = f"{home() / 'bin'}{os.pathsep}{os.environ['PATH']}"
    made = make_map(ROOT, MAP, SKILLS)
    print(f"{made['skills']} skills in .claude/skills; {map_where()}")


if __name__ == '__main__':
    if sys.argv[1:] == ['upstreams']:
        fetch_upstreams()
    elif sys.argv[1:] == ['map']:
        build_map()
    elif sys.argv[1:] == ['map-where']:
        print(map_where())
    elif not sys.argv[1:]:
        for label, path in (('corpus', CORPUS), ('measure', MEASURE), ('upstream-src', UPSTREAMS), ('truth', TRUTH), ('pipelines', PIPELINES), ('map', MAP)):
            print(f'{label:13} {path}{"" if path.exists() else "  (absent)"}')
    else:
        raise SystemExit(__doc__)

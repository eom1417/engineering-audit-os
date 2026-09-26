"""GitNexus: a knowledge graph of the code, read for its import cycles, its most depended-on files and its communities.

`gitnexus analyze` writes where it reads: its index, and by default AGENTS.md, CLAUDE.md and skill files,
and it touches .git. So it never runs on the project. It runs on a real copy (not hardlinks: a hardlinked
file is the original) without .git or dependency folders, with --index-only so it injects nothing, and
with GITNEXUS_HOME inside the work directory so its registry stays out of the user's home.

It is a third witness beside EAOS's own graph, CodeGraph and dependency-cruiser. Its cycles are the
source graph's (type imports included); a file at least FAN_IN files import is a coupling finding; its
communities (Leiden clusters) are candidate boundaries of today's components for S02 and NS7, written to
facts/external.json -> summary.communities. Agreement between witnesses raises a claim; disagreement is
recorded and decided by none of them. The licence is non-commercial (upstreams/toolchain.json license_note).
"""
import json
import os
import shutil
from pathlib import Path

from . import tool
from .contract import ERROR, FILE, OBSERVED, Report, finding, measurement, subject
from .process import run, which

NAME = BINARY = 'gitnexus'
PINNED = tool.pinned(NAME)
FAN_IN = 20
PAGE, PIPE_LIMIT = 300, 65536
NOT_COPIED = ('.git', 'node_modules', '.venv', 'venv', 'dist', 'build', '.next', '__pycache__', 'vendor', 'coverage')


def capabilities():
    from .contract import Capability
    return [Capability('cycle', 'gitnexus.check.cycles', granularity=FILE),
            Capability('coupling', f'gitnexus.fan_in>={FAN_IN}', granularity=FILE)]


def version():
    return tool.version(BINARY)


def table(markdown):
    """Rows of the markdown table `gitnexus cypher` prints, as lists of cell strings."""
    lines = [line.strip() for line in (markdown or '').splitlines() if line.strip().startswith('|')]
    return [[cell.strip() for cell in line.strip('|').split(' | ')] for line in lines[2:]]


def excluded(path, patterns):
    return any(f'/{pattern.strip("/")}/' in f'/{path}' for pattern in patterns)


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target)
    if declined: return declined
    found = version()
    workdir = Path(workdir).resolve() / NAME
    if workdir.exists(): shutil.rmtree(workdir)
    copy, home = workdir / 'copy', workdir / 'home'
    shutil.copytree(Path(target).resolve(), copy, symlinks=True, ignore=shutil.ignore_patterns(*NOT_COPIED))
    home.mkdir(parents=True)
    env = {**os.environ, 'GITNEXUS_HOME': str(home)}
    binary = which(BINARY)
    code, _, error, seconds = run([binary, 'analyze', '.', '--index-only', '--skip-git', '--skip-fts'], cwd=copy, env=env,
                                  timeout=1800)
    if code:
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')

    def cypher(query):
        """All rows of a query, a page at a time: piped, the CLI stops writing at 64 KiB, so a page that
        reaches that size is an error, never a silently shorter answer."""
        nonlocal seconds
        rows, offset = [], 0
        while True:
            code_, out, error_, spent = run([binary, 'cypher', '-r', str(copy), f'{query} SKIP {offset} LIMIT {PAGE}'],
                                            cwd=copy, env=env, timeout=600)
            seconds += spent
            if code_: raise RuntimeError(error_.strip()[-300:] or f'cypher exit {code_}')
            if len(out.encode()) >= PIPE_LIMIT: raise RuntimeError(f'a page of {PAGE} rows reached the {PIPE_LIMIT}-byte output limit')
            page = table(json.loads(out[out.index('{'):]).get('markdown'))
            rows += page
            if len(page) < PAGE: return rows
            offset += PAGE

    try:
        imports = cypher("MATCH (a:File)-[r]->(b:File) WHERE r.type='IMPORTS' RETURN a.filePath AS source, b.filePath AS sink ORDER BY source, sink")
        members = cypher("MATCH (s)-[r]->(c:Community) WHERE r.type='MEMBER_OF' RETURN DISTINCT c.id AS cid, c.label AS clabel, "
                         "s.filePath AS path ORDER BY cid, path")
        relations = dict((kind, int(count)) for kind, count in cypher("MATCH ()-[r]->() RETURN r.type AS kind, count(*) AS n ORDER BY kind"))
    except (RuntimeError, ValueError) as problem:
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=f'query failed: {problem}'[:300])
    code, out, error, spent = run([binary, 'check', '--cycles', '--json', '-r', str(copy)], cwd=copy, env=env, timeout=600)
    seconds += spent
    try: cycles = json.loads(out[out.index('{'):]).get('cycles') or []
    except ValueError: return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=f'check --cycles: {error.strip()[-200:]}')

    findings, seen = [], set()
    for cycle in cycles:
        members_ = cycle.get('files') or []
        key = tuple(sorted(set(members_)))
        if not key or key in seen or all(excluded(path, exclude) for path in key): continue
        seen.add(key)
        findings.append(finding(NAME, found, 'gitnexus.check.cycles', 'cycle', subject('module', ' -> '.join(key), key[0]),
                                'import cycle (type imports included): ' + ' -> '.join(members_),
                                raw_ref=f'{NAME}/check-cycles', sites=[{'path': path, 'line': None} for path in key]))
    fan_in, fan_out = {}, {}
    for source, sink in imports:
        fan_in[sink] = fan_in.get(sink, 0) + 1
        fan_out[source] = fan_out.get(source, 0) + 1
    for path, count in sorted(fan_in.items(), key=lambda item: (-item[1], item[0])):
        if count < FAN_IN or excluded(path, exclude): continue
        findings.append(finding(NAME, found, f'gitnexus.fan_in>={FAN_IN}', 'coupling', subject('file', path, path),
                                f'{path}: imported by {count} files (fan-in {count}); a change to it reaches all of them',
                                measurements=[measurement('fan_in', count, threshold=FAN_IN)], raw_ref=f'{NAME}/imports'))
    communities = {}
    for identifier, label, path in members:
        if path and not excluded(path, exclude):
            communities.setdefault((identifier, label), set()).add(path)
    metrics = [{'path': path, 'granularity': 'file', 'measurements': {'fan_in': fan_in.get(path, 0), 'fan_out': fan_out.get(path, 0)}}
               for path in sorted(set(fan_in) | set(fan_out)) if not excluded(path, exclude)]
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, metrics=metrics,
                  coverage={'status': 'observed', 'relations': relations, 'import_edges': len(imports),
                            'cycles': len(cycles), 'fan_in_threshold': FAN_IN,
                            'communities': [{'name': f'{label} ({identifier})', 'files': sorted(files)}
                                            for (identifier, label), files in sorted(communities.items())]},
                  evaluated={'cycle': {'status': 'observed', 'granularity': FILE},
                             'coupling': {'status': 'observed', 'granularity': FILE}})

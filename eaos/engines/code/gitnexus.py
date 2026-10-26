"""GitNexus: a knowledge graph of the code, read for its import cycles, its most depended-on files and its communities.

`gitnexus analyze` writes where it reads: its index, and by default AGENTS.md, CLAUDE.md and skill files,
and it touches .git. So it never runs on the project. It runs on a real copy (not hardlinks: a hardlinked
file is the original) without .git or dependency folders, with --index-only so it injects nothing, and
with GITNEXUS_HOME inside the work directory so its registry stays out of the user's home.

It is a third witness beside EAOS's own graph, CodeGraph and dependency-cruiser. Its cycles are the
source graph's (type imports included); a file at least FAN_IN files import is a coupling finding; its
communities (Leiden clusters) are candidate boundaries of today's components for S02 and NS7, written to
facts/external.json -> summary.communities. Agreement between witnesses raises a claim; disagreement is
recorded and decided by none of them. Two of its cycles are its own misreading of Python, never a finding
(`misread`): a module of a package reading a sibling (`from . import core`) read as importing the package's
`__init__.py`, and a standard library module (`import html`) read as a project file of that name; on EAOS they were
all six of its cycles (M4.6, 2026-10-24). The licence is non-commercial (eaos/data/toolchain.json license_note).
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

from .. import tool
from ..contract import ERROR, FILE, OBSERVED, Report, finding, measurement, subject
from ..process import run, which

NAME = BINARY = 'gitnexus'
PINNED = tool.pinned(NAME)
FAN_IN = 20
PAGE, PIPE_LIMIT = 300, 65536
NOT_COPIED = ('.git', 'node_modules', '.venv', 'venv', 'dist', 'build', '.next', '__pycache__', 'vendor', 'coverage')


def capabilities():
    from ..contract import Capability
    return [Capability('cycle', 'gitnexus.check.cycles', granularity=FILE),
            Capability('coupling', f'gitnexus.fan_in>={FAN_IN}', granularity=FILE)]


def version(): return tool.version(BINARY)


def table(markdown):
    """Rows of the markdown table `gitnexus cypher` prints, as lists of cell strings."""
    lines = [line.strip() for line in (markdown or '').splitlines() if line.strip().startswith('|')]
    return [[cell.strip() for cell in line.strip('|').split(' | ')] for line in lines[2:]]


def excluded(path, patterns):
    return any(f'/{pattern.strip("/")}/' in f'/{path}' for pattern in patterns)


class _Index:
    """The copy GitNexus indexed, and the seconds its commands have taken so far."""

    def __init__(self, binary, copy, env, seconds):
        self.binary, self.copy, self.env, self.seconds = binary, copy, env, seconds

    def cypher(self, query):
        """All rows of a query, a page at a time: piped, the CLI stops writing at 64 KiB, so a page that
        reaches that size is an error, never a silently shorter answer."""
        rows, offset = [], 0
        while True:
            code_, out, error_, spent = run([self.binary, 'cypher', '-r', str(self.copy), f'{query} SKIP {offset} LIMIT {PAGE}'],
                                            cwd=self.copy, env=self.env, timeout=600)
            self.seconds += spent
            if code_: raise RuntimeError(error_.strip()[-300:] or f'cypher exit {code_}')
            if len(out.encode()) >= PIPE_LIMIT: raise RuntimeError(f'a page of {PAGE} rows reached the {PIPE_LIMIT}-byte output limit')
            page = table(json.loads(out[out.index('{'):]).get('markdown'))
            rows += page
            if len(page) < PAGE: return rows
            offset += PAGE

    def check_cycles(self):
        """(the cycles, or None when the answer is not JSON; the command's error output)."""
        code, out, error, spent = run([self.binary, 'check', '--cycles', '--json', '-r', str(self.copy)], cwd=self.copy, env=self.env, timeout=600)
        self.seconds += spent
        try: return json.loads(out[out.index('{'):]).get('cycles') or [], error
        except ValueError: return None, error


def _indexed(target, workdir):
    """(the index of a fresh copy of the project, why indexing failed or None)."""
    workdir = Path(workdir).resolve() / NAME
    if workdir.exists(): shutil.rmtree(workdir)
    copy, home = workdir / 'copy', workdir / 'home'
    shutil.copytree(Path(target).resolve(), copy, symlinks=True, ignore=shutil.ignore_patterns(*NOT_COPIED))
    home.mkdir(parents=True)
    env = {**os.environ, 'GITNEXUS_HOME': str(home)}
    binary = which(BINARY)
    code, _, error, seconds = run([binary, 'analyze', '.', '--index-only', '--skip-git', '--skip-fts'], cwd=copy, env=env,
                                  timeout=1800)
    return _Index(binary, copy, env, seconds), ((error.strip()[-300:] or f'exit {code}') if code else None)


def _graph(index):
    """(import edges, community members, {relation kind: count}) of the indexed copy."""
    imports = index.cypher("MATCH (a:File)-[r]->(b:File) WHERE r.type='IMPORTS' RETURN a.filePath AS source, b.filePath AS sink ORDER BY source, sink")
    members = index.cypher("MATCH (s)-[r]->(c:Community) WHERE r.type='MEMBER_OF' RETURN DISTINCT c.id AS cid, c.label AS clabel, "
                           "s.filePath AS path ORDER BY cid, path")
    relations = dict((kind, int(count)) for kind, count in index.cypher("MATCH ()-[r]->() RETURN r.type AS kind, count(*) AS n ORDER BY kind"))
    return imports, members, relations


def misread(cycle, copy):
    """Whether a cycle of Python files has a hop GitNexus misread: into the `__init__.py` of the importing module's own
    package (`from . import sibling` loads the sibling, not the package's code), or into a file named like a standard
    library module the importer imports by that bare name (`import html`)."""
    hops = list(zip(cycle, cycle[1:] + cycle[:1]))
    return any(a.endswith('.py') and b.endswith('.py') and (_own_package(a, b) or _standard(a, b, copy)) for a, b in hops)


def _own_package(a, b):
    return Path(b).name == '__init__.py' and Path(a).parent == Path(b).parent and Path(a).name != '__init__.py'


def _standard(a, b, copy):
    stem = Path(b).stem
    if stem not in sys.stdlib_module_names: return False
    try: text = (Path(copy) / a).read_text(encoding='utf-8', errors='replace')
    except OSError: return False
    return bool(re.search(rf'^\s*import {stem}\b', text, re.M)) and not re.search(rf'^\s*from \.+\S* import .*\b{stem}\b', text, re.M)


def _cycle_findings(cycles, exclude, found, copy):
    """One finding per distinct cycle with a file outside the excluded folders, its misreadings left out (misread)."""
    findings, seen = [], set()
    for cycle in cycles:
        members_ = cycle.get('files') or []
        key = tuple(sorted(set(members_)))
        if not key or key in seen or all(excluded(path, exclude) for path in key) or misread(members_, copy): continue
        seen.add(key)
        findings.append(finding(NAME, found, 'gitnexus.check.cycles', 'cycle', subject('module', ' -> '.join(key), key[0]),
                                'import cycle (type imports included): ' + ' -> '.join(members_),
                                raw_ref=f'{NAME}/check-cycles', sites=[{'path': path, 'line': None} for path in key]))
    return findings


def _fans(imports):
    fan_in, fan_out = {}, {}
    for source, sink in imports:
        fan_in[sink] = fan_in.get(sink, 0) + 1
        fan_out[source] = fan_out.get(source, 0) + 1
    return fan_in, fan_out


def _fan_findings(fan_in, exclude, found):
    """A coupling finding for each file at least FAN_IN files import, the most imported first."""
    return [finding(NAME, found, f'gitnexus.fan_in>={FAN_IN}', 'coupling', subject('file', path, path),
                    f'{path}: imported by {count} files (fan-in {count}); a change to it reaches all of them',
                    measurements=[measurement('fan_in', count, threshold=FAN_IN)], raw_ref=f'{NAME}/imports')
            for path, count in sorted(fan_in.items(), key=lambda item: (-item[1], item[0]))
            if count >= FAN_IN and not excluded(path, exclude)]


def _communities(members, exclude):
    communities = {}
    for identifier, label, path in members:
        if path and not excluded(path, exclude):
            communities.setdefault((identifier, label), set()).add(path)
    return [{'name': f'{label} ({identifier})', 'files': sorted(files)} for (identifier, label), files in sorted(communities.items())]


def analyze(target, workdir, exclude=(), formats=None):
    declined, found = tool.started(NAME, BINARY, target)
    if declined: return declined
    index, failure = _indexed(target, workdir)
    if failure:
        return Report(NAME, found, PINNED, ERROR, seconds=index.seconds, reason=failure)
    try: imports, members, relations = _graph(index)
    except (RuntimeError, ValueError) as problem:
        return Report(NAME, found, PINNED, ERROR, seconds=index.seconds, reason=f'query failed: {problem}'[:300])
    cycles, error = index.check_cycles()
    if cycles is None: return Report(NAME, found, PINNED, ERROR, seconds=index.seconds, reason=f'check --cycles: {error.strip()[-200:]}')
    fan_in, fan_out = _fans(imports)
    findings = _cycle_findings(cycles, exclude, found, index.copy) + _fan_findings(fan_in, exclude, found)
    metrics = [{'path': path, 'granularity': 'file', 'measurements': {'fan_in': fan_in.get(path, 0), 'fan_out': fan_out.get(path, 0)}}
               for path in sorted(set(fan_in) | set(fan_out)) if not excluded(path, exclude)]
    return Report(NAME, found, PINNED, OBSERVED, seconds=index.seconds, findings=findings, metrics=metrics,
                  coverage={'status': 'observed', 'relations': relations, 'import_edges': len(imports),
                            'cycles': len(cycles), 'fan_in_threshold': FAN_IN,
                            'communities': _communities(members, exclude)},
                  evaluated={'cycle': {'status': 'observed', 'granularity': FILE},
                             'coupling': {'status': 'observed', 'granularity': FILE}})

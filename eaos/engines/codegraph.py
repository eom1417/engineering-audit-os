"""CodeGraph: a persistent cross-file symbol graph over 38 languages.

Run one-shot with --graph-only: no embeddings, no MCP handshake, no model. Only the two tools
whose output shape we verified against this repository are used; the rest are declared unused
rather than assumed to work.
"""
import json
from pathlib import Path

from .contract import Capability, Report, OBSERVED, UNAVAILABLE, ERROR, FILE, finding, subject
from .process import run, which

NAME, BINARY, PINNED = 'codegraph', 'codegraph-server', 'v0.20.1'
TOOLS = {'codegraph_find_circular_deps': 'cycle'}
# Measured over two cold, isolated runs of an unchanged tree: dead-import detection returned 131
# entries and then 129. A fact set that is not byte-identical is not a fact set, so the tool is
# recorded as declined rather than quietly making our own reproducibility claim false.
DECLINED = {'codegraph_find_dead_imports':
            'not reproducible: two cold runs over an unchanged tree returned 131 and 129 entries'}
RESULT_LIMIT = 5000


def capabilities():
    return [Capability(kind, tool, granularity=FILE) for tool, kind in sorted(TOOLS.items())]


def version():
    binary = which(BINARY)
    if not binary:
        return None
    code, out, _, _ = run([binary, '--info'], timeout=60)
    return out.strip().split()[1] if code == 0 and len(out.split()) > 1 else None


def _one_tool(binary, target, tool, timeout, home):
    # The engine persists its graph under $HOME and reuses it, so a run would depend on earlier runs.
    # Pointing HOME at this run's workdir buys reproducibility at the price of a cold index.
    code, out, error, seconds = run([binary, '--graph-only', '-w', str(target), '--run-tool', tool,
                                     '--tool-args', json.dumps({'limit': RESULT_LIMIT})],
                                    timeout=timeout, env={'HOME': str(home)})
    if code != 0 or not out.strip():
        return None, seconds, error.strip()[-200:] or f'exit {code}'
    try:
        return json.loads(out), seconds, ''
    except ValueError:
        return None, seconds, 'tool did not return JSON'


def analyze(target, workdir, exclude=(), formats=None, timeout=900):
    found = version()
    if found is None:
        return Report(NAME, None, PINNED, UNAVAILABLE, reason='codegraph-server is not installed')
    workdir = Path(workdir) / 'codegraph'
    workdir.mkdir(parents=True, exist_ok=True)
    home = workdir / 'home'
    home.mkdir(parents=True, exist_ok=True)
    findings, elapsed, failures, warnings = [], 0.0, {}, {}
    for tool, kind in sorted(TOOLS.items()):
        payload, seconds, problem = _one_tool(which(BINARY), target, tool, timeout, home)
        elapsed += seconds
        if payload is None:
            failures[tool] = problem
            continue
        (workdir / f'{tool}.json').write_text(json.dumps(payload, indent=1), encoding='utf-8')
        # The engine says when its own answer may be incomplete. Recording that as a clean "none
        # found" is the absence-as-evidence error this product exists to catch.
        if payload.get('warning'):
            warnings[tool] = payload['warning']
        for cycle in payload.get('cycles', []):
            members = cycle if isinstance(cycle, list) else cycle.get('modules', [])
            findings.append(finding(NAME, found, tool, kind, subject('module', ' -> '.join(map(str, members))),
                                    'cycle: ' + ' -> '.join(map(str, members)), raw_ref=f'codegraph/{tool}.json'))
    if failures and len(failures) == len(TOOLS):
        return Report(NAME, found, PINNED, ERROR, seconds=elapsed, reason='; '.join(failures.values())[:300])
    findings.sort(key=lambda row: row['id'])
    coverage = {'status': 'observed', 'tools_run': sorted(set(TOOLS) - set(failures)), 'tools_failed': failures,
                'engine_warnings': warnings,
                'declined_tools': DECLINED, 'mode': 'graph-only (no embeddings, no model)'}
    return Report(NAME, found, PINNED, OBSERVED, seconds=elapsed, findings=findings, coverage=coverage,
                  provenance={'tools': sorted(TOOLS)}, raw=str(workdir),
                  evaluated={TOOLS[tool]: {'status': 'partial' if tool in warnings else 'observed',
                                           'granularity': FILE}
                             for tool in TOOLS if tool not in failures})

"""CodeGraph engine: imports, calls, complexity, hot paths across every language the engine parses.

Four tools, all run as one-shot invocations against the pinned CodeGraph binary:

  codegraph_get_dependency_graph  module and file dependency graph
  codegraph_get_call_graph        callers/callees of a symbol
  codegraph_analyze_complexity    per-symbol complexity (lines, branches, etc.)
  codegraph_find_hot_paths        ranked call-paths through the codebase

Each tool returns a JSON payload. The wrapper flattens the payload into the engine's
fact shape and emits a `module_edge_external` / `call_edge_external` fact for each
call or import. Tools that return a warning ("unknown tool", "invalid URI", "missing
parameter") are downgraded to `partial` and the reason recorded in the summary.

The wrapper never guesses what the tool would have returned; if the payload is empty
or it failed, the tool is recorded as DECLINED with a measured reason.
"""
import json
import subprocess
from pathlib import Path

NAME, VERSION, PINNED = 'codegraph', '1', 'v0.20.1'

TOOLS = {
    'codegraph_get_dependency_graph': 'module_edge_external',
    'codegraph_get_call_graph': 'call_edge_external',
    'codegraph_analyze_complexity': 'symbol_metric_external',
    'codegraph_find_hot_paths': 'hot_path_external',
}

BINARY = '/workspace/engine-tools/bin/codegraph-server'


def _run(tool, args, workspace, timeout=600):
    """One tool, one payload. Never raise: return (payload_str_or_None, error_str_or_None)."""
    cmd = [BINARY, '--graph-only', '-w', str(workspace),
           '--run-tool', tool, '--tool-args', json.dumps(args or {})]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = result.stdout.strip()
        err = result.stderr.strip()
        if 'Tool ' in err and ' failed: ' in err:
            return out or None, err.split('Tool ', 1)[-1].split(' failed: ', 1)[-1].strip()
        if result.returncode != 0 and not out:
            return None, err or f'exit {result.returncode}'
        if not out:
            return None, 'empty payload'
        return out, None
    except subprocess.TimeoutExpired:
        return None, f'timeout after {timeout}s'
    except FileNotFoundError:
        return None, f'binary missing at {BINARY}'


def _parse_payload(text):
    if not text: return None
    text = text.strip()
    if not text.startswith('{'):
        for line in text.splitlines():
            line = line.strip()
            if line.startswith('{'):
                text = line; break
    try: return json.loads(text)
    except ValueError: return None


def _module_edges_from_dep_graph(payload, root):
    facts = []
    edges = payload.get('edges', []) if isinstance(payload, dict) else []
    for edge in edges:
        facts.append({'kind': 'module_edge_external',
                      'location': {'path': root},
                      'value': {'from': edge.get('from', ''), 'to': edge.get('to', ''),
                                 'weight': edge.get('weight', 1), 'tool': 'codegraph_get_dependency_graph'}})
    return facts


def _call_edges_from_call_graph(payload, root):
    facts = []
    symbol = payload.get('symbol', {}) if isinstance(payload, dict) else {}
    path = symbol.get('path', root) if isinstance(symbol, dict) else root
    for call in payload.get('callees', []) or []:
        facts.append({'kind': 'call_edge_external',
                      'location': {'path': path},
                      'value': {'caller': symbol.get('name', ''),
                                 'callee': call.get('name', ''),
                                 'callee_path': call.get('path', ''),
                                 'line': call.get('line_start', 0),
                                 'tool': 'codegraph_get_call_graph'}})
    for call in payload.get('callers', []) or []:
        facts.append({'kind': 'call_edge_external',
                      'location': {'path': path},
                      'value': {'caller': call.get('name', ''),
                                 'callee': symbol.get('name', ''),
                                 'caller_path': call.get('path', ''),
                                 'line': call.get('line_start', 0),
                                 'tool': 'codegraph_get_call_graph'}})
    return facts


def _complexity_facts(payload, root):
    if not isinstance(payload, dict): return []
    fns = payload.get('functions', payload.get('symbols', [])) or []
    out = []
    for fn in fns:
        out.append({'kind': 'symbol_metric_external',
                     'location': {'path': fn.get('path', root)},
                     'value': {'name': fn.get('name', ''), 'lines': fn.get('lines', 0),
                                'branches': fn.get('branches', 0),
                                'complexity': fn.get('complexity', 0),
                                'tool': 'codegraph_analyze_complexity'}})
    return out


def _hot_paths(payload, root):
    if not isinstance(payload, dict): return []
    out = []
    for path in payload.get('paths', payload.get('hot_paths', [])) or []:
        out.append({'kind': 'hot_path_external',
                     'location': {'path': root},
                     'value': {'symbol': path.get('symbol', ''),
                                'transitive_callers': path.get('transitive_callers', 0),
                                'score': path.get('score', 0),
                                'tool': 'codegraph_find_hot_paths'}})
    return out


CONVERTERS = {
    'codegraph_get_dependency_graph': _module_edges_from_dep_graph,
    'codegraph_get_call_graph': _call_edges_from_call_graph,
    'codegraph_analyze_complexity': _complexity_facts,
    'codegraph_find_hot_paths': _hot_paths,
}


def run(target, out, tools=None, **options):
    target = Path(target).resolve()
    available = Path(BINARY).is_file()
    summary = {'binary': BINARY, 'tools': {}, 'partial': [], 'declined': []}
    if not available:
        summary['declined'].append({'tool': '*', 'reason': 'binary missing'})
        return {'facts': [], 'summary': summary, 'available': False,
                'input_sha': '', 'reason': f'CodeGraph binary not installed at {BINARY}'}
    facts = []
    tool_selection = tools or {}

    if tool_selection.get('get_dependency_graph', True):
        text, err = _run('codegraph_get_dependency_graph', {'uri': f'file://{target}',
                            'summary': True, 'direction': 'both', 'depth': 3}, target)
        _record(summary, 'codegraph_get_dependency_graph', text, err)
        payload = _parse_payload(text)
        if payload:
            facts.extend(CONVERTERS['codegraph_get_dependency_graph'](payload, '.'))

    if tool_selection.get('find_hot_paths', True):
        text, err = _run('codegraph_find_hot_paths', {'limit': 5, 'depth': 3}, target)
        _record(summary, 'codegraph_find_hot_paths', text, err)
        payload = _parse_payload(text)
        if payload:
            facts.extend(CONVERTERS['codegraph_find_hot_paths'](payload, '.'))

    if tool_selection.get('get_call_graph', True):
        probe_paths = [target / 'cmd' / 'enola' / 'main.go',
                       target / 'pkg' / 'plugin' / 'plugin.go',
                       target / 'internal' / 'factpath' / 'factpath.go']
        landed = False
        for probe in probe_paths:
            if not probe.exists(): continue
            text, err = _run('codegraph_get_call_graph', {'uri': f'file://{probe}',
                                                          'name': probe.stem, 'depth': 2}, target)
            if err:
                _record(summary, 'codegraph_get_call_graph', text, err)
                continue
            payload = _parse_payload(text)
            if payload and payload.get('symbol'):
                facts.extend(CONVERTERS['codegraph_get_call_graph'](payload, '.'))
                summary['tools']['codegraph_get_call_graph'] = 'ok'
                landed = True
                break
        if not landed:
            summary['tools']['codegraph_get_call_graph'] = 'partial'
            summary['partial'].append({'tool': 'codegraph_get_call_graph',
                                        'reason': 'no probe landed a symbol'})

    if tool_selection.get('analyze_complexity', True):
        text, err = _run('codegraph_analyze_complexity', {'limit': 5}, target)
        if err:
            _record(summary, 'codegraph_analyze_complexity', text, err)
        else:
            payload = _parse_payload(text)
            if payload:
                facts.extend(CONVERTERS['codegraph_analyze_complexity'](payload, '.'))
                summary['tools']['codegraph_analyze_complexity'] = 'ok'
    return {'facts': facts, 'summary': summary,
            'available': True, 'input_sha': '', 'reason': None}


def _record(summary, tool, text, err):
    if err:
        summary['tools'][tool] = 'declined' if 'binary missing' in err else 'partial'
        summary['declined'].append({'tool': tool, 'reason': err})
    elif text:
        summary['tools'][tool] = 'ok'
    else:
        summary['tools'][tool] = 'partial'
        summary['partial'].append({'tool': tool, 'reason': 'no payload'})

def version():
    """Return the installed CodeGraph version, or None if missing."""
    import subprocess
    if not Path(BINARY).is_file(): return None
    try:
        result = subprocess.run([BINARY, '--version'], capture_output=True, text=True, timeout=30)
        return (result.stdout + result.stderr).strip().splitlines()[-1].strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None

def capabilities():
    """One Capability per tool the wrapper exposes. The kind is the fact vocabulary each produces."""
    from eaos.engines.contract import Capability
    return [Capability(kind=kind, rule='codegraph:' + tool, granularity='file')
            for tool, kind in TOOLS.items()]

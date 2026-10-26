"""CodeGraph's tool payloads turned into the engine's facts (eaos/engines/code/codegraph.py asks the tools): module and
call edges whose ends are named, per-symbol complexity, and hot paths. A payload that is not what a tool returns gives
no fact."""
import json
from pathlib import Path


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
    """Turn one file's dependency payload into module edges whose ends are named, not numbered.

    The payload numbers its ends: `edges[].from` and `.to` are node ids. Only a node of type
    `codefile` carries a real path; a `module` node carries a name and an empty path. Emitting the
    raw ids would hand the reader a number it cannot resolve, so an edge whose ends we cannot name
    is dropped rather than recorded as an edge between unknowns.
    """
    if not isinstance(payload, dict): return []
    nodes = {str(node.get('id')): node for node in payload.get('nodes') or []}
    edges = (_dep_edge(edge, nodes, root) for edge in payload.get('edges') or [] if edge.get('type') in (None, 'import'))
    return [fact for fact in edges if fact]


def _dep_edge(edge, nodes, root):
    """The module edge between two named ends; None when either end cannot be named."""
    ends = _named_ends(edge, nodes)
    if not ends: return None
    source, destination, from_path, to_name = ends
    return {'kind': 'module_edge_external',
            'location': {'path': _relative(from_path, root)},
            'value': {'from': _relative(from_path, root), 'to': to_name,
                      'to_path': _relative(destination.get('path') or '', root) or None,
                      'to_is_external': bool(destination.get('is_external')),
                      'language': destination.get('language') or source.get('language') or '',
                      'weight': 1, 'tool': 'codegraph_get_dependency_graph'}}


def _named_ends(edge, nodes):
    """(source, destination, the source's path, the destination's name) of an edge, or None when an end has no name."""
    source, destination = nodes.get(str(edge.get('from'))), nodes.get(str(edge.get('to')))
    if not source or not destination: return None
    from_path = source.get('path') or ''
    to_name = destination.get('name') or destination.get('path') or ''
    return (source, destination, from_path, to_name) if from_path and to_name else None


def _relative(path, root):
    """A path the reader can open: relative to the scanned tree, never the engine's absolute path."""
    if not path: return ''
    try: return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except (ValueError, OSError): return str(path)


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


def _complexity_facts(payload, root, path=None):
    """Per-symbol complexity for one file. The file is the caller's, not the payload's.

    `codegraph_analyze_complexity` answers about the file named in its `uri` and does not repeat
    that path in every function it returns. Recording the scanned root instead would put every
    measurement at `.` and make it unjoinable to a flow, so the caller's path is authoritative.
    """
    if not isinstance(payload, dict): return []
    fns = payload.get('functions', payload.get('symbols', [])) or []
    out = []
    for fn in fns:
        detail = fn.get('details') or {}
        out.append({'kind': 'symbol_metric_external',
                     'location': {'path': path or fn.get('path') or root,
                                  'line': fn.get('line_start', 0)},
                     'value': {'name': fn.get('name', ''),
                                'lines': detail.get('lines_of_code', fn.get('lines', 0)),
                                'branches': detail.get('complexity_branches', fn.get('branches', 0)),
                                'loops': detail.get('complexity_loops', 0),
                                'nesting': detail.get('complexity_nesting', 0),
                                'complexity': fn.get('complexity', 0),
                                'grade': fn.get('grade', ''),
                                'rule': 'performance',
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

"""LangGraph graphs read without running them (eaos/facts/declared_pipelines/detect.py): add_node, add_edge, the
entry and finish points and add_conditional_edges, a node name taken from a `for` loop over a literal list counting as
each listed value."""
import ast

from .. import call_name
from .read import slug, site, Found, _str, _strs, _unparse, describe


def langgraph(py, out):
    """The LangGraph graphs of every module that imports LangGraph."""
    for rel, tree in py.trees.items():
        if any((module or '').split('.')[0] == 'langgraph' for module, _ in py.imports.get(rel, {}).values()):
            out.extend(graphs_of(py, rel, tree))


def graphs_of(py, rel, tree):
    """The graphs one module builds, with their stages, edges and routers; those with no stage are left out."""
    graphs = _graphs(py, rel, tree)
    if not graphs: return []
    loops = _loop_values(tree)
    calls = sorted((s for s in ast.walk(tree) if isinstance(s, ast.Call) and isinstance(s.func, ast.Attribute)
                    and _unparse(s.func.value) in graphs), key=lambda s: s.lineno)
    for call in calls:
        graph = _Graph(graphs[_unparse(call.func.value)], site(rel, call.lineno, py.line(rel, call.lineno)), loops(call))
        _graph_call(py, rel, graph, call)
    return [f for f in graphs.values() if f.stages]


def _graphs(py, rel, tree):
    """{name: Found} of every graph the module builds (StateGraph, Graph, MessageGraph)."""
    graphs = {}
    for sub in ast.walk(tree):
        if isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Call) and call_name(sub.value.func) in ('StateGraph', 'Graph', 'MessageGraph') \
                and len(sub.targets) == 1 and isinstance(sub.targets[0], (ast.Name, ast.Attribute)):
            name = _unparse(sub.targets[0])
            graphs[name] = Found(f'{rel}:{name}', f'{name} ({rel})', 'langgraph', site(rel, sub.lineno, py.line(rel, sub.lineno)),
                                 [site(rel, sub.lineno, py.line(rel, sub.lineno))])
    return graphs


class _Graph:
    """A graph read at one call: the stage of a label, and the labels an argument names (a loop's values included)."""

    def __init__(self, found, where, bound):
        self.found, self.where, self.bound = found, where, bound

    def key(self, label):
        return self.found.stage(label, self.where, kind='source' if label == 'START' else 'sink' if label == 'END' else 'stage')

    def labels(self, expr):
        if _str(expr) is not None: return [_str(expr)]
        if isinstance(expr, ast.Name): return self.bound.get(expr.id) or [expr.id]
        if isinstance(expr, (ast.List, ast.Tuple)): return [label for e in expr.elts for label in self.labels(e)]
        return []

    def first(self, expr):
        return (self.labels(expr) or [None])[0]


def _graph_call(py, rel, g, call):
    """One call on a graph: a node, an edge, its entry or finish point, or conditional edges."""
    method, args, found, where = call.func.attr, call.args, g.found, g.where
    if method == 'add_node' and args: _add_node(py, rel, g, args)
    elif method == 'add_edge' and len(args) >= 2: _add_edge(g, args)
    elif method in ('set_entry_point', 'set_finish_point') and args:
        ends = (g.key('START'), g.key(g.first(args[0]))) if method == 'set_entry_point' else (g.key(g.first(args[0])), g.key('END'))
        found.edge(*ends, 'declared', where)
    elif method == 'add_conditional_edges' and len(args) >= 2: _conditional(py, rel, g, call)


def _add_edge(g, args):
    """An edge from each node the first argument names to each the second names."""
    for a in g.labels(args[0]):
        for b in g.labels(args[1]): g.found.edge(g.key(a), g.key(b), 'declared', g.where, kind='data')


def _add_node(py, rel, g, args):
    """A node, and the function it runs, described from its body when the project defines it."""
    key = g.key(g.first(args[0]))
    fn = args[1] if len(args) > 1 else args[0]
    target = py.resolve(rel, fn.id) if isinstance(fn, ast.Name) else None
    g.found.stages[key]['symbol'] = f"{target[0][:-3].replace('/', '.')}.{target[1].name}" if target else _unparse(fn, 120)
    if target: describe(py, target[0], target[1], g.found.stages[key])


def _conditional(py, rel, g, call):
    """Conditional edges: a router stage, and an edge to each node its path map names (unresolved when it names none)."""
    found, where = g.found, g.where
    source = g.key(g.first(call.args[0]))
    mapping = call.args[2] if len(call.args) > 2 else next((k.value for k in call.keywords if k.arg in ('path_map', 'conditional_edge_mapping')), None)
    branches = []
    for condition, value, evidence in _routes(py, rel, g, call, mapping):
        to = g.key(g.first(value))
        branches.append({'condition': condition, 'to': to, 'evidence': evidence})
        found.edge(source, to, 'declared', where, kind='control', condition=condition)
    if not isinstance(mapping, (ast.Dict, ast.List, ast.Tuple)):
        found.unresolved.append({'id': f'{source}:route:{call.lineno}', 'pipeline': found.id, 'stage': source,
                                 'call': _unparse(call.args[1]), 'reason': 'the router returns node names EAOS cannot list', 'evidence': where})
    router_fn = g.first(call.args[1]) or _unparse(call.args[1], 40) or 'router'
    router = found.stage(router_fn, where, kind='router')
    found.edge(source, router, 'declared', where, kind='control')
    found.routers.append({'id': f'{found.id}:{slug(router_fn)}:{call.lineno}', 'pipeline': found.id, 'stage': router,
                          'kind': 'conditional_edges', 'table': router_fn, 'on': f'{router_fn}(state)', 'entry': where,
                          'branches': branches, 'total': None if branches else False, 'default': None, 'unhandled': []})


def _routes(py, rel, g, call, mapping):
    """(condition, the node it routes to, evidence) of a path map: a dict of conditions, or a list of node names."""
    if isinstance(mapping, ast.Dict):
        return [(_str(key) or _unparse(key), value, site(rel, line, py.line(rel, line)))
                for key, value in zip(mapping.keys, mapping.values) for line in [key.lineno if key else call.lineno]]
    if isinstance(mapping, (ast.List, ast.Tuple)): return [(g.first(value), value, g.where) for value in mapping.elts]
    return []


def _loop_values(tree):
    """A function giving, for a node, {name: [literal strings]} of the `for name in <literal list>` loops around it (the list
    written in place or assigned to a name), so `add_edge('a', name)` in such a loop means each listed value."""
    parents, lists = _parents(tree), _literal_lists(tree)

    def values(node):
        found, current = {}, parents.get(id(node))
        while current is not None:
            if isinstance(current, ast.For) and isinstance(current.target, ast.Name):
                items = _loop_items(current, lists)
                if items: found.setdefault(current.target.id, items)
            current = parents.get(id(current))
        return found
    return values


def _parents(tree):
    """{id(node): its parent} over the whole tree."""
    return {id(child): parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _literal_lists(tree):
    """{name: [strings]} of the names assigned a list or tuple of string literals."""
    lists = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and \
                isinstance(node.value, (ast.List, ast.Tuple)) and node.value.elts and all(_str(e) is not None for e in node.value.elts):
            lists[node.targets[0].id] = _strs(node.value)
    return lists


def _loop_items(loop, lists):
    """The strings a `for` loop walks: a list written in place, or one assigned to the name it iterates."""
    if isinstance(loop.iter, (ast.List, ast.Tuple)): return _strs(loop.iter)
    return lists.get(loop.iter.id) if isinstance(loop.iter, ast.Name) else None

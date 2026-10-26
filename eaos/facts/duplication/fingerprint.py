"""Structural fingerprints: a normal form of an AST subtree that ignores names.

Two functions doing the same thing under different identifiers should produce the same
fingerprint. This is what makes the L3 ("same shape, different names") detector possible:
the reference example from the doctrine, two functions computing the same pricing rule
under different parameter names, lands in a single cluster.

The fingerprint walks one parsed AST, replaces every identifier with a slot, keeps the
control-flow and operator skeleton, and hashes the result. Two fingerprints are equal iff
the underlying shapes are equal modulo identifier choice.
"""
import ast
from collections import defaultdict
from .. import digest, make, tree_sitter_tree
from ..source import language_of

NAME = 'fingerprint'
VERSION = '2'
LIMITATIONS = [
    'Identifier renames are normalised; literal renames are not.',
    'A fingerprint is a syntactic observation; two functions with identical fingerprints can still '
    'behave differently when their parameters carry different units, ranges or business meanings.',
    'Larger syntactic trees give longer fingerprints; the cluster size threshold keeps noise down.',
    'Only parsed languages produce fingerprints; unparsed files stay out of the denominator.',
]

_MIN_SIZE = 8
_CLUSTER_MIN_MEMBERS = 2


_UNSHAPED = frozenset({'ctx', 'type_comment', 'type_ignore', 'end_lineno', 'end_col_offset', 'lineno', 'col_offset', 'parent'})


def _field_shape(value, depth):
    """One field of a node: a subtree, a list of subtrees and plain values, or the type of a plain value."""
    if isinstance(value, ast.AST): return _python_shape(value, depth)
    if isinstance(value, list): return [_python_shape(item, depth) if isinstance(item, ast.AST) else item for item in value]
    return type(value).__name__


def _python_shape(node, depth=0):
    """Render a Python AST as a normalised shape tree, with depth to bound recursion."""
    if depth > 60: return ('<over>',)
    return (type(node).__name__, tuple((field, _field_shape(value, depth + 1)) for field, value in ast.iter_fields(node)
                                       if field not in _UNSHAPED))


_PY_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)


def _python_row(node, scope):
    shape_str = repr(_python_shape(node))
    return {'qualified': '.'.join(scope + [node.name]), 'name': node.name,
            'start': node.lineno, 'end': node.end_lineno or node.lineno,
            'size': sum(1 for _ in ast.walk(node)), 'shape_str': shape_str,
            'shape_sha': digest(shape_str.encode('utf-8'))}


def _visit_python(node, scope, rows):
    """Every function and method under `node`, qualified by the functions and classes around it."""
    if isinstance(node, _PY_FUNCTIONS): rows.append(_python_row(node, scope))
    named = isinstance(node, _PY_FUNCTIONS + (ast.ClassDef,))
    if named: scope.append(node.name)
    for child in ast.iter_child_nodes(node): _visit_python(child, scope, rows)
    if named: scope.pop()


def _python_fingerprints(text, rel):
    """Return [(qualified_name, sha, body_lines, shape_str, normalized, end_line)] or None on parse failure."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    rows = []
    for node in tree.body: _visit_python(node, [], rows)
    return rows


def _tree_sitter_shape_subtree(node, depth=0, max_depth=60):
    """Render a tree-sitter subtree as a normalised shape, ignoring identifier text."""
    if depth > max_depth: return ('<over>',)
    if not node.children:
        return (node.type,)
    children_shapes = []
    for child in node.children:
        if not child.is_named:
            continue
        children_shapes.append(_tree_sitter_shape_subtree(child, depth + 1, max_depth))
    return (node.type, tuple(children_shapes))


def _subtree_size(node):
    """How many nodes the symbol's whole body holds, the same quantity the Python path reports.

    `_MIN_SIZE` is one threshold applied to both paths, so both have to be the same measurement.
    Counting only a node's direct children made every Go function score 5 against a threshold of
    8: 1021 Go files produced 7 fingerprints and no duplicate cluster, and the dashboard read that
    silence as a perfect "one source of truth". A threshold is only meaningful over one scale.
    """
    total = 0
    stack = [node]
    while stack:
        current = stack.pop()
        total += 1
        stack.extend(current.children)
    return total


_TS_FUNCTIONS = {'function_declaration', 'function_definition', 'function_item',
                 'method_declaration', 'method_definition', 'function', 'function_expression',
                 'arrow_function', 'generator_function_declaration', 'singleton_method',
                 'function_signature', 'method_signature', 'local_function_statement'}
_TS_CONTAINERS = {'class_declaration', 'class_definition', 'impl_item', 'class_specifier', 'struct_item', 'object_definition'}


def _function_types(language):
    types = set(_TS_FUNCTIONS)
    # In TypeScript a signature is a declaration with no body: an overload, an interface member, a .d.ts entry.
    # Two signatures with the same parameter shape share no logic, so there is nothing to canonicalize.
    if language in ('typescript', 'tsx'): types -= {'function_signature', 'method_signature'}
    return types


def _tree_row(node, scope):
    shape_str = repr(_tree_sitter_shape_subtree(node))
    return {'qualified': '.'.join(scope + [node.type]),
            'name': node.type, 'start': node.start_point[0] + 1,
            'end': node.end_point[0] + 1, 'size': _subtree_size(node),
            'shape_str': shape_str, 'shape_sha': digest(shape_str.encode('utf-8'))}


def _walk_tree(node, scope, walk):
    types = walk['types']
    if node.type in types: walk['rows'].append(_tree_row(node, scope))
    inner = scope + [node.type if node.type in types else '']
    for child in node.children:
        _walk_tree(child, inner if child.type in types or child.type in _TS_CONTAINERS else scope, walk)


def _tree_sitter_fingerprints(text, rel, language):
    """Fingerprint every function-shaped node in a tree-sitter file."""
    tree = tree_sitter_tree(text, language)
    if tree is None: return None
    walk = {'types': _function_types(language), 'rows': []}
    _walk_tree(tree.root_node, [], walk)
    return walk['rows']


def _file_rows(text, rel, language):
    if language == 'python': return _python_fingerprints(text, rel)
    return _tree_sitter_fingerprints(text, rel, language)


def _fingerprint_files(source):
    """(every fingerprint large enough to compare, files fingerprinted, files that could not be parsed)."""
    fingerprints, observed, blocked = [], 0, 0
    for item in source.readable():
        rel = item['path']
        language = language_of(rel)
        if language is None or rel.endswith('.d.ts'): continue   # declarations only: types for code that lives elsewhere
        text = source.text(rel)
        if text is None: continue
        rows = _file_rows(text, rel, language)
        if rows is None:
            blocked += 1
            continue
        observed += 1
        for row in (row for row in rows if row['size'] >= _MIN_SIZE):
            row['path'] = rel
            fingerprints.append(row)
    return fingerprints, observed, blocked


def _distinct(members):
    # Take only members in distinct paths or distinct qualified names; ignore same name in same file.
    members.sort(key=lambda m: (m['path'], m['start']))
    distinct, seen = [], set()
    for member in members:
        key = (member['path'], member['start'])
        if key in seen: continue
        seen.add(key)
        distinct.append(member)
    return distinct


def _clusters(fingerprints):
    by_sha = defaultdict(list)
    for row in fingerprints: by_sha[row['shape_sha']].append(row)
    clusters = []
    for sha, members in sorted(by_sha.items(), key=lambda item: -len(item[1])):
        distinct = _distinct(members) if len(members) >= _CLUSTER_MIN_MEMBERS else []
        if len(distinct) < _CLUSTER_MIN_MEMBERS: continue
        clusters.append({'shape_sha': sha, 'members': distinct, 'shared_shape_size': distinct[0]['size']})
    return clusters


def _fingerprint_fact(row):
    return make('fingerprint', NAME, VERSION, row['shape_sha'],
                {'path': row['path'], 'start_line': row['start'], 'end_line': row['end'], 'symbol': row['qualified']},
                {'name': row['name'], 'size': row['size'], 'shape_sha': row['shape_sha']},
                limitations=LIMITATIONS)


def _cluster_fact(cluster):
    first = cluster['members'][0]
    return make('duplicate_cluster', NAME, VERSION, cluster['shape_sha'],
                {'path': first['path'], 'start_line': first['start']},
                {'shape_sha': cluster['shape_sha'], 'shared_size': cluster['shared_shape_size'],
                 'occurrences': [{'path': m['path'], 'start_line': m['start'], 'end_line': m['end'],
                                  'symbol': m['qualified'], 'name': m['name']} for m in cluster['members']]},
                limitations=LIMITATIONS)


def run(target, source, symbols=None, **options):
    fingerprints, files_observed, files_blocked = _fingerprint_files(source)
    fingerprints_for_facts = [_fingerprint_fact(row) for row in fingerprints]
    cluster_facts = [_cluster_fact(cluster) for cluster in _clusters(fingerprints)]
    summary = {'files_observed': files_observed, 'files_blocked': files_blocked,
               'fingerprints': len(fingerprints),
               'clusters': len(cluster_facts),
               'interpretation': 'A cluster contains symbols whose AST shape is identical up to identifier names. '
                                 'Membership is structural; the cluster itself is a hypothesis, not a defect.'}
    return {'facts': fingerprints_for_facts + cluster_facts, 'summary': summary,
            'available': True, 'input_sha': digest(''.join(sorted([m['shape_sha'] for m in fingerprints])).encode()) if fingerprints else digest(b''),
            'reason': None}

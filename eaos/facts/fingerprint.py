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
from . import digest, make
from .source import language_of

NAME = 'fingerprint'
VERSION = '1'
LIMITATIONS = [
    'Identifier renames are normalised; literal renames are not.',
    'A fingerprint is a syntactic observation; two functions with identical fingerprints can still '
    'behave differently when their parameters carry different units, ranges or business meanings.',
    'Larger syntactic trees give longer fingerprints; the cluster size threshold keeps noise down.',
    'Only parsed languages produce fingerprints; unparsed files stay out of the denominator.',
]

_MIN_SIZE = 8
_CLUSTER_MIN_MEMBERS = 2


def _python_shape(node, depth=0):
    """Render a Python AST as a normalised shape tree, with depth to bound recursion."""
    if depth > 60: return ('<over>',)
    if isinstance(node, ast.AST):
        attrs = []
        for field, value in ast.iter_fields(node):
            if field in {'ctx', 'type_comment', 'type_ignore', 'end_lineno', 'end_col_offset',
                         'lineno', 'col_offset', 'parent'}:
                continue
            if isinstance(value, ast.AST):
                attrs.append((field, _python_shape(value, depth + 1)))
            elif isinstance(value, list):
                attrs.append((field, [_python_shape(item, depth + 1) if isinstance(item, ast.AST) else item
                                       for item in value]))
            else:
                attrs.append((field, type(value).__name__))
        return (type(node).__name__, tuple(attrs))
    return type(node).__name__


def _python_walk_function(tree, rel):
    """Yield (qualified_name, start, end, sha, shape) for every top-level function and method."""
    items = []
    scope = []

    def visit(node, parent_qual):
        pieces = []
        for child in ast.iter_child_nodes(node):
            pieces.append(child)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qualified = '.'.join(scope + [node.name]) if scope else node.name
            start, end = node.lineno, node.end_lineno or node.lineno
            body_lines = (end - start + 1) if end and start else 0
            yield qualified, start, end, body_lines
            scope.append(node.name)
            for child in ast.iter_child_nodes(node):
                yield from visit(child, qualified)
            scope.pop()
            return
        if isinstance(node, ast.ClassDef):
            scope.append(node.name)
            for child in ast.iter_child_nodes(node):
                yield from visit(child, parent_qual)
            scope.pop()
            return
        for child in ast.iter_child_nodes(node):
            yield from visit(child, parent_qual)
    for node in tree.body:
        yield from visit(node, None)


def _python_fingerprints(text, rel):
    """Return [(qualified_name, sha, body_lines, shape_str, normalized, end_line)] or None on parse failure."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    rows = []
    for symbol in _python_walk_function(tree, rel):
        qualified, start, end, body_lines = symbol
        # We don't have the actual function node here, so re-find it.
    # Walk again with the actual node
    rows = []

    def visit(node, scope):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qualified = '.'.join(scope + [node.name])
            shape = _python_shape(node)
            shape_str = repr(shape)
            size = sum(1 for _ in ast.walk(node))
            rows.append({'qualified': qualified, 'name': node.name,
                         'start': node.lineno, 'end': node.end_lineno or node.lineno,
                         'size': size, 'shape_str': shape_str,
                         'shape_sha': digest(shape_str.encode('utf-8'))})
            scope.append(node.name)
            for child in ast.iter_child_nodes(node):
                visit(child, scope)
            scope.pop()
            return
        if isinstance(node, ast.ClassDef):
            scope.append(node.name)
            for child in ast.iter_child_nodes(node):
                visit(child, scope)
            scope.pop()
            return
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    for node in tree.body:
        visit(node, [])
    return rows


def _tree_sitter_shape_subtree(node, parser, depth=0, max_depth=60):
    """Render a tree-sitter subtree as a normalised shape, ignoring identifier text."""
    if depth > max_depth: return ('<over>',)
    if not node.children:
        return (node.type,)
    children_shapes = []
    for child in node.children:
        if not child.is_named:
            continue
        children_shapes.append(_tree_sitter_shape_subtree(child, parser, depth + 1, max_depth))
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


def _tree_sitter_fingerprints(text, rel, language):
    """Fingerprint every function-shaped node in a tree-sitter file."""
    try:
        from tree_sitter_language_pack import get_parser
    except ImportError:
        return None
    try:
        parser = get_parser('c_sharp' if language == 'csharp' else language)
    except Exception:
        return None
    try:
        tree = parser.parse(text.encode('utf-8'))
    except Exception:
        return None
    root = tree.root_node

    function_types = {'function_declaration', 'function_definition', 'function_item',
                      'method_declaration', 'method_definition', 'function', 'function_expression',
                      'arrow_function', 'generator_function_declaration', 'singleton_method',
                      'function_signature', 'method_signature', 'local_function_statement'}
    rows = []

    def walk(node, scope):
        if node.type in function_types:
            shape = _tree_sitter_shape_subtree(node, parser)
            shape_str = repr(shape)
            size = _subtree_size(node)
            rows.append({'qualified': '.'.join(scope + [node.type]),
                          'name': node.type, 'start': node.start_point[0] + 1,
                          'end': node.end_point[0] + 1, 'size': size,
                          'shape_str': shape_str, 'shape_sha': digest(shape_str.encode('utf-8'))})
        for child in node.children:
            if child.type in function_types or child.type in {'class_declaration', 'class_definition',
                                                              'impl_item', 'class_specifier',
                                                              'struct_item', 'object_definition'}:
                walk(child, scope + [node.type if node.type in function_types else ''])
            else:
                walk(child, scope)
    walk(root, [])
    return rows


def run(target, source, symbols=None, **options):
    from . import syntax as syntax_module
    if symbols is None:
        syntax_result = syntax_module.run(target, source)
        symbols = [f for f in syntax_result['facts'] if f['kind'] == 'symbol']
    fingerprints = []
    fingerprints_by_sha = defaultdict(list)
    fingerprints_for_facts = []
    files_observed = 0
    files_blocked = 0
    for item in source.readable():
        rel = item['path']
        language = language_of(rel)
        if language is None: continue
        text = source.text(rel)
        if text is None: continue
        rows = None
        if language == 'python':
            rows = _python_fingerprints(text, rel)
        else:
            rows = _tree_sitter_fingerprints(text, rel, language)
        if rows is None:
            files_blocked += 1; continue
        files_observed += 1
        for row in rows:
            if row['size'] < _MIN_SIZE: continue
            row['path'] = rel
            fingerprints.append(row)
            fingerprints_by_sha[row['shape_sha']].append(row)
    for row in fingerprints:
        facts_row = make('fingerprint', NAME, VERSION, row['shape_sha'],
                          {'path': row['path'], 'start_line': row['start'], 'end_line': row['end'],
                           'symbol': row['qualified']},
                          {'name': row['name'], 'size': row['size'],
                           'shape_sha': row['shape_sha']},
                          limitations=LIMITATIONS)
        fingerprints_for_facts.append(facts_row)
    clusters = []
    for sha, members in sorted(fingerprints_by_sha.items(), key=lambda item: -len(item[1])):
        if len(members) < _CLUSTER_MIN_MEMBERS: continue
        # Take only members in distinct paths or distinct qualified names; ignore same name in same file.
        members.sort(key=lambda m: (m['path'], m['start']))
        distinct = []
        seen = set()
        for member in members:
            key = (member['path'], member['start'])
            if key in seen: continue
            seen.add(key); distinct.append(member)
        if len(distinct) < _CLUSTER_MIN_MEMBERS: continue
        clusters.append({'shape_sha': sha, 'members': distinct,
                          'shared_shape_size': distinct[0]['size']})
    cluster_facts = []
    for cluster in clusters:
        cluster_facts.append(make('duplicate_cluster', NAME, VERSION, cluster['shape_sha'],
                                    {'path': cluster['members'][0]['path'],
                                     'start_line': cluster['members'][0]['start']},
                                    {'shape_sha': cluster['shape_sha'],
                                     'shared_size': cluster['shared_shape_size'],
                                     'occurrences': [{'path': m['path'], 'start_line': m['start'],
                                                       'end_line': m['end'], 'symbol': m['qualified'],
                                                       'name': m['name']}
                                                      for m in cluster['members']]},
                                    limitations=LIMITATIONS))
    summary = {'files_observed': files_observed, 'files_blocked': files_blocked,
               'fingerprints': len(fingerprints),
               'clusters': len(cluster_facts),
               'interpretation': 'A cluster contains symbols whose AST shape is identical up to identifier names. '
                                  'Membership is structural; the cluster itself is a hypothesis, not a defect.'}
    return {'facts': fingerprints_for_facts + cluster_facts, 'summary': summary,
            'available': True, 'input_sha': digest(''.join(sorted([m['shape_sha'] for m in fingerprints])).encode()) if fingerprints else digest(b''),
            'reason': None}

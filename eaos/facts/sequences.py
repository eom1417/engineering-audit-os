"""Repeated call-sequence fingerprints (the L4 detector).

Two functions that call (validate → save → notify) in the same order are doing
the same coordination work, even if the actual functions differ. The detector
sliding-windows each function's ordered list of callees, hashes the resulting
sequences, and clusters the duplicates across files.
"""
import ast
from collections import defaultdict
from . import digest, make
from .source import language_of

NAME = 'sequences'
VERSION = '1'
LIMITATIONS = [
    'A sequence is a source-order listing of callees; a runtime branch that takes a different path is invisible.',
    'A short sequence (<= 2 calls) is too common to be a signal; it is filtered out.',
    'A cluster requires at least three occurrences by default; near-duplicate pairs are common noise.',
    'Only languages with a parsed tree produce sequences; unparsed files stay out of the denominator.',
]

_MIN_SEQUENCE = 3
_CLUSTER_MIN = 3
_MIN_FUNCTION_SIZE = 3


def _python_call_name(node):
    if isinstance(node, ast.Name): return node.id
    if isinstance(node, ast.Attribute): return node.attr
    return None


def _python_callees(func_node):
    """Source-order list of callee names inside one Python function."""
    calls = []
    for sub in ast.walk(func_node):
        if isinstance(sub, ast.Call):
            name = _python_call_name(sub.func)
            if name: calls.append(name)
    return calls


def _python_sequences(text):
    """Yield (qualified, start, end, [callees]) for every Python function in the file."""
    try: tree = ast.parse(text)
    except SyntaxError: return
    def visit(node, scope):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qualified = '.'.join(scope + [node.name])
            yield qualified, node.lineno, node.end_lineno or node.lineno, _python_callees(node)
            new_scope = scope + [node.name]
            for child in ast.iter_child_nodes(node):
                for item in visit(child, new_scope): yield item
            return
        if isinstance(node, ast.ClassDef):
            new_scope = scope + [node.name]
            for child in ast.iter_child_nodes(node):
                for item in visit(child, new_scope): yield item
            return
        for child in ast.iter_child_nodes(node):
            for item in visit(child, scope): yield item
    for node in tree.body:
        for item in visit(node, []): yield item


def _ts_callee(node):
    if node.type in {'method_invocation', 'invocation_expression', 'member_call_expression', 'selector'}:
        for child in node.children:
            if child.type in {'identifier', 'field_identifier', 'property_identifier', 'name'}:
                text = child.text.decode('utf-8', errors='replace') if child.text else ''
                return text
        return ''
    for child in node.children:
        if child.type not in {'arguments', 'argument_list', 'type_arguments'}:
            text = child.text.decode('utf-8', errors='replace') if child.text else ''
            return text.split('.')[-1]
    return ''


def _tree_sitter_sequences(text, language):
    try:
        from tree_sitter_language_pack import get_parser
    except ImportError: return None
    try: parser = get_parser('c_sharp' if language == 'csharp' else language)
    except Exception: return None
    try: tree = parser.parse(text.encode('utf-8'))
    except Exception: return None
    function_types = {'function_declaration', 'function_definition', 'function_item',
                       'method_declaration', 'method_definition', 'function', 'function_expression',
                       'arrow_function', 'singleton_method', 'local_function_statement'}
    call_types = {'call_expression', 'method_invocation', 'invocation_expression',
                   'function_call_expression', 'member_call_expression', 'selector'}
    rows = []

    def function_calls(node):
        calls = []
        for child in node.children:
            if child.type in call_types: calls.append(_ts_callee(child))
            calls.extend(function_calls(child))
        return calls

    def walk(node, scope):
        if node.type in function_types:
            calls = [c for c in function_calls(node) if c]
            qualified = '.'.join(scope + [node.type])
            rows.append((qualified, node.start_point[0] + 1, node.end_point[0] + 1, calls))
            for child in node.children: walk(child, scope + [node.type])
            return
        if node.type in {'class_declaration', 'class_definition', 'impl_item'}:
            for child in node.children: walk(child, scope + [node.type])
            return
        for child in node.children: walk(child, scope)
    walk(tree.root_node, [])
    return rows


def run(target, source, symbols=None, **options):
    from . import syntax as syntax_module
    if symbols is None:
        syntax_result = syntax_module.run(target, source)
        symbols = [f for f in syntax_result['facts'] if f['kind'] == 'symbol']
    sequence_clusters = defaultdict(list)
    files_observed = 0; files_blocked = 0
    for item in source.readable():
        rel = item['path']; language = language_of(rel)
        if language is None: continue
        text = source.text(rel)
        if text is None: continue
        rows = None
        if language == 'python': rows = list(_python_sequences(text))
        else: rows = _tree_sitter_sequences(text, language)
        if rows is None: files_blocked += 1; continue
        files_observed += 1
        for qualified, start, end, callees in rows:
            if len(callees) < _MIN_FUNCTION_SIZE: continue
            for i in range(0, len(callees) - _MIN_SEQUENCE + 1):
                window = tuple(callees[i:i + _MIN_SEQUENCE])
                sequence_clusters[window].append({'path': rel, 'start': start, 'end': end,
                                                   'qualified': qualified})
    cluster_facts = []
    for window, occurrences in sorted(sequence_clusters.items(), key=lambda item: -len(item[1])):
        if len(occurrences) < _CLUSTER_MIN: continue
        unique = []
        seen = set()
        for occ in occurrences:
            key = (occ['path'], occ['start'])
            if key in seen: continue
            seen.add(key); unique.append(occ)
        if len(unique) < _CLUSTER_MIN: continue
        seq_sha = digest(repr(window).encode())
        cluster_facts.append(make('sequence_cluster', NAME, VERSION, seq_sha,
                                    {'path': unique[0]['path'], 'start_line': unique[0]['start']},
                                    {'sequence': list(window), 'length': len(window),
                                     'occurrences': unique},
                                    limitations=LIMITATIONS))
    summary = {'files_observed': files_observed, 'files_blocked': files_blocked,
               'clusters': len(cluster_facts),
               'interpretation': 'A cluster contains functions that perform the same ordered list of callees. '
                                  'The cluster is a hypothesis; one shared list may be coincidence or coordination copy.'}
    return {'facts': cluster_facts, 'summary': summary,
            'available': True, 'input_sha': digest(b''),
            'reason': None}

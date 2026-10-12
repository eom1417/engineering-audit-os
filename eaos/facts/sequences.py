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

# Idiomatic call patterns per language. A sequence whose every element belongs to the
# idiomatic set is not a coordination copy; it is the language's normal way of writing
# a particular kind of work. The detector records the exclusion in the summary rather
# than silently dropping the cluster.
IDIOMS = {
    'python': {frozenset({'assertEqual', 'assertTrue', 'assertFalse', 'assertNotEqual',
                          'assertRaises', 'assertIsNone', 'assertIsNotNone',
                          'patch', 'mock', 'MagicMock'})},
    'go': {frozenset({'t.Run', 't.Fatalf', 't.Errorf', 't.Logf', 't.Skip',
                      'require', 'assert', 'NoError', 'Equal', 'NotEqual',
                      'len', 'cap', 'err', 'nil'})},
    'javascript': {frozenset({'expect', 'describe', 'it', 'beforeEach', 'afterEach',
                              'jest', 'fn'})},
    'typescript': {frozenset({'expect', 'describe', 'it', 'beforeEach', 'afterEach',
                              'jest', 'fn'})},
}


def _is_idiomatic(sequence, language):
    """A sequence is idiomatic when all of its calls are in the language's idiom set."""
    idioms = IDIOMS.get(language) or set()
    seq_set = frozenset(sequence)
    return any(seq_set <= idiom for idiom in idioms)


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


_PY_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)


def _visit_python(node, scope, rows):
    if isinstance(node, _PY_FUNCTIONS):
        rows.append(('.'.join(scope + [node.name]), node.lineno, node.end_lineno or node.lineno, _python_callees(node)))
    inner = scope + [node.name] if isinstance(node, _PY_FUNCTIONS + (ast.ClassDef,)) else scope
    for child in ast.iter_child_nodes(node): _visit_python(child, inner, rows)


def _python_sequences(text):
    """(qualified, start, end, [callees]) for every Python function in the file; none when it does not parse."""
    try: tree = ast.parse(text)
    except SyntaxError: return []
    rows = []
    for node in tree.body: _visit_python(node, [], rows)
    return rows


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


_TS_FUNCTIONS = {'function_declaration', 'function_definition', 'function_item',
                 'method_declaration', 'method_definition', 'function', 'function_expression',
                 'arrow_function', 'singleton_method', 'local_function_statement'}
_TS_CALLS = {'call_expression', 'method_invocation', 'invocation_expression',
             'function_call_expression', 'member_call_expression', 'selector'}
_TS_CLASSES = {'class_declaration', 'class_definition', 'impl_item'}


def _tree_sitter_tree(text, language):
    try:
        from tree_sitter_language_pack import get_parser
    except ImportError: return None
    try: parser = get_parser('c_sharp' if language == 'csharp' else language)
    except Exception: return None
    try: return parser.parse(text.encode('utf-8'))
    except Exception: return None


def _function_calls(node):
    calls = []
    for child in node.children:
        if child.type in _TS_CALLS: calls.append(_ts_callee(child))
        calls.extend(_function_calls(child))
    return calls


def _walk_tree(node, scope, rows):
    if node.type in _TS_FUNCTIONS:
        calls = [c for c in _function_calls(node) if c]
        rows.append(('.'.join(scope + [node.type]), node.start_point[0] + 1, node.end_point[0] + 1, calls))
    inner = scope + [node.type] if node.type in _TS_FUNCTIONS or node.type in _TS_CLASSES else scope
    for child in node.children: _walk_tree(child, inner, rows)


def _tree_sitter_sequences(text, language):
    tree = _tree_sitter_tree(text, language)
    if tree is None: return None
    rows = []
    _walk_tree(tree.root_node, [], rows)
    return rows


def _sequences_of(text, language):
    if language == 'python': return _python_sequences(text)
    return _tree_sitter_sequences(text, language)


def _add_windows(row, rel, language, found):
    """Every window of one function's callees into the clusters, or counted as idiomatic."""
    qualified, start, end, callees = row
    if len(callees) < _MIN_FUNCTION_SIZE: return
    for i in range(0, len(callees) - _MIN_SEQUENCE + 1):
        window = tuple(callees[i:i + _MIN_SEQUENCE])
        if _is_idiomatic(window, language):
            found['idiomatic'] += 1
            found['idiom_languages'][language] = found['idiom_languages'].get(language, 0) + 1
            continue
        found['clusters'][window].append({'path': rel, 'start': start, 'end': end, 'qualified': qualified})


def _collect(source):
    found = {'clusters': defaultdict(list), 'observed': 0, 'blocked': 0, 'idiomatic': 0, 'idiom_languages': {}}
    for item in source.readable():
        rel = item['path']; language = language_of(rel)
        if language is None: continue
        text = source.text(rel)
        if text is None: continue
        rows = _sequences_of(text, language)
        if rows is None:
            found['blocked'] += 1
            continue
        found['observed'] += 1
        for row in rows: _add_windows(row, rel, language, found)
    return found


def _unique(occurrences):
    unique, seen = [], set()
    for occ in occurrences:
        key = (occ['path'], occ['start'])
        if key in seen: continue
        seen.add(key)
        unique.append(occ)
    return unique


def _cluster_fact(window, unique):
    return make('sequence_cluster', NAME, VERSION, digest(repr(window).encode()),
                {'path': unique[0]['path'], 'start_line': unique[0]['start']},
                {'sequence': list(window), 'length': len(window), 'occurrences': unique},
                limitations=LIMITATIONS)


def run(target, source, symbols=None, **options):
    found = _collect(source)
    cluster_facts = []
    for window, occurrences in sorted(found['clusters'].items(), key=lambda item: -len(item[1])):
        unique = _unique(occurrences) if len(occurrences) >= _CLUSTER_MIN else []
        if len(unique) >= _CLUSTER_MIN: cluster_facts.append(_cluster_fact(window, unique))
    summary = {'files_observed': found['observed'], 'files_blocked': found['blocked'],
               'clusters': len(cluster_facts),
               'idiomatic_clusters_excluded': found['idiomatic'],
               'idiomatic_clusters_by_language': found['idiom_languages'],
               'interpretation': 'A cluster contains functions that perform the same ordered list of callees. '
                                 'Idiomatic sequences (test patterns, common library calls) are excluded and reported.'}
    return {'facts': cluster_facts, 'summary': summary,
            'available': True, 'input_sha': digest(b''),
            'reason': None}

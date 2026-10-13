"""Loops, branches, scopes and call sites, extracted by walking one parse tree.

These facts are the substrate of every redundancy detector that follows:
a duplicate call must sit inside a function, a hoistable call must sit inside
a loop, a pass-through layer must have a body that is one call, and a call
sequence must come from an ordered list of call sites. Without these facts,
L3/L4/L5 detection cannot exist at all.
"""
import ast
from . import digest, make, tree_sitter_tree
from .source import language_of

NAME = 'structure'
VERSION = '1'
LIMITATIONS = [
    'Only languages with a parser produce structure facts; the rest stay in the denominator.',
    'A control-flow fact is a syntactic observation, not a runtime trace: a branch that is statically unreachable still appears here.',
    'A call_site binds the call to its enclosing symbol; dynamic dispatch and reflection are invisible.',
    'Scopes reflect lexical containment, not lifetime; a closure is reported under its defining scope.',
]


_LOOP_KINDS = {
    'For': 'for', 'AsyncFor': 'for',
    'While': 'while',
    'DoWhileStatement': 'do_while', 'do_statement': 'do_while',
    'for_statement': 'for', 'for_in_statement': 'for',
    'while_statement': 'while', 'do_statement': 'do_while',
}
_BRANCH_KINDS = {
    'If': 'if', 'IfExp': 'if_expr',
    'For': 'for', 'AsyncFor': 'for', 'While': 'while',
    'Try': 'try', 'TryStar': 'try',
    'With': 'with', 'AsyncWith': 'with',
    'Match': 'match',
    'if_statement': 'if', 'conditional_expression': 'if_expr',
    'switch_statement': 'switch', 'switch_expression': 'switch',
    'try_statement': 'try', 'with_statement': 'with',
    'match_expression': 'match', 'match_statement': 'match',
    'case_statement': 'for_clause',
}

# Python nodes: the scopes they open, the loops and the branches they are.
_PY_SCOPES = {ast.FunctionDef: 'function', ast.AsyncFunctionDef: 'function', ast.ClassDef: 'class', ast.Lambda: 'lambda'}
_PY_LOOPS = {ast.For: 'for', ast.AsyncFor: 'for', ast.While: 'while'}
_PY_BRANCHES = {ast.If: 'if', ast.With: 'with', ast.AsyncWith: 'with', ast.Try: 'try', ast.IfExp: 'if_expr'}


def _qualified(stack, name='<module>'):
    return '.'.join([p[1] for p in stack] + ([name] if name and name != '<module>' else []))


def _enclosing(stack, outside=None):
    return stack[-1][1] if stack else outside


def _py_scope(node, kind, walk):
    name = '<lambda>' if kind == 'lambda' else node.name
    qname = _qualified(walk['parents'], name)
    walk['scopes'].append({'qualified': qname, 'name': name, 'kind': kind,
                           'start': node.lineno, 'end': node.end_lineno or node.lineno,
                           'parent': _enclosing(walk['parents'])})
    walk['parents'].append((node, qname))
    for child in ast.iter_child_nodes(node): _py_visit(child, walk)
    walk['parents'].pop()


def _py_call(node, walk):
    callee, attribute = _python_callee(node.func)
    walk['calls'].append({'callee': callee, 'attribute': attribute, 'start': node.lineno,
                          'end': node.end_lineno or node.lineno})
    walk['call_sites'].append({'callee': callee, 'attribute': attribute, 'start': node.lineno,
                               'end': node.end_lineno or node.lineno,
                               'enclosing': _enclosing(walk['parents'], '<module>')})


def _py_control(node, kind, into, walk):
    walk[into].append({'kind': kind, 'start': node.lineno, 'end': node.end_lineno or node.lineno,
                       'parent': _enclosing(walk['parents'])})


def _py_visit(node, walk):
    kind = type(node)
    if kind in _PY_SCOPES:
        _py_scope(node, _PY_SCOPES[kind], walk)
        return
    if kind in _PY_LOOPS: _py_control(node, _PY_LOOPS[kind], 'loops', walk)
    elif kind in _PY_BRANCHES: _py_control(node, _PY_BRANCHES[kind], 'branches', walk)
    elif kind is ast.Call: _py_call(node, walk)
    for child in ast.iter_child_nodes(node): _py_visit(child, walk)


def _python_parse(text, rel):
    """Return (tree, scopes, calls, loops, branches, call_sites) for a Python file or None on failure."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    walk = {'scopes': [], 'calls': [], 'loops': [], 'branches': [], 'call_sites': [], 'parents': [(tree, '<module>')]}
    for node in tree.body: _py_visit(node, walk)
    return walk['scopes'], walk['calls'], walk['loops'], walk['branches'], walk['call_sites']


def _python_callee(node):
    """Resolve a Python callee expression to (name, is_attribute) without crashing on exotic forms."""
    if isinstance(node, ast.Name): return node.id, False
    if isinstance(node, ast.Attribute): return node.attr, True
    return '<expr>', False


_TS_FUNCTIONS = {'function_declaration', 'function_definition', 'function_item', 'method_declaration',
                 'method_definition', 'function', 'function_expression', 'arrow_function',
                 'method_invocation', 'generator_function_declaration', 'singleton_method',
                 'function_signature', 'method_signature', 'local_function_statement'}
_TS_CLASSES = {'class_declaration', 'class_definition', 'class_specifier', 'struct_item',
               'struct_specifier', 'interface_declaration', 'protocol_declaration',
               'trait_declaration', 'record_declaration', 'type_declaration',
               'object_definition', 'object_declaration', 'impl_item', 'enum_item'}
_TS_CALLS = {'call_expression', 'method_invocation', 'invocation_expression',
             'function_call_expression', 'member_call_expression', 'selector'}
_TS_LOOPS = {'for_statement', 'for_in_statement', 'while_statement', 'do_statement',
             'for_expression'}
_TS_BRANCHES = {'if_statement', 'switch_statement', 'try_statement', 'with_statement',
                'match_expression', 'match_statement', 'conditional_expression',
                'switch_expression', 'elif_clause', 'else_clause'}


def _ts_scope(node, kind, walk, span):
    name = _ts_name(node, kind) or '<anon>'
    qname = _qualified(walk['stack'], name)
    walk['scopes'].append({'qualified': qname, 'name': name,
                           'kind': 'function' if kind in _TS_FUNCTIONS else 'class',
                           'start': span[0], 'end': span[1],
                           'parent': _enclosing(walk['stack'])})
    walk['stack'].append((node, qname))
    for child in node.children: _ts_walk(child, walk)
    walk['stack'].pop()


def _ts_call(node, kind, walk, span):
    callee, attribute = _ts_callee(node, kind)
    walk['calls'].append({'callee': callee, 'attribute': attribute, 'start': span[0], 'end': span[1]})
    walk['call_sites'].append({'callee': callee, 'attribute': attribute, 'start': span[0], 'end': span[1],
                               'enclosing': _enclosing(walk['stack'], '<module>')})


def _ts_walk(node, walk):
    kind = node.type
    span = (node.start_point[0] + 1, node.end_point[0] + 1)
    if kind in _TS_FUNCTIONS or kind in _TS_CLASSES:
        _ts_scope(node, kind, walk, span)
        return
    if kind in _TS_LOOPS:
        walk['loops'].append({'kind': _LOOP_KINDS.get(kind, kind), 'start': span[0], 'end': span[1],
                              'parent': _enclosing(walk['stack'])})
    elif kind in _TS_BRANCHES:
        walk['branches'].append({'kind': _BRANCH_KINDS.get(kind, kind), 'start': span[0], 'end': span[1],
                                 'parent': _enclosing(walk['stack'])})
    elif kind in _TS_CALLS:
        _ts_call(node, kind, walk, span)
    else:
        for child in node.children: _ts_walk(child, walk)
        return
    # A loop, a branch or a call is descended into through its first child only, as the extractor always has;
    # the golden facts (tests/fixtures/golden/structure.json) record that.
    if node.children: _ts_walk(node.children[0], walk)


def _tree_sitter_parse(text, rel, language):
    """Return (scopes, calls, loops, branches, call_sites) for a tree-sitter language, or None on failure."""
    tree = tree_sitter_tree(text, language)
    if tree is None: return None
    root = tree.root_node
    walk = {'scopes': [], 'calls': [], 'loops': [], 'branches': [], 'call_sites': [], 'stack': [(root, '<module>')]}
    for child in root.children: _ts_walk(child, walk)
    return walk['scopes'], walk['calls'], walk['loops'], walk['branches'], walk['call_sites']


def _ts_name(node, kind):
    """Pick the most useful identifier from a tree-sitter symbol node."""
    for child in node.children:
        if child.type in {'identifier', 'type_identifier', 'field_identifier', 'property_identifier',
                          'constant', 'scoped_identifier', 'name', 'simple_identifier'}:
            return child.text.decode('utf-8', errors='replace') if child.text else None
    if kind == 'arrow_function': return '<arrow>'
    if kind == 'function_expression': return '<func_expr>'
    if kind == 'lambda': return '<lambda>'
    return None


def _text(node): return node.text.decode('utf-8', errors='replace') if node.text else ''


# kind -> (the child types that name the callee, whether it is an attribute, the name when none does)
_TS_CALLEES = {
    'method_invocation': ({'identifier', 'field_identifier', 'property_identifier'}, True, '<method>'),
    'invocation_expression': ({'identifier', 'field_identifier', 'property_identifier'}, True, '<method>'),
    'member_call_expression': ({'identifier', 'property_identifier', 'name'}, True, '<member>'),
    'function_call_expression': ({'name', 'identifier'}, False, '<call>'),
    'selector': ({'identifier'}, True, '<selector>'),
}
_CALL_TARGETS = {'identifier', 'member_expression', 'field_expression', 'scoped_identifier', 'attribute', 'property_identifier'}


def _call_expression_callee(node):
    # call_expression: function arguments
    target = next((child for child in node.children if child.type in _CALL_TARGETS), None)
    if target is None: return '<expr>', False
    return _text(target).split('.')[-1], target.type in {'member_expression', 'field_expression'}


def _ts_callee(node, kind):
    """Resolve a tree-sitter call node to (callee, is_attribute)."""
    if kind == 'call_expression': return _call_expression_callee(node)
    rule = _TS_CALLEES.get(kind)
    if rule is None: return '<call>', False
    types, attribute, fallback = rule
    named = next((child for child in node.children if child.type in types), None)
    return (_text(named), attribute) if named is not None else (fallback, attribute)


def _parse_file(rel, text, language):
    if language == 'python': return _python_parse(text, rel), 'python_ast'
    return _tree_sitter_parse(text, rel, language), 'tree_sitter:' + language


def _file_info(parse, language, sha):
    if parse is None: return {'status': 'BLOCKED', 'language': language, 'sha': sha}
    scopes, calls, loops, branches, call_sites = parse
    return {'status': 'OBSERVED', 'language': language, 'sha': sha, 'scopes': scopes,
            'calls': calls, 'loops': loops, 'branches': branches, 'call_sites': call_sites}


def _file_facts(rel, info, parser_name):
    sha = info['sha']
    facts = [make('structure_file', NAME, VERSION, sha, {'path': rel},
                  {'language': info['language'], 'parse_status': info['status'],
                   'parser': parser_name if info['status'] == 'OBSERVED' else None,
                   'scopes': len(info.get('scopes', [])),
                   'loops': len(info.get('loops', [])),
                   'branches': len(info.get('branches', [])),
                   'call_sites': len(info.get('call_sites', []))},
                  limitations=LIMITATIONS)]
    if info['status'] != 'OBSERVED': return facts
    facts += [make('scope', NAME, VERSION, sha,
                   {'path': rel, 'start_line': scope['start'], 'end_line': scope['end'], 'symbol': scope['qualified']},
                   {'name': scope['name'], 'kind': scope['kind'], 'parent': scope['parent']},
                   limitations=LIMITATIONS) for scope in info['scopes']]
    facts += [make('loop', NAME, VERSION, sha,
                   {'path': rel, 'start_line': loop['start'], 'end_line': loop['end'], 'parent_symbol': loop['parent']},
                   {'kind': loop['kind']}, limitations=LIMITATIONS) for loop in info['loops']]
    facts += [make('branch', NAME, VERSION, sha,
                   {'path': rel, 'start_line': branch['start'], 'end_line': branch['end'], 'parent_symbol': branch['parent']},
                   {'kind': branch['kind']}, limitations=LIMITATIONS) for branch in info['branches']]
    facts += [make('call_site', NAME, VERSION, sha,
                   {'path': rel, 'start_line': site['start'], 'end_line': site['end'], 'symbol': site['enclosing']},
                   {'callee': site['callee'], 'attribute': site['attribute']},
                   limitations=LIMITATIONS) for site in info['call_sites']]
    return facts


def _summary(facts, by_path):
    observed = sum(1 for info in by_path.values() if info['status'] == 'OBSERVED')
    blocked = sum(1 for info in by_path.values() if info['status'] == 'BLOCKED')
    considered = observed + blocked
    return {'files_considered': considered, 'files_observed': observed, 'files_blocked': blocked,
            'parse_coverage': round(observed / considered, 3) if considered else 0.0,
            'scopes': sum(f['kind'] == 'scope' for f in facts),
            'loops': sum(f['kind'] == 'loop' for f in facts),
            'branches': sum(f['kind'] == 'branch' for f in facts),
            'call_sites': sum(f['kind'] == 'call_site' for f in facts),
            'interpretation': 'Structure facts are lexical. They enable redundancy detection that needs to '
                              'know where control flow and iterate live; they prove nothing about runtime behaviour.'}


def run(target, source, symbols=None, **options):
    """Extract structure facts from every file the syntax extractor could parse."""
    fingerprints, by_path, parser_name = [], {}, None
    for item in source.readable():
        rel = item['path']
        language = language_of(rel)
        if language is None: continue
        text = source.text(rel)
        if text is None: continue
        fingerprints.append(item['sha256'])
        parse, parser_name = _parse_file(rel, text, language)
        by_path[rel] = _file_info(parse, language, item['sha256'])
    # Every structure_file names the parser of the last file read, as the golden facts record.
    facts = [fact for rel, info in by_path.items() for fact in _file_facts(rel, info, parser_name)]
    facts.sort(key=lambda f: (f['location']['path'], f['location'].get('start_line') or 0,
                              f['kind'], f['id']))
    return {'facts': facts, 'summary': _summary(facts, by_path), 'available': True,
            'input_sha': digest(''.join(sorted(fingerprints)).encode('utf-8')) if fingerprints else digest(b''),
            'reason': None}

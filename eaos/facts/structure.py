"""Loops, branches, scopes and call sites, extracted by walking one parse tree.

These facts are the substrate of every redundancy detector that follows:
a duplicate call must sit inside a function, a hoistable call must sit inside
a loop, a pass-through layer must have a body that is one call, and a call
sequence must come from an ordered list of call sites. Without these facts,
L3/L4/L5 detection cannot exist at all.
"""
import ast
from collections import defaultdict
from . import digest, make
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


def _scope_chain(call_chain, call_index):
    """The enclosing-symbol stack for a call at the given index."""
    chain = []
    for entry in call_chain:
        if entry['start'] <= call_index <= entry['end']:
            chain.append(entry['qualified'])
    return chain


def _python_parse(text, rel):
    """Return (tree, scopes, calls, loops, branches, call_sites) for a Python file or None on failure."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None

    scopes = []  # list of dicts: qualified_name, start, end, parent
    calls = []  # list of dicts: callee, attribute, start, end
    loops = []  # list of dicts: kind, start, end, parent
    branches = []  # list of dicts: kind, start, end, parent
    call_sites = []  # list of dicts: callee, attribute, start, enclosing
    parents = []  # stack of (node, qualified_name)

    def qualified(name='<module>'):
        return '.'.join([p[1] for p in parents] + ([name] if name and name != '<module>' else []))

    def visit(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qname = qualified(node.name)
            scopes.append({'qualified': qname, 'name': node.name, 'kind': 'function',
                           'start': node.lineno, 'end': node.end_lineno or node.lineno,
                           'parent': parents[-1][1] if parents else None})
            parents.append((node, qname))
            for child in ast.iter_child_nodes(node): visit(child)
            parents.pop()
            return
        if isinstance(node, ast.ClassDef):
            qname = qualified(node.name)
            scopes.append({'qualified': qname, 'name': node.name, 'kind': 'class',
                           'start': node.lineno, 'end': node.end_lineno or node.lineno,
                           'parent': parents[-1][1] if parents else None})
            parents.append((node, qname))
            for child in ast.iter_child_nodes(node): visit(child)
            parents.pop()
            return
        if isinstance(node, ast.Lambda):
            qname = qualified('<lambda>')
            scopes.append({'qualified': qname, 'name': '<lambda>', 'kind': 'lambda',
                           'start': node.lineno, 'end': node.end_lineno or node.lineno,
                           'parent': parents[-1][1] if parents else None})
            parents.append((node, qname))
            for child in ast.iter_child_nodes(node): visit(child)
            parents.pop()
            return
        if isinstance(node, (ast.For, ast.AsyncFor)):
            loops.append({'kind': 'for', 'start': node.lineno, 'end': node.end_lineno or node.lineno,
                          'parent': parents[-1][1] if parents else None})
            for child in ast.iter_child_nodes(node):
                visit(child)
            return
        if isinstance(node, ast.While):
            loops.append({'kind': 'while', 'start': node.lineno, 'end': node.end_lineno or node.lineno,
                          'parent': parents[-1][1] if parents else None})
            for child in ast.iter_child_nodes(node):
                visit(child)
            return
        if isinstance(node, ast.If):
            branches.append({'kind': 'if', 'start': node.lineno, 'end': node.end_lineno or node.lineno,
                             'parent': parents[-1][1] if parents else None})
            for child in ast.iter_child_nodes(node):
                visit(child)
            return
        if isinstance(node, (ast.With, ast.AsyncWith)):
            branches.append({'kind': 'with', 'start': node.lineno, 'end': node.end_lineno or node.lineno,
                             'parent': parents[-1][1] if parents else None})
            for child in ast.iter_child_nodes(node):
                visit(child)
            return
        if isinstance(node, ast.Try):
            branches.append({'kind': 'try', 'start': node.lineno, 'end': node.end_lineno or node.lineno,
                             'parent': parents[-1][1] if parents else None})
            for child in ast.iter_child_nodes(node):
                visit(child)
            return
        if isinstance(node, ast.IfExp):
            branches.append({'kind': 'if_expr', 'start': node.lineno, 'end': node.end_lineno or node.lineno,
                             'parent': parents[-1][1] if parents else None})
            for child in ast.iter_child_nodes(node):
                visit(child)
            return
        if isinstance(node, ast.Call):
            callee, attribute = _python_callee(node.func)
            calls.append({'callee': callee, 'attribute': attribute, 'start': node.lineno,
                          'end': node.end_lineno or node.lineno})
            call_sites.append({'callee': callee, 'attribute': attribute, 'start': node.lineno,
                               'end': node.end_lineno or node.lineno,
                               'enclosing': parents[-1][1] if parents else '<module>'})
            for child in ast.iter_child_nodes(node): visit(child)
            return
        for child in ast.iter_child_nodes(node): visit(child)

    parents.append((tree, '<module>'))
    for node in tree.body: visit(node)
    parents.pop()
    return scopes, calls, loops, branches, call_sites


def _python_callee(node):
    """Resolve a Python callee expression to (name, is_attribute) without crashing on exotic forms."""
    if isinstance(node, ast.Name): return node.id, False
    if isinstance(node, ast.Attribute): return node.attr, True
    return '<expr>', False


def _walk_tree_sitter(node, language):
    """Yield descendants of a tree-sitter node in source order."""
    cursor = node.walk()
    if not cursor.goto_first_child(): return
    while True:
        yield cursor.node
        yield from _walk_tree_sitter(cursor.node, language)
        if not cursor.goto_next_sibling(): return


def _tree_sitter_parse(text, rel, language):
    """Return (scopes, calls, loops, branches, call_sites) for a tree-sitter language, or None on failure."""
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

    function_types = {'function_declaration', 'function_definition', 'function_item', 'method_declaration',
                      'method_definition', 'function', 'function_expression', 'arrow_function',
                      'method_invocation', 'generator_function_declaration', 'singleton_method',
                      'function_signature', 'method_signature', 'local_function_statement'}
    class_types = {'class_declaration', 'class_definition', 'class_specifier', 'struct_item',
                   'struct_specifier', 'interface_declaration', 'protocol_declaration',
                   'trait_declaration', 'record_declaration', 'type_declaration',
                   'object_definition', 'object_declaration', 'impl_item', 'enum_item'}
    call_types = {'call_expression', 'method_invocation', 'invocation_expression',
                  'function_call_expression', 'member_call_expression', 'selector'}
    loop_types = {'for_statement', 'for_in_statement', 'while_statement', 'do_statement',
                  'for_expression'}
    branch_types = {'if_statement', 'switch_statement', 'try_statement', 'with_statement',
                    'match_expression', 'match_statement', 'conditional_expression',
                    'switch_expression', 'elif_clause', 'else_clause'}

    scopes = []
    calls = []
    loops = []
    branches = []
    call_sites = []

    stack = []  # (node, qualified_name)

    def qualified(name='<module>'):
        return '.'.join([p[1] for p in stack] + ([name] if name and name != '<module>' else []))

    def walk(node):
        kind = node.type
        start = node.start_point[0] + 1
        end = node.end_point[0] + 1
        if kind in function_types or kind in class_types:
            name = _ts_name(node, kind) or '<anon>'
            qname = qualified(name)
            scopes.append({'qualified': qname, 'name': name,
                           'kind': 'function' if kind in function_types else 'class',
                           'start': start, 'end': end,
                           'parent': stack[-1][1] if stack else None})
            stack.append((node, qname))
            for child in node.children: walk(child)
            stack.pop()
            return
        if kind in loop_types:
            loops.append({'kind': _LOOP_KINDS.get(kind, kind), 'start': start, 'end': end,
                          'parent': stack[-1][1] if stack else None})
            for child in node.children: walk(child); return
        if kind in branch_types:
            branches.append({'kind': _BRANCH_KINDS.get(kind, kind), 'start': start, 'end': end,
                             'parent': stack[-1][1] if stack else None})
            for child in node.children: walk(child); return
        if kind in call_types:
            callee, attribute = _ts_callee(node, kind)
            calls.append({'callee': callee, 'attribute': attribute, 'start': start, 'end': end})
            call_sites.append({'callee': callee, 'attribute': attribute, 'start': start, 'end': end,
                               'enclosing': stack[-1][1] if stack else '<module>'})
            for child in node.children: walk(child); return
        for child in node.children: walk(child)

    stack.append((root, '<module>'))
    for child in root.children: walk(child)
    stack.pop()
    return scopes, calls, loops, branches, call_sites


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


def _ts_callee(node, kind):
    """Resolve a tree-sitter call node to (callee, is_attribute)."""
    if kind == 'call_expression':
        # call_expression: function arguments
        for child in node.children:
            if child.type not in {'arguments', 'argument_list', 'type_arguments'}:
                if child.type in {'identifier', 'member_expression', 'field_expression',
                                  'scoped_identifier', 'attribute', 'property_identifier'}:
                    text = child.text.decode('utf-8', errors='replace') if child.text else ''
                    if child.type in {'member_expression', 'field_expression'}: return text.split('.')[-1], True
                    return text.split('.')[-1], False
        return '<expr>', False
    if kind == 'method_invocation' or kind == 'invocation_expression':
        for child in node.children:
            if child.type in {'identifier', 'field_identifier', 'property_identifier'}:
                text = child.text.decode('utf-8', errors='replace') if child.text else ''
                return text, True
        return '<method>', True
    if kind == 'member_call_expression':
        for child in node.children:
            if child.type in {'identifier', 'property_identifier', 'name'}:
                text = child.text.decode('utf-8', errors='replace') if child.text else ''
                return text, True
        return '<member>', True
    if kind == 'function_call_expression':
        for child in node.children:
            if child.type == 'name' or child.type == 'identifier':
                text = child.text.decode('utf-8', errors='replace') if child.text else ''
                return text, False
        return '<call>', False
    if kind == 'selector':
        for child in node.children:
            if child.type == 'identifier':
                text = child.text.decode('utf-8', errors='replace') if child.text else ''
                return text, True
        return '<selector>', True
    return '<call>', False


def run(target, source, symbols=None, **options):
    """Extract structure facts from every file the syntax extractor could parse."""
    from . import syntax as syntax_module
    if symbols is None:
        syntax_result = syntax_module.run(target, source)
        symbols = [f for f in syntax_result['facts'] if f['kind'] == 'symbol']
    symbol_index = defaultdict(dict)
    for fact in symbols:
        path = fact['location']['path']
        symbol_index[path][fact['location'].get('start_line', 0)] = fact['location']

    facts, fingerprints = [], []
    by_path = {}
    for item in source.readable():
        rel = item['path']
        language = language_of(rel)
        if language is None: continue
        text = source.text(rel)
        if text is None: continue
        fingerprints.append(item['sha256'])
        parse = None
        if language == 'python':
            parse = _python_parse(text, rel)
            parser_name = 'python_ast'
        else:
            parse = _tree_sitter_parse(text, rel, language)
            parser_name = 'tree_sitter:' + language
        if parse is None:
            by_path[rel] = {'status': 'BLOCKED', 'language': language}
            continue
        scopes, calls, loops, branches, call_sites = parse
        by_path[rel] = {'status': 'OBSERVED', 'language': language, 'scopes': scopes,
                        'calls': calls, 'loops': loops, 'branches': branches, 'call_sites': call_sites}
    for rel, info in by_path.items():
        item = next((it for it in source.readable() if it['path'] == rel), None)
        if item is None: continue
        sha = item['sha256']
        facts.append(make('structure_file', NAME, VERSION, sha, {'path': rel},
                          {'language': info['language'], 'parse_status': info['status'],
                           'parser': parser_name if info['status'] == 'OBSERVED' else None,
                           'scopes': len(info.get('scopes', [])),
                           'loops': len(info.get('loops', [])),
                           'branches': len(info.get('branches', [])),
                           'call_sites': len(info.get('call_sites', []))},
                          limitations=LIMITATIONS))
        if info['status'] != 'OBSERVED': continue
        for scope in info['scopes']:
            facts.append(make('scope', NAME, VERSION, sha,
                              {'path': rel, 'start_line': scope['start'], 'end_line': scope['end'],
                               'symbol': scope['qualified']},
                              {'name': scope['name'], 'kind': scope['kind'], 'parent': scope['parent']},
                              limitations=LIMITATIONS))
        for loop in info['loops']:
            facts.append(make('loop', NAME, VERSION, sha,
                              {'path': rel, 'start_line': loop['start'], 'end_line': loop['end'],
                               'parent_symbol': loop['parent']},
                              {'kind': loop['kind']}, limitations=LIMITATIONS))
        for branch in info['branches']:
            facts.append(make('branch', NAME, VERSION, sha,
                              {'path': rel, 'start_line': branch['start'], 'end_line': branch['end'],
                               'parent_symbol': branch['parent']},
                              {'kind': branch['kind']}, limitations=LIMITATIONS))
        for site in info['call_sites']:
            facts.append(make('call_site', NAME, VERSION, sha,
                              {'path': rel, 'start_line': site['start'], 'end_line': site['end'],
                               'symbol': site['enclosing']},
                              {'callee': site['callee'], 'attribute': site['attribute']},
                              limitations=LIMITATIONS))
    facts.sort(key=lambda f: (f['location']['path'], f['location'].get('start_line') or 0,
                              f['kind'], f['id']))
    observed = sum(1 for info in by_path.values() if info['status'] == 'OBSERVED')
    blocked = sum(1 for info in by_path.values() if info['status'] == 'BLOCKED')
    considered = observed + blocked
    summary = {'files_considered': considered, 'files_observed': observed, 'files_blocked': blocked,
               'parse_coverage': round(observed / considered, 3) if considered else 0.0,
               'scopes': sum(f['kind'] == 'scope' for f in facts),
               'loops': sum(f['kind'] == 'loop' for f in facts),
               'branches': sum(f['kind'] == 'branch' for f in facts),
               'call_sites': sum(f['kind'] == 'call_site' for f in facts),
               'interpretation': 'Structure facts are lexical. They enable redundancy detection that needs to '
                                 'know where control flow and iterate live; they prove nothing about runtime behaviour.'}
    return {'facts': facts, 'summary': summary, 'available': True,
            'input_sha': digest(''.join(sorted(fingerprints)).encode('utf-8')) if fingerprints else digest(b''),
            'reason': None}

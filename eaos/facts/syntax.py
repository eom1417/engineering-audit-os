"""Symbols, imports and intra-file calls for every language we can actually parse.

Python uses the standard library parser so the core keeps working with no extra dependency.
Other languages use tree-sitter when the optional extra is installed; without it they are reported
as unparsed rather than guessed at, and a file we cannot parse stays visible in the denominator.
"""
import ast
from pathlib import Path
from . import digest, make
from .source import language_of

NAME = 'syntax'
VERSION = '1'
LIMITATIONS = [
    'Syntax only: a parsed import or call is not proof that the code runs at runtime.',
    'Dynamic imports, reflection, dependency injection and framework routing are invisible here.',
    'Call facts are intra-file references by name; they are unresolved until the resolver links them.',
    'Files reported as unparsed remain in the review denominator and are never treated as reviewed.',
]

TREE_SITTER = {
    'javascript': {'functions': {'function_declaration', 'function_expression', 'arrow_function', 'method_definition', 'generator_function_declaration'},
                   'classes': {'class_declaration', 'class'}, 'imports': {'import_statement'}, 'calls': {'call_expression'}},
    'go': {'functions': {'function_declaration', 'method_declaration'}, 'classes': {'type_declaration'},
           'imports': {'import_spec'}, 'calls': {'call_expression'}},
    'java': {'functions': {'method_declaration', 'constructor_declaration'}, 'classes': {'class_declaration', 'interface_declaration', 'enum_declaration', 'record_declaration'},
             'imports': {'import_declaration'}, 'calls': {'method_invocation'}},
    'rust': {'functions': {'function_item'}, 'classes': {'struct_item', 'enum_item', 'trait_item', 'impl_item'},
             'imports': {'use_declaration'}, 'calls': {'call_expression'}},
    'ruby': {'functions': {'method', 'singleton_method'}, 'classes': {'class', 'module'},
             'imports': {'call'}, 'calls': {'call'}},
    'php': {'functions': {'function_definition', 'method_declaration'}, 'classes': {'class_declaration', 'interface_declaration', 'trait_declaration'},
            'imports': {'namespace_use_declaration', 'require_expression', 'include_expression'}, 'calls': {'function_call_expression', 'member_call_expression'}},
    'csharp': {'functions': {'method_declaration', 'constructor_declaration', 'local_function_statement'}, 'classes': {'class_declaration', 'interface_declaration', 'record_declaration', 'struct_declaration'},
               'imports': {'using_directive'}, 'calls': {'invocation_expression'}},
    'kotlin': {'functions': {'function_declaration'}, 'classes': {'class_declaration', 'object_declaration'},
               'imports': {'import_header'}, 'calls': {'call_expression'}},
    'swift': {'functions': {'function_declaration'}, 'classes': {'class_declaration', 'protocol_declaration'},
              'imports': {'import_declaration'}, 'calls': {'call_expression'}},
    'c': {'functions': {'function_definition'}, 'classes': {'struct_specifier'}, 'imports': {'preproc_include'}, 'calls': {'call_expression'}},
    'cpp': {'functions': {'function_definition'}, 'classes': {'class_specifier', 'struct_specifier'}, 'imports': {'preproc_include'}, 'calls': {'call_expression'}},
    'scala': {'functions': {'function_definition'}, 'classes': {'class_definition', 'object_definition', 'trait_definition'},
              'imports': {'import_declaration'}, 'calls': {'call_expression'}},
    'dart': {'functions': {'function_signature', 'method_signature'}, 'classes': {'class_definition'},
             'imports': {'import_or_export'}, 'calls': {'selector'}},
    'bash': {'functions': {'function_definition'}, 'classes': set(), 'imports': set(), 'calls': {'command'}},
}
TREE_SITTER['typescript'] = dict(TREE_SITTER['javascript'], classes={'class_declaration', 'interface_declaration', 'enum_declaration', 'type_alias_declaration', 'abstract_class_declaration'})
TREE_SITTER['tsx'] = TREE_SITTER['typescript']


def parser_for(language):
    try:
        from tree_sitter_language_pack import get_parser
    except ImportError:
        return None
    try:
        return get_parser('c_sharp' if language == 'csharp' else language)
    except Exception:
        return None


def python_units(text):
    """Symbols, imports and calls from the standard library parser, with real qualified names."""
    tree = ast.parse(text)
    symbols, imports, calls = [], [], []
    scope = []

    def visit(node, parent):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = 'class' if isinstance(node, ast.ClassDef) else ('method' if parent else 'function')
            qualified = '.'.join(scope + [node.name])
            signature = None
            if not isinstance(node, ast.ClassDef):
                arguments = node.args
                names = [a.arg for a in [*arguments.posonlyargs, *arguments.args]]
                if arguments.vararg: names.append('*' + arguments.vararg.arg)
                names += [a.arg for a in arguments.kwonlyargs]
                if arguments.kwarg: names.append('**' + arguments.kwarg.arg)
                required = len(names) - len(arguments.defaults) - len(arguments.kw_defaults or [])
                signature = {'parameters': names, 'required': max(required, 0)}
            symbols.append({'name': node.name, 'qualified_name': qualified, 'kind': kind, 'parent': parent,
                            'start_line': node.lineno, 'end_line': node.end_lineno,
                            'exported': not node.name.startswith('_'), 'signature': signature,
                            'decorators': [ast.unparse(d) for d in node.decorator_list][:8]})
            scope.append(node.name)
            for child in ast.iter_child_nodes(node): visit(child, qualified)
            scope.pop()
            return
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({'module': alias.name, 'names': [], 'level': 0, 'line': node.lineno, 'style': 'absolute'})
        elif isinstance(node, ast.ImportFrom):
            imports.append({'module': node.module or '', 'names': [a.name for a in node.names], 'level': node.level,
                            'line': node.lineno, 'style': 'relative' if node.level else 'absolute'})
        elif isinstance(node, ast.Call):
            callee = node.func
            name = getattr(callee, 'id', None) or getattr(callee, 'attr', None)
            if name: calls.append({'caller': parent, 'callee': name, 'line': node.lineno,
                                   'attribute': isinstance(callee, ast.Attribute)})
        for child in ast.iter_child_nodes(node): visit(child, parent)

    for child in ast.iter_child_nodes(tree): visit(child, None)
    return symbols, imports, calls


def node_text(node, blob): return blob[node.start_byte:node.end_byte].decode('utf-8', errors='replace')


def named_child(node, blob):
    field = node.child_by_field_name('name')
    if field is not None: return node_text(field, blob)
    for child in node.named_children:
        if child.type in {'identifier', 'type_identifier', 'field_identifier', 'property_identifier', 'constant', 'scoped_identifier'}:
            return node_text(child, blob)
    return None


def anonymous_name(node, blob):
    """An arrow function or function expression is named by whatever binds it."""
    parent = node.parent
    for _ in range(3):
        if parent is None: break
        if parent.type in {'variable_declarator', 'pair', 'assignment_expression', 'public_field_definition'}:
            return named_child(parent, blob) or node_text(parent.named_children[0], blob) if parent.named_children else None
        parent = parent.parent
    return None


def imported_names(node, blob):
    """Names an import statement actually brings in, so a later probe can reason about them."""
    names, stack = [], [node]
    while stack:
        current = stack.pop(0)
        if current.type in {'import_specifier', 'namespace_import', 'identifier', 'shorthand_property_identifier_pattern'}:
            field = current.child_by_field_name('name') or current
            text = node_text(field, blob).strip()
            if text and text.isidentifier(): names.append(text)
            if current.type == 'import_specifier': continue
        stack.extend(current.named_children)
    unique = []
    for name in names:
        if name not in unique: unique.append(name)
    return unique


def first_string(node, blob):
    stack = [node]
    while stack:
        current = stack.pop(0)
        if current.type in {'string', 'string_literal', 'interpreted_string_literal', 'raw_string_literal', 'string_fragment'}:
            return node_text(current, blob).strip('\'"`')
        stack.extend(current.named_children)
    return None


def tree_sitter_units(language, text, config):
    parser = parser_for(language)
    if parser is None: return None
    blob = text.encode('utf-8')
    tree = parser.parse(blob)
    symbols, imports, calls = [], [], []

    def walk(node, enclosing):
        kind = None
        if node.type in config['functions']: kind = 'method' if enclosing else 'function'
        elif node.type in config['classes']: kind = 'class'
        current = enclosing
        if kind:
            name = named_child(node, blob) or anonymous_name(node, blob)
            if name:
                qualified = (enclosing + '.' + name) if enclosing else name
                parameters = node.child_by_field_name('parameters') or node.child_by_field_name('formal_parameters')
                signature = None
                if parameters is not None:
                    names = [node_text(child, blob).split(':')[0].strip()
                             for child in parameters.named_children if child.type != 'comment']
                    signature = {'parameters': [name for name in names if name], 'required': None}
                symbols.append({'name': name, 'qualified_name': qualified, 'kind': kind, 'parent': enclosing,
                                'start_line': node.start_point[0] + 1, 'end_line': node.end_point[0] + 1,
                                'exported': True, 'signature': signature, 'decorators': []})
                current = qualified
        if node.type in config['imports']:
            module = first_string(node, blob)
            if module is None and node.named_children:
                module = node_text(node.named_children[0], blob).strip('\'"`;')
            if module:
                imports.append({'module': module, 'names': imported_names(node, blob), 'level': 0,
                                'line': node.start_point[0] + 1,
                                'style': 'relative' if module.startswith('.') else 'absolute'})
        elif node.type in config['calls']:
            target = node.child_by_field_name('function') or node.child_by_field_name('method') or (node.named_children[0] if node.named_children else None)
            if target is not None:
                raw_callee = node_text(target, blob).split('(')[0].strip()
                callee = raw_callee.split('.')[-1].split('::')[-1].split('->')[-1].strip()
                if callee and callee.isidentifier():
                    if callee in {'require', 'import'}:
                        module = first_string(node, blob)
                        if module: imports.append({'module': module, 'names': [], 'level': 0, 'line': node.start_point[0] + 1,
                                                   'style': 'relative' if module.startswith('.') else 'absolute'})
                    calls.append({'caller': current, 'callee': callee, 'line': node.start_point[0] + 1,
                                  'attribute': raw_callee != callee})
        for child in node.named_children: walk(child, current)

    walk(tree.root_node, None)
    return symbols, imports, calls


def parse_text(path, text):
    """Return (units, parser_name, status). Status is OBSERVED, UNSUPPORTED or BLOCKED."""
    language = language_of(path)
    if language == 'python':
        try:
            return python_units(text), 'python_ast', 'OBSERVED', language
        except (SyntaxError, ValueError, RecursionError):
            return None, 'python_ast', 'BLOCKED', language
    config = TREE_SITTER.get(language)
    if config:
        try:
            units = tree_sitter_units(language, text, config)
        except (RecursionError, ValueError, RuntimeError):
            units = None
        if units is not None: return units, 'tree_sitter:' + language, 'OBSERVED', language
        return None, 'tree_sitter_unavailable', 'UNSUPPORTED', language
    return None, 'none', 'UNSUPPORTED', language


def run(target, source, cache=None, **options):
    """Per-file results are cached by content hash, so re-running after a small change is cheap."""
    facts, statuses, languages = [], {}, {}
    fingerprints = []
    cache = cache if cache is not None else {}
    reused = 0
    for item in source.readable():
        rel = item['path']
        if source.category(rel) not in {'source', 'test', 'manifest'} and language_of(rel) is None: continue
        text = source.text(rel)
        if text is None:
            statuses['BLOCKED'] = statuses.get('BLOCKED', 0) + 1
            continue
        fingerprints.append(item['sha256'])
        key = item['sha256'] + '|' + rel + '|' + VERSION
        cached = cache.get(key)
        if cached is not None:
            reused += 1
            statuses[cached['status']] = statuses.get(cached['status'], 0) + 1
            languages[cached['language'] or 'unknown'] = languages.get(cached['language'] or 'unknown', 0) + 1
            facts.extend(cached['facts'])
            continue
        produced_before = len(facts)
        units, parser_name, status, language = parse_text(rel, text)
        if language is None and source.category(rel) in {'manifest', 'configuration'}:
            status, parser_name = 'NOT_SOURCE', 'not_a_source_language'
        statuses[status] = statuses.get(status, 0) + 1
        languages[language or 'unknown'] = languages.get(language or 'unknown', 0) + 1
        lines = text.count('\n') + 1
        facts.append(make('source_file', NAME, VERSION, item['sha256'], {'path': rel},
                          {'language': language, 'lines': lines, 'parse_status': status, 'parser': parser_name,
                           'category': source.category(rel)}, limitations=LIMITATIONS))
        if units is None: continue
        symbols, imports, calls = units
        for symbol in symbols:
            facts.append(make('symbol', NAME, VERSION, item['sha256'],
                              {'path': rel, 'start_line': symbol['start_line'], 'end_line': symbol['end_line'], 'symbol': symbol['qualified_name']},
                              {k: symbol[k] for k in ['name', 'kind', 'parent', 'exported', 'decorators', 'signature']} | {'language': language},
                              limitations=LIMITATIONS))
        for entry in imports:
            facts.append(make('import_edge', NAME, VERSION, item['sha256'], {'path': rel, 'start_line': entry['line']},
                              {'module': entry['module'], 'names': entry['names'], 'level': entry['level'],
                               'style': entry['style'], 'language': language},
                              resolution='UNRESOLVED', limitations=LIMITATIONS))
        for entry in calls:
            facts.append(make('call_edge', NAME, VERSION, item['sha256'], {'path': rel, 'start_line': entry['line'], 'symbol': entry['caller']},
                              {'callee': entry['callee'], 'attribute': entry.get('attribute', False), 'language': language},
                              resolution='UNRESOLVED', limitations=LIMITATIONS))
        cache[key] = {'status': status, 'language': language, 'facts': facts[produced_before:]}
    facts.sort(key=lambda f: (f['location']['path'], f['location'].get('start_line', 0), f['kind'], f['id']))
    parsed = statuses.get('OBSERVED', 0)
    considered = sum(statuses.values())
    source_files = considered - statuses.get('NOT_SOURCE', 0)
    summary = {'files_considered': considered, 'source_files': source_files, 'files_parsed': parsed,
               'parse_coverage': round(parsed / source_files, 3) if source_files else 0.0,
               'by_status': dict(sorted(statuses.items())), 'by_language': dict(sorted(languages.items())),
               'symbols': sum(f['kind'] == 'symbol' for f in facts),
               'imports': sum(f['kind'] == 'import_edge' for f in facts),
               'calls': sum(f['kind'] == 'call_edge' for f in facts),
               'tree_sitter_available': parser_for('typescript') is not None,
               'interpretation': 'Structural observations only. No responsibility, boundary or defect is implied by any symbol or edge.'}
    # The cache counter is run telemetry, not a fact about the code: keeping it out of the fact set
    # means a cached run and a cold run produce byte-identical output.
    return {'facts': facts, 'summary': summary, 'available': True, 'reused_from_cache': reused,
            'input_sha': digest(''.join(sorted(fingerprints)).encode('utf-8')), 'reason': None}

"""Symbols, imports and intra-file calls for every language we can actually parse.

Python uses the standard library parser so the core keeps working with no extra dependency.
Other languages use tree-sitter when the optional extra is installed; without it they are reported
as unparsed rather than guessed at, and a file we cannot parse stays visible in the denominator.
"""
import re
import ast
from . import digest, make
from .source import language_of

NAME = 'syntax'
VERSION = '3'
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
    units = {'symbols': [], 'imports': [], 'calls': [], 'scope': []}
    for child in ast.iter_child_nodes(tree): _visit_python(child, None, units)
    return units['symbols'], units['imports'], units['calls']


def _python_signature(node):
    if isinstance(node, ast.ClassDef): return None
    arguments = node.args
    names = [a.arg for a in [*arguments.posonlyargs, *arguments.args]]
    if arguments.vararg: names.append('*' + arguments.vararg.arg)
    names += [a.arg for a in arguments.kwonlyargs]
    if arguments.kwarg: names.append('**' + arguments.kwarg.arg)
    required = len(names) - len(arguments.defaults) - len(arguments.kw_defaults or [])
    return {'parameters': names, 'required': max(required, 0)}


def _python_symbol(node, parent, units):
    kind = 'class' if isinstance(node, ast.ClassDef) else ('method' if parent else 'function')
    qualified = '.'.join(units['scope'] + [node.name])
    units['symbols'].append({'name': node.name, 'qualified_name': qualified, 'kind': kind, 'parent': parent,
                             'start_line': node.lineno, 'end_line': node.end_lineno,
                             'exported': not node.name.startswith('_'), 'signature': _python_signature(node),
                             'decorators': [ast.unparse(d) for d in node.decorator_list][:8]})
    units['scope'].append(node.name)
    for child in ast.iter_child_nodes(node): _visit_python(child, qualified, units)
    units['scope'].pop()


def _python_import(node, units):
    if isinstance(node, ast.Import):
        units['imports'] += [{'module': alias.name, 'names': [], 'level': 0, 'line': node.lineno, 'style': 'absolute'}
                             for alias in node.names]
    else:
        units['imports'].append({'module': node.module or '', 'names': [a.name for a in node.names], 'level': node.level,
                                 'line': node.lineno, 'style': 'relative' if node.level else 'absolute'})


def _python_call(node, parent, units):
    callee = node.func
    name = getattr(callee, 'id', None) or getattr(callee, 'attr', None)
    if name: units['calls'].append({'caller': parent, 'callee': name, 'line': node.lineno,
                                    'attribute': isinstance(callee, ast.Attribute)})


def _visit_python(node, parent, units):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        _python_symbol(node, parent, units)
        return
    if isinstance(node, (ast.Import, ast.ImportFrom)): _python_import(node, units)
    elif isinstance(node, ast.Call): _python_call(node, parent, units)
    for child in ast.iter_child_nodes(node): _visit_python(child, parent, units)


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


def literal_argument(node, blob):
    """The specifier of `import("./x")` or `require("./x")`: the first argument when it is a literal, else None.
    `import(new URL("../server/", import.meta.url).href)` loads a computed path; the string inside it is a base
    folder, not the module, and reading it as one reported a missing import."""
    arguments = node.child_by_field_name('arguments')
    first = arguments.named_children[0] if arguments is not None and arguments.named_children else None
    if first is None: return None
    if first.type == 'template_string' and any(child.type == 'template_substitution' for child in first.named_children): return None
    if first.type not in {'string', 'template_string', 'string_literal', 'interpreted_string_literal', 'raw_string_literal'}: return None
    return node_text(first, blob).strip('\'"`')


def tree_sitter_units(language, text, config):
    parser = parser_for(language)
    if parser is None: return None
    blob = text.encode('utf-8')
    tree = parser.parse(blob)
    walker = {'config': config, 'blob': blob, 'symbols': [], 'imports': [], 'calls': []}
    _walk_tree(tree.root_node, None, walker)
    return walker['symbols'], walker['imports'], walker['calls']


def _module_import(module, names, line):
    return {'module': module, 'names': names, 'level': 0, 'line': line,
            'style': 'relative' if module.startswith('.') else 'absolute'}


def _tree_kind(node, config, enclosing):
    if node.type in config['functions']: return 'method' if enclosing else 'function'
    if node.type in config['classes']: return 'class'
    return None


def _tree_signature(node, blob):
    parameters = node.child_by_field_name('parameters') or node.child_by_field_name('formal_parameters')
    if parameters is None: return None
    names = [node_text(child, blob).split(':')[0].strip()
             for child in parameters.named_children if child.type != 'comment']
    return {'parameters': [name for name in names if name], 'required': None}


def _tree_symbol(node, kind, enclosing, walker):
    """Record the symbol `node` declares; its qualified name, or `enclosing` when it has no name."""
    blob = walker['blob']
    name = named_child(node, blob) or anonymous_name(node, blob)
    if not name: return enclosing
    qualified = (enclosing + '.' + name) if enclosing else name
    walker['symbols'].append({'name': name, 'qualified_name': qualified, 'kind': kind, 'parent': enclosing,
                              'start_line': node.start_point[0] + 1, 'end_line': node.end_point[0] + 1,
                              'exported': True, 'signature': _tree_signature(node, blob), 'decorators': []})
    return qualified


def _tree_import(node, blob):
    module = first_string(node, blob)
    if module is None and node.named_children:
        module = node_text(node.named_children[0], blob).strip('\'"`;')
    return _module_import(module, imported_names(node, blob), node.start_point[0] + 1) if module else None


def _tree_reexport(node, blob):
    # A re-export (`export { Dialog } from "./Dialog"`, `export * from "./types"`) depends on its source
    # exactly as an import does. A barrel index.ts made only of these was a file with no edges, and every
    # module behind it looked unreachable.
    module = node_text(node.child_by_field_name('source'), blob).strip('\'"`')
    clause = re.search(r'\{([^}]*)\}', node_text(node, blob))
    names = [part.split(' as ')[0].strip() for part in clause.group(1).split(',') if part.strip()] if clause else ['*']
    return _module_import(module, [n for n in names if n == '*' or n.isidentifier()], node.start_point[0] + 1)


def _tree_call(node, current, walker):
    blob = walker['blob']
    target = node.child_by_field_name('function') or node.child_by_field_name('method') or (node.named_children[0] if node.named_children else None)
    if target is None: return
    raw_callee = node_text(target, blob).split('(')[0].strip()
    callee = raw_callee.split('.')[-1].split('::')[-1].split('->')[-1].strip()
    if not (callee and callee.isidentifier()): return
    if callee in {'require', 'import'}:
        module = literal_argument(node, blob)
        if module: walker['imports'].append(_module_import(module, [], node.start_point[0] + 1))
    walker['calls'].append({'caller': current, 'callee': callee, 'line': node.start_point[0] + 1,
                            'attribute': raw_callee != callee})


def _tree_edges(node, current, walker):
    config, blob = walker['config'], walker['blob']
    if node.type in config['imports']:
        found = _tree_import(node, blob)
        if found: walker['imports'].append(found)
    elif node.type == 'export_statement' and node.child_by_field_name('source') is not None:
        walker['imports'].append(_tree_reexport(node, blob))
    elif node.type in config['calls']:
        _tree_call(node, current, walker)


def _walk_tree(node, enclosing, walker):
    kind = _tree_kind(node, walker['config'], enclosing)
    current = _tree_symbol(node, kind, enclosing, walker) if kind else enclosing
    _tree_edges(node, current, walker)
    for child in node.named_children: _walk_tree(child, current, walker)


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
    """Per-file results are cached by content hash, so re-running after a small change is cheap. The cache keeps only
    today's files: an edited or removed file's old entry goes, else every edit grew it for good (175 MB on EAOS)."""
    facts, statuses, languages = [], {}, {}
    fingerprints, seen = [], set()
    cache = cache if cache is not None else {}
    reused = 0
    for item in source.readable():
        rel = item['path']
        if not _considered(source, rel): continue
        text = source.text(rel)
        if text is None:
            _count(statuses, 'BLOCKED')
            continue
        fingerprints.append(item['sha256'])
        key = item['sha256'] + '|' + rel + '|' + VERSION
        seen.add(key)
        entry = cache.get(key)
        if entry is not None: reused += 1
        else: entry = cache[key] = _parsed_file(item, rel, text, source)
        _count(statuses, entry['status'])
        _count(languages, entry['language'] or 'unknown')
        facts.extend(entry['facts'])
    for stale in cache.keys() - seen: del cache[stale]
    facts.sort(key=lambda f: (f['location']['path'], f['location'].get('start_line', 0), f['kind'], f['id']))
    # The cache counter is run telemetry, not a fact about the code: keeping it out of the fact set
    # means a cached run and a cold run produce byte-identical output.
    return {'facts': facts, 'summary': _summary(facts, statuses, languages), 'available': True, 'reused_from_cache': reused,
            'input_sha': digest(''.join(sorted(fingerprints)).encode('utf-8')), 'reason': None}


def _count(table, key): table[key] = table.get(key, 0) + 1


def _considered(source, rel):
    return source.category(rel) in {'source', 'test', 'manifest'} or language_of(rel) is not None


def _unit_facts(item, rel, language, units):
    symbols, imports, calls = units
    facts = [make('symbol', NAME, VERSION, item['sha256'],
                  {'path': rel, 'start_line': symbol['start_line'], 'end_line': symbol['end_line'], 'symbol': symbol['qualified_name']},
                  {k: symbol[k] for k in ['name', 'kind', 'parent', 'exported', 'decorators', 'signature']} | {'language': language},
                  limitations=LIMITATIONS) for symbol in symbols]
    facts += [make('import_edge', NAME, VERSION, item['sha256'], {'path': rel, 'start_line': entry['line']},
                   {'module': entry['module'], 'names': entry['names'], 'level': entry['level'],
                    'style': entry['style'], 'language': language},
                   resolution='UNRESOLVED', limitations=LIMITATIONS) for entry in imports]
    facts += [make('call_edge', NAME, VERSION, item['sha256'], {'path': rel, 'start_line': entry['line'], 'symbol': entry['caller']},
                   {'callee': entry['callee'], 'attribute': entry.get('attribute', False), 'language': language},
                   resolution='UNRESOLVED', limitations=LIMITATIONS) for entry in calls]
    return facts


def _parsed_file(item, rel, text, source):
    """The cache entry of one file parsed now: its status, language and facts."""
    units, parser_name, status, language = parse_text(rel, text)
    if language is None and source.category(rel) in {'manifest', 'configuration'}:
        status, parser_name = 'NOT_SOURCE', 'not_a_source_language'
    facts = [make('source_file', NAME, VERSION, item['sha256'], {'path': rel},
                  {'language': language, 'lines': text.count('\n') + 1, 'parse_status': status, 'parser': parser_name,
                   'category': source.category(rel)}, limitations=LIMITATIONS)]
    if units is not None: facts += _unit_facts(item, rel, language, units)
    return {'status': status, 'language': language, 'facts': facts}


def _summary(facts, statuses, languages):
    parsed = statuses.get('OBSERVED', 0)
    considered = sum(statuses.values())
    source_files = considered - statuses.get('NOT_SOURCE', 0)
    return {'files_considered': considered, 'source_files': source_files, 'files_parsed': parsed,
            'parse_coverage': round(parsed / source_files, 3) if source_files else 0.0,
            'by_status': dict(sorted(statuses.items())), 'by_language': dict(sorted(languages.items())),
            'symbols': sum(f['kind'] == 'symbol' for f in facts),
            'imports': sum(f['kind'] == 'import_edge' for f in facts),
            'calls': sum(f['kind'] == 'call_edge' for f in facts),
            'tree_sitter_available': parser_for('typescript') is not None,
            'interpretation': 'Structural observations only. No responsibility, boundary or defect is implied by any symbol or edge.'}

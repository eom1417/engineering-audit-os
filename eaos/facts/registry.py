"""A dead-code candidate whose name is held in a distribution registry of the analysed project is
not dead: the registry invokes it by name. The detector scans the project's source for the
patterns the spec calls out: module lists ``MODULES = [a, b, c]``, dict lookups
``REGISTRY['key']``, getattr-by-string, ``__all__``, importlib/import() with a literal argument,
and JSON ``name``/``id`` fields in any directory under the snapshot.

A registry-referenced candidate is kept on disk but tagged
``value.referenced_by_registry = True``; the cluster pass (eaos/analysis/correlate.py) skips it so no dead_code claim
is raised for it, which is the contract the spec phrases as 'a candidate referenced by one of
these sources stays as engine_finding and does not become a dead_code claim'.
"""
import ast
import json
import re as _re

from .source import Source

_MODULE_LIST = _re.compile(r"\[\s*[A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*\s*\]")
_DICT_GET = _re.compile(r"\b[A-Za-z_][\w.]*\[[\'\"](?P<key>[A-Za-z_][\w]*)[\'\"]\s*[,:=]\s*[A-Za-z_][\w.]*")
_GETATTR_STRING = _re.compile(r"""\bgetattr\s*\(\s*[^,]+,\s*["\'](?P<name>[A-Za-z_][\w]*)["\']""")
__ALL__ = _re.compile(r"""__all__\s*=\s*\[(?P<names>[^\]]*)\]""")
_IMPORTLIB = _re.compile(r"""importlib\.import_module\(\s*['\"](?P<name>[A-Za-z_][\w.]*)['\"]""")
_DYNAMIC_IMPORT = _re.compile(r"""\bimport\s*\(\s*['\"](?P<name>[A-Za-z_@/][\w./@-]*)['\"]""")


def _module_names_in_list(text):
    found = set()
    for match in _MODULE_LIST.finditer(text):
        for token in _re.findall(r"\b[A-Za-z_][\w.]*\b", match.group(0)):
            found.add(token)
    return found


def _all_names(text):
    names = set()
    for match in __ALL__.finditer(text):
        for token in _re.findall(r"""['\"]([A-Za-z_]\w*)['\"]""", match.group('names')):
            names.add(token)
    return names


def _dynamic_import_names(text):
    names = set()
    for pattern in (_DYNAMIC_IMPORT, _IMPORTLIB):
        for match in pattern.finditer(text):
            names.add(match.group('name').split('.')[-1])
    return names


def _recursive_callers(source):
    """Symbols whose body calls the symbol by name — ref itself is enough to keep it alive."""
    recursive = set()
    for item in source.readable():
        rel = item['path']
        text = source.text(rel)
        if text is None: continue
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _calls_itself(node):
                recursive.add(f"{rel.rsplit('.', 1)[0]}.{node.name}".replace('/', '.'))
    return recursive


def _calls_itself(function):
    """Whether a function's body calls it by its bare name."""
    return function.name in {c.func.id for c in ast.walk(function) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}


def _pyproject_entry_points(text):
    names = set()
    for match in _re.finditer(r'''\[\[project\.scripts\]\][^\[]*?(?P<name>[A-Za-z_][\w.-]*)\s*=''',
                              text):
        names.add(match.group('name'))
    for match in _re.finditer(
            r'''\[\[project\.entry-points\.([^\]]+)\]\][^\[]*?(?P<name>[A-Za-z_][\w.-]*)\s*=\s*[A-Za-z_][\w.]*:(?P<callable>[A-Za-z_][\w]*)''',
            text):
        names.add(f"{match.group('name')}:{match.group('callable')}")
    return names


def _json_string_keys(text):
    found = set()
    for pattern in ('"name"', "'name'", '"id"', "'id'", '"module"', '"entry"', '"function"'):
        for match in _re.finditer(pattern + r'\s*:\s*["\']([A-Za-z_][\w.-]*)', text):
            found.add(match.group(1))
    return found


def _walk_json_names(obj):
    found = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in ('name', 'id', 'module', 'entry', 'function') and isinstance(value, str):
                found.add(value.split('.')[-1])
            found.update(_walk_json_names(value))
    elif isinstance(obj, list):
        for item in obj:
            found.update(_walk_json_names(item))
    return found


def _dict_lookup_names(text):
    return {token for match in _DICT_GET.finditer(text)
            for token in _re.findall(r"\b[A-Za-z_][\w.]*\b", match.group(0)) if token != match.group('key')}


def _python_registry(text, symbols, modules):
    for module_name in _module_names_in_list(text):
        modules.add(module_name)
        symbols.update((f"{module_name}.detect", f"{module_name}.capabilities"))
    symbols.update(_all_names(text))
    symbols.update(_dynamic_import_names(text))
    symbols.update(_dict_lookup_names(text))
    symbols.update(_GETATTR_STRING.findall(text))


def _json_registry(text):
    try: return _walk_json_names(json.loads(text))
    except (ValueError, TypeError): return _json_string_keys(text)


def _registry_symbols(source):
    symbols, modules = set(), set()
    for item in source.readable():
        rel = item['path']
        text = source.text(rel)
        if text is None: continue
        if rel.endswith('.py'): _python_registry(text, symbols, modules)
        elif rel == 'pyproject.toml' or rel.endswith('/pyproject.toml'): symbols.update(_pyproject_entry_points(text))
        elif rel.endswith('.json'): symbols.update(_json_registry(text))
    return symbols, modules


def _is_real_dead_code_finding(fact):
    """A dead_code finding must name a function or method, not a marker the engine mislabels."""
    message = ((fact.get('value') or {})).get('message') or ''
    return ('function' in message or 'method' in message
            or (fact.get('value') or {}).get('rule') in ('unreachable-module', 'unreachable-symbol'))


def _is_referenced_dead_code(fact, symbols, modules):
    """A candidate reachable through a registry invocation is not actually dead."""
    value = fact.get('value') or {}
    if value.get('kind') != 'dead_code' or not _is_real_dead_code_finding(fact):
        return False
    qualified = _qualified_name(value.get('message') or '')
    if not qualified:
        return False
    bare = qualified.rsplit('.', 1)[-1].rsplit('/', 1)[-1]
    if bare in symbols or qualified in symbols: return True
    return _registered_hook(qualified, bare, modules)


def _qualified_name(message):
    # The qualified name is either inside backticks (``.detect in module.x``) or after the
    # ``function `` / ``method `` keyword in the prose form.
    if '`' in message: return message.split('`')[1]
    for keyword in ('function', 'method'):
        head, sep, tail = message.rpartition(keyword)
        if sep and tail.strip(): return tail.strip().rstrip('.').split(' ', 1)[0]
    return None


def _registered_hook(qualified, bare, modules):
    """`<module>.detect` or `<module>.capabilities` of a module a registry lists."""
    if bare not in {'detect', 'capabilities'} or not qualified.endswith('.' + bare): return False
    prefix = qualified[:-(len(bare) + 1)]
    return prefix.rsplit('.', 1)[-1].rsplit('/', 1)[-1] in modules


def _mark_registry_referenced(facts, source):
    """(the facts, how many were marked): each dead-code fact a registry reaches gets value.referenced_by_registry."""
    symbols, modules = _registry_symbols(source)
    symbols.update(_recursive_callers(source))
    marked = 0
    for fact in facts:
        if not (_is_real_dead_code_finding(fact) and _is_referenced_dead_code(fact, symbols, modules)): continue
        value = fact.get('value') or {}
        value['referenced_by_registry'] = True
        value['registry_symbols_seen'] = sorted(list(symbols))[:8]
        fact['value'] = value
        marked += 1
    return list(facts), marked


def filter_in_sets(facts, sets):
    """Annotate the dead_code facts whose name is held in a distribution registry.

    The function does not remove facts from disk; a registry-referenced candidate is still a
    valid place the engine looked, and downstream stages that read the fact set (the S2 measure,
    the dossier table) keep working. Marking the fact with ``value.referenced_by_registry = True``
    lets the cluster pass skip it so no dead_code claim is raised for it — the NS4.T2 spec.
    """
    source = _source_from_sets(sets)
    if source is None:
        return facts
    return _mark_registry_referenced(facts, source)[0]


def _source_from_sets(sets):
    """Build a Source from the inventory recorded with the persisted facts, if any."""
    inventory = (sets.get('index') or {}).get('inventory')
    if not inventory:
        return None
    if hasattr(Source, 'from_dict'):
        return Source.from_dict(inventory)
    return None


# Backward-compatible public hook kept for facts/run.py:collect_external().
# New behaviour: annotate facts in place; return (annotated_facts, count_marked).
def filter_dead_code_references(facts, source):
    if source is None:
        return facts, 0
    return _mark_registry_referenced(facts, source)

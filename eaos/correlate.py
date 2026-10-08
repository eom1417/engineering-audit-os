"""Four engines describing one place, read as one problem — and their disagreements kept visible.

Nothing here decides that a finding is true. It decides how many independent engines said it, how
many looked and did not, and therefore what a claim built on it may honestly assert.

NS4.T2 (registry-aware dead-code filter) adds an annotation pass that tags candidates whose name is
held in a distribution registry of the analysed project. The tagged facts stay on disk so the S2
measure and downstream stages still see them, but clusters() skips them so no dead_code claim is
raised for them.
"""
import re
import json
from collections import defaultdict
from hashlib import sha1
from .facts.source import Source

CORROBORATED, SINGLE, CONTESTED = 'corroborated', 'single_engine', 'contested'
GRANULARITY_GAP = 'different_resolution'
OBSERVED, PARTIAL = 'observed', 'partial'
# Silence only contradicts where the property is structural: a graph either has that cycle or it
# does not.
DENIABLE = ('cycle',)


def _findings(sets):
    """Engine findings from every engine, EAOS's own dead-code detector included, minus the dead-code
    candidates adjudication refuted or found to name no symbol (facts/deadcode.adjudicate)."""
    out = [fact for name in ('external', 'deadcode') for fact in (sets.get(name) or {}).get('facts', [])
           if fact.get('kind') == 'engine_finding']
    return [fact for fact in out
            if ((fact.get('value') or {}).get('adjudication') or {}).get('verdict') not in ('refuted', 'not_a_symbol')]


def _evaluated(sets):
    out = ((sets.get('external') or {}).get('summary') or {}).get('evaluated_kinds', {})
    out = dict(out)
    extra = ((sets.get('deadcode') or {}).get('summary') or {}).get('evaluated_kinds', {})
    out.update(extra)
    return out


def _places(fact):
    """Every place this finding touches; a five-file duplicate belongs to five places."""
    sites = [site['path'] for site in fact['value'].get('sites', []) if site.get('path')]
    if sites:
        return sorted(set(sites))
    location = fact['location']
    return [location.get('path') or location.get('symbol')] if (location.get('path') or location.get('symbol')) else []


def _resolution(evaluated, engine, kind):
    detail = (evaluated.get(engine) or {}).get(kind)
    return (detail or {}).get('granularity') if isinstance(detail, dict) else None


def _status(evaluated, engine, kind):
    detail = (evaluated.get(engine) or {}).get(kind)
    return detail.get('status') if isinstance(detail, dict) else detail


def verdict(kind, asserted_by, evaluated):
    """How much weight a kind of finding at one place has earned."""
    silent = {engine: state for engine in evaluated
              if (state := _status(evaluated, engine, kind)) and engine not in asserted_by}
    asserted_at = {_resolution(evaluated, engine, kind) for engine in asserted_by}
    same_resolution = sorted(engine for engine, state in silent.items()
                             if state == OBSERVED and _resolution(evaluated, engine, kind) in asserted_at)
    other_resolution = sorted(engine for engine, state in silent.items()
                              if state == OBSERVED and _resolution(evaluated, engine, kind) not in asserted_at)
    denied_fully = same_resolution if kind in DENIABLE else []
    if len(asserted_by) > 1:
        decision = CORROBORATED
    elif denied_fully:
        decision = CONTESTED
    elif kind in DENIABLE and other_resolution:
        decision = GRANULARITY_GAP
    else:
        decision = SINGLE
    return {'verdict': decision, 'asserted_by': sorted(asserted_by),
            'asserted_at': sorted(level for level in asserted_at if level),
            'evaluated_and_silent': dict(sorted(silent.items())), 'denied_by': denied_fully,
            'silent_at_another_resolution': other_resolution}


# --------------------------------------------------------------------------
# Distribution-registry detector (NS4.T2)
# --------------------------------------------------------------------------
# A dead-code candidate whose name is held in a distribution registry of the analysed project is
# not dead: the registry invokes it by name. The detector scans the project's source for the
# patterns the spec calls out: module lists ``MODULES = [a, b, c]``, dict lookups
# ``REGISTRY['key']``, getattr-by-string, ``__all__``, importlib/import() with a literal argument,
# and JSON ``name``/``id`` fields in any directory under the snapshot.
#
# A registry-referenced candidate is kept on disk but tagged
# ``value.referenced_by_registry = True``; the cluster pass below skips it so no dead_code claim
# is raised for it, which is the contract the spec phrases as 'a candidate referenced by one of
# these sources stays as engine_finding and does not become a dead_code claim'.
import re as _re

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
    try:
        import ast as _ast
    except ImportError:
        return set()
    recursive = set()
    for item in source.readable():
        rel = item['path']
        text = source.text(rel)
        if text is None: continue
        try:
            tree = _ast.parse(text)
        except (SyntaxError, ValueError):
            continue
        for node in _ast.walk(tree):
            if not isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                continue
            body_calls = {c.func.id for c in _ast.walk(node)
                          if isinstance(c, _ast.Call) and isinstance(c.func, _ast.Name)}
            if node.name in body_calls:
                recursive.add(f"{rel.rsplit('.', 1)[0]}.{node.name}".replace('/', '.'))
    return recursive


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


def _registry_symbols(source):
    symbols = set()
    modules = set()
    for item in source.readable():
        rel = item['path']
        text = source.text(rel)
        if text is None: continue
        if rel.endswith('.py'):
            for module_name in _module_names_in_list(text):
                modules.add(module_name)
                symbols.add(f"{module_name}.detect")
                symbols.add(f"{module_name}.capabilities")
            symbols.update(_all_names(text))
            symbols.update(_dynamic_import_names(text))
            for match in _DICT_GET.finditer(text):
                for token in _re.findall(r"\b[A-Za-z_][\w.]*\b", match.group(0)):
                    if token != match.group('key'):
                        symbols.add(token)
            for match in _GETATTR_STRING.findall(text):
                symbols.add(match)
        elif rel == 'pyproject.toml' or rel.endswith('/pyproject.toml'):
            symbols.update(_pyproject_entry_points(text))
        elif rel.endswith('.json'):
            try:
                parsed = json.loads(text)
                symbols.update(_walk_json_names(parsed))
            except (ValueError, TypeError):
                symbols.update(_json_string_keys(text))
    return symbols, modules


def _is_real_dead_code_finding(fact):
    """A dead_code finding must name a function or method, not a marker the engine mislabels."""
    message = ((fact.get('value') or {})).get('message') or ''
    return ('function' in message or 'method' in message
            or (fact.get('value') or {}).get('rule') in ('unreachable-module', 'unreachable-symbol'))


def _is_referenced_dead_code(fact, symbols, modules):
    """A candidate reachable through a registry invocation is not actually dead."""
    value = fact.get('value') or {}
    if value.get('kind') != 'dead_code':
        return False
    message = value.get('message') or ''
    if not ('function' in message or 'method' in message
            or value.get('rule') in ('unreachable-module', 'unreachable-symbol')):
        return False
    # The qualified name is either inside backticks (``.detect in module.x``) or after the
    # ``function `` / ``method `` keyword in the prose form.
    qualified = None
    if '`' in message:
        qualified = message.split('`')[1]
    else:
        for keyword in ('function', 'method'):
            head, sep, tail = message.rpartition(keyword)
            if sep and tail.strip():
                qualified = tail.strip().rstrip('.').split(' ', 1)[0]
                break
    if not qualified:
        return False
    bare = qualified.rsplit('.', 1)[-1].rsplit('/', 1)[-1]
    if bare in symbols or qualified in symbols: return True
    if bare in {'detect', 'capabilities'} and qualified.endswith('.' + bare):
        prefix = qualified[:-(len(bare) + 1)]
        module_segment = prefix.rsplit('.', 1)[-1].rsplit('/', 1)[-1]
        if module_segment in modules: return True
    return False


def _filter_registry_referenced_dead_code(facts, sets):
    """Annotate the dead_code facts whose name is held in a distribution registry.

    The function does not remove facts from disk; a registry-referenced candidate is still a
    valid place the engine looked, and downstream stages that read the fact set (the S2 measure,
    the dossier table) keep working. Marking the fact with ``value.referenced_by_registry = True``
    lets the cluster pass skip it so no dead_code claim is raised for it — the NS4.T2 spec.
    """
    source = _source_from_sets(sets)
    if source is None:
        return facts
    symbols, modules = _registry_symbols(source)
    symbols.update(_recursive_callers(source))
    out = []
    for fact in facts:
        if not _is_real_dead_code_finding(fact):
            out.append(fact); continue
        if _is_referenced_dead_code(fact, symbols, modules):
            value = fact.get('value') or {}
            value['referenced_by_registry'] = True
            value['registry_symbols_seen'] = sorted(list(symbols))[:8]
            fact['value'] = value
        out.append(fact)
    return out


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
    symbols, modules = _registry_symbols(source)
    symbols.update(_recursive_callers(source))
    dropped = 0
    kept = []
    for fact in facts:
        if not _is_real_dead_code_finding(fact):
            kept.append(fact); continue
        if _is_referenced_dead_code(fact, symbols, modules):
            value = fact.get('value') or {}
            value['referenced_by_registry'] = True
            value['registry_symbols_seen'] = sorted(list(symbols))[:8]
            fact['value'] = value
            dropped += 1
        kept.append(fact)
    return kept, dropped


def is_wide(fact):
    """A finding about a group spread over more than WIDE files is evidence about the group, not about each file in it:
    a word repeated across 17 files says nothing about the complexity of any one of them (NS30.T1)."""
    return fact['value'].get('subject_kind') == 'group' and len(_places(fact)) > WIDE


WIDE = 3


def clusters(sets):
    """One cluster per place, holding every engine's evidence about it; a wide group finding is a cluster of its own."""
    evaluated = _evaluated(sets)
    filtered = _filter_registry_referenced_dead_code(_findings(sets), sets)
    by_place = {}
    for fact in filtered:
        if is_wide(fact):
            by_place.setdefault('group:' + fact['id'], []).append(fact)
            continue
        for place in _places(fact):
            by_place.setdefault(place, []).append(fact)
    built = []
    for place, facts in sorted(by_place.items()):
        kinds = {}
        for fact in facts:
            # A registry-referenced fact is by name still alive, so it does not contribute
            # to any finding-kind cluster: keep the fact on disk but skip the cluster slot.
            if (fact.get('value') or {}).get('referenced_by_registry'):
                continue
            kinds.setdefault(fact['value']['kind'], set()).add(fact['value']['engine'])
        corroboration = {kind: verdict(kind, engines, evaluated) for kind, engines in sorted(kinds.items())}
        if not corroboration:
            continue
        engines = sorted({fact['value']['engine'] for fact in facts
                          if not (fact.get('value') or {}).get('referenced_by_registry')})
        built.append({
            'id': 'CLU-' + sha1(place.encode('utf-8')).hexdigest()[:10],
            'place': place,
            'engines': engines,
            'kinds': sorted(kinds),
            'corroboration': corroboration,
            'fact_ids': sorted(fact['id'] for fact in facts
                               if not (fact.get('value') or {}).get('referenced_by_registry')),
            # A claim about one kind cites only the evidence of that kind, so its files are where that evidence lies.
            'fact_ids_by_kind': {kind: sorted(fact['id'] for fact in facts if fact['value']['kind'] == kind
                                              and not (fact.get('value') or {}).get('referenced_by_registry'))
                                 for kind in sorted(kinds)},
            'scope': 'group' if place.startswith('group:') else 'place',
            'findings': len([f for f in facts if not (f.get('value') or {}).get('referenced_by_registry')]),
            'weight': round(sum(2.0 if detail['verdict'] == CORROBORATED else
                                0.5 if detail['verdict'] in (CONTESTED, GRANULARITY_GAP) else 1.0
                                for detail in corroboration.values()), 2),
            'measurements': sorted({(m['name'], m.get('unit')) for fact in facts
                                    for m in fact['value'].get('measurements', []) if m.get('name')}),
        })
    built.sort(key=lambda cluster: (-cluster['weight'], -cluster['findings'], cluster['place']))
    return built


def summary(sets):
    built = clusters(sets)
    verdicts = {}
    for cluster in built:
        for kind, detail in cluster['corroboration'].items():
            verdicts.setdefault(detail['verdict'], set()).add((cluster['place'], kind))
    return {'clusters': len(built),
            'places_with_more_than_one_engine': sum(1 for c in built if len(c['engines']) > 1),
            'by_verdict': {name: len(items) for name, items in sorted(verdicts.items())},
            'limits': 'A cluster is a verdict about one place, not the truth of the finding itself.'}

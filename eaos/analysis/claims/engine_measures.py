"""What a corroborated engine finding measured (eaos/analysis/claims/ledger.py from_engines): the impact key and the numbers
of its claim, so the report reads the same measurement the claim carries.
"""
import re


def _extract_measurement(fact, name):
    for m in fact.get('value', {}).get('measurements', []) or []:
        if m.get('name') == name:
            return m
    return None


def _number(value):
    return int(value) if isinstance(value, float) and value.is_integer() else value


def _complexity(facts):
    # reforge names it function.complexity and declares a threshold; an engine may name it complexity
    # without one. A measurement that carries its threshold is preferred over one that does not.
    found = [m for fact in facts for name in ('function.complexity', 'cyclomatic_complexity', 'cognitive_complexity', 'complexity')
             for m in [_extract_measurement(fact, name)] if m is not None and m.get('value') is not None]
    found.sort(key=lambda m: m.get('threshold') is None)
    if not found: return None
    if found[0].get('threshold') is not None:
        return 'engine_cluster_complexity', {'value': _number(found[0]['value']), 'threshold': _number(found[0]['threshold'])}
    return 'engine_cluster_complexity_value', {'value': _number(found[0]['value'])}


def _literal_duplication(facts):
    # reforge reports the occurrence count as group.size; its sites list also carries file-level
    # entries, so counting sites overstates it. jscpd reports one site per copy.
    sizes = [m['value'] for fact in facts for m in [_extract_measurement(fact, 'group.size')]
             if m is not None and m.get('value') is not None]
    counts = sizes or [len((fact.get('value') or {}).get('sites') or []) for fact in facts]
    return ('engine_cluster_literal_duplication', {'sites': _number(max(counts))}) if any(counts) else None


def _coupling_parts(message):
    return [label + ' ' + found.group(1) for label in ('fan-in', 'fan-out')
            for found in [re.search(label + r'\s+(\d+)', message)] if found]


def _coupling(facts):
    for parts in (_coupling_parts((fact.get('value') or {}).get('message') or '') for fact in facts):
        if parts: return 'engine_cluster_coupling', {'measure': ', '.join(parts)}
    return None


def _dead_symbol(fact):
    """The dead symbol a finding names: its location's symbol, the one its message names, else its first site's path."""
    location, value = fact.get('location') or {}, fact.get('value') or {}
    symbol = location.get('symbol')
    if symbol and symbol != location.get('path'): return symbol
    found = re.search(r'(?:function|method|class)\s+([\w./]+)', value.get('message') or '')
    if found: return found.group(1)
    sites = value.get('sites') or []
    return sites[0]['path'] if sites and sites[0].get('path') else None


def _dead_code_measure(facts):
    for symbol in map(_dead_symbol, facts):
        if symbol: return 'engine_cluster_dead_code', {'symbol': symbol}
    return None


MEASURES = {'complexity': _complexity, 'literal_duplication': _literal_duplication, 'coupling': _coupling,
            'dead_code': _dead_code_measure}


def engine_measurement(kind, cluster, fact_sets):
    """Return ``(impact_key, params)`` naming the measurement a corroborated finding was earned by.

    The key selects a template in ``compose.labels.IMPACTS`` for every language, so the report reads
    the same measurement the claim carries. With no measurement the key says so rather than guessing.
    """
    by_id = {fact['id']: fact for fact in (fact_sets.get('external') or {}).get('facts', [])}
    facts = [by_id.get(fid) for fid in cluster.get('fact_ids', [])]
    facts = [fact for fact in facts if fact and (fact.get('value') or {}).get('kind') == kind]
    measure = MEASURES.get(kind)
    return (measure(facts) if measure else None) or ('engine_cluster_unmeasured', {})

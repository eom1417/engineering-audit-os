"""The technical-debt register: every live claim, and every committed credential, as one item with its witnesses.

An item says what the debt is (category), how bad (severity), who saw it (witnesses), where it is (files),
how hot that place is (hotspot), what it costs to leave (impact) and what to do (recommendation).

Severity comes from the evidence, never from a wish to look calm. High or critical needs either one
deterministic witness (a lookup that admits no reading: a committed key, an IBAN or national id whose check
digit holds, a locked version the advisory database lists, a name that is not defined, a table without row-level
security) or two witnesses from different tools. Without either, the item is written at medium and `probe_needed`
says a probe must decide.

hotspot, for the item's hottest file, from measurements.json:
    score = pct(complexity_max) x pct(churn) x (1 + pct(fan_in))
where pct is the file's percentile rank (0..1) among the analysed files. The item keeps the three ranks,
not only the product, so a reader sees why a place is hot.
"""
from pathlib import Path

from ...core import progress
from ...core.contracts.card_kinds import card_kind
from ...core.system.files import read_json

FORMULA = 'score = pct(complexity_max) x pct(churn) x (1 + pct(fan_in)), percentile ranks among the analysed files'
SEVERITIES = ('low', 'medium', 'high', 'critical')
DETERMINISTIC_FACTS = ('committed_credential', 'broken_code')
# render key (or engine kind) -> (category, severity when the evidence says nothing more precise)
KEYS = {
    'vulnerable_dependency': ('supply_chain', None), 'security_weakness': ('security', None), 'broken_code': ('reliability', None),
    'dead_code': ('dead_code', 'low'), 'dead_code_review': ('dead_code', 'low'), 'leftover': ('dead_code', 'low'),
    'load_blocker': ('reliability', 'medium'), 'trace_gap': ('reliability', 'low'), 'mutable_global': ('reliability', 'medium'),
    'cycle': ('architecture', 'medium'), 'cochange': ('architecture', 'low'), 'hotspot': ('maintainability', 'medium'),
    'large_module': ('maintainability', 'medium'),
    'duplicated_rule': ('maintainability', 'medium'), 'redundant_work': ('reliability', 'medium'),
    'policy': ('architecture', 'medium'), 'untested': ('reliability', 'medium'),
}
# The debt category of each boundary of the layers (M6).
LAYER_CATEGORY = {'browser': 'security', 'endpoints': 'security', 'data': 'security', 'rules': 'architecture',
                  'layers': 'architecture', 'operations': 'reliability', 'tests': 'reliability'}
ENGINE_KINDS = {
    'secret': ('security', 'high'), 'vulnerability': ('security', 'high'), 'misconfiguration': ('security', 'medium'),
    'dataflow': ('reliability', 'medium'), 'cycle': ('architecture', 'medium'), 'coupling': ('architecture', 'medium'),
    'boundary': ('architecture', 'medium'), 'complexity': ('maintainability', 'medium'), 'duplication': ('maintainability', 'low'),
    'literal_duplication': ('maintainability', 'low'), 'dead_code': ('dead_code', 'low'), 'surface': ('security', 'medium'),
    'sql_quality': ('data', 'low'), 'api_contract': ('architecture', 'medium'), 'naming': ('maintainability', 'low'),
    'test_quality': ('reliability', 'low'), 'unused_dependency': ('supply_chain', 'low'),
}
RECOMMENDATIONS = {
    'security': 'Close the exposure first: rotate or move the secret, or add the missing policy, then add a check that keeps it closed.',
    'supply_chain': 'Upgrade to the fixed version in the manifest, regenerate the lockfile, run the tests.',
    'reliability': 'Handle the failing path explicitly and pin it with a test that exercises it.',
    'architecture': 'Break the dependency: move the shared part to its own module that both sides import.',
    'maintainability': 'Keep one definition and make the others use it; measure again after the change.',
    'data': 'Change the schema or query in a new migration; never edit an applied one.',
    'dead_code': 'Delete it in one commit; the audit shows nothing reaches it.',
}
CREDENTIAL_SEVERITY = {'public': 'low', 'test': 'low'}
# Personal values whose check digits were verified (an IBAN, a Saudi national id, a card number): a lookup, not a guess.
CHECKED_VALUES = ('IBAN_CODE', 'SA_NATIONAL_ID', 'CREDIT_CARD')


def percentiles(rows, field):
    """{path: rank in 0..1} among the rows that have the field; ties share their lowest rank."""
    values = sorted(r[field] for r in rows if r.get(field) is not None)
    if not values: return {}
    rank = {}
    for index, value in enumerate(values): rank.setdefault(value, index / max(len(values) - 1, 1))
    return {r['path']: rank[r[field]] for r in rows if r.get(field) is not None}


def hotspots(measurements):
    rows = (measurements or {}).get('files') or []
    complexity, churn, fan_in = (percentiles(rows, f) for f in ('complexity_max', 'churn', 'fan_in'))
    out = {}
    for row in rows:
        path = row['path']
        if path in complexity and path in churn:
            ranks = {'complexity_pct': round(complexity[path], 3), 'churn_pct': round(churn[path], 3),
                     'fan_in_pct': round(fan_in.get(path, 0.0), 3)}
            out[path] = {'file': path, **ranks,
                         'score': round(ranks['complexity_pct'] * ranks['churn_pct'] * (1 + ranks['fan_in_pct']), 4)}
    return out


def witness(fact):
    """(tool, kind) of the fact a claim rests on."""
    value = fact.get('value') or {}
    if fact.get('kind') in ('engine_finding', 'symbol_metric_external'):    # a finding, or a record (a value Presidio found, M12)
        checked = value.get('method') == 'deterministic' or value.get('entity') in CHECKED_VALUES
        return value.get('engine') or 'engine', 'deterministic' if checked else 'heuristic'
    if fact.get('kind') in DETERMINISTIC_FACTS: return f"eaos.{fact.get('extractor', fact['kind'])}", 'deterministic'
    if fact.get('kind') == 'data_table' and value.get('rls_enabled') is False: return 'eaos.domain', 'deterministic'
    return f"eaos.{fact.get('extractor', fact.get('kind'))}", 'heuristic'


def _paths(fact):
    location, value = fact.get('location') or {}, fact.get('value') or {}
    return [location.get('path')] + [site.get('path') for site in value.get('sites') or []]


def _files(facts):
    # A dict keeps the first-seen order and answers "seen already" without scanning a list.
    found = {path: None for fact in facts for path in _paths(fact) if path and not path.endswith('.cdx.json')}
    return list(found)


def _witnesses_same(fact, category, paths, packages):
    """True when another tool's finding reports this item's thing at this item's place."""
    value = fact.get('value') or {}
    if category == 'security':
        return value.get('kind') == 'secret' and (fact.get('location') or {}).get('path') in paths
    if category != 'supply_chain' or value.get('kind') != 'vulnerability' or value.get('engine') == 'osv-scanner':
        return False
    return _names_a_package(value, packages)


def _names_a_package(value, packages):
    """Whether a finding's message names one of the packages."""
    message = (value.get('message') or '') + ' '
    return any(package and package + ' ' in message for package in packages)


def _packages(facts):
    """The packages of the vulnerability findings among the facts."""
    return {str((f.get('location') or {}).get('symbol', '')).split(':', 1)[-1].rsplit('@', 1)[0]
            for f in facts if (f.get('value') or {}).get('kind') == 'vulnerability'}


def _second_witnesses(facts, all_facts, category):
    """Other tools reporting the same thing at the same place: a scanner's secret on a committed key's file,
    a scanner's vulnerability on the same package."""
    paths, packages = {(f.get('location') or {}).get('path') for f in facts}, _packages(facts)
    return [fact for fact in all_facts.values()
            if fact.get('kind') == 'engine_finding' and fact not in facts and _witnesses_same(fact, category, paths, packages)]


def _severity(claim, key, default, facts):
    # Archived code does not run: whatever it breaks is a leftover to remove, not a product defect.
    if claim.get('origin') == 'archive' and key != 'vulnerable_dependency': return 'low'
    if key in ('vulnerable_dependency', 'security_weakness'): return _stated_severity(claim)
    if key == 'broken_code': return 'high' if claim.get('claim_type') == 'risk' else 'medium'
    if key == 'engine_cluster': return _cluster_severity(claim)
    return default or 'medium'


def _stated_severity(claim):
    """The severity the finding states itself (an advisory's, a scanner's), else medium."""
    return ((claim.get('render') or {}).get('params') or {}).get('severity') or 'medium'


def _cluster_severity(claim):
    """An engine cluster's severity, by its kind of finding."""
    kind = ((claim.get('probe_spec') or {}).get('specification') or {}).get('kind')
    return ENGINE_KINDS.get(kind, ('maintainability', 'medium'))[1]


def _witness_rows(evidence):
    return [{'tool': tool, 'finding_id': fact['id'], 'kind': kind} for fact in evidence for tool, kind in [witness(fact)]]


def _category(key, kind, facts):
    """(category, the facts that witness the item)."""
    if key != 'engine_cluster': return KEYS.get(key, ('maintainability', 'medium'))[0], facts
    # A cluster holds every finding at its place; only the ones of its own kind witness this item.
    return (ENGINE_KINDS.get(kind, ('maintainability', 'medium'))[0],
            [f for f in facts if (f.get('value') or {}).get('kind') == kind] or facts)


def _credentials_at(evidence, all_facts):
    """The committed credentials on the files of a scanner's secret cluster."""
    places = set(_files(evidence))
    return [f for f in all_facts.values() if f.get('kind') == 'committed_credential' and (f.get('location') or {}).get('path') in places]


def _with_credentials(evidence, all_facts, severity):
    """(evidence, severity) of a scanner's secret cluster with the committed credentials on its files: the key family
    decides, not the scanner's pattern (EAOS reads what kind of key it is)."""
    credentials = _credentials_at(evidence, all_facts)
    families = [(f.get('value') or {}).get('severity') for f in credentials]
    if families: severity = 'low' if all(CREDENTIAL_SEVERITY.get(x) == 'low' for x in families) else 'critical'
    return evidence + credentials, severity


def _layered(render, category, severity):
    """(category, severity): a layer finding's own, its boundary's category and its rule's severity
    (eaos/analysis/layers/catalog.py); any other item's as they were."""
    key, params = render.get('key'), render.get('params') or {}
    if key == 'repository_finding': return 'maintainability', 'low'      # never raises the risk grade (M7.8)
    if card_kind(key).debt_category: return card_kind(key).debt_category, params.get('severity') or 'medium'
    if key in ('logic_flaw', 'experience_difficulty', 'real_data'): return params.get('category') or 'reliability', params.get('severity') or 'medium'
    if key != 'layer_finding': return category, severity
    return LAYER_CATEGORY.get(params.get('boundary'), 'architecture'), params.get('severity') or 'medium'


def _probe_witnesses(probes):
    return [{'tool': 'eaos.probe', 'finding_id': probe['id'], 'kind': 'probe'} for probe in probes if probe.get('status') == 'CONFIRMED']


def _item(claim, facts, all_facts, probes):
    render = claim.get('render') or {}
    specification = (claim.get('probe_spec') or {}).get('specification') or {}
    key = render.get('key') or ('cycle' if specification.get('query') == 'cycle_present' else None)
    kind = specification.get('kind')
    category, facts = _category(key, kind, facts)
    severity = _severity(claim, key, KEYS.get(key, (None, None))[1], facts)
    category, severity = _layered(render, category, severity)
    evidence = facts + _second_witnesses(facts, all_facts, category)
    if key == 'engine_cluster' and kind == 'secret': evidence, severity = _with_credentials(evidence, all_facts, severity)
    witnesses = _witness_rows(evidence) + _probe_witnesses(probes.get(claim['id'], []))
    return {'title': claim['statement'], 'category': category, 'severity': severity, 'witnesses': witnesses,
            'files': _files(evidence), 'impact': (claim.get('impact') or {}).get('scenario') or claim.get('falsifier', ''),
            'recommendation': RECOMMENDATIONS[category], 'claim_id': claim['id'], 'priority': claim.get('priority')}


def corroborated(item):
    """High or critical rests on a deterministic witness or on two different tools."""
    return (any(w['kind'] == 'deterministic' for w in item['witnesses'])
            or len({w['tool'] for w in item['witnesses'] if w['kind'] != 'probe'}) >= 2)


def _probes(out):
    probes = {}
    for probe in read_json(out / 'probes.json', []) or []:
        if isinstance(probe, dict): probes.setdefault(probe.get('claim_id'), []).append(probe)
    return probes


def _claim_items(claims, all_facts, probes):
    items = []
    for done, claim in enumerate(claims):
        progress.count('debt items', done, len(claims))
        if claim.get('status') in ('refuted', 'superseded') or claim.get('confidence') == 'REFUTED': continue
        facts = [all_facts[i] for i in claim.get('fact_ids') or [] if i in all_facts]
        items.append(_item(claim, facts, all_facts, probes))
    progress.count('debt items', len(claims), len(claims))
    return items


def _credential_item(fact, all_facts):
    value = fact.get('value') or {}
    severity = CREDENTIAL_SEVERITY.get(value.get('severity'), 'critical')
    evidence = [fact] + _second_witnesses([fact], all_facts, 'security')
    return {'title': f"A {value.get('severity', 'secret')} credential ({value.get('key_family', 'key')}) is committed "
                     f"in {fact['location']['path']}",
            'category': 'security', 'severity': severity,
            'witnesses': _witness_rows(evidence),
            'files': _files(evidence),
            'impact': 'Anyone with the repository has the key; it stays valid until it is rotated.'
                      if severity != 'low' else 'A publishable key is meant to be public; its safety rests on row-level security.',
            'recommendation': RECOMMENDATIONS['security'], 'claim_id': None}


def _settle(item, heat):
    """An uncorroborated high or critical drops to medium; the item takes its hottest file."""
    if item['severity'] in ('high', 'critical') and not corroborated(item):
        item['severity'], item['probe_needed'] = 'medium', f"{item['severity']} on a single heuristic witness: a probe must decide"
    item['hotspot'] = max((heat[path] for path in item['files'] if path in heat), key=lambda h: h['score'], default=None)


def _facts(out, claims):
    """{id: fact}: the claims' facts and every engine finding and committed credential (the witnesses), read from
    the sets that hold them only."""
    from ...facts.store import by_id, facts
    witnesses = {row['id']: row for row in facts(out, 'engine_finding', 'committed_credential') if row.get('id')}
    return {**by_id(out, {i for claim in claims for i in claim.get('fact_ids') or []}), **witnesses}


def _unclaimed_credentials(claims, items, all_facts):
    """The committed credentials no claim or item holds: each is an item of its own."""
    # A credential already witnessing an item (the scanners' secret cluster on its file) is that item, not a second one.
    claimed = {i for claim in claims for i in claim.get('fact_ids') or []}
    claimed |= {w['finding_id'] for item in items for w in item['witnesses']}
    return [fact for fact in all_facts.values() if fact.get('kind') == 'committed_credential' and fact['id'] not in claimed]


def build(out, dossier):
    out = Path(out)
    claims = dossier.get('claims') or []
    all_facts = _facts(out, claims)
    heat = hotspots(read_json(out / 'measurements.json', {}))
    items = _claim_items(claims, all_facts, _probes(out))
    items += [_credential_item(fact, all_facts) for fact in _unclaimed_credentials(claims, items, all_facts)]
    for item in items: _settle(item, heat)
    # Severity first; within a level, the claim's declared priority (reach x confidence x origin / cost, which
    # ranks product code above fixtures), then how hot the place is.
    items.sort(key=lambda i: (-SEVERITIES.index(i['severity']), -(i.get('priority') or 0),
                              -((i['hotspot'] or {}).get('score') or 0), i['title']))
    for index, item in enumerate(items, 1): item['id'] = f'DEBT-{index:03d}'
    return {'schema_version': 1, 'formula': FORMULA, 'items': [{'id': i.pop('id'), **i} for i in items]}

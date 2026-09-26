"""The technical-debt register: every live claim, and every committed credential, as one item with its witnesses.

An item says what the debt is (category), how bad (severity), who saw it (witnesses), where it is (files),
how hot that place is (hotspot), what it costs to leave (impact) and what to do (recommendation).

Severity comes from the evidence, never from a wish to look calm. High or critical needs either one
deterministic witness (a lookup that admits no reading: a committed key, a locked version the advisory
database lists, a name that is not defined, a table without row-level security) or two witnesses from
different tools. Without either, the item is written at medium and `probe_needed` says a probe must decide.

hotspot, for the item's hottest file, from measurements.json:
    score = pct(complexity_max) x pct(churn) x (1 + pct(fan_in))
where pct is the file's percentile rank (0..1) among the analysed files. The item keeps the three ranks,
not only the product, so a reader sees why a place is hot.

RISK-REGISTER.md is rendered from this record; there is one register.
"""
import json
from pathlib import Path

FORMULA = 'score = pct(complexity_max) x pct(churn) x (1 + pct(fan_in)), percentile ranks among the analysed files'
SEVERITIES = ('low', 'medium', 'high', 'critical')
DETERMINISTIC_FACTS = ('committed_credential', 'broken_code')
# render key (or engine kind) -> (category, severity when the evidence says nothing more precise)
KEYS = {
    'vulnerable_dependency': ('supply_chain', None), 'broken_code': ('reliability', None),
    'access_gap_no_rls': ('security', 'high'), 'access_gap_open_write': ('security', 'critical'),
    'dead_code': ('dead_code', 'low'), 'dead_code_review': ('dead_code', 'low'), 'leftover': ('dead_code', 'low'),
    'load_blocker': ('reliability', 'medium'), 'trace_gap': ('reliability', 'low'), 'mutable_global': ('reliability', 'medium'),
    'cycle': ('architecture', 'medium'), 'cochange': ('architecture', 'low'), 'hotspot': ('maintainability', 'medium'),
    'structural_duplicate': ('maintainability', 'low'), 'sequence_duplicate': ('maintainability', 'low'),
    'duplicated_rule': ('maintainability', 'medium'), 'redundant_work': ('reliability', 'medium'),
    'policy': ('architecture', 'medium'), 'untested': ('reliability', 'medium'),
}
ENGINE_KINDS = {
    'secret': ('security', 'high'), 'vulnerability': ('security', 'high'), 'misconfiguration': ('security', 'medium'),
    'dataflow': ('reliability', 'medium'), 'cycle': ('architecture', 'medium'), 'coupling': ('architecture', 'medium'),
    'boundary': ('architecture', 'medium'), 'complexity': ('maintainability', 'medium'), 'duplication': ('maintainability', 'low'),
    'literal_duplication': ('maintainability', 'low'), 'dead_code': ('dead_code', 'low'), 'surface': ('security', 'medium'),
    'sql_quality': ('data', 'low'), 'api_contract': ('architecture', 'medium'), 'naming': ('maintainability', 'low'),
    'test_quality': ('reliability', 'low'),
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


def _load(path, default):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def _facts(out):
    rows = {}
    for path in sorted((Path(out) / 'facts').glob('*.json')):
        for fact in (_load(path, {}) or {}).get('facts') or []:
            if isinstance(fact, dict) and fact.get('id'): rows[fact['id']] = fact
    return rows


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
    if fact.get('kind') == 'engine_finding':
        return value.get('engine') or 'engine', 'deterministic' if value.get('method') == 'deterministic' else 'heuristic'
    if fact.get('kind') in DETERMINISTIC_FACTS: return f"eaos.{fact.get('extractor', fact['kind'])}", 'deterministic'
    if fact.get('kind') == 'data_table' and value.get('rls_enabled') is False: return 'eaos.domain', 'deterministic'
    return f"eaos.{fact.get('extractor', fact.get('kind'))}", 'heuristic'


def _files(facts):
    found = []
    for fact in facts:
        location, value = fact.get('location') or {}, fact.get('value') or {}
        for path in [location.get('path')] + [site.get('path') for site in value.get('sites') or []]:
            if path and path not in found and not path.endswith('.cdx.json'): found.append(path)
    return found


def _second_witnesses(facts, all_facts, category):
    """Other tools reporting the same thing at the same place: a scanner's secret on a committed key's file,
    a scanner's vulnerability on the same package."""
    extra = []
    paths = {(f.get('location') or {}).get('path') for f in facts}
    packages = {str((f.get('location') or {}).get('symbol', '')).split(':', 1)[-1].rsplit('@', 1)[0]
                for f in facts if (f.get('value') or {}).get('kind') == 'vulnerability'}
    for fact in all_facts.values():
        value = fact.get('value') or {}
        if fact.get('kind') != 'engine_finding' or fact in facts: continue
        if category == 'security' and value.get('kind') == 'secret' and (fact.get('location') or {}).get('path') in paths:
            extra.append(fact)
        elif category == 'supply_chain' and value.get('kind') == 'vulnerability' and value.get('engine') != 'osv-scanner' \
                and any(package and package + ' ' in (value.get('message') or '') + ' ' for package in packages):
            extra.append(fact)
    return extra


def _severity(claim, key, default, facts):
    params = (claim.get('render') or {}).get('params') or {}
    if key == 'vulnerable_dependency': return params.get('severity') or 'medium'
    if key == 'broken_code': return 'high' if claim.get('claim_type') == 'risk' else 'medium'
    if key == 'engine_cluster':
        kind = ((claim.get('probe_spec') or {}).get('specification') or {}).get('kind')
        return ENGINE_KINDS.get(kind, ('maintainability', 'medium'))[1]
    return default or 'medium'


def _item(claim, facts, all_facts, probes):
    render = claim.get('render') or {}
    query = ((claim.get('probe_spec') or {}).get('specification') or {}).get('query')
    key = render.get('key') or ('cycle' if query == 'cycle_present' else None)
    kind = ((claim.get('probe_spec') or {}).get('specification') or {}).get('kind')
    if key == 'engine_cluster':
        category = ENGINE_KINDS.get(kind, ('maintainability', 'medium'))[0]
        # A cluster holds every finding at its place; only the ones of its own kind witness this item.
        facts = [f for f in facts if (f.get('value') or {}).get('kind') == kind] or facts
    else:
        category = KEYS.get(key, ('maintainability', 'medium'))[0]
    severity = _severity(claim, key, KEYS.get(key, (None, None))[1], facts)
    evidence = facts + _second_witnesses(facts, all_facts, category)
    if key == 'engine_cluster' and kind == 'secret':
        # The key family decides, not the scanner's pattern: EAOS reads what kind of key it is.
        places = {path for path in _files(evidence)}
        families = [(f.get('value') or {}).get('severity') for f in all_facts.values()
                    if f.get('kind') == 'committed_credential' and (f.get('location') or {}).get('path') in places]
        evidence += [f for f in all_facts.values() if f.get('kind') == 'committed_credential' and (f.get('location') or {}).get('path') in places]
        if families: severity = 'low' if all(CREDENTIAL_SEVERITY.get(x) == 'low' for x in families) else 'critical'
    witnesses = [{'tool': tool, 'finding_id': fact['id'], 'kind': kind} for fact in evidence for tool, kind in [witness(fact)]]
    witnesses += [{'tool': 'eaos.probe', 'finding_id': probe['id'], 'kind': 'probe'}
                  for probe in probes.get(claim['id'], []) if probe.get('status') == 'CONFIRMED']
    return {'title': claim['statement'], 'category': category, 'severity': severity, 'witnesses': witnesses,
            'files': _files(evidence), 'impact': (claim.get('impact') or {}).get('scenario') or claim.get('falsifier', ''),
            'recommendation': RECOMMENDATIONS[category], 'claim_id': claim['id'], 'priority': claim.get('priority')}


def corroborated(item):
    """High or critical rests on a deterministic witness or on two different tools."""
    return (any(w['kind'] == 'deterministic' for w in item['witnesses'])
            or len({w['tool'] for w in item['witnesses'] if w['kind'] != 'probe'}) >= 2)


def build(out, dossier):
    out = Path(out)
    all_facts = _facts(out)
    probes = {}
    for probe in _load(out / 'probes.json', []) or []:
        if isinstance(probe, dict): probes.setdefault(probe.get('claim_id'), []).append(probe)
    heat = hotspots(_load(out / 'measurements.json', {}))
    items = []
    for claim in dossier.get('claims') or []:
        if claim.get('status') in ('refuted', 'superseded') or claim.get('confidence') == 'REFUTED': continue
        facts = [all_facts[i] for i in claim.get('fact_ids') or [] if i in all_facts]
        items.append(_item(claim, facts, all_facts, probes))
    # A credential already witnessing an item (the scanners' secret cluster on its file) is that item, not a second one.
    claimed = {i for claim in dossier.get('claims') or [] for i in claim.get('fact_ids') or []}
    claimed |= {w['finding_id'] for item in items for w in item['witnesses']}
    for fact in all_facts.values():
        if fact.get('kind') != 'committed_credential' or fact['id'] in claimed: continue
        value = fact.get('value') or {}
        severity = CREDENTIAL_SEVERITY.get(value.get('severity'), 'critical')
        evidence = [fact] + _second_witnesses([fact], all_facts, 'security')
        items.append({'title': f"A {value.get('severity', 'secret')} credential ({value.get('key_family', 'key')}) is committed "
                               f"in {fact['location']['path']}",
                      'category': 'security', 'severity': severity,
                      'witnesses': [{'tool': tool, 'finding_id': f['id'], 'kind': kind} for f in evidence for tool, kind in [witness(f)]],
                      'files': _files(evidence),
                      'impact': 'Anyone with the repository has the key; it stays valid until it is rotated.'
                                if severity != 'low' else 'A publishable key is meant to be public; its safety rests on row-level security.',
                      'recommendation': RECOMMENDATIONS['security'], 'claim_id': None})
    for item in items:
        if item['severity'] in ('high', 'critical') and not corroborated(item):
            item['severity'], item['probe_needed'] = 'medium', f"{item['severity']} on a single heuristic witness: a probe must decide"
        hottest = max((heat[path] for path in item['files'] if path in heat), key=lambda h: h['score'], default=None)
        item['hotspot'] = hottest
    # Severity first; within a level, the claim's declared priority (reach x confidence x origin / cost, which
    # ranks product code above fixtures), then how hot the place is.
    items.sort(key=lambda i: (-SEVERITIES.index(i['severity']), -(i.get('priority') or 0),
                              -((i['hotspot'] or {}).get('score') or 0), i['title']))
    for index, item in enumerate(items, 1): item['id'] = f'DEBT-{index:03d}'
    return {'schema_version': 1, 'formula': FORMULA, 'items': [{'id': i.pop('id'), **i} for i in items]}


def render(record, language='ar', limit=30):
    from .compose import Document
    from .ranking import WEIGHTS
    ar = language == 'ar'
    document = Document('سجل الدَّين والمخاطر' if ar else 'Debt and risk register', language, budget_lines=200)
    counts = {s: sum(i['severity'] == s for i in record['items']) for s in reversed(SEVERITIES)}
    document.header([(f"{len(record['items'])} بندًا: " if ar else f"{len(record['items'])} items: ")
                     + ', '.join(f'{s} {n}' for s, n in counts.items()),
                     ('الخطورة العالية تحتاج شاهدًا حتميًا أو أداتين مستقلتين؛ ما سواها يُكتب متوسطًا حتى يقرر مجس.' if ar else
                      'High needs one deterministic witness or two independent tools; otherwise it is written as medium until a probe decides.'),
                     ('الأولوية داخل كل مستوى: ' if ar else 'Priority within a level: ') + WEIGHTS['formula'],
                     ('السخونة: ' if ar else 'Hotspot: ') + record['formula']])
    rows = [[item['id'], item['severity'], item['category'], str(item['title'])[:100],
             ', '.join(sorted({w['tool'] for w in item['witnesses']}))[:40],
             '—' if not item['hotspot'] else f"{item['hotspot']['score']} ({item['hotspot']['file']})"[:50]]
            for item in record['items']]
    document.table(['#', 'الخطورة' if ar else 'Severity', 'الفئة' if ar else 'Category', 'البند' if ar else 'Item',
                    'الشهود' if ar else 'Witnesses', 'السخونة' if ar else 'Hotspot'], rows, limit=limit)
    document.bullets([('السجل الكامل مع الملفات والتوصية لكل بند: debt-register.json' if ar
                       else 'The full register, with files and a recommendation per item: debt-register.json')])
    return document

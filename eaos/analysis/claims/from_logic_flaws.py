"""The claims the logic-flaw hunt earns (M9.2): one per flaw of the `logic_flaws` fact set (eaos/analysis/logic_flaws/),
read as a finding of the business rules' boundary, so the plan, the debt register and the fix read it as they read the
layers'. Found by an assistant, never by a rule: LIKELY when its second reading held it, a HYPOTHESIS when it was unsure;
the card triage rules on each before it reaches the plan."""


def logic_flaws(fact_sets, add, target):
    """One claim per logic flaw (eaos/analysis/claims/ledger.py BUILDERS)."""
    for fact in (fact_sets.get('logic_flaws') or {}).get('facts', []):
        value, where = fact['value'], fact['location']
        confidence = 'LIKELY' if value['verdict'] == 'holds' else 'HYPOTHESIS'
        add(value['title'], 'risk', confidence, ['model_inference'], f"Not reproduced by: {value['test']}",
            fact_ids=[fact['id']], confidence_ceiling=confidence,
            render={'key': 'layer_finding', 'params': {'rule': 'logic-flaw', 'boundary': 'rules', 'severity': value['severity'],
                                                       'en': value['title'], 'ar': value.get('title_ar') or value['title'],
                                                       'fix_en': value['fix'], 'fix_ar': value.get('fix_ar') or value['fix'],
                                                       'path': where['path'], 'line': where.get('start_line')}},
            probe_spec={'probe_type': 'graph_query',
                        'specification': {'query': 'logic_flaw_present', 'path': where['path'], 'title': value['title'],
                                          'expected': 'The last hunt still holds this flaw.'}},
            impact={'scenario': value['impact']})


def present(specification, sets):
    """The probe of a logic-flaw card: CONFIRMED while the last hunt still lists it at its place."""
    facts = (sets.get('logic_flaws') or {}).get('facts') or []
    if any(f['location']['path'] == specification['path'] and f['value']['title'] == specification['title'] for f in facts):
        return 'CONFIRMED', f"the last hunt still holds it at {specification['path']}"
    return 'REFUTED', f"the last hunt no longer finds it at {specification['path']}"

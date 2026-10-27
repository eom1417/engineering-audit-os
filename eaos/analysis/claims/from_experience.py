"""The claims the simulated users earn (M10.7): one per confirmed difficulty of the `experience` fact set
(eaos/analysis/experience/judging.py), its own card key `experience_difficulty` (eaos/core/language/words.py: its title,
why it matters, what would refute it), filed under reliability by the debt register, its fix its own, its steps to
reproduce in its scenario. Met twice and ruled on by an assistant, never proven by a
rule: LIKELY at most."""


def experience(fact_sets, add, target):
    """One claim per confirmed difficulty (eaos/analysis/claims/ledger.py BUILDERS)."""
    for fact in (fact_sets.get('experience') or {}).get('facts', []):
        if fact.get('kind') != 'experience_difficulty': continue
        value = fact['value']
        steps = ' '.join(f'{n}. {step}' for n, step in enumerate(value['repro'], 1))
        add(value['title'], 'risk', 'LIKELY', ['model_inference'],
            f"A fresh simulated user reaching {value['goal']} without meeting it, by these steps: {steps}",
            fact_ids=[fact['id']], confidence_ceiling='LIKELY',
            render={'key': 'experience_difficulty', 'params': {'kind': value['kind'], 'goal': value['goal'], 'severity': value['severity'],
                                                       'en': value['title'], 'ar': value.get('title_ar') or value['title'],
                                                       'fix_en': value['fix'], 'fix_ar': value.get('fix_ar') or value['fix'],
                                                       'path': fact['location']['path'], 'line': None}},
            probe_spec={'probe_type': 'graph_query',
                        'specification': {'query': 'experience_difficulty_present', 'goal': value['goal'], 'kind': value['kind'],
                                          'screen': value.get('screen'), 'expected': 'The last judging still confirms this difficulty.'}},
            impact={'scenario': f"{value['harmed']}. Steps to reproduce: {steps}"})


def present(specification, sets):
    """The probe of an experience card: CONFIRMED while the last judging still confirms it on the same goal and screen."""
    facts = (sets.get('experience') or {}).get('facts') or []
    key = (specification['goal'], specification['kind'], specification.get('screen'))
    if any((f['value']['goal'], f['value']['kind'], f['value'].get('screen')) == key for f in facts):
        return 'CONFIRMED', f"the last judging still confirms it on {specification['goal']}"
    return 'REFUTED', f"the last judging no longer confirms it on {specification['goal']}"

"""The claims the repository earns (M7.8, M7.9): one per finding of the `repository` fact set (eaos/facts/repository/), its
craft or its assistants' context. Low severity and read from the files alone: CONFIRMED, never a risk; the card triage
(eaos/ai/nodes/triage.py) still rules on each before it reaches the plan."""


def repository_findings(fact_sets, add, target):
    """One claim per repository finding (eaos/analysis/claims/ledger.py BUILDERS)."""
    for fact in (fact_sets.get('repository') or {}).get('facts', []):
        value = fact['value']
        add(value['en'], 'structure', 'CONFIRMED', ['static_fact'],
            'The files no longer showing it when the repository is read again.', fact_ids=[fact['id']], confidence_ceiling='CONFIRMED',
            render={'key': 'repository_finding', 'params': {k: value[k] for k in ('rule', 'severity', 'en', 'ar', 'fix_en', 'fix_ar', 'path')}},
            probe_spec={'probe_type': 'graph_query',
                        'specification': {'query': 'repository_finding_present', 'rule': value['rule'], 'path': value['path'],
                                          'expected': 'The repository still shows this finding.'}},
            impact={'scenario': value['fix_en']})


def present(specification, sets):
    """The probe of a repository card: CONFIRMED while the repository still shows the finding at its place."""
    facts = (sets.get('repository') or {}).get('facts') or []
    if any(f['value']['rule'] == specification['rule'] and f['value']['path'] == specification['path'] for f in facts):
        return 'CONFIRMED', f"{specification['rule']} still shown at {specification['path']}"
    return 'REFUTED', f"the repository no longer shows {specification['rule']} at {specification['path']}"

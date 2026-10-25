"""The claims the layers earn (M6): one per finding of the `boundaries` fact set (eaos/analysis/layers/), each naming the
boundary it breaks and the reference's fix, and the questions the layers could not decide.

A finding of a rule read from the code is CONFIRMED; one that reads the code's intent (whose row it is, whether a rule is
only in the browser) is LIKELY, for the assistant's triage to judge; a live finding carries the request that proved it.
A chain of files from browser code to server code that only dependency-cruiser followed (the layer rules it is given,
eaos/engines/dependency_cruiser.py) is a finding of its own.
"""
from .layers.catalog import fix, sentence

INTENT = {'unowned-row', 'unguarded-private-read', 'browser-only-rule', 'ui-calculation', 'untested-write'}
REACH = 'eaos-browser-reaches-server'


def _reached(fact_sets, known):
    """Browser-to-server chains only dependency-cruiser followed: (from, to, message)."""
    return [(f['location']['path'], f['value'].get('message', ''))
            for f in (fact_sets.get('external') or {}).get('facts', [])
            if f.get('kind') == 'engine_finding' and f['value'].get('rule') == REACH and f['location']['path'] not in known]


def _claim(fact, add):
    value = fact['value']
    confidence = 'LIKELY' if value['rule'] in INTENT and not value.get('live') else 'CONFIRMED'
    where = fact['location']
    add(value['en'], 'risk', confidence, ['runtime_probe' if value.get('live') else 'static_fact'],
        'The code, the migrations or the built output no longer showing it when the layers are read again.',
        fact_ids=[fact['id']], confidence_ceiling=confidence,
        render={'key': 'layer_finding', 'params': {'rule': value['rule'], 'boundary': value['boundary'], 'severity': value['severity'],
                                                   'en': value['en'], 'ar': value['ar'], 'fix_en': value['fix_en'],
                                                   'fix_ar': value['fix_ar'], 'path': where['path'], 'line': where.get('start_line')}},
        probe_spec={'probe_type': 'graph_query',
                    'specification': {'query': 'boundary_finding_present', 'rule': value['rule'], 'path': where['path'],
                                      'params': value['params'], 'expected': 'The layers still show this finding.'}},
        impact={'scenario': value['fix_en']})


def layer_findings(fact_sets, add, target):
    """One claim per layer finding (eaos/analysis/claims.py BUILDERS)."""
    facts = [f for f in (fact_sets.get('boundaries') or {}).get('facts', []) if f.get('kind') == 'boundary_finding']
    for fact in facts: _claim(fact, add)
    known = {f['location']['path'] for f in facts if f['value']['rule'] == 'server-module-in-browser'}
    for path, message in _reached(fact_sets, known):
        params = {'path': path, 'target': message.rsplit(' imports ', 1)[-1].split(',')[0] or 'server code'}
        add(sentence('server-module-in-browser', params), 'risk', 'LIKELY', ['external_engine'],
            'A resolved import chain from this browser file to server code no longer existing.',
            render={'key': 'layer_finding', 'params': {'rule': 'server-module-in-browser', 'boundary': 'browser', 'severity': 'high',
                                                       'en': sentence('server-module-in-browser', params),
                                                       'ar': sentence('server-module-in-browser', params, 'ar'),
                                                       'fix_en': fix('server-module-in-browser', params),
                                                       'fix_ar': fix('server-module-in-browser', params, 'ar'), 'path': path, 'line': None}},
            impact={'scenario': fix('server-module-in-browser', params)})


NAMED = ('route', 'method', 'name', 'table', 'field')


def _same(fact, specification):
    """Whether a finding is the one a card is about: its rule, its file and the values that name it."""
    value, wanted = fact['value'], {k: v for k, v in (specification.get('params') or {}).items() if k in NAMED}
    return (value['rule'] == specification['rule'] and fact['location']['path'] == specification['path']
            and all(value['params'].get(k) == v for k, v in wanted.items()))


def present(specification, sets):
    """The probe of a layer card: CONFIRMED while the layers still show the finding at its file."""
    facts = (sets.get('boundaries') or {}).get('facts') or []
    if any(_same(fact, specification) for fact in facts): return 'CONFIRMED', f"{specification['rule']} still shown at {specification['path']}"
    return 'REFUTED', f"the layers no longer show {specification['rule']} at {specification['path']}"

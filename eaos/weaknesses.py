"""Security findings in the project's own code, read as a few cards and never dropped.

Every engine that reads code for security (Semgrep's patterns, Bandit's syntax tree, CodeQL's data flow, Gitleaks'
and Trivy's secret scanners) reports weaknesses its own way, and a real one is often seen by only one of them. So:
- Two engines agree when they report a weakness of the same kind (a secret, or a vulnerability) in the same file
  within LINE_WINDOW lines of each other: the group is corroborated, a LIKELY card.
- A finding no other engine confirms still becomes a card, a HYPOTHESIS the assistant's triage decides on the code
  (eaos/studio/nodes/triage.py): confirmed, it is work; rejected, it leaves with the reason written.
- Few cards: findings group by file and weakness (its CWE, else its rule). A finding no other engine confirms that is
  low in severity, or whose rule its own engine calls low in confidence (an audit hint: "a command is run here, check
  its input"), groups by weakness across the whole project: one card listing every file, one judgement for all.
A weakness in test code is not a card: tests do not ship, so nothing reaches it from outside. A secret is, wherever it
is written: a real key in a test file leaks like any other. A vulnerable dependency is not here: it has its own card
(eaos/fact_claims.py), and its engines answer per package.
"""
from .vocabulary import classify
SECURITY = ('secret', 'vulnerability')
LINE_WINDOW = 2
SEVERITIES = ('low', 'medium', 'high', 'critical')
PROJECT = '*'


def _findings(sets):
    return [fact for fact in (sets.get('external') or {}).get('facts', [])
            if fact.get('kind') == 'engine_finding' and fact['value'].get('kind') in SECURITY
            and fact['value'].get('subject_kind') != 'package' and fact['location'].get('path')
            and (fact['value']['kind'] == 'secret' or classify(fact['location']['path']) != 'test')]


def _severity(fact):
    found = next((m.get('value') for m in fact['value'].get('measurements') or [] if m.get('name') == 'severity'), None)
    return found if found in SEVERITIES else 'medium'


def _label(fact):
    value = fact['value']
    return 'secret' if value['kind'] == 'secret' else (value.get('cwe') or [value['rule']])[0]


def _agree(one, other):
    a, b = one['location'], other['location']
    return (one['value']['engine'] != other['value']['engine'] and one['value']['kind'] == other['value']['kind']
            and a['path'] == b['path'] and isinstance(a.get('line'), int) and isinstance(b.get('line'), int)
            and abs(a['line'] - b['line']) <= LINE_WINDOW)


def groups(sets):
    """[{key, kind, place, labels, engines, agreed, severity, paths, fact_ids}], the most severe first."""
    facts = _findings(sets)
    parent = list(range(len(facts)))
    def root(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    agreed = set()
    for i, one in enumerate(facts):
        for j in range(i + 1, len(facts)):
            if _agree(one, facts[j]):
                parent[root(j)] = root(i)
                agreed |= {i, j}
    weak = {i for i, fact in enumerate(facts) if i not in agreed
            and (_severity(fact) == 'low' or fact['value'].get('engine_confidence') == 'low')}
    # A weak finding beside a sound one of the same weakness in the same file is that file's card, not the project's.
    sound = {(fact['location']['path'], _label(fact)) for i, fact in enumerate(facts) if i not in weak}
    first = {}
    for i, fact in enumerate(facts):
        key = (fact['location']['path'], _label(fact))
        if i in weak and key not in sound: key = (PROJECT, key[1])
        parent[root(i)] = root(first.setdefault(key, i))
    members = {}
    for i in range(len(facts)): members.setdefault(root(i), []).append(i)
    built = [_group([facts[i] for i in rows], any(i in agreed for i in rows)) for rows in members.values()]
    return sorted(built, key=lambda g: (-SEVERITIES.index(g['severity']), not g['agreed'], g['key']))


def _group(facts, agreed):
    paths = sorted({f['location']['path'] for f in facts})
    labels = sorted({_label(f) for f in facts})
    place = paths[0] if len(paths) == 1 else PROJECT
    return {'key': f"{place}|{'+'.join(labels)}", 'kind': facts[0]['value']['kind'], 'place': place, 'labels': labels,
            'engines': sorted({f['value']['engine'] for f in facts}), 'agreed': agreed,
            'severity': max((_severity(f) for f in facts), key=SEVERITIES.index), 'paths': paths,
            'rules': sorted({f['value']['rule'] for f in facts}), 'fact_ids': sorted(f['id'] for f in facts)}


def present(specification, sets):
    """The probe of a weakness card: CONFIRMED while an engine still reports its weakness at its files."""
    labels, paths = set(specification['labels']), set(specification['paths'])
    left = [f for f in _findings(sets) if _label(f) in labels and f['location']['path'] in paths]
    if left:
        return 'CONFIRMED', f"{len(left)} finding(s) of {', '.join(sorted(labels))} still reported at " + \
               ', '.join(sorted({f['location']['path'] for f in left})[:5])
    return 'REFUTED', f"no engine reports {', '.join(sorted(labels))} at these files any more"


def claims(fact_sets, add, target):
    """One claim per group (eaos/fact_claims.py BUILDERS): LIKELY when engines agree, else a HYPOTHESIS the triage decides.
    Its probe asking the engines again never raises it: one engine repeating itself is not corroboration."""
    for group in groups(fact_sets):
        confidence = 'LIKELY' if group['agreed'] else 'HYPOTHESIS'
        files = group['place'] if group['place'] != PROJECT else f"{len(group['paths'])} files"
        said = (f"{len(group['engines'])} engines ({', '.join(group['engines'])}) agree on" if group['agreed']
                else f"{group['engines'][0]} alone reports")
        add(f"{said} {group['kind']} {', '.join(group['labels'])} in {files}; {group['severity']} severity", 'risk', confidence,
            ['external_engine'],
            'Show from the code at each finding that no untrusted input reaches it, or that the secret is not a real '
            'credential (a test value, a documented example).',
            fact_ids=group['fact_ids'], confidence_ceiling=confidence,
            render={'key': 'security_weakness',
                    'params': {'place': files, 'kind': group['kind'], 'labels': ', '.join(group['labels']),
                               'engines': ', '.join(group['engines']), 'agreed': group['agreed'],
                               'severity': group['severity'], 'count': len(group['fact_ids'])}},
            probe_spec={'probe_type': 'graph_query',
                        'specification': {'query': 'weakness_present', 'labels': group['labels'], 'paths': group['paths'],
                                          'engines': group['engines'],
                                          'expected': 'An engine still reports this weakness at these files.'}})

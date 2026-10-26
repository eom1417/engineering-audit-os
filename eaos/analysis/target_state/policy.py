"""An architecture policy the project declares, and the build can fail on.

Layering is usually an opinion held in someone's head. Here the team writes it down, and every
resolved import edge is checked against it. A violation is a fact with a location, not a debate.
"""
from fnmatch import fnmatch
import json
from pathlib import Path
from ...facts import digest, make
from ...facts.store import read_set
from ...core.project.workspace import read, write

NAME = 'policy'
VERSION = '1'
FILENAME = 'eaos.policy.json'
LIMITATIONS = [
    'Only statically resolved imports are checked; dynamic wiring is invisible to this rule set.',
    'A layer is a set of path patterns, not a runtime boundary.',
    'An unmatched path belongs to no layer and is reported rather than silently allowed.',
]




def _validate(policy):
    """Raise ValueError at the first part of the policy its schema refuses."""
    if policy.get('schema_version') != 1: raise ValueError('Unsupported policy schema_version')
    if not isinstance(policy.get('layers'), dict) or not policy['layers']:
        raise ValueError('A policy needs at least one layer')
    analysis = policy.get('analysis')
    if analysis is not None and not isinstance(analysis, dict): raise ValueError('analysis must be an object')
    for rule in policy.get('rules', []):
        if not ({'deny', 'allow_only'} & set(rule)): raise ValueError('Each rule needs deny or allow_only')
        if not rule.get('reason'): raise ValueError('Each rule needs a reason; an unexplained rule cannot be argued with')


def load_policy(target, path=None):
    candidate = Path(path) if path else Path(target) / FILENAME
    if not candidate.is_file(): return None, str(candidate)
    policy = read(candidate)
    _validate(policy)
    return policy, str(candidate)


def layer_of(path, layers):
    for name, patterns in sorted(layers.items()):
        for pattern in patterns:
            if fnmatch(path, pattern): return name
    return None


def scaffold(target, sets):
    """A starting policy derived from the current structure, with today's edges allowed."""
    paths = sorted({fact['location']['path'] for fact in sets['graph']['facts'] if fact['kind'] == 'graph_node'})
    groups = {}
    for path in paths:
        parts = path.split('/')
        name = parts[0] if len(parts) > 1 else 'root'
        if len(parts) > 2 and parts[0] in {'src', 'lib', 'app', 'packages'}: name = parts[1]
        groups.setdefault(name, set()).add(('/'.join(parts[:-1]) or '.') + '/**')
    return {'schema_version': 1,
            'layers': {name: sorted(patterns) for name, patterns in sorted(groups.items())},
            'rules': [],
            'notes': 'Generated starting point: no rule is declared yet. Add deny or allow_only rules with a reason, '
                     'then run eaos policy check in CI.'}


def violations(policy, sets):
    layers = policy['layers']
    found = []
    unmatched = {f['location']['path'] for f in sets.get('graph', {}).get('facts', [])
                 if f['kind'] == 'graph_node' and layer_of(f['location']['path'], layers) is None}
    for edge in sets['resolve']['facts']: found += _edge_violations(edge, policy, layers, unmatched)
    return found, sorted(unmatched)


def _breaks(rule, source_layer, target_layer):
    """Whether an import from one layer to another breaks a deny or an allow_only rule."""
    deny = rule.get('deny')
    allow_only = rule.get('allow_only')
    if deny and deny.get('from') == source_layer and deny.get('to') == target_layer: return True
    if not (allow_only and allow_only.get('from') == source_layer): return False
    return target_layer not in (allow_only.get('to') or []) and target_layer != source_layer


def allowed(policy, source_layer, target_layer):
    """Whether the policy's rules let one layer use another."""
    return not any(_breaks(rule, source_layer, target_layer) for rule in policy.get('rules', []))


def _edge_violations(edge, policy, layers, unmatched):
    """The rules one resolved import breaks; a path in no layer is noted in `unmatched` instead."""
    if edge['resolution'] != 'RESOLVED': return []
    source_path, target_path = edge['location']['path'], edge['value'].get('to_path')
    if not target_path: return []
    source_layer, target_layer = layer_of(source_path, layers), layer_of(target_path, layers)
    if source_layer is None: unmatched.add(source_path)
    if target_layer is None: unmatched.add(target_path)
    if source_layer is None or target_layer is None: return []
    return [{'from_path': source_path, 'to_path': target_path,
             'from_layer': source_layer, 'to_layer': target_layer,
             'reason': rule['reason'], 'line': edge['location'].get('start_line'),
             'module': edge['value']['module'], 'edge_fact_id': edge['id']}
            for rule in policy.get('rules', []) if _breaks(rule, source_layer, target_layer)]


def run(target, out, policy_path=None, **options):
    sets = {name: read_set(out, name) for name in ['resolve', 'graph'] if (Path(out) / 'facts' / (name + '.json')).is_file()}
    if 'resolve' not in sets or 'graph' not in sets:
        raise ValueError('Collect facts before checking policy: eaos facts or eaos dossier')
    policy, location = load_policy(target, policy_path)
    if policy is None:
        return {'facts': [], 'summary': {'declared': False, 'expected_at': location,
                                         'interpretation': 'No policy is declared, so no layering rule is enforced. '
                                                           'Create one with eaos policy init to turn the intended architecture into a checked contract.'},
                'available': False, 'input_sha': digest(b''), 'reason': 'No policy file at ' + location}
    found, unmatched = violations(policy, sets)
    facts = [make('policy_violation', NAME, VERSION, digest(json.dumps(policy, sort_keys=True).encode()),
                  {'path': row['from_path'], 'start_line': row['line']},
                  {'to_path': row['to_path'], 'from_layer': row['from_layer'], 'to_layer': row['to_layer'],
                   'module': row['module'], 'reason': row['reason'], 'edge_fact_id': row['edge_fact_id']}, limitations=LIMITATIONS)
             for row in sorted(found, key=lambda row: (row['from_path'], row['to_path']))]
    summary = {'declared': True, 'policy_file': location, 'layers': sorted(policy['layers']),
               'rules': len(policy.get('rules', [])), 'violations': len(facts),
               'paths_outside_every_layer': unmatched, 'unclassified_count': len(unmatched),
               'interpretation': 'Violations are resolved import edges that contradict a rule the project declared.'}
    return {'facts': facts, 'summary': summary, 'available': True,
            'input_sha': digest(json.dumps(policy, sort_keys=True).encode()), 'reason': None}


def check(target, out, policy_path=None):
    from ...facts.store import write_set
    target, out = Path(target).resolve(), Path(out).resolve()
    result = run(target, out, policy_path)
    write_set(out, NAME, NAME, VERSION, LIMITATIONS, result)
    summary = result['summary']
    return {'target': str(target), 'out': str(out), 'declared': summary.get('declared', False),
            'violations': summary.get('violations', 0), 'unclassified_count': summary.get('unclassified_count', 0),
            'record': str(out / 'facts' / 'policy.json'), 'status': _status(summary),
            'limits': 'Statically resolved imports only; a policy cannot see dynamic wiring.'}


def _status(summary):
    if summary.get('violations'): return 'VIOLATED'
    if summary.get('unclassified_count'): return 'INCOMPLETE'
    return 'OK' if summary.get('declared') else 'NO_POLICY'


def init(target, out, policy_path=None):
    target = Path(target).resolve()
    sets = {name: read_set(out, name) for name in ['graph'] if (Path(out) / 'facts' / (name + '.json')).is_file()}
    if 'graph' not in sets: raise ValueError('Collect facts before scaffolding a policy')
    destination = Path(policy_path) if policy_path else target / FILENAME
    if destination.exists(): raise ValueError('A policy already exists at ' + str(destination))
    write(destination, scaffold(target, sets))
    return {'created': str(destination), 'layers': sorted(read(destination)['layers']),
            'next': 'Add deny or allow_only rules with a reason, then run eaos policy check in CI.'}

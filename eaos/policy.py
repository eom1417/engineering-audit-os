"""An architecture policy the project declares, and the build can fail on.

Layering is usually an opinion held in someone's head. Here the team writes it down, and every
resolved import edge is checked against it. A violation is a fact with a location, not a debate.
"""
from fnmatch import fnmatch
import json
from pathlib import Path
from .facts import digest, make
from .facts.store import read_set
from .workspace import read, write

NAME = 'policy'
VERSION = '1'
FILENAME = 'eaos.policy.json'
LIMITATIONS = [
    'Only statically resolved imports are checked; dynamic wiring is invisible to this rule set.',
    'A layer is a set of path patterns, not a runtime boundary.',
    'An unmatched path belongs to no layer and is reported rather than silently allowed.',
]


from .facts.scope import declared_exclusions  # noqa: F401  (re-exported for callers)


def load_policy(target, path=None):
    candidate = Path(path) if path else Path(target) / FILENAME
    if not candidate.is_file(): return None, str(candidate)
    policy = read(candidate)
    if policy.get('schema_version') != 1: raise ValueError('Unsupported policy schema_version')
    if not isinstance(policy.get('layers'), dict) or not policy['layers']:
        raise ValueError('A policy needs at least one layer')
    analysis = policy.get('analysis')
    if analysis is not None and not isinstance(analysis, dict): raise ValueError('analysis must be an object')
    for rule in policy.get('rules', []):
        if not ({'deny', 'allow_only'} & set(rule)): raise ValueError('Each rule needs deny or allow_only')
        if not rule.get('reason'): raise ValueError('Each rule needs a reason; an unexplained rule cannot be argued with')
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
    found, unmatched = [], set()
    for edge in sets['resolve']['facts']:
        if edge['resolution'] != 'RESOLVED': continue
        source_path, target_path = edge['location']['path'], edge['value'].get('to_path')
        if not target_path: continue
        source_layer, target_layer = layer_of(source_path, layers), layer_of(target_path, layers)
        if source_layer is None: unmatched.add(source_path)
        if target_layer is None: unmatched.add(target_path)
        if source_layer is None or target_layer is None: continue
        for rule in policy.get('rules', []):
            deny = rule.get('deny')
            allow_only = rule.get('allow_only')
            broken = False
            if deny and deny.get('from') == source_layer and deny.get('to') == target_layer: broken = True
            if allow_only and allow_only.get('from') == source_layer:
                permitted = allow_only.get('to') or []
                if target_layer not in permitted and target_layer != source_layer: broken = True
            if broken:
                found.append({'from_path': source_path, 'to_path': target_path,
                              'from_layer': source_layer, 'to_layer': target_layer,
                              'reason': rule['reason'], 'line': edge['location'].get('start_line'),
                              'module': edge['value']['module']})
    return found, sorted(unmatched)


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
                   'module': row['module'], 'reason': row['reason']}, limitations=LIMITATIONS)
             for row in sorted(found, key=lambda row: (row['from_path'], row['to_path']))]
    summary = {'declared': True, 'policy_file': location, 'layers': sorted(policy['layers']),
               'rules': len(policy.get('rules', [])), 'violations': len(facts),
               'paths_outside_every_layer': unmatched[:30],
               'interpretation': 'Violations are resolved import edges that contradict a rule the project declared.'}
    return {'facts': facts, 'summary': summary, 'available': True,
            'input_sha': digest(json.dumps(policy, sort_keys=True).encode()), 'reason': None}


def check(target, out, policy_path=None, language='ar'):
    from .compose import Document
    from .facts.store import write_set
    target, out = Path(target).resolve(), Path(out).resolve()
    result = run(target, out, policy_path)
    write_set(out, NAME, NAME, VERSION, result['facts'], result['input_sha'], LIMITATIONS,
              result['summary'], result['available'], result['reason'])
    document = Document('السياسة المعمارية' if language == 'ar' else 'Architecture policy', language, budget_lines=160)
    summary = result['summary']
    if not summary.get('declared'):
        document.header([summary['interpretation']])
        document.text(f"expected at: {summary['expected_at']}")
    else:
        document.header([f"{summary['policy_file']} · layers {len(summary['layers'])} · rules {summary['rules']} · "
                         f"violations {summary['violations']}"])
        document.section('الطبقات المعلنة' if language == 'ar' else 'Declared layers')
        document.bullets(summary['layers'])
        document.section('المخالفات' if language == 'ar' else 'Violations')
        document.table(['من' if language == 'ar' else 'from', 'إلى' if language == 'ar' else 'to',
                        'السبب' if language == 'ar' else 'reason'],
                       [[f"{fact['location']['path']}:{fact['location'].get('start_line') or 1} [{fact['value']['from_layer']}]",
                         f"{fact['value']['to_path']} [{fact['value']['to_layer']}]", fact['value']['reason']]
                        for fact in result['facts']], limit=30)
        if summary['paths_outside_every_layer']:
            document.section('خارج كل طبقة' if language == 'ar' else 'Outside every layer')
            document.bullets(summary['paths_outside_every_layer'][:15])
    (out / 'POLICY.md').write_text(document.render(), encoding='utf-8')
    return {'target': str(target), 'out': str(out), 'declared': summary.get('declared', False),
            'violations': summary.get('violations', 0), 'artifact': str(out / 'POLICY.md'),
            'status': 'VIOLATED' if summary.get('violations') else ('OK' if summary.get('declared') else 'NO_POLICY'),
            'limits': 'Statically resolved imports only; a policy cannot see dynamic wiring.'}


def init(target, out, policy_path=None):
    target = Path(target).resolve()
    sets = {name: read_set(out, name) for name in ['graph'] if (Path(out) / 'facts' / (name + '.json')).is_file()}
    if 'graph' not in sets: raise ValueError('Collect facts before scaffolding a policy')
    destination = Path(policy_path) if policy_path else target / FILENAME
    if destination.exists(): raise ValueError('A policy already exists at ' + str(destination))
    write(destination, scaffold(target, sets))
    return {'created': str(destination), 'layers': sorted(read(destination)['layers']),
            'next': 'Add deny or allow_only rules with a reason, then run eaos policy check in CI.'}

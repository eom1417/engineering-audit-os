"""Extend a checked project with a feature, a page or a part, planned against what the project already is
(docs/BUILD-FROM-PLAN.md, "Extend a project"). No new machine builds it: the plan is read as a build's is
(eaos/plan_source.py), the spec is the build's (eaos/blueprint.py SPEC) with what ties it to the project, and its cards
join the project's plan as one milestone that the usual batches build, through every gate of a fix (fix_start, fix_edit,
fix_finish in eaos/agent_tools.py: the tests, the app's own checks, the layers, copies, dead code and security).

  extend_start  the feature's plan, saved beside the report (extend/SOURCE.md), with the project as its check read it:
                its parts, its layers and their rules, the functions to reuse, and its look (DESIGN.md)
  extend_plan   the spec checked, then every file it names held to the project: in a layer of its policy (else in a
                folder the project has), reusing only functions it has and its rules let that layer use, and writing
                no function the project already has; then its cards in the plan, ready for a batch
  carry         a later check keeps the cards not built yet (the pipeline's cards stage)
"""
import json
from pathlib import Path

from . import blueprint, design, guided
from .ledger import key, walk
from .plan_source import read_plan
from .policy import allowed, layer_of, load_policy
from .workspace import read, write

FOLDER = 'extend'
SPEC = {**{k: v for k, v in blueprint.SPEC.items() if k not in ('look', 'stack_preferences')},
        'touches': ['the parts of the project it changes, by their names in `project.parts`'],
        'features': [{**blueprint.SPEC['features'][0],
                      'paths': ['the files it adds or changes, where the project keeps such code (`project.layers`)'],
                      'functions': ['the new functions or components it writes, by name'],
                      'reuses': ['module#name of each function of the project it calls instead of writing it again'],
                      'layers': {'a new file no layer of eaos.policy.json matches yet': 'the layer it joins (the card declares it there)'},
                      'tests': ['the test files that prove its acceptance']}]}
GENERIC = 3            # a function name in this many modules is a convention (main, render), not one home to reuse
SHOWN = 300            # the reusable functions listed, the most called first


def folder(report):
    return Path(report).parent / FOLDER


def extend_start(state, source=None, text=None):
    """The feature's plan and the project it joins, for the assistant to write the spec from."""
    report = guided.report_of(state)
    if not (report / 'plan.json').is_file(): raise LookupError('no check of this project yet: audit it first, then extend it')
    plan, pictures = read_plan(source, text)
    folder(report).mkdir(parents=True, exist_ok=True)
    (folder(report) / 'SOURCE.md').write_text(plan + '\n', encoding='utf-8')
    return {'saved': str(folder(report) / 'SOURCE.md'), 'plan_text': plan[:40000], 'more': len(plan) > 40000, 'pictures': pictures,
            'project': project(state, report), 'spec_format': SPEC,
            'what_now': 'Read the plan whole (and every picture), then the project as its check read it. Write the spec in '
                        'spec_format: the feature in the parts it touches, each file where the project keeps such code, '
                        'reusing its functions (`reuses`) rather than writing them again, each criterion a test; new screens '
                        'follow `project.look`. Ask the person only real choices, your recommendation first. Then call '
                        'extend_plan with the spec.'}


def project(state, report):
    """The project as its check read it: parts, layers and rules, functions to reuse, and its look."""
    target = _json(report / 'target-architecture.json')
    policy = load_policy(state['project'])[0]
    parts = [{'name': c['name'], 'responsibility': c.get('responsibility') or '', 'files': c.get('files'),
              'paths': (c.get('paths') or [])[:4]} for c in target.get('current_components') or [] if c.get('name')]
    functions = _functions(report)
    reusable = sorted((f for f in functions if _public(f)), key=lambda f: -len(f.get('callers') or []))[:SHOWN]
    return {'parts': parts[:80], 'layers': _layers(policy, target), 'look': design.target(report),
            'functions': [{'id': f['id'], 'signature': f.get('signature'), 'summary': f.get('summary')} for f in reusable],
            'more_functions': 'ask and impact answer about any other function' if len(functions) > SHOWN else None}


def _layers(policy, target):
    """The project's layers: those its policy declares, with the reasons of its rules, else the check's target."""
    if policy: return {'declared_by': 'eaos.policy.json', 'layers': policy['layers'], 'rules': [r['reason'] for r in policy.get('rules') or []]}
    return {'declared_by': "the check's target",
            'layers': [{k: c.get(k) for k in ('name', 'layer', 'responsibility')} for c in target.get('target_components') or []]}


def extend_plan(state, spec):
    """The spec checked against itself and against the project; when it holds, its cards in the project's plan."""
    report = guided.report_of(state)
    problems, questions = blueprint.validate_spec(spec, look=False)
    if not problems: problems = fit(spec, load_policy(state['project'])[0], _functions(report), _known(report))
    folder(report).mkdir(parents=True, exist_ok=True)
    write(folder(report) / 'spec.json', spec)
    if problems or questions:
        return {'status': 'spec_incomplete' if problems else 'questions', 'problems': problems, 'questions': questions,
                'what_now': 'Fix these in the spec and call extend_plan again.' if problems else
                            'Ask the person these questions (your recommendation first), put the answers in the spec, and call '
                            'extend_plan again.'}
    cards = add(report, spec, design.target(report) is not None)
    state['extend'] = {'name': spec['name'], 'cards': [c['id'] for c in cards]}
    guided.save(state)
    guided.publish(state)
    return {'status': 'planned', 'milestone': cards[0]['milestone'], 'cards': [{k: c[k] for k in ('id', 'title', 'paths')} for c in cards],
            'what_now': 'Tell the person simply what will be added and where, and ask their agreement to build it. Then build it as '
                        'any fix, through every gate: run_setup and safety_net when status asks, fix_start with cards='
                        + json.dumps([c['id'] for c in cards]) + ', fix_edit per card (its acceptance and tests in `finding`), '
                        'fix_finish; the person accepts. Then audit again (the check keeps the cards not built yet).'}


def fit(spec, policy, functions, known):
    """What in the spec does not fit the project: a file outside its layers (or its folders), a reuse of what it does
    not have or a layer may not use, a function written again that it already has."""
    homes = _homes(functions)
    return [problem for feature in spec.get('features') or [] for problem in _feature_fit(feature, policy, functions, (known, homes))]


def _feature_fit(feature, policy, functions, project):
    """What of one feature does not fit; `project`: (its folders, {function name: the modules that define it})."""
    known, homes = project
    where = f"feature {feature.get('id')}"
    paths = [_path(p) for p in feature.get('paths') or []]
    problems = [] if paths else [f'{where}: name the files it adds or changes (`paths`)']
    layers = {p: _layer(p, policy, feature.get('layers') or {}) for p in paths} if policy else {}
    problems += [_misplaced(where, path, policy) for path in paths
                 if (layers[path] is None if policy else str(Path(path).parent) not in known)]
    for ref in feature.get('reuses') or []:
        problems += _reuse_problems(where, ref, functions, policy, set(layers.values()) - {None})
    return problems + [f"{where}: {name} already exists ({', '.join(homes[name])}): reuse it (`reuses`) instead of writing it again"
                       for name in feature.get('functions') or [] if name in homes]


def _layer(path, policy, joins):
    """The policy layer of `path`: the one its patterns give, else the one the feature says it joins, when it is one."""
    return layer_of(path, policy['layers']) or (joins.get(path) if joins.get(path) in policy['layers'] else None)


def _misplaced(where, path, policy):
    if policy: return (f"{where}: {path} is in no layer of eaos.policy.json ({', '.join(sorted(policy['layers']))}): put it "
                       'where the project keeps such code, or name the layer it joins (`layers`)')
    return f'{where}: {path} is in no folder the project has: put it beside the code of its kind'


def _reuse_problems(where, ref, functions, policy, layers):
    found = next((f for f in functions if f['id'] == ref), None)
    if found is None: return [f'{where}: {ref} is not a function of the project (module#name, from `project.functions`)']
    used = layer_of(found['module'], policy['layers']) if policy else None
    if used and layers and not any(allowed(policy, layer, used) for layer in layers):
        return [f"{where}: {ref} is in the layer {used}, which {', '.join(sorted(layers))} may not use (eaos.policy.json)"]
    return []


def add(report, spec, looked):
    """The spec's features as build cards, one milestone of the project's plan; the cards, also kept in extend/cards.json."""
    plan = read(report / 'plan.json')
    number = 1 + sum(m['id'].startswith('X') for m in plan.get('milestones') or [])
    mid, taken = f'X{number:02d}', sum(t['id'].startswith('EXT-') for t in plan['tasks'])
    cards, previous = [], None
    for index, feature in enumerate(spec['features'], start=taken + 1):
        card = _card(f'EXT-{index:03d}', mid, spec['name'], feature, looked)
        card['prerequisites'] = [{'task_id': previous, 'why': 'built in the order of the plan'}] if previous else []
        cards.append(card)
        previous = card['id']
    milestone = {'id': mid, 'name': f"Extension: {spec['name']}", 'name_ar': f"توسعة: {spec['name']}", 'tasks': [c['id'] for c in cards],
                 'goal': spec.get('summary') or '', 'goal_ar': spec.get('summary') or '',
                 'exit': 'every card here passes the gates of a fix and its own tests'}
    plan['tasks'] += cards
    plan['milestones'] = (plan.get('milestones') or []) + [milestone]
    write(report / 'plan.json', plan)
    kept = _json(folder(report) / 'cards.json') or {'milestones': [], 'tasks': []}
    write(folder(report) / 'cards.json', {'milestones': kept['milestones'] + [milestone], 'tasks': kept['tasks'] + cards})
    return cards


def _card(card_id, mid, name, feature, looked):
    acceptance = list(feature.get('acceptance') or []) + (["every new screen follows the project's DESIGN.md"] if looked else [])
    acceptance += [f'{_path(path)} is declared in the layer {layer} of eaos.policy.json' for path, layer in (feature.get('layers') or {}).items()]
    reuses, tests = feature.get('reuses') or [], feature.get('tests') or []
    after = ('Accepted when: ' + '; '.join(acceptance) + (f". Tests: {', '.join(tests)}" if tests else '')
             + (f". Reuse, never write again: {', '.join(reuses)}" if reuses else ''))
    return {'id': card_id, 'kind': 'build', 'pattern': 'extend_feature', 'milestone': mid, 'title': f"{name}: {feature['name']}",
            'module': feature.get('module'), 'feature': feature.get('id'), 'paths': [_path(p) for p in feature['paths']] + (['eaos.policy.json'] if feature.get('layers') else []),
            'acceptance': acceptance, 'tests': tests, 'reuses': reuses, 'priority': 0, 'before': 'Not in the project yet.',
            'after': after, 'impact': feature.get('description') or '', 'decision': {'kind': 'build', 'readiness': 'ready'},
            'status': 'planned'}


def carry(target, out):
    """The extension cards a new check's plan lost and the project does not hold yet (no commit carries their key):
    back in plan.json, each in its milestone. The number of cards carried."""
    kept = _json(folder(out) / 'cards.json')
    if not kept: return 0
    plan = read(Path(out) / 'plan.json')
    built, have = walk(target, 'HEAD')[0], {t['id'] for t in plan['tasks']}
    cards = [c for c in kept['tasks'] if c['id'] not in have and key(c) not in built]
    if not cards: return 0
    ids = {c['id'] for c in cards}
    plan['tasks'] += cards
    plan['milestones'] = (plan.get('milestones') or []) + [{**m, 'tasks': [t for t in m['tasks'] if t in ids]}
                                                           for m in kept['milestones'] if ids & set(m['tasks'])]
    write(Path(out) / 'plan.json', plan)
    return len(cards)


def _path(path):
    path = str(path).strip()
    return path[2:] if path.startswith('./') else path


def _functions(report):
    return _json(Path(report) / 'studio' / 'functions.json').get('functions') or []


def _public(function):
    return function.get('kind') != 'method' and not str(function.get('name') or '_').startswith('_')


def _homes(functions):
    """{name: the modules that define it} of the project's public functions with one home (not a convention)."""
    homes = {}
    for f in filter(_public, functions): homes.setdefault(f['name'], []).append(f['module'])
    return {name: modules for name, modules in homes.items() if len(modules) < GENERIC}


def _known(report):
    """Every folder the check saw a file in, '.' for the top."""
    files = {m['id'] for m in _json(Path(report) / 'studio' / 'functions.json').get('modules') or [] if m.get('id')}
    files |= {p for c in _json(Path(report) / 'target-architecture.json').get('current_components') or [] for p in c.get('paths') or []}
    return {'.'} | {str(parent) for f in files for parent in Path(f).parents}


def _json(path):
    try: return read(path)
    except (OSError, ValueError): return {}

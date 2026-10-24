"""The product spec of a project built from its plan (docs/BUILD-FROM-PLAN.md; eaos/report/blueprint.py draws the
build from it): the example the assistant follows (SPEC), what makes a spec unbuildable and what the person should
decide (validate_spec), the person's answers (answer), the stacks catalogue and the standard cards a product needs."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'data'


def stacks():
    return json.loads((DATA / 'stacks.json').read_text(encoding='utf-8'))


SPEC = {
    'name': 'the product name',
    'summary': 'what it is and for whom, in two or three sentences',
    'users': [{'id': 'owner', 'name': 'who they are', 'needs': ['what they come to do']}],
    'modules': [{'id': 'orders', 'name': 'Orders', 'responsibility': 'one sentence: what this part alone is responsible for'}],
    'entities': [{'id': 'order', 'name': 'Order', 'module': 'orders',
                  'fields': [{'name': 'total', 'type': 'money | text | number | date | boolean | id | enum | json', 'required': True}]}],
    'features': [{'id': 'F1', 'name': 'Place an order', 'module': 'orders', 'priority': 'must | should | could',
                  'entities': ['order'], 'roles': ['customer'], 'description': 'what the user can do',
                  'acceptance': ['Given ..., when ..., then ... (each becomes a test)']}],
    'flows': [{'id': 'FL1', 'name': 'First order', 'actor': 'customer', 'features': ['F1'], 'steps': ['...']}],
    'roles': [{'id': 'customer', 'name': 'Customer', 'can': ['F1']}],
    'integrations': [{'id': 'payments', 'name': 'Stripe', 'purpose': 'take payments'}],
    'nonfunctional': {'expected_users': 1000, 'languages': ['ar', 'en'], 'data_sensitivity': 'personal | health | payment | none',
                      'platforms': ['web', 'mobile web']},
    'look': {'theme': 'the one theme: light or dark', 'colors': {'primary': '#0F766E', 'background': '#FFFFFF', 'text': '#111827'},
             'fonts': ['IBM Plex Sans Arabic'], 'components': ['button', 'input', 'table', 'card', 'message'],
             'design_md': 'the whole DESIGN.md (Google Stitch format), from the design brief\'s sources and standard',
             'screens': [{'id': 'S1', 'name': 'Orders', 'features': ['F1'], 'picture': 'the path of its picture in the plan, or empty'}]},
    'requirements': [{'id': 'the plan\'s own id (FR-12), else R1, R2...', 'text': 'one requirement of the plan, in its words',
                      'covered_by': ['what builds it: a feature id, a flow id, or a standard card (languages, privacy, offline, '
                                     'integration:<id>, security, errors, accessibility, speed, load, release)']}],
    'stack_preferences': {'database': 'an option id from the catalogue, or empty to take the recommendation'},
    'decisions': [{'id': 'D1', 'question': 'an open product question', 'options': ['A', 'B'], 'recommendation': 'A',
                   'why': 'the research behind it', 'chosen': 'A, once the person chose (empty until then)'}],
}


REQUIRED = {'requirements': 'list every requirement of the plan, with its own id and what builds it (covered_by)',
            'nonfunctional': 'say the languages, the data sensitivity, the platforms and the expected users'}


def validate_spec(spec, look=True):
    """(problems, questions): what makes the spec unbuildable, and what the person should decide. `look` false: the
    project's own look holds (a feature added to it, eaos/journeys/extend.py), so the spec draws none."""
    if not isinstance(spec, dict): return ['the spec must be one JSON object shaped like the example'], []
    problems = _empty_keys(spec, look)
    modules, entities, features, roles = set(_by_id(spec, 'modules')), _by_id(spec, 'entities'), _by_id(spec, 'features'), set(_by_id(spec, 'roles'))
    if not modules: problems.append('no module: group the features into parts, each with one responsibility')
    if not features: problems.append('no feature: list what a user can do')
    problems += (_module_problems(spec.get('modules') or [], features) + _entity_problems(entities, modules, features)
                 + _feature_problems(features, entities, modules, roles) + _flow_problems(spec.get('flows') or [], features)
                 + _look_problems(spec.get('look'), features, look) + _requirement_problems(spec, features))
    return problems, _spec_questions(spec)


def _empty_keys(spec, look):
    """The spec's name and summary when empty and, for a new product (`look`), every required key left empty."""
    problems = [f'`{key}` is empty' for key in ('name', 'summary') if not str(spec.get(key) or '').strip()]
    if look:            # a new product: nothing of its plan may be left out, and its facts choose the standard cards
        problems += [f'`{key}` is empty: {why}' for key, why in REQUIRED.items() if not spec.get(key)]
    return problems


def _by_id(spec, key):
    """The spec's `key` list as {id: item}, what is not an object dropped."""
    return {item.get('id'): item for item in spec.get(key) or [] if isinstance(item, dict)}


def _module_problems(modules, features):
    problems = []
    for module in modules:
        if not str(module.get('responsibility') or '').strip(): problems.append(f"module {module.get('id')}: its responsibility is empty")
        if not any(f.get('module') == module.get('id') for f in features.values()):
            problems.append(f"module {module.get('id')}: no feature belongs to it (merge it, or give it one)")
    return problems


def _entity_problems(entities, modules, features):
    problems = []
    for entity_id, entity in entities.items():
        if entity.get('module') not in modules:
            problems.append(f'entity {entity_id}: its owning module is not one of the modules (every piece of data has one owner)')
        if not entity.get('fields'): problems.append(f'entity {entity_id}: it has no fields')
        if not any(entity_id in (f.get('entities') or []) for f in features.values()):
            problems.append(f'entity {entity_id}: no feature uses it (remove it, or say which feature needs it)')
    return problems


def _feature_problems(features, entities, modules, roles):
    problems = []
    for feature_id, feature in features.items():
        if feature.get('module') not in modules: problems.append(f'feature {feature_id}: its module is not one of the modules')
        problems += _unknown_uses(feature_id, feature, entities, roles)
        if not [a for a in feature.get('acceptance') or [] if str(a).strip()]:
            problems.append(f'feature {feature_id}: no acceptance criterion (how do we know it works? each becomes a test)')
    return problems


def _unknown_uses(feature_id, feature, entities, roles):
    """A feature's entities that are not entities, and its roles that are not roles."""
    problems = []
    for entity_id in feature.get('entities') or []:
        if entity_id not in entities: problems.append(f'feature {feature_id}: uses {entity_id}, which is not an entity')
    for role in feature.get('roles') or []:
        if roles and role not in roles: problems.append(f'feature {feature_id}: role {role} is not one of the roles')
    return problems


def _flow_problems(flows, features):
    return [f"flow {flow.get('id')}: uses {feature_id}, which is not a feature"
            for flow in flows for feature_id in flow.get('features') or [] if feature_id not in features]


def _requirement_problems(spec, features):
    """Every requirement of the plan is built by something of the product: a feature, a flow or a standard card."""
    known = set(features) | set(_by_id(spec, 'flows')) | {key for _, _, key in _applicable(spec)}
    problems = []
    for row in spec.get('requirements') or []:
        if not isinstance(row, dict): continue
        by = [str(x) for x in row.get('covered_by') or []]
        if not by: problems.append(f"requirement {row.get('id')}: nothing builds it; name the feature, flow or standard card that does")
        problems += [f"requirement {row.get('id')}: {x} is not a feature, a flow or a standard card of this product" for x in by if x not in known]
    return problems


def _nonfunctional(spec):
    return spec.get('nonfunctional') if isinstance(spec.get('nonfunctional'), dict) else {}


STANDARD_WHEN = {
    'always': lambda nf: True,
    'languages': lambda nf: len(nf.get('languages') or []) > 1,
    'personal_data': lambda nf: str(nf.get('data_sensitivity') or '') in ('personal', 'health', 'payment'),
    'mobile': lambda nf: any('mobile' in str(p).lower() or 'phone' in str(p).lower() for p in nf.get('platforms') or []),
    'users': lambda nf: bool(nf.get('expected_users')),
}


def _applicable(spec):
    """(row, its spec entry or {}, its key) for each standard card this product needs, in the file's order."""
    nf = _nonfunctional(spec)
    for row in json.loads((DATA / 'product-standard.json').read_text(encoding='utf-8'))['rows']:
        if 'each' in row:
            for entry in [e for e in spec.get(row['each']) or [] if isinstance(e, dict) and e.get('id')]:
                yield row, entry, f"{row['id']}:{entry['id']}"
        elif STANDARD_WHEN[row['when']](nf):
            yield row, {}, row['id']


def _spec_questions(spec):
    """What the person should decide: a stack choice EAOS does not lay out, an open product decision, the journeys."""
    questions = _stack_questions(spec)
    for decision in spec.get('decisions') or []:
        if not str(decision.get('chosen') or '').strip():
            questions.append({'id': decision.get('id'), 'kind': 'choice', 'text': decision.get('question'),
                              'options': decision.get('options') or [], 'recommendation': decision.get('recommendation'),
                              'why': decision.get('why')})
    if not spec.get('flows') and not spec.get('no_flows'):
        questions.append({'id': 'flows', 'kind': 'yes_no', 'text': 'The plan names no user journey from start to finish. '
                          'May the assistant write the main ones from the features?', 'recommendation': 'yes'})
    return questions


def _stack_questions(spec):
    """A question for each technology the plan prefers that EAOS does not lay out, with the catalogue's options."""
    questions = []
    catalogue = stacks()['concerns']
    for concern, choice in (spec.get('stack_preferences') or {}).items():
        if concern in catalogue and choice and choice not in catalogue[concern]['options']:
            questions.append({'id': f'stack-{concern}', 'kind': 'choice', 'text': f"{catalogue[concern]['title']}: which one?",
                              'options': list(catalogue[concern]['options']), 'recommendation': catalogue[concern]['recommended'],
                              'why': f'{choice!r} is not one EAOS lays out yet'})
    return questions


def answer(spec, question, choice):
    """The spec with the person's choice for one of its questions (_spec_questions): a technology, a product decision's
    option, or whether the journeys are written (yes: one per role, through the features it can use)."""
    if question.startswith('stack-'):
        spec.setdefault('stack_preferences', {})[question[len('stack-'):]] = choice
    elif question == 'flows':
        if choice == 'yes': spec['flows'] = _role_flows(spec)
        spec['no_flows'] = not spec.get('flows')
    else:
        decision = next((d for d in spec.get('decisions') or [] if isinstance(d, dict) and d.get('id') == question), None)
        if decision is None: raise KeyError(question)
        decision['chosen'] = choice
    return spec


def _role_flows(spec):
    """A journey per role through the features it can use, in the plan's order; one over every feature when no role."""
    features = _by_id(spec, 'features')
    flows = []
    for role in _roles(spec, features):
        can = [f for f in role.get('can') or [] if f in features]
        if can: flows.append({'id': f'FL{len(flows) + 1}', 'name': f"{role.get('name') or role['id']}: main journey", 'actor': role['id'],
                              'features': can, 'steps': [features[f].get('name') or f for f in can]})
    return flows


def _roles(spec, features):
    """The spec's roles; one user who can use every feature when it names none."""
    return [r for r in spec.get('roles') or [] if isinstance(r, dict)] or [{'id': 'user', 'name': 'User', 'can': list(features)}]


def _look_problems(look, features, drawn=True):
    """What keeps the look from being built once: one theme, its colours and fonts, and every screen tied to features;
    nothing when the spec draws no look (`drawn` false)."""
    if not drawn: return []
    if not isinstance(look, dict) or not look.get('screens'):
        return ['`look` is empty: write the one theme, its colours, fonts and shared components, and the screens with their '
                'features (from the pictures when the plan has them)']
    problems = [f'`look.{key}` is empty' for key in ('theme', 'colors', 'fonts', 'design_md') if not look.get(key)]
    problems += [p for p in (_screen_problem(screen, features) for screen in look['screens']) if p]
    return problems


def _screen_problem(screen, features):
    """What keeps one screen from being built: no feature named, or names that are not features; None when none."""
    unknown = [f for f in screen.get('features') or [] if f not in features]
    if screen.get('features') and not unknown: return None
    return f"screen {screen.get('id')}: name the features it shows" + (f" ({', '.join(unknown)} are not features)" if unknown else '')

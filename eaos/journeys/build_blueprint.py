"""The blueprint of a project built from its plan (docs/BUILD-FROM-PLAN.md): the plan read, the product spec
checked, the target and the build plan drawn, and the page for people (BLUEPRINT.html) and the Studio kept
with them. The build itself, milestone after milestone: eaos/journeys/build_tools.py."""
import json
from pathlib import Path

from . import agent_tools, guided, catalog as journeys
from ..report import blueprint, blueprint_view
from ..analysis import design
from .build_look import read as _read
from ..analysis.plan_source import read_plan


def folder(state):
    return guided.outputs(state) / 'blueprint'


def _write(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def _state(project):
    state = agent_tools.state_of(project, new=True)
    if state.get('mode') != 'build':
        state['mode'] = 'build'
        guided.save(state)
    return state


# ---------------------------------------------------------------- the blueprint

def blueprint_start(source=None, text=None, project=None):
    state = _state(project)
    plan, pictures = read_plan(source, text)
    where = folder(state)
    where.mkdir(parents=True, exist_ok=True)
    (where / 'SOURCE.md').write_text(plan + '\n', encoding='utf-8')
    catalogue = blueprint.stacks()['concerns']
    return {'saved': str(where / 'SOURCE.md'), 'characters': len(plan), 'plan_text': plan[:40000], 'more': len(plan) > 40000,
            'pictures': pictures, 'spec_format': blueprint.SPEC, 'design': design.brief(plan.strip().splitlines()[0][:120] if plan.strip() else ''),
            'stack_catalogue': {concern: {'title': entry['title'], 'recommended': entry['recommended'],
                                          'options': {key: option['why'] for key, option in entry['options'].items()}}
                                for concern, entry in catalogue.items()},
            'what_now': 'Read the plan whole, and look at every one of its pictures (open each file): they show the screens and '
                        'the look. Write the product spec in spec_format. Its `look` comes from the pictures and from `design`: '
                        'the suggestion and the free sources, held to its standard (fonts from fonts.arabic when the app speaks '
                        'Arabic); look.design_md is the whole DESIGN.md (Google Stitch\'s format). Group the features into modules with one '
                        'responsibility each, give every piece of data one owning module, turn each feature into checkable '
                        'acceptance criteria. List every requirement of the plan in `requirements` (its own id, its words), each '
                        'with what builds it in covered_by: nothing of the plan may be left out. Fill `nonfunctional` (languages, '
                        'data_sensitivity, platforms, expected_users): the blueprint adds from it the cards every product needs '
                        '(languages, privacy, offline, one adapter per integration, security, errors, accessibility, speed, load, '
                        'release), so never write those as features. Where the plan is thin, research what products of this kind need and add it as a '
                        'decision with options and your recommendation. Ask the person only what they must decide (choices, '
                        'with your recommendation first), including whether they have technology preferences. Then call '
                        'blueprint_spec with the spec.'}


def blueprint_spec(spec, project=None):
    state = _state(project)
    problems, questions = blueprint.validate_spec(spec)
    _write(folder(state) / 'product-spec.json', spec)
    state['blueprint'] = {**(state.get('blueprint') or {}), 'spec_ok': not problems, 'open_questions': len(questions)}
    guided.save(state)
    return {'problems': problems, 'questions': questions,
            'what_now': ('Fix these in the spec and call blueprint_spec again.' if problems else
                         'Ask the person these questions (choices, your recommendation first), put their answers in the spec '
                         '(decisions[].chosen, stack_preferences), call blueprint_spec again, then blueprint_design.' if questions else
                         'The spec is complete: call blueprint_design.')}


def blueprint_answer(question, choice, project=None):
    """The person's choice for one of the spec's questions (from the Studio's inbox): kept in the spec, which is checked
    again; a blueprint drawn and not built yet is drawn again with it."""
    state = _state(project)
    spec = _read(folder(state) / 'product-spec.json')
    if spec is None: return {'status': 'no_spec', 'what_now': 'Call blueprint_start, then blueprint_spec.'}
    checked = blueprint_spec(blueprint.answer(spec, question, choice), project)
    state = _state(project)
    if not checked['problems'] and (state.get('blueprint') or {}).get('designed') and not (state.get('built') or state.get('open_build')):
        drawn = {concern: row['id'] for concern, row in (_read(folder(state) / 'stack.json') or {}).items() if question != f'stack-{concern}'}
        return blueprint_design(drawn, project)
    publish(state)
    return checked


def answered(project, row, response):
    """An inbox row of the blueprint (eaos/report/studio/build_plan.py) answered in the Studio: the choice goes into the spec at
    once, with no assistant to review it. A technology or the journeys take the option's id, a product decision its words
    (the option's, or the person's own)."""
    question = row['id'].removeprefix('blueprint:')
    by_id = question.startswith('stack-') or question == 'flows'
    blueprint_answer(question, response['option'] if by_id and response['option'] else response['label'], str(project))
    return {**row, 'response': {**response, 'status': 'applied'}, 'execution': None}


def blueprint_design(stack=None, project=None):
    state = _state(project)
    spec = _read(folder(state) / 'product-spec.json')
    if spec is None: return {'status': 'no_spec', 'what_now': 'Call blueprint_start, then blueprint_spec.'}
    problems, questions = blueprint.validate_spec(spec)
    if problems: return {'status': 'spec_incomplete', 'problems': problems, 'what_now': 'Fix the spec with blueprint_spec first.'}
    chosen = blueprint.choose_stack(spec, stack)
    built = blueprint.design(spec, chosen)
    where = folder(state)
    _write(where / 'stack.json', chosen)
    _write(guided.report_of(state) / 'target-architecture.json', built['architecture'])     # where a check keeps its own
    _keep_look(state, spec)
    _write(where / 'eaos.policy.json', built['policy'])
    _write(where / 'plan.json', built['plan'])
    (where / 'BLUEPRINT.md').write_text(blueprint_view.document(spec, chosen, built) + '\n', encoding='utf-8')
    publish(state, spec, chosen, built)
    state['blueprint'] = {**(state.get('blueprint') or {}), 'designed': agent_tools._now(),
                          'cards': len(built['plan']['tasks']), 'milestones': [m['id'] for m in built['plan']['milestones']]}
    state.setdefault('built', [])
    guided.save(state)
    return {'status': 'designed', 'blueprint': str(where / 'BLUEPRINT.md'), 'for_the_person': str(guided.outputs(state) / 'BLUEPRINT.html'),
            'stack': {concern: {'chosen': row['name'], 'why': row['why'], 'change_later': row['switch']} for concern, row in chosen.items()},
            'layers': sorted(built['policy']['layers']), 'rules': [r['reason'] for r in built['policy']['rules']],
            'vendors_kept_in_one_place': built['policy']['vendors'],
            'milestones': [{'id': m['id'], 'name': m['name'], 'cards': len(m['tasks'])} for m in built['plan']['milestones']],
            'open_questions': questions,
            'what_now': 'Tell the person, simply, the parts, the technologies and why, and the order of the build. Then call '
                        'build_start (it asks their agreement once).'}


def _keep_look(state, spec):
    """The spec's DESIGN.md, when it wrote one, kept as the project's look."""
    look = str((spec.get('look') or {}).get('design_md') or '').strip()
    if look.startswith('#'): design.choose(guided.report_of(state), look)       # the one home of the look: the screen review reads it


def publish(state, spec=None, stack=None, built=None):
    """BLUEPRINT.html in the outputs folder, beside README.md: the blueprint and the build's progress for a person; and
    the same in the Studio: the progress on its live map (journeys.draw_build), the blueprint and the look in its library
    while no check of the project exists yet (after one, the check's own publishing keeps the Studio)."""
    journeys.draw_build(state)
    if not guided.scan_done(state): _studio(state)
    where = folder(state)
    spec = spec or _read(where / 'product-spec.json')
    stack = stack or _read(where / 'stack.json')
    if not (spec and stack): return None
    built = built or {'policy': _read(where / 'eaos.policy.json'), 'plan': _read(where / 'plan.json'),
                      'architecture': _read(guided.report_of(state) / 'target-architecture.json', {})}
    target = guided.outputs(state) / 'BLUEPRINT.html'
    target.write_text(blueprint_view.page(spec, stack, built, state.get('built')), encoding='utf-8')
    return target


def studio_build(state):
    """{'spec', 'plan', 'built', 'open'} of a project being built from its plan, for the Studio (eaos/report/studio/build_plan.py)."""
    spec = _read(folder(state) / 'product-spec.json')
    return {'spec': spec, 'plan': _plan(state), 'built': state.get('built') or [], 'open': state.get('open_build')} if isinstance(spec, dict) else None


def _studio(state):
    """The Studio's data of a project not checked yet (eaos/report/studio/export.py): its library shows the blueprint and the
    look. Never a reason for a build step to fail: a failure is logged and the step goes on."""
    from ..report.studio.export import export
    try:
        report = guided.report_of(state)
        report.mkdir(parents=True, exist_ok=True)
        export(report, state.get('lang') or 'en', Path(state['project']).name, state['project'], None, state, studio_build(state))
    except Exception as problem:
        guided.log_failure(guided.outputs(state), problem)


guided.PUBLISHERS['build'] = lambda state: publish(state)


def open_blueprint(project=None, show=True):
    state = _state(project)
    page = publish(state)
    if page is None: return {'status': 'no_blueprint', 'what_now': 'Draw the blueprint first: blueprint_start, blueprint_spec, blueprint_design.'}
    opened = False
    if show:
        import webbrowser
        try: opened = webbrowser.open(page.resolve().as_uri())
        except Exception: opened = False
    return {'blueprint_for_people': str(page), 'opened_in_browser': opened, 'outputs_folder': str(guided.outputs(state))}


def _plan(state):
    return _read(folder(state) / 'plan.json')

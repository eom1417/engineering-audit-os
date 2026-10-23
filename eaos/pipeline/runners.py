"""One thin wrapper per stage. No analysis lives here; every runner calls the module that owns it.

A runner may raise SkipStage when the stage does not apply to this project — no policy declared,
no provider configured, no engine installed. That is a recorded absence, not a failure.
"""
import json
from pathlib import Path

from .live_app import NO_RUN, _keep, _live, _ran
from .pages import crawl, journeys, screens
from .stages import SkipStage

POLICY_FILE = 'eaos.policy.json'


def facts(context):
    from ..facts.run import collect
    from ..facts.scope import declared_exclusions
    from ..facts.source import Source
    # collect() merges the project's declared exclusions, but a Source built before that call has
    # already walked the tree. Building it here without them analysed 98 fixture files this project
    # had explicitly put out of scope, and they dominated the sustainability dashboard.
    context['exclude'] = sorted({*context.exclude, *declared_exclusions(context.target)})
    context['source'] = Source(context.target, exclude=context['exclude'],
                               max_files=context.max_files, max_bytes=context.max_bytes)
    context['collected'] = collect(context.target, context.out, None, source=context['source'], exclude=context['exclude'],
                                   cache=Path(context.runtime) / 'syntax-cache.json' if context.get('runtime') else None)
    # A tree with no source file to read is not an audited project, whatever its history says:
    # an empty checkout used to be reported COMPLETE, with claims drawn from git history alone.
    from ..vocabulary import classify
    if not any(classify(item['path']) == 'source' for item in context['source'].readable()):
        raise SkipStage('the target holds no source file this tool reads, so no project was audited', code='no_source_files')
    return {'facts': context['collected']['facts'], 'sets': len(context['collected']['sets']),
            'exclude': context['exclude']}


def engines(context):
    if context.engines is None:
        raise SkipStage('external engines were not requested for this run', code='engines_not_requested')
    from ..facts.run import add_to_index, collect_external
    if 'source' not in context:
        from ..facts.source import Source
        context['source'] = Source(context.target, exclude=context.exclude, max_files=context.max_files, max_bytes=context.max_bytes)
    # Run again within the same check (eaos/pipeline/run.py again), the engines named join the others' results.
    entries = collect_external(context.target, context.out, context['source'], only=context.engines or None,
                               keep=bool(context.get('again')))
    external_entry = _index_engines(context, entries if isinstance(entries, list) else [entries], add_to_index)
    from ..facts.store import read_set
    external = read_set(context.out, 'external')
    return {'findings': external_entry['facts'], 'tools_failed': external['summary'].get('engines_failed') or {}}


def _index_engines(context, entries, add_to_index):
    """Index the engines' sets and join them to the facts stage's list; the `external` set's entry. SkipStage when no
    engine is installed."""
    for entry in entries: add_to_index(context.out, context.target, entry)
    external_entry = next((entry for entry in reversed(entries) if entry['set'] == 'external'), None)
    if external_entry is None or not external_entry['available']:
        raise SkipStage('no external engine is installed', code='no_engine_installed')
    # The facts stage handed us its set list; a later stage rebuilding the dossier reads that list,
    # so the set we just added has to join it or the evidence is on disk and invisible.
    collected = context.get('collected')
    if collected is not None:
        collected['sets'] = ([row for row in collected['sets'] if row['set'] not in {e['set'] for e in entries}]
                              + entries)
    return external_entry




def _owner(target):
    import subprocess
    done = subprocess.run(['git', '-C', str(target), 'config', 'user.name'], capture_output=True, text=True)
    return done.stdout.strip() or 'the owner'


def setup(context):
    """The app installed and started in an isolated copy (eaos/live_setup.py), once the person agreed to it."""
    if not context.get('runtime'):
        raise SkipStage(NO_RUN, code='no_run_consent')
    from ..live_setup import authorize, setup as start
    authorize(context.target, context.runtime, _owner(context.target))
    result = start(context.target, Path(context.runtime), report=context.out, provider=context.provider or None, say=lambda n: None)
    _keep(context, 'setup.json', result)
    if not result['ok']:
        raise SkipStage('the app did not start in the isolated copy: ' + '; '.join(result['limitations'])[:250], code='app_not_running')
    return {'attempts': result['attempts'], 'limitations': len(result['limitations'])}


def verify(context):
    """The project's own tests from its run profile in the isolated copy, with coverage (eaos/verify.py run_profile),
    once the person agreed to run the app; else which test imports which file, and why nothing ran."""
    from ..verify import declared, run_profile
    if not context.get('runtime'):
        declared(context.target, context.out, NO_RUN, context.get('source'))
        raise SkipStage(NO_RUN, code='no_run_consent')
    if not (Path(context.runtime) / 'run.json').is_file():
        reason = 'the app has no run profile in the isolated copy, so its tests have no command to run with'
        declared(context.target, context.out, reason, context.get('source'))
        raise SkipStage(reason, code='no_test_command')
    try:
        result = run_profile(context.target, context.out, context.runtime)
    except LookupError as problem:
        declared(context.target, context.out, str(problem), context.get('source'))
        raise SkipStage(f"{problem}, so the project's tests were not run", code='no_test_command') from None
    except Exception as problem:                       # an install that fails is the project's state, not EAOS's
        reason = f'the tests could not run in the isolated copy: {type(problem).__name__}: {problem}'[:300]
        declared(context.target, context.out, reason, context.get('source'))
        raise SkipStage(reason, code='tests_not_run') from None
    return {'commands': len(result['attempts']), 'passed': result['passed'], 'overall_percent': result.get('overall_percent'),
            'covered_files': len(result.get('coverage') or {})}


def record(context):
    """The lock run twice on today's code (eaos/behavior_lock.py run_lock): the screens and interfaces it recorded."""
    runtime = _live(context)
    if not (context.out / 'behavior-lock/plan.json').is_file():
        raise SkipStage('the program has no feature to lock', code='no_features')
    from ..behavior_lock import run_lock
    from .live_app import shared_app
    result = run_lock(context.out, context.target, runtime, app=shared_app(context))     # on the app the person signed in to
    passed = sum(r['status'] == 'passed' for r in result['results'])
    _keep(context, 'lock.json', {**result, 'specs': len(result['results']), 'passed': passed})
    return {'specs': len(result['results']), 'passed': passed}


def baseline(context):
    """Today's speed under the intake's load scenarios (eaos/runtime_baseline.py), on a production build that started."""
    runtime = _live(context)
    import json as _json
    profile = _json.loads((runtime / 'run.json').read_text(encoding='utf-8'))
    if not (profile.get('baseline') or {}).get('verified'):
        raise SkipStage('the production build of the app did not start in the isolated copy, so its speed was not measured',
                        code='no_production_run')
    from ..nfr import write as scenarios
    from ..runtime_baseline import PagesOnly, run_baseline
    scenarios(context.out)
    if not list((context.out / 'nfr/k6').glob('*.js')):
        raise SkipStage("the intake's load scenarios name no route of the app a load test can request", code='no_load_scenario')
    try: record = run_baseline(context.out, context.target, runtime)
    except PagesOnly as problem: raise SkipStage(str(problem), code='baseline_pages_only') from problem
    _keep(context, 'baseline.json', record)
    return {'scenarios': len(record['scenarios']),
            'p95_ms': max((s['before']['p95_ms'] for s in record['scenarios'] if s.get('before')), default=None)}


def readiness(context):
    """Production readiness under pressure as findings with evidence (eaos/production_readiness.py); the k6 baseline is
    read only when it ran in this check."""
    from ..production_readiness import write
    record = write(context.out, measured=_ran(context, 'baseline'))
    return {aspect: counts for aspect, counts in record['summary'].items()}


def architecture(context):
    """The city and the clusters of the code (eaos/engines/architecture.py) and their digest, in architecture/map.json."""
    if context.engines is None:
        raise SkipStage('external engines were not requested for this run', code='engines_not_requested')
    from ..engines.architecture import city, clusters, digest
    from ..workspace import write
    folder = context.out / 'architecture'
    drawn = {'city': city(context.target, folder), 'clusters': clusters(context.target, folder)}
    if all(row['status'] != 'observed' for row in drawn.values()):
        raise SkipStage('; '.join(row.get('reason', '') for row in drawn.values())[:300], code='no_architecture_map')
    summary = digest(folder)
    write(folder / 'map.json', {'schema_version': 1, **drawn, 'digest': summary})
    return {**{name: row['status'] for name, row in drawn.items()}, 'hotspots': len(summary['hotspots']),
            'clusters': len(summary['clusters'])}


def sustainability(context):
    """The six indicators against their targets (eaos/sustainability.py): sustainability.json."""
    from ..sustainability import write
    result = write(context.out)
    return {'measured': sum(1 for row in result['rows'] if row['measured']), 'moves': len(result['moves'])}


def transform(context):
    """A canonical home for each repeated definition and the move that gets there (eaos/transform_plan.py)."""
    from ..transform_plan import build, write
    policy_path = Path(context.policy_path) if context.policy_path else Path(context.target) / POLICY_FILE
    plan = build(context.out, policy_path=str(policy_path) if policy_path.is_file() else None)
    write(context.out, plan)
    return {'stages': plan['summary']['stages'], 'without_home': plan['summary']['moves_with_no_viable_candidate']}


def policy(context):
    if not context.policy_path and not (Path(context.target) / POLICY_FILE).is_file():
        raise SkipStage(f'the project declares no {POLICY_FILE}', code='no_policy')
    from ..policy import check
    result = check(context.target, context.out, policy_path=context.policy_path)
    return {'violations': result.get('violations')}


def claims(context):
    from ..dossier import assemble
    from ..workspace import read, write
    result = assemble(context.target, context.out, run=context.get('audit_run'), language=context.language,
                      exclude=context.exclude, collected=context.get('collected'))
    if context.get('goal'):
        dossier = read(context.out / 'dossier.json')
        dossier['review_goal'] = context['goal']
        write(context.out / 'dossier.json', dossier)
    context['dossier_status'] = result['status']
    return {'claims': result['claims'], 'counts': result['claim_counts']}


def probe(context):
    from ..probes import run_all
    return run_all(context.target, context.out)


NO_ASSISTANT = 'no assistant was installed or allowed for this check, so the rules stand alone'


def _absent(provider):
    """SkipStage for an AI stage without its assistant: the reason the provider carries (eaos/assistants/readiness.py
    NoAssistant: the person said no, the assistant is not signed in, ...), else nobody allowed one."""
    code = getattr(provider, 'code', None)
    return SkipStage(provider.reason, code=code) if code else SkipStage(NO_ASSISTANT, code='no_provider')


def _lost(context, problem, code):
    """SkipStage for an AI stage whose assistant failed midway: asked for one word again, an assistant that is no
    longer ready gives its own reason (signed out during the check, its limit reached); else `problem` and `code`."""
    name = (getattr(context.provider, 'config', None) or {}).get('assistant')
    if name:
        from ..assistants import readiness
        try: found = readiness.probe(name, fresh=True)
        except Exception: found = {'ready': True}
        if not found['ready']:
            return SkipStage(f"during the check {found['name']} stopped answering ({found['code']}): {problem}"[:300], code=found['code'],
                             lost={'assistant': name, 'resets': found.get('resets'), 'code': found['code']})
    return SkipStage(problem, code=code)


def roles(context):
    """The kinds of users the app has, read from its code by the assistant (eaos/roles.py): the app is opened as each."""
    if not context.provider: raise _absent(context.provider)
    from ..assistants.command import Stuck
    from ..roles import find
    try: kinds = find(context.target, context.out, context.provider)
    except Stuck as problem: raise _lost(context, str(problem), 'ai_stuck') from None
    except Exception as problem:                       # the assistant never decides the fate of the check
        raise _lost(context, f"the kinds of users could not be read ({type(problem).__name__}: {problem})"[:300], 'ai_failed') from None
    return {'kinds': len(kinds)}


def semantic(context):
    if not context.provider:
        raise _absent(context.provider)
    from ..assistants.command import Stuck
    from ..semantic import run
    from ..views import refresh
    try: result = run(context.target, context.out, context.provider, language=context.language)
    except Stuck as problem:
        raise _lost(context, str(problem), 'ai_stuck') from None
    except Exception as problem:                       # the assistant never decides the fate of the check
        raise _lost(context, f'the assistant\'s reading could not be used ({type(problem).__name__}: {problem})'[:300],
                    'ai_failed') from None
    refresh(context.out, context.language)
    return {'hypotheses': result['claims'], 'questions': result['questions'], 'calls': result['calls']}


def _node(context, name):
    """Run one AI node of eaos/studio/nodes inside the check, with its cache and evidence check, as long as the assistant
    works; return its record and what the live map reports. Without an assistant, stuck or on a failure the rules'
    result stands."""
    if not context.provider:
        raise _absent(context.provider)
    from ..studio.nodes import core, run
    record = run(context.out, names=[name], project=str(context.target), lang=context.language,
                 adapters=_adapters_of(context), assistants=context.get('assistants')).get(name)
    if record is None:
        raise SkipStage('there was nothing for the assistant to decide', code='not_applicable')
    if record['method'] != 'model':
        raise _lost(context, record['why'], 'ai_stuck' if record['why'] == core.WORDS['stuck'] else 'ai_failed')
    return record, {'dropped': len(record['dropped']), 'calls': 0 if record['cached'] else record['calls'],
                    'assistant': record['assistant'], 'model': record['model'], **_partly(context, record.get('batches'))}


def _partly(context, batches):
    """A node whose assistant answered only some of its batches (its limit reached midway, a batch that failed): the
    rules decided the rest, so the stage says so and the check is PARTIAL; running the stage again asks only those."""
    if not batches: return {}
    answered = batches['asked'] - batches['failed']
    lost = _lost(context, f"the assistant answered {answered} of {batches['asked']} batches; the rules decided the rest "
                          f"({batches['why']})", 'ai_partial')
    who = (getattr(context.provider, 'config', None) or {}).get('assistant')
    return {'assistant_lost': {**(lost.lost or {'assistant': who, 'resets': None}), 'why': str(lost)[:300],
                               'answered': answered, 'asked': batches['asked']}}


def _adapters_of(context):
    """Only the assistant the person chose for the check, when they chose one; else None (any installed)."""
    chosen = (getattr(context.provider, 'config', None) or {}).get('assistant')
    if not chosen: return None
    from ..studio.actions.adapters import installed
    return {key: adapter for key, adapter in installed().items() if key == chosen}


def ideal(context):
    """The ideal planner node (eaos/studio/nodes/ideal_planner.py) before the target is final: plan, critique and the
    evidence check; the reconcile stage turns its decisions into the target, and the rules' target stands without it."""
    record, detail = _node(context, 'ideal_planner')
    return {'elements': record['decisions'][0]['detail']['elements'], **detail}


def triage(context):
    """The card triage node (eaos/studio/nodes/triage.py): each open card confirmed, doubted or rejected on its own
    evidence, a doubted one judged again on all its facts, with why in the person's words; the cards stage then applies
    the verdicts once (eaos/card_review.py apply_verdicts) before anything ranks, plans or reports."""
    record, detail = _node(context, 'card_triage')
    return {**{row['decision']: len(row['subjects']) for row in record['routes']}, **detail}


def order(context):
    """The plan orderer node (eaos/studio/nodes/plan_orderer.py): the order and grouping of the plan's cards, every
    prerequisite kept; the steps stage writes it into the plan."""
    record, detail = _node(context, 'plan_orderer')
    return {'decision': record['decisions'][0]['decision'], **detail}


def load(context):
    from ..load_model import compute, project
    from ..workspace import write
    record = compute(context.out)
    record = project(record)
    if _ran(context, 'baseline'):
        measured = json.loads((context.out / 'live/baseline.json').read_text(encoding='utf-8'))
        record['measured'] = {'source': 'live/baseline.json', 'conditions': measured['conditions'],
                              'scenarios': [{'id': s['id'], 'threshold': s['threshold'], **(s.get('before') or {})}
                                            for s in measured['scenarios']]}
    write(context.out / 'load-model.json', record)
    return {'entry_points': len(record.get('entry_points', [])),
            'incomplete': sum(1 for e in record.get('entry_points', []) if (e.get('projection') or {}).get('incomplete'))}


def plan(context):
    from ..plan import build
    result = build(context.target, context.out, context.language, context.get('patterns'))
    return {'tasks': result['tasks'], 'waves': result['waves']}


def lock(context):
    from ..lock_specs import build
    plan = build(context.out, context.target)
    if not plan['specs']:
        raise SkipStage('the program has no feature to lock', code='no_features')
    return {'specs': len(plan['specs']), 'without_spec': sum(1 for s in plan['specs'] if not s['path'])}


def reports(context):
    # The C4 diagrams first: CURRENT-STATE and TARGET-STATE embed them; START-HERE.md counts this check's plan.
    from ..c4 import write as diagrams
    from ..compose.four_reports import write
    from ..start_here import project_name, start_here
    diagrams(context.out)
    start_here(context.out, context.language, project_name(context.target))
    return write(context.out, context.language)


def measure(context):
    from ..measurements import run
    return run(context.out)


def intake(context):
    from ..intake import write
    record = write(context.target, context.out, context.get('intake'))
    return {'answered': sum(q['status'] == 'answered' for q in record['questions']), 'scenarios': len(record['scenarios'])}


def features(context):
    """Group user-facing surfaces into the program's features and bind them to data.

    The ``facts`` stage records a count, not the flat list, in ``context['collected']``;
    the list is read back from the persisted fact sets the facts stage has just written
    to disk. Doing it this way keeps the in-memory payload of the Context small while
    the disk keeps the source of truth.
    """
    from ..features import build
    from ..workspace import write
    from ..facts.store import read_set
    collected = context.get('collected') or {}
    set_names = collected.get('sets') or []
    facts = []
    for entry in set_names:
        name = entry.get('set') if isinstance(entry, dict) else entry
        try:
            facts.extend(read_set(context.out, name).get('facts') or [])
        except (OSError, ValueError):
            continue
    record = build(facts)
    write(context.out / 'features.json', record)
    return {'features': len(record['features']),
            'unassigned': len(record['unassigned_surfaces']),
            'critical': sum(1 for f in record['features'] if f['critical'])}


RUNNERS = {'setup': setup, 'crawl': crawl, 'record': record, 'screens': screens, 'baseline': baseline,
           'facts': facts, 'features': features, 'intake': intake, 'measure': measure, 'lock': lock, 'reports': reports,
           'engines': engines, 'policy': policy, 'claims': claims, 'probe': probe, 'load': load, 'semantic': semantic, 'roles': roles,
           'plan': plan}


def target(context):
    """The rules' proposal, kept as it was (target-proposal.json) and as the target until the reconcile decides it."""
    from ..target_architecture import build
    from ..workspace import write
    result = build(context.out, target=context.target)
    write(context.out / 'target-proposal.json', result)
    write(context.out / 'target-architecture.json', result)
    return {'components': len(result['components']), 'status': result['status']}


def proposals(context):
    """The Studio's records of this check so far: what the triage, the ideal and the pipeline-gap planner read."""
    if not context.provider:
        raise _absent(context.provider)
    from .live_app import studio
    result = studio(context)
    return {'sections': len(result['written']), 'errors': len(result['errors'])}


def cards(context):
    from ..plan import confirm
    from ..extend import carry
    record = confirm(context.target, context.out, context.language, triaged=_ran(context, 'triage'), reviewed=_ran(context, 'visual'))
    return {'extension': carry(context.target, context.out), 'kept': len(record['kept']), 'set_aside': len(record['set_aside']), 'doubted': len(record['doubted']),
            'design': len(record['design']), 'decided_by': record['decided_by']}


def visual(context):
    """The visual reviewer node (eaos/studio/nodes/visual_reviewer.py): the assistant opens each picture of the app's
    screens, and only those, and names what a person would notice there; the cards stage makes each a design card."""
    record, detail = _node(context, 'visual_reviewer')
    return {**{row['decision']: len(row['subjects']) for row in record['routes']}, **detail}


def pipeline_gaps(context):
    """The pipeline-gap planner node (eaos/studio/nodes/pipeline_gap_planner.py): how each broken pipeline rule is
    closed; the plan orderer reads its steps."""
    record, detail = _node(context, 'pipeline_gap_planner')
    return {**{row['decision']: len(row['subjects']) for row in record['routes']}, **detail}


def reconcile(context):
    from ..target_architecture import reconcile as decide
    from ..target_document import render
    policy_path = Path(context.policy_path) if context.policy_path else Path(context.target) / POLICY_FILE
    result = decide(context.out, planned=_ran(context, 'ideal'), policy_path=policy_path if policy_path.is_file() else None)
    render(context.out, result, language=context.language)
    return result['decided']


def steps(context):
    from ..plan import sequence
    record = sequence(context.out, context.language, ordered=_ran(context, 'order'))
    return {'steps': len(record['steps']), 'decided_by': record['source']}


RUNNERS.update(target=target, proposals=proposals, cards=cards, pipeline_gaps=pipeline_gaps, reconcile=reconcile, steps=steps)
RUNNERS.update(ideal=ideal, triage=triage, visual=visual, order=order)


def session(context):
    """Whether the pages need a sign-in, and the one session every page stage opens them with (eaos/pipeline/sign_in_stage.py)."""
    from .sign_in_stage import session as signed
    return signed(context)


RUNNERS['session'] = session


def translate(context):
    """Every document in both languages (eaos/bilingual.py)."""
    if not context.provider: raise _absent(context.provider)
    from ..bilingual import translate as both
    return both(context.out, context.provider)


RUNNERS.update(translate=translate, verify=verify, journeys=journeys, readiness=readiness, architecture=architecture,
               sustainability=sustainability, transform=transform)

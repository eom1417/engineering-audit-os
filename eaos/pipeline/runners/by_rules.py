"""One thin wrapper per stage. No analysis lives here; every runner calls the module that owns it.

A runner may raise SkipStage when the stage does not apply to this project — no policy declared,
no provider configured, no engine installed. That is a recorded absence, not a failure. The runners of the stages an
assistant does are pipeline/runners/by_assistant.py's; RUNNERS, here, names every stage's.
"""
import json
from pathlib import Path

from .by_assistant import ideal, order, pipeline_gaps, proposals, roles, semantic, translate, triage, visual
from .live_app import NO_RUN, _keep, _live, _ran
from .experience import experience, replayed
from .layers_live import layers_trial
from .pages import crawl, journeys, screens
from ..stages import SkipStage

POLICY_FILE = 'eaos.policy.json'


def facts(context):
    from ...facts.run import collect
    from ...facts.scope import declared_exclusions
    from ...facts.source import Source
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
    # A site of pages alone (its script inside its .html) is a project too: it was refused, its app never run.
    from ...core.contracts.vocabulary import classify
    if not any(classify(item['path']) == 'source' or item['path'].endswith(('.html', '.htm')) for item in context['source'].readable()):
        raise SkipStage('the target holds no source file this tool reads, so no project was audited', code='no_source_files')
    return {'facts': context['collected']['facts'], 'sets': len(context['collected']['sets']),
            'exclude': context['exclude']}


def engines(context):
    if context.engines is None:
        raise SkipStage('external engines were not requested for this run', code='engines_not_requested')
    from ...facts.run import add_to_index, collect_external
    if 'source' not in context:
        from ...facts.source import Source
        context['source'] = Source(context.target, exclude=context.exclude, max_files=context.max_files, max_bytes=context.max_bytes)
    # Run again within the same check (eaos/pipeline/run.py again), the engines named join the others' results.
    from ...analysis.layers import depcruise_rules
    depcruise_rules(context.target, context.out)          # the layer map's rules, for dependency-cruiser (M6.2)
    entries = collect_external(context.target, context.out, context['source'], only=context.engines or None,
                               keep=bool(context.get('again')))
    external_entry = _index_engines(context, entries if isinstance(entries, list) else [entries], add_to_index)
    from ...facts.store import read_set
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




def setup(context):
    """The app installed and started in an isolated copy (eaos/live/app/setup.py), once the person agreed to it."""
    if not context.get('runtime'):
        raise SkipStage(NO_RUN, code='no_run_consent')
    from ...live.app.setup import authorize, owner, setup as start
    authorize(context.target, context.runtime, owner(context.target))
    result = start(context.target, Path(context.runtime), report=context.out, provider=context.provider or None, say=lambda n: None)
    _keep(context, 'setup.json', result)
    if not result['ok']:
        raise SkipStage('the app did not start in the isolated copy: ' + '; '.join(result['limitations'])[:250], code='app_not_running')
    return {'attempts': result['attempts'], 'limitations': len(result['limitations'])}


def verify(context):
    """The project's own tests from its run profile in the isolated copy, with coverage (eaos/live/testing/verify.py run_profile),
    once the person agreed to run the app; else which test imports which file, and why nothing ran."""
    from ...live.testing.verify import declared, run_profile
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
    """The lock run twice on today's code (eaos/live/behavior/lock.py run_lock): the screens and interfaces it recorded."""
    runtime = _live(context)
    if not (context.out / 'behavior-lock/plan.json').is_file():
        raise SkipStage('the program has no feature to lock', code='no_features')
    from ...live.behavior.lock import run_lock
    from .live_app import shared_app
    result = run_lock(context.out, context.target, runtime, app=shared_app(context))     # on the app the person signed in to
    result = replayed(context, result)                   # the saved journeys, replayed with no assistant, as its rows
    passed = sum(r['status'] == 'passed' for r in result['results'])
    _keep(context, 'lock.json', {**result, 'specs': len(result['results']), 'passed': passed})
    return {'specs': len(result['results']), 'passed': passed}


def baseline(context):
    """Today's speed under the intake's load scenarios (eaos/live/trials/load_baseline.py), on a production build that started."""
    runtime = _live(context)
    import json as _json
    profile = _json.loads((runtime / 'run.json').read_text(encoding='utf-8'))
    if not (profile.get('baseline') or {}).get('verified'):
        raise SkipStage('the production build of the app did not start in the isolated copy, so its speed was not measured',
                        code='no_production_run')
    from ...live.trials.load_plans import write as scenarios
    from ...live.trials.load_baseline import PagesOnly, run_baseline
    scenarios(context.out)
    if not list((context.out / 'nfr/k6').glob('*.js')):
        raise SkipStage("the intake's load scenarios name no route of the app a load test can request", code='no_load_scenario')
    try: record = run_baseline(context.out, context.target, runtime)
    except PagesOnly as problem: raise SkipStage(str(problem), code='baseline_pages_only') from problem
    _keep(context, 'baseline.json', record)
    return {'scenarios': len(record['scenarios']),
            'p95_ms': max((s['before']['p95_ms'] for s in record['scenarios'] if s.get('before')), default=None)}


def readiness(context):
    """Production readiness under pressure as findings with evidence (eaos/analysis/readiness/production.py); the k6 baseline is
    read only when it ran in this check."""
    from ...analysis.readiness.production import write
    record = write(context.out, measured=_ran(context, 'baseline'))
    return {aspect: counts for aspect, counts in record['summary'].items()}


def architecture(context):
    """The code map (eaos/analysis/maps/code_map.py): the hotspots, the import clusters and their modularity, in
    architecture/map.json."""
    from ...analysis.maps.code_map import digest
    from ...core.project.workspace import write
    drawn = digest(context.out)
    if not drawn['hotspots'] and not drawn['clusters']:
        raise SkipStage('no production file was measured or imports another', code='no_architecture_map')
    (context.out / 'architecture').mkdir(parents=True, exist_ok=True)
    write(context.out / 'architecture' / 'map.json', {'schema_version': 2, 'digest': drawn})
    return {'hotspots': len(drawn['hotspots']), 'clusters': len(drawn['clusters'])}


def sustainability(context):
    """The six indicators against their targets (eaos/analysis/target_state/sustainability.py): sustainability.json."""
    from ...analysis.target_state.sustainability import write
    result = write(context.out)
    return {'measured': sum(1 for row in result['rows'] if row['measured']), 'moves': len(result['moves'])}


def transform(context):
    """A canonical home for each repeated definition and the move that gets there (eaos/analysis/target_state/transform.py)."""
    from ...analysis.target_state.transform import build, write
    policy_path = Path(context.policy_path) if context.policy_path else Path(context.target) / POLICY_FILE
    plan = build(context.out, policy_path=str(policy_path) if policy_path.is_file() else None)
    write(context.out, plan)
    return {'stages': plan['summary']['stages'], 'without_home': plan['summary']['moves_with_no_viable_candidate']}


def policy(context):
    if not context.policy_path and not (Path(context.target) / POLICY_FILE).is_file():
        raise SkipStage(f'the project declares no {POLICY_FILE}', code='no_policy')
    from ...analysis.target_state.policy import check
    result = check(context.target, context.out, policy_path=context.policy_path)
    return {'violations': result.get('violations')}


def layers(context):
    """The system read as layers (eaos/analysis/layers/): the map, the boundaries and every layer's findings; the
    project's tests as this check ran them, when it did."""
    from ...analysis import layers as layered
    from .live_app import _ran
    verification = layered.read(context.out / 'verification.json') if _ran(context, 'verify') else None
    summary = layered.run(context.target, context.out, verification)
    return {'findings': summary['findings'], 'questions': summary['questions'], 'files': summary['files'],
            'gaps': summary['gaps'], 'endpoints': summary['endpoints']}


def _proposed_tokens(context):
    """The tokens the look calls for, for the person and the card: design/tokens.proposed.json, W3C 2025.10."""
    from ...analysis.assessments.one_source_look import proposed
    tokens = proposed(context.out)
    if not tokens: return
    (context.out / 'design').mkdir(parents=True, exist_ok=True)
    (context.out / 'design' / 'tokens.proposed.json').write_text(json.dumps(tokens, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def _guide_draft(context):
    """The project's extension guide as EAOS would write it, in extending/ of the report (M18.3), for its card and batch."""
    from ...analysis.repair import project_guide
    drawn = project_guide.drawn_from_report(context.target, context.out)
    if not drawn: return                 # a path that does not read the layers has none to draw it from
    (context.out / 'extending').mkdir(parents=True, exist_ok=True)
    (context.out / 'extending' / project_guide.NAME).write_text(project_guide.text(drawn, Path(context.target).name), encoding='utf-8')


def claims(context):
    from ...analysis.understanding.dossier import assemble
    from ...core.project.workspace import read, write
    result = assemble(context.target, context.out, run=context.get('audit_run'), language=context.language,
                      exclude=context.exclude, collected=context.get('collected'))
    if context.get('goal'):
        dossier = read(context.out / 'dossier.json')
        dossier['review_goal'] = context['goal']
        write(context.out / 'dossier.json', dossier)
    context['dossier_status'] = result['status']
    return {'claims': result['claims'], 'counts': result['claim_counts']}


def probe(context):
    from ...analysis.claims.probes import run_all
    return run_all(context.target, context.out)


def load(context):
    from ...analysis.readiness.load_model import compute, project
    from ...core.project.workspace import write
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
    from ...analysis.planning.cards import build
    result = build(context.target, context.out, context.language, context.get('patterns'))
    return {'tasks': result['tasks'], 'waves': result['waves']}


def lock(context):
    from ...live.behavior.specs import build
    plan = build(context.out, context.target)
    if not plan['specs']:
        raise SkipStage('the program has no feature to lock', code='no_features')
    return {'specs': len(plan['specs']), 'without_spec': sum(1 for s in plan['specs'] if not s['path'])}


def reports(context):
    # The C4 diagrams first: CURRENT-STATE and TARGET-STATE embed them; START-HERE.md counts this check's plan.
    from ...analysis.maps.c4 import write as diagrams
    from ...report.documents.four_reports import write
    from ...report.documents.start_here import project_name, start_here
    diagrams(context.out)
    _guide_draft(context)
    _proposed_tokens(context)
    start_here(context.out, context.language, project_name(context.target))
    return write(context.out, context.language)


def measure(context):
    from ...analysis.understanding.measurements import run
    return run(context.out)


def intake(context):
    from ...analysis.understanding.intake import write
    record = write(context.target, context.out, context.get('intake'))
    return {'answered': sum(q['status'] == 'answered' for q in record['questions']), 'scenarios': len(record['scenarios'])}


def features(context):
    """Group user-facing surfaces into the program's features and bind them to data.

    The ``facts`` stage records a count, not the flat list, in ``context['collected']``;
    the list is read back from the persisted fact sets the facts stage has just written
    to disk. Doing it this way keeps the in-memory payload of the Context small while
    the disk keeps the source of truth.
    """
    from ...analysis.understanding.features import build
    from ...core.project.workspace import write
    from ...facts.store import read_set
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
           'engines': engines, 'policy': policy, 'layers': layers, 'layers_trial': layers_trial, 'experience': experience, 'claims': claims, 'probe': probe, 'load': load, 'semantic': semantic, 'roles': roles,
           'plan': plan}


def target(context):
    """The rules' proposal, kept as it was (target-proposal.json) and as the target until the reconcile decides it."""
    from ...report.target_architecture.picture import build
    from ...core.project.workspace import write
    result = build(context.out, target=context.target)
    write(context.out / 'target-proposal.json', result)
    write(context.out / 'target-architecture.json', result)
    return {'components': len(result['components']), 'status': result['status']}


def cards(context):
    from ...analysis.planning.extension import carry
    from ...analysis.planning.cards import confirm
    record = confirm(context.target, context.out, context.language, triaged=_ran(context, 'triage'), reviewed=_ran(context, 'visual'))
    _experience_cards(context)
    return {'extension': carry(context.target, context.out), 'kept': len(record['kept']), 'set_aside': len(record['set_aside']), 'doubted': len(record['doubted']),
            'design': len(record['design']), 'decided_by': record['decided_by']}


def _experience_cards(context):
    """The experience report told again once the plan's cards are final, each confirmed difficulty with its fix card."""
    from ...report.experience.document import DATA, FOLDER, write
    if (context.out / FOLDER / DATA).exists(): write(context.out, context.language)


def reconcile(context):
    from ...report.target_architecture.picture import reconcile as decide
    from ...report.target_architecture.document import render
    policy_path = Path(context.policy_path) if context.policy_path else Path(context.target) / POLICY_FILE
    result = decide(context.out, planned=_ran(context, 'ideal'), policy_path=policy_path if policy_path.is_file() else None)
    render(context.out, result, language=context.language)
    return result['decided']


def steps(context):
    from ...analysis.planning.cards import sequence
    record = sequence(context.out, context.language, ordered=_ran(context, 'order'))
    return {'steps': len(record['steps']), 'decided_by': record['source']}


RUNNERS.update(target=target, proposals=proposals, cards=cards, pipeline_gaps=pipeline_gaps, reconcile=reconcile, steps=steps)
RUNNERS.update(ideal=ideal, triage=triage, visual=visual, order=order)


def session(context):
    """Whether the pages need a sign-in, and the one session every page stage opens them with (eaos/pipeline/runners/sign_in.py)."""
    from .sign_in import session as signed
    return signed(context)


RUNNERS['session'] = session


from .keeping import keeping  # noqa: E402  (the data's saving and keeping, M14)
RUNNERS['keeping'] = keeping


RUNNERS.update(translate=translate, verify=verify, journeys=journeys, readiness=readiness, architecture=architecture,
               sustainability=sustainability, transform=transform)


from .rules import rules  # noqa: E402  (the person's own rules, M16)
RUNNERS['rules'] = rules

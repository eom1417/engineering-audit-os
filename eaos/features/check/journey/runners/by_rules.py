"""One thin wrapper per stage. No analysis lives here; every runner calls the module that owns it.

A runner may raise SkipStage when the stage does not apply to this project — no policy declared, no provider configured,
no engine installed. That is a recorded absence, not a failure. The runners of the stages an assistant does are
pipeline/runners/by_assistant.py's; RUNNERS, here, names every stage's. """
from pathlib import Path

from .....kernel.system.errors import noted
from .by_assistant import order, roles, translate, triage
from .live_app import NO_RUN, _keep, _live, _ran
from .pages import crawl, journeys, screens
from ..stages import SkipStage

POLICY_FILE = 'eaos.policy.json'


UNREAD_SHOWN = 10


def _unread_said(paths):
    """The names a person sees in red; all of them are in facts/index.json."""
    return paths[:UNREAD_SHOWN] + ([f'+{len(paths) - UNREAD_SHOWN}'] if len(paths) > UNREAD_SHOWN else [])


def facts(context):
    from .....kernel.facts.run import collect
    from .....kernel.facts.scope import declared_exclusions
    from .....kernel.facts.source import Source
    # collect() merges the project's declared exclusions, but a Source built before that call has
    # already walked the tree. Building it here without them analysed 98 fixture files this project
    # had explicitly put out of scope, and they dominated the sustainability dashboard.
    context['exclude'] = sorted({*context.exclude, *declared_exclusions(context.target)})
    context['source'] = Source(context.target, exclude=context['exclude'],
                               max_files=context.max_files, max_bytes=context.max_bytes)
    context['collected'] = collect(context.target, context.out, None, source=context['source'],
                                   exclude=context['exclude'],
                                   cache=Path(context.runtime) / 'syntax-cache.json' if context.get('runtime')
                                   else None)
    # A tree with no source file to read is not an audited project, whatever its history says:
    # an empty checkout must not be reported COMPLETE: its claims would come from git history alone.
    # A site of pages alone (its script inside its .html) is a project too: it was refused, its app never run.
    from .....kernel.contracts.vocabulary import classify
    unread = [row['path'] for row in context['collected']['unread_names']]
    if not any(classify(item['path']) == 'source' or item['path'].endswith(('.html', '.htm'))
               for item in context['source'].readable()):
        if unread: raise SkipStage(', '.join(_unread_said(unread)), code='no_source_unread')
        raise SkipStage('the target holds no source file this tool reads, so no project was audited',
                        code='no_source_files')
    return {'facts': context['collected']['facts'], 'sets': len(context['collected']['sets']),
            'exclude': context['exclude'],
            **({'unread_names': _unread_said(unread)} if unread else {})}


def engines(context):
    if context.engines is None:
        raise SkipStage('external engines were not requested for this run', code='engines_not_requested')
    from .....kernel.facts.run import add_to_index, collect_external
    if 'source' not in context:
        from .....kernel.facts.source import Source
        context['source'] = Source(context.target, exclude=context.exclude, max_files=context.max_files,
                                   max_bytes=context.max_bytes)
    # Run again within the same check (eaos/features/check/journey/run.py again), the engines named join the others' results.
    from ....layers.analysis import depcruise_rules
    depcruise_rules(context.target, context.out)          # the layer map's rules, for dependency-cruiser
    entries = collect_external(context.target, context.out, context['source'], only=context.engines or None,
                               keep=bool(context.get('again')))
    external_entry = _index_engines(context, entries if isinstance(entries, list) else [entries], add_to_index)
    from .....kernel.facts.store import read_set
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
    """The app installed and started in an isolated copy (eaos/features/app_run/adapters/app/setup.py), once the person agreed to it."""
    if not context.get('runtime'):
        raise SkipStage(NO_RUN, code='no_run_consent')
    from ....app_run.adapters.app.setup import authorize, owner, setup as start
    authorize(context.target, context.runtime, owner(context.target))
    result = start(context.target, Path(context.runtime), report=context.out, provider=context.provider or None,
                   say=lambda n: None)
    _keep(context, 'setup.json', result)
    if not result['ok']:
        raise SkipStage('the app did not start in the isolated copy: ' + '; '.join(result['limitations'])[:250],
                        code='app_not_running')
    return {'attempts': result['attempts'], 'limitations': len(result['limitations'])}


def verify(context):
    """The project's own tests from its run profile in the isolated copy, with coverage (eaos/features/app_run/adapters/testing/verify.py
    run_profile), once the person agreed to run the app; else which test imports which file, and why nothing ran."""
    from ....app_run.adapters.testing.verify import declared, run_profile
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
    return {'commands': len(result['attempts']), 'passed': result['passed'],
            'overall_percent': result.get('overall_percent'),
            'covered_files': len(result.get('coverage') or {})}


def record(context):
    """The lock run twice on today's code (eaos/features/behaviour_lock/analysis/lock.py run_lock): the screens and interfaces it
    recorded."""
    runtime = _live(context)
    if not (context.out / 'behavior-lock/plan.json').is_file():
        raise SkipStage('the program has no feature to lock', code='no_features')
    from ....behaviour_lock.analysis.lock import run_lock
    from .live_app import shared_app
    result = run_lock(context.out, context.target, runtime,
                      app=shared_app(context))     # on the app the person signed in to
    passed = sum(r['status'] == 'passed' for r in result['results'])
    _keep(context, 'lock.json', {**result, 'specs': len(result['results']), 'passed': passed})
    return {'specs': len(result['results']), 'passed': passed}


def architecture(context):
    """The code map (eaos/features/code_reading/analysis/code_map.py): the hotspots, the import clusters and their modularity, in
    architecture/map.json."""
    from ....code_reading.analysis.code_map import digest
    from .....kernel.project.workspace import write
    drawn = digest(context.out)
    if not drawn['hotspots'] and not drawn['clusters']:
        raise SkipStage('no production file was measured or imports another', code='no_architecture_map')
    (context.out / 'architecture').mkdir(parents=True, exist_ok=True)
    write(context.out / 'architecture' / 'map.json', {'schema_version': 2, 'digest': drawn})
    return {'hotspots': len(drawn['hotspots']), 'clusters': len(drawn['clusters'])}


def policy(context):
    if not context.policy_path and not (Path(context.target) / POLICY_FILE).is_file():
        raise SkipStage(f'the project declares no {POLICY_FILE}', code='no_policy')
    from ....layers.analysis.target_state.policy import check
    result = check(context.target, context.out, policy_path=context.policy_path)
    return {'violations': result.get('violations')}


def layers(context):
    """The system read as layers (eaos/features/layers/analysis/): the map, the boundaries and every layer's findings; the
    project's tests as this check ran them, when it did."""
    from ....layers import analysis as layered
    from .live_app import _ran
    verification = layered.read(context.out / 'verification.json') if _ran(context, 'verify') else None
    summary = layered.run(context.target, context.out, verification)
    return {'findings': summary['findings'], 'questions': summary['questions'], 'files': summary['files'],
            'gaps': summary['gaps'], 'endpoints': summary['endpoints']}


def claims(context):
    from ....plan.analysis.dossier import assemble
    from .....kernel.project.workspace import read, write
    result = assemble(context.target, context.out, run=context.get('audit_run'), language=context.language,
                      exclude=context.exclude, collected=context.get('collected'))
    if context.get('goal'):
        dossier = read(context.out / 'dossier.json')
        dossier['review_goal'] = context['goal']
        write(context.out / 'dossier.json', dossier)
    context['dossier_status'] = result['status']
    return {'claims': result['claims'], 'counts': result['claim_counts']}


def probe(context):
    from ....claims.analysis.probes import run_all
    return run_all(context.target, context.out)


def plan(context):
    from ....plan.analysis.cards import build
    result = build(context.target, context.out, context.language, context.get('patterns'))
    return {'tasks': result['tasks'], 'waves': result['waves']}


def lock(context):
    from ....app_run.adapters.specs import build
    plan = build(context.out, context.target)
    if not plan['specs']:
        raise SkipStage('the program has no feature to lock', code='no_features')
    return {'specs': len(plan['specs']), 'without_spec': sum(1 for s in plan['specs'] if not s['path'])}


def reports(context):
    # START-HERE.md counts this check's plan.
    from ....report.interface.documents.four_reports import write
    from ....report.interface.documents.start_here import project_name, start_here
    start_here(context.out, context.language, project_name(context.target))
    return write(context.out, context.language)


def measure(context):
    from ....plan.analysis.understanding.measurements import run
    return run(context.out)


def intake(context):
    from ....plan.analysis.understanding.intake import write
    record = write(context.target, context.out, context.get('intake'))
    return {'answered': sum(q['status'] == 'answered' for q in record['questions']),
            'scenarios': len(record['scenarios'])}


def features(context):
    """Group user-facing surfaces into the program's features and bind them to data.

    The ``facts`` stage records a count, not the flat list, in ``context['collected']``; the list is read back from the
    persisted fact sets the facts stage has just written to disk. Doing it this way keeps the in-memory payload of the
    Context small while the disk keeps the source of truth. """
    from ....plan.analysis.understanding.features import build
    from .....kernel.project.workspace import write
    from .....kernel.facts.store import read_set
    collected = context.get('collected') or {}
    set_names = collected.get('sets') or []
    facts = []
    for entry in set_names:
        name = entry.get('set') if isinstance(entry, dict) else entry
        try:
            facts.extend(read_set(context.out, name).get('facts') or [])
        except (OSError, ValueError) as error:
            noted('a fact set that is missing or unreadable adds no facts', error)
            continue
    record = build(facts)
    write(context.out / 'features.json', record)
    return {'features': len(record['features']),
            'unassigned': len(record['unassigned_surfaces']),
            'critical': sum(1 for f in record['features'] if f['critical'])}


RUNNERS = {'setup': setup, 'crawl': crawl, 'record': record, 'screens': screens,
           'facts': facts, 'features': features, 'intake': intake, 'measure': measure, 'lock': lock, 'reports': reports,
           'engines': engines, 'policy': policy, 'layers': layers, 'claims': claims, 'probe': probe, 'roles': roles,
           'plan': plan}


def cards(context):
    from ....plan.analysis.cards import confirm
    record = confirm(context.target, context.out, context.language, triaged=_ran(context, 'triage'), reviewed=False)
    return {'kept': len(record['kept']), 'set_aside': len(record['set_aside']), 'doubted': len(record['doubted']),
            'design': len(record['design']), 'decided_by': record['decided_by']}


def steps(context):
    from ....plan.analysis.cards import sequence
    record = sequence(context.out, context.language, ordered=_ran(context, 'order'))
    return {'steps': len(record['steps']), 'decided_by': record['source']}


RUNNERS.update(cards=cards, steps=steps, triage=triage, order=order)


def session(context):
    """Whether the pages need a sign-in, and the one session every page stage opens them with
    (eaos/features/check/journey/runners/sign_in.py)."""
    from .sign_in import session as signed
    return signed(context)


RUNNERS['session'] = session


RUNNERS.update(translate=translate, verify=verify, journeys=journeys, architecture=architecture)


from .rules import rules  # noqa: E402  (the person's own rules, M16)
RUNNERS['rules'] = rules

"""One thin wrapper per stage. No analysis lives here; every runner calls the module that owns it.

A runner may raise SkipStage when the stage does not apply to this project — no policy declared,
no provider configured, no engine installed. That is a recorded absence, not a failure.
"""
import json
from pathlib import Path

from .live_app import NO_RUN, _keep, _live, _ran
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
    context['collected'] = collect(context.target, context.out, None, source=context['source'],
                                   exclude=context['exclude'])
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
    from ..engines_report import document
    from ..facts.store import read_set
    external = read_set(context.out, 'external')
    (context.out / 'ENGINES.md').write_text(document({'external': external}, context.language).render(), encoding='utf-8')
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
    result = start(context.target, Path(context.runtime), report=context.out, provider=context.provider or None, say=lambda n: None,
                   by_hand=(context.get('sign_in') or {}).get('how') in ('hand', 'none'))
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


def _published(context):
    """The published address the person named for this check, read by the stages that only read pages (S9)."""
    return (context.get('sign_in') or {}).get('published')


def record(context):
    """The lock run twice on today's code (eaos/behavior_lock.py run_lock): the screens and interfaces it recorded."""
    runtime = _live(context)
    if not (context.out / 'behavior-lock/plan.json').is_file():
        raise SkipStage('the program has no feature to lock', code='no_features')
    from ..behavior_lock import run_lock
    result = run_lock(context.out, context.target, runtime)
    passed = sum(r['status'] == 'passed' for r in result['results'])
    _keep(context, 'lock.json', {**result, 'specs': len(result['results']), 'passed': passed})
    return {'specs': len(result['results']), 'passed': passed}


def journeys(context):
    """Each feature's pages walked once more, rrweb recording and the trace of a failure kept, capped in size
    (eaos/behavior_lock.py run_journeys)."""
    runtime = _live(context)
    plan = json.loads((context.out / 'behavior-lock/plan.json').read_text(encoding='utf-8')) \
        if (context.out / 'behavior-lock/plan.json').is_file() else {}
    if not any(spec.get('tool') == 'playwright' and spec.get('path') for spec in plan.get('specs') or []):
        raise SkipStage('the lock has no page to walk through', code='no_pages')
    from ..behavior_lock import run_journeys
    try:
        from .live_app import shared_app
        result = run_journeys(context.out, context.target, runtime, context.out / 'live/journeys', app=shared_app(context))
    except FileNotFoundError as problem:
        raise SkipStage(str(problem)[:300], code='no_engine_installed') from None
    _keep(context, 'journeys.json', result)
    return {'specs': result['specs'], 'failed': result['failed'], 'recordings': len(result['recordings']),
            'traces': len(result['traces'])}


def screens(context):
    """Each distinct page of the running app (one picture per template: /items/1 stands for /items/2) at phone and
    desktop width, in the app's own theme, with axe; Lighthouse on the entry, unless the crawl measured it already
    (eaos/screens/audit.py, eaos/screens/crawl.py distinct). The published address the person named, read only."""
    if not _published(context): _live(context)
    groups, measured = _screen_pages(context)
    audit, speed = _audit_pages(context, groups, measured)
    if audit['status'] != 'observed':
        raise SkipStage(f"the pages could not be opened: {audit.get('reason')}"[:300], code='screens_unavailable')
    rows = [{**row, 'screenshot': Path(row['screenshot']).relative_to(context.out).as_posix() if row.get('screenshot') else None}
            for row in audit['rows']]
    _keep(context, 'screens.json', {'schema_version': 1, 'base': '/', 'tools': audit['tools'], 'rows': rows,
                                    'pages': [{'path': paths[0], 'template': template, 'same_as': paths[1:]}
                                              for template, paths in groups.items()],
                                    'lighthouse': {k: v for k, v in speed.items() if k != 'report'}})
    return {'pages': len(groups), 'screens': len(rows), 'failing': sum(bool(r.get('failures')) for r in rows),
            'lighthouse': (speed.get('scores') or {}).get('performance')}


def _screen_pages(context):
    """({template: its pages}, the crawl's measured entry or None): the app's static page routes and the crawled ones."""
    from ..lock_specs import surfaces
    from ..screens.crawl import distinct
    pages = ['/'] + [route for route, (kind, _, _) in surfaces(context.out).items()
                     if kind == 'page' and route.startswith('/') and not any(mark in route for mark in (':', '*', '['))]
    crawled = json.loads((context.out / 'live/crawl.json').read_text(encoding='utf-8'))['routes'] if _ran(context, 'crawl') else []
    pages += [row['path'] for row in crawled]
    measured = next((row for row in crawled if row.get('measured') and row.get('template') == '/'), None)
    return distinct(pages), measured


def _audit_pages(context, groups, measured):
    """(the page audit, the entry's speed) of the app running in the sandbox: Lighthouse only when the crawl did not
    measure the entry already."""
    from .live_app import shared_app
    from ..screens.audit import VIEWPORTS, lighthouse, page_audit, variants
    live, base, state = shared_app(context, published=True)
    state = state if state.is_file() else None
    folder = context.out / 'live/screens'
    audit = page_audit([base + paths[0] for paths in groups.values()], [v for v in VIEWPORTS if v['name'] != 'tablet'],
                       variants(**((live.profile.get('screens') if live else None) or {})), out=folder, storage_state=state,
                       read_only=not live)
    speed = ({'status': 'observed', 'source': 'live/crawl.json', **{k: measured.get(k) for k in ('scores', 'lcp_ms', 'cls')}}
             if measured else lighthouse(base + '/', out=folder, storage_state=state if live else None))    # published: as a visitor
    return audit, speed


def crawl(context):
    """Every page of the running app found by following its links, Lighthouse on the entry and the first page of each
    distinct template, ten at most (eaos/screens/crawl.py); the published address the person named, read only, a few."""
    if not _published(context): _live(context)
    from .live_app import shared_app
    from ..screens.crawl import crawl as find
    live, base, state = shared_app(context, published=True)
    found = find(base, context.out / 'live/crawl', storage_state=state if state.is_file() else None, read_only=not live)
    if found['status'] != 'observed':
        raise SkipStage(f"the pages could not be crawled: {found.get('reason')}"[:300], code='screens_unavailable')
    _keep(context, 'crawl.json', {'schema_version': 1, **found})
    return {'pages': len(found['routes'])}


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
    """The six indicators against their targets (eaos/sustainability.py): SUSTAINABILITY.md and sustainability.json."""
    from ..sustainability import render
    result = render(context.out, language=context.language)
    return {'measured': sum(1 for row in result['rows'] if row['measured']), 'moves': len(result['moves'])}


def transform(context):
    """A canonical home for each repeated definition and the move that gets there (eaos/transform_plan.py)."""
    from ..transform_plan import build, render
    policy_path = Path(context.policy_path) if context.policy_path else Path(context.target) / POLICY_FILE
    plan = build(context.out, policy_path=str(policy_path) if policy_path.is_file() else None)
    render(context.out, plan, language=context.language)
    return {'stages': plan['summary']['stages'], 'without_home': plan['summary']['moves_with_no_viable_candidate']}


def policy(context):
    if not context.policy_path and not (Path(context.target) / POLICY_FILE).is_file():
        raise SkipStage(f'the project declares no {POLICY_FILE}', code='no_policy')
    from ..policy import check
    result = check(context.target, context.out, policy_path=context.policy_path, language=context.language)
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
            return SkipStage(f"during the check {found['name']} stopped answering ({found['code']}): {problem}"[:300], code=found['code'])
    return SkipStage(problem, code=code)


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
                    'assistant': record['assistant'], 'model': record['model']}


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
    from ..load_report import write
    record = compute(context.out)
    record = project(record)
    if _ran(context, 'baseline'):
        measured = json.loads((context.out / 'live/baseline.json').read_text(encoding='utf-8'))
        record['measured'] = {'source': 'live/baseline.json', 'conditions': measured['conditions'],
                              'scenarios': [{'id': s['id'], 'threshold': s['threshold'], **(s.get('before') or {})}
                                            for s in measured['scenarios']]}
    write(context.out, record, language=context.language)
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
    return run(context.out, context.language)


def intake(context):
    from ..intake import write
    record = write(context.target, context.out, context.get('intake'))
    return {'answered': sum(q['status'] == 'answered' for q in record['questions']), 'scenarios': len(record['scenarios'])}


def _feature_block(feature):
    """One feature's lines in FEATURES.md: its name, critical or not, what it does, its surfaces, tables and files."""
    block = [f"## {feature['name']}"] + (['**critical**'] if feature['critical'] else []) + [feature['description'],
             'Surfaces: ' + ', '.join(f"`{s}`" for s in feature['surfaces'])]
    if feature['tables']: block.append('Tables: ' + ', '.join(f"`{t}`" for t in feature['tables']))
    if feature['files']: block.append('Files: ' + ', '.join(f"`{f}`" for f in feature['files']))
    return block + ['']


def features_markdown(record):
    """FEATURES.md within its line budget (compose/artifacts.py): every feature while they fit, then a line naming how
    many more features.json holds; the surfaces no feature claims on one line."""
    from ..compose.artifacts import BUDGETS
    budget = BUDGETS['FEATURES.md']
    tail = []
    if record['unassigned_surfaces']:
        tail = ['## Surfaces not assigned to a feature', ', '.join(f"`{s}`" for s in record['unassigned_surfaces'])]
    lines = ['# Features', '']
    for shown, feature in enumerate(record['features']):
        block = _feature_block(feature)
        if len(lines) + len(block) + len(tail) + 2 > budget:
            lines += [f"… {len(record['features']) - shown} more features in features.json", '']
            break
        lines += block
    return '\n'.join(lines + tail)


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
    (context.out / 'FEATURES.md').write_text(features_markdown(record), encoding='utf-8')
    return {'features': len(record['features']),
            'unassigned': len(record['unassigned_surfaces']),
            'critical': sum(1 for f in record['features'] if f['critical'])}


RUNNERS = {'setup': setup, 'crawl': crawl, 'record': record, 'screens': screens, 'baseline': baseline,
           'facts': facts, 'features': features, 'intake': intake, 'measure': measure, 'lock': lock, 'reports': reports,
           'engines': engines, 'policy': policy, 'claims': claims, 'probe': probe, 'load': load, 'semantic': semantic,
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
    from ..studio.export import export
    from ..workspace import write
    result = export(context.out, context.language, Path(context.target).name, context.target)
    write(context.out / 'proposals.json', result)
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

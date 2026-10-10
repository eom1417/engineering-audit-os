"""One thin wrapper per stage. No analysis lives here; every runner calls the module that owns it.

A runner may raise SkipStage when the stage does not apply to this project — no policy declared,
no provider configured, no engine installed. That is a recorded absence, not a failure.
"""
import json
from pathlib import Path

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
    entries = collect_external(context.target, context.out, context['source'], only=context.engines or None)
    if not isinstance(entries, list):
        entries = [entries]
    external_entry = None
    for entry in entries:
        add_to_index(context.out, context.target, entry)
        if entry['set'] == 'external':
            external_entry = entry
    if external_entry is None or not external_entry['available']:
        raise SkipStage('no external engine is installed', code='no_engine_installed')
    # The facts stage handed us its set list; a later stage rebuilding the dossier reads that list,
    # so the set we just added has to join it or the evidence is on disk and invisible.
    collected = context.get('collected')
    if collected is not None:
        collected['sets'] = ([row for row in collected['sets'] if row['set'] not in {e['set'] for e in entries}]
                              + entries)
    from ..engines_report import document
    from ..facts.store import read_set
    (context.out / 'ENGINES.md').write_text(
        document({'external': read_set(context.out, 'external')}, context.language).render(), encoding='utf-8')
    return {'findings': external_entry['facts']}


def verify(context):
    if not context.test_command:
        raise SkipStage('no test command was given, so nothing was executed', code='no_test_command')
    from ..verify import run
    result = run(context.target, context.out, command=context.test_command, execute=True)
    return {'covered_files': result.get('covered_files'), 'command': context.test_command}


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


def semantic(context):
    if not context.provider:
        raise SkipStage(NO_ASSISTANT, code='no_provider')
    from ..runtime.provider import Stuck
    from ..semantic import run
    from ..views import refresh
    try: result = run(context.target, context.out, context.provider, language=context.language)
    except Stuck as problem:
        raise SkipStage(str(problem), code='ai_stuck') from None
    except Exception as problem:                       # the assistant never decides the fate of the check
        raise SkipStage(f'the assistant\'s reading could not be used ({type(problem).__name__}: {problem})'[:300],
                        code='ai_failed') from None
    refresh(context.out, context.language)
    return {'hypotheses': result['claims'], 'questions': result['questions'], 'calls': result['calls']}


def _node(context, name):
    """Run one AI node of eaos/studio/nodes inside the check, with its cache and evidence check, as long as the assistant
    works; return its record and what the live map reports. Without an assistant, stuck or on a failure the rules'
    result stands."""
    if not context.provider:
        raise SkipStage(NO_ASSISTANT, code='no_provider')
    from ..studio.nodes import core, run
    record = run(context.out, names=[name], project=str(context.target), lang=context.language).get(name)
    if record is None:
        raise SkipStage('there was nothing for the assistant to decide', code='not_applicable')
    if record['method'] != 'model':
        raise SkipStage(record['why'], code='ai_stuck' if record['why'] == core.WORDS['stuck'] else 'ai_failed')
    return record, {'dropped': len(record['dropped']), 'calls': 0 if record['cached'] else record['calls'],
                    'assistant': record['assistant'], 'model': record['model']}


def ideal(context):
    """The ideal planner node (eaos/studio/nodes/ideal_planner.py) right after the check: plan, critique and the
    evidence check; the rules' target stands without it."""
    record, detail = _node(context, 'ideal_planner')
    return {'elements': record['decisions'][0]['detail']['elements'], **detail}


def triage(context):
    """The card triage node (eaos/studio/nodes/triage.py): each open card confirmed, doubted or rejected on its own
    evidence, with why in the person's words; the cards themselves stay as the engines wrote them."""
    record, detail = _node(context, 'card_triage')
    return {**{row['decision']: len(row['subjects']) for row in record['routes']}, **detail}


def order(context):
    """The plan orderer node (eaos/studio/nodes/plan_orderer.py): the order and grouping of the plan's cards, every
    prerequisite kept; the plan itself is not changed."""
    record, detail = _node(context, 'plan_orderer')
    return {'decision': record['decisions'][0]['decision'], **detail}


def load(context):
    from ..load_model import compute, project
    from ..load_report import write
    record = compute(context.out)
    record = project(record)
    write(context.out, record, language=context.language)
    return {'entry_points': len(record.get('entry_points', [])),
            'incomplete': sum(1 for e in record.get('entry_points', []) if (e.get('projection') or {}).get('incomplete'))}


def sustainability(context):
    from ..sustainability import render
    render(context.out, language=context.language)
    return {}


def transform(context):
    from ..transform_plan import build, render
    from ..guarantee import record_predictions
    policy_path = Path(context.policy_path) if context.policy_path else Path(context.target) / POLICY_FILE
    plan = build(context.out, policy_path=str(policy_path) if policy_path.is_file() else None)
    render(context.out, plan, language=context.language)
    predictions = record_predictions(context.out, plan)
    return {'moves': len(plan.get('stages', plan.get('moves', []))),
            'predictions': predictions['recorded'], 'predictions_skipped': predictions['skipped']}


def plan(context):
    from ..plan import build
    result = build(context.target, context.out, context.language)
    return {'tasks': result['tasks'], 'waves': result['waves']}


def lock(context):
    from ..behavior_lock import build
    plan = build(context.out, context.target)
    if not plan['specs']:
        raise SkipStage('the program has no feature to lock', code='no_features')
    return {'specs': len(plan['specs']), 'without_spec': sum(1 for s in plan['specs'] if not s['path'])}


def reports(context):
    from ..compose.four_reports import write
    return write(context.out, context.language)


def quality(context):
    from ..report_quality import check
    from ..engines.process import which
    if not (which('vale') or which('markdownlint-cli2')):
        raise SkipStage('neither Vale nor markdownlint-cli2 is installed', code='no_report_linters')
    record = check(context.out)
    return {'reports': len(record['reports']), 'passing': record['passing']}


def pdf(context):
    from ..compose.pdf import available, write
    reason = available(context.language)
    if reason: raise SkipStage(reason, code='pdf_unavailable')
    return {'pages': write(context.out, context.language)}


def measure(context):
    from ..measurements import run
    return run(context.out, context.language)


def intake(context):
    from ..intake import write
    record = write(context.target, context.out, context.get('intake'))
    return {'answered': sum(q['status'] == 'answered' for q in record['questions']), 'scenarios': len(record['scenarios'])}


def compose(context):
    from .. import progress
    from ..compose.product_report import render
    from ..human_report import write as human_page
    from ..start_here import start_here
    from ..studio.export import export as studio
    from ..workspace import read
    name = Path(context.target).name
    writers = (lambda: render(context.out, read(context.out / 'dossier.json'), context.language),
               lambda: human_page(context.out, context.language, name),
               lambda: studio(context.out, context.language, name, context.target),
               lambda: start_here(context.out, context.language, name))
    for done, write in enumerate(writers):
        progress.count('artifacts', done, len(writers))
        write()
    progress.count('artifacts', len(writers), len(writers))
    return {}


def execution_guide(context):
    from ..execution_guide import render
    return render(context.out, language=context.language)


def site(context):
    if not context.site:
        raise SkipStage('the site was turned off for this run', code='site_off')
    from ..site import build
    result = build(context.out)
    return {'bytes': result.get('bytes')}


def emit(context):
    from ..emit import emit as run
    written, rows = run(context.out, validate=True)
    if not written:
        raise SkipStage('no emitter applies', code='no_emitter')
    return {'files': len(written), 'accepted': sum(1 for row in rows if row['ok'])}


def validate(context):
    from ..compose.rules import validate as check
    from ..workspace import read
    from .report import document
    # RUN.md is written first so the contract checker judges it like any other artifact.
    manifest = read(context.out / 'run-manifest.json') if (context.out / 'run-manifest.json').is_file() else None
    (context.out / 'RUN.md').write_text(document(manifest or context['manifest_so_far'],
                                                 context.language).render(), encoding='utf-8')
    from ..dossier import write_verdict
    dossier = read(context.out / 'dossier.json')
    violations = check(context.out, dossier)
    write_verdict(context.out, dossier, violations, target=str(context.target))
    return {'violations': len(violations)}



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
        block = [f"## {feature['name']}"] + (['**critical**'] if feature['critical'] else []) + [feature['description'],
                 'Surfaces: ' + ', '.join(f"`{s}`" for s in feature['surfaces'])]
        if feature['tables']: block.append('Tables: ' + ', '.join(f"`{t}`" for t in feature['tables']))
        if feature['files']: block.append('Files: ' + ', '.join(f"`{f}`" for f in feature['files']))
        block.append('')
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


RUNNERS = {'facts': facts, 'features': features, 'intake': intake, 'measure': measure, 'lock': lock, 'reports': reports, 'quality': quality, 'pdf': pdf, 'engines': engines, 'verify': verify, 'policy': policy, 'claims': claims,
           'probe': probe, 'load': load, 'semantic': semantic, 'sustainability': sustainability,
           'transform': transform, 'plan': plan, 'execution_guide': execution_guide,
           'compose': compose, 'emit': emit, 'site': site, 'validate': validate}


def target(context):
    from ..target_architecture import build, render
    result = build(context.out, target=context.target)
    render(context.out, result, language=context.language)
    return {'components': len(result['components']), 'status': result['status']}


def executive(context):
    from ..executive import render
    # The transform stage wrote this run's plan; building it again took as long as that stage (45 s on EAOS itself).
    plan = json.loads((context.out / 'transform-plan.json').read_text(encoding='utf-8'))
    return render(context.out, language=context.language, transform_plan=plan)


def bundles(context):
    from ..bundles import build
    return build(context.out, language=context.language)


RUNNERS.update(target=target, executive=executive, bundles=bundles, ideal=ideal, triage=triage, order=order)

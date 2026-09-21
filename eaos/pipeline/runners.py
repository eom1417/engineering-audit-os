"""One thin wrapper per stage. No analysis lives here; every runner calls the module that owns it.

A runner may raise SkipStage when the stage does not apply to this project — no policy declared,
no provider configured, no engine installed. That is a recorded absence, not a failure.
"""
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
    return {'facts': context['collected']['facts'], 'sets': len(context['collected']['sets']),
            'exclude': context['exclude']}


def engines(context):
    if context.engines is None:
        raise SkipStage('external engines were not requested for this run')
    from ..facts.run import add_to_index, collect_external
    if 'source' not in context:
        from ..facts.source import Source
        context['source'] = Source(context.target, exclude=context.exclude, max_files=context.max_files, max_bytes=context.max_bytes)
    entry = collect_external(context.target, context.out, context['source'], only=context.engines or None)
    add_to_index(context.out, context.target, entry)
    if not entry['available']:
        raise SkipStage('no external engine is installed')
    # The facts stage handed us its set list; a later stage rebuilding the dossier reads that list,
    # so the set we just added has to join it or the evidence is on disk and invisible.
    collected = context.get('collected')
    if collected is not None:
        collected['sets'] = [row for row in collected['sets'] if row['set'] != 'external'] + [entry]
    from ..engines_report import document
    from ..facts.store import read_set
    (context.out / 'ENGINES.md').write_text(
        document({'external': read_set(context.out, 'external')}, context.language).render(), encoding='utf-8')
    return {'findings': entry['facts']}


def verify(context):
    if not context.test_command:
        raise SkipStage('no test command was given, so nothing was executed')
    from ..verify import run
    result = run(context.target, context.out, command=context.test_command, execute=True)
    return {'covered_files': result.get('covered_files'), 'command': context.test_command}


def policy(context):
    if not context.policy_path and not (Path(context.target) / POLICY_FILE).is_file():
        raise SkipStage(f'the project declares no {POLICY_FILE}')
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


def semantic(context):
    if not context.provider:
        raise SkipStage('no model provider was configured, so no interpretation was attempted')
    from ..semantic import run
    from ..views import refresh
    result = run(context.target, context.out, context.provider, language=context.language)
    refresh(context.out, context.language)
    return {'hypotheses': result.get('claims')}


def sustainability(context):
    from ..sustainability import render
    render(context.out, language=context.language)
    return {}


def transform(context):
    from ..transform_plan import build, render
    policy_path = Path(context.policy_path) if context.policy_path else Path(context.target) / POLICY_FILE
    plan = build(context.out, policy_path=str(policy_path) if policy_path.is_file() else None)
    render(context.out, plan, language=context.language)
    return {'moves': len(plan.get('stages', plan.get('moves', [])))}


def plan(context):
    from ..plan import build
    result = build(context.target, context.out, context.language)
    return {'tasks': result['tasks'], 'waves': result['waves']}


def compose(context):
    from ..compose.product_report import render
    from ..workspace import read
    render(context.out, read(context.out / 'dossier.json'), context.language)
    return {}


def site(context):
    if not context.site:
        raise SkipStage('the site was turned off for this run')
    from ..site import build
    result = build(context.out)
    return {'bytes': result.get('bytes')}


def validate(context):
    from ..compose.rules import validate as check
    from ..workspace import read, write
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


RUNNERS = {'facts': facts, 'engines': engines, 'verify': verify, 'policy': policy, 'claims': claims,
           'probe': probe, 'semantic': semantic, 'sustainability': sustainability, 'transform': transform,
           'plan': plan, 'compose': compose, 'site': site, 'validate': validate}


def target(context):
    from ..target_architecture import build, render
    result = build(context.out)
    render(context.out, result, language=context.language)
    return {'components': len(result['components']), 'status': result['status']}


def executive(context):
    from ..executive import render
    return render(context.out, language=context.language)


def bundles(context):
    from ..bundles import build
    return build(context.out, language=context.language)


RUNNERS.update(target=target, executive=executive, bundles=bundles)

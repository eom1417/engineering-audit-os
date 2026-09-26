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
    # A tree with no source file to read is not an audited project, whatever its history says:
    # an empty checkout used to be reported COMPLETE, with claims drawn from git history alone.
    from ..vocabulary import classify
    if not any(classify(item['path']) == 'source' for item in context['source'].readable()):
        raise SkipStage('the target holds no source file this tool reads, so no project was audited')
    return {'facts': context['collected']['facts'], 'sets': len(context['collected']['sets']),
            'exclude': context['exclude']}


def engines(context):
    if context.engines is None:
        raise SkipStage('external engines were not requested for this run')
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
        raise SkipStage('no external engine is installed')
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
        raise SkipStage('the program has no feature to lock')
    return {'specs': len(plan['specs']), 'without_spec': sum(1 for s in plan['specs'] if not s['path'])}


def measure(context):
    from ..measurements import run
    return run(context.out, context.language)


def intake(context):
    from ..intake import write
    record = write(context.target, context.out, context.get('intake'))
    return {'answered': sum(q['status'] == 'answered' for q in record['questions']), 'scenarios': len(record['scenarios'])}


def compose(context):
    from ..compose.product_report import render
    from ..workspace import read
    render(context.out, read(context.out / 'dossier.json'), context.language)
    return {}


def execution_guide(context):
    from ..execution_guide import render
    return render(context.out, language=context.language)


def site(context):
    if not context.site:
        raise SkipStage('the site was turned off for this run')
    from ..site import build
    result = build(context.out)
    return {'bytes': result.get('bytes')}


def emit(context):
    from ..emit import emit as run
    written, rows = run(context.out, validate=True)
    if not written:
        raise SkipStage('no emitter applies')
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
    md_lines = ['# Features', '']
    for feature in record['features']:
        md_lines.append(f"## {feature['name']}")
        if feature['critical']: md_lines.append('**critical**')
        md_lines.append(feature['description'])
        md_lines.append('Surfaces: ' + ', '.join(f"`{s}`" for s in feature['surfaces']))
        if feature['tables']:
            md_lines.append('Tables: ' + ', '.join(f"`{t}`" for t in feature['tables']))
        if feature['files']:
            md_lines.append('Files: ' + ', '.join(f"`{f}`" for f in feature['files']))
        md_lines.append('')
    if record['unassigned_surfaces']:
        md_lines.append('## Surfaces not assigned to a feature')
        for s in record['unassigned_surfaces']:
            md_lines.append(f"- `{s}`")
    (context.out / 'FEATURES.md').write_text('\n'.join(md_lines), encoding='utf-8')
    return {'features': len(record['features']),
            'unassigned': len(record['unassigned_surfaces']),
            'critical': sum(1 for f in record['features'] if f['critical'])}


RUNNERS = {'facts': facts, 'features': features, 'intake': intake, 'measure': measure, 'lock': lock, 'engines': engines, 'verify': verify, 'policy': policy, 'claims': claims,
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
    return render(context.out, language=context.language)


def bundles(context):
    from ..bundles import build
    return build(context.out, language=context.language)


RUNNERS.update(target=target, executive=executive, bundles=bundles)

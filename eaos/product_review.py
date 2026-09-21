"""One entry point for the output-first dossier, plan and browsable report."""
from pathlib import Path
from .workspace import read, write

GOALS = {'onboarding', 'debugging', 'evolution', 'architecture'}


def run(target, out, *, goal='evolution', language='ar', provider=None, exclude=(), audit_run=None):
    if goal not in GOALS: raise ValueError('Unknown review goal')
    target, out = Path(target).resolve(), Path(out).resolve()
    if out == target or target in out.parents:
        raise ValueError('Review output must be outside the target to avoid analyzing generated artifacts')
    from .dossier import assemble
    from .plan import build
    from .site import build as build_site
    result = assemble(target, out, run=audit_run, language=language, exclude=exclude)
    dossier = read(out / 'dossier.json')
    dossier['review_goal'] = goal
    write(out / 'dossier.json', dossier)
    if provider:
        from .semantic import run as interpret
        interpret(target, out, provider, language=language)
        from .views import refresh
        refresh(out, language)
    build(target, out, language)
    dossier = read(out / 'dossier.json')
    from .compose.product_report import render
    render(out, dossier, language)
    site = build_site(out)
    from .compose.rules import validate
    violations = validate(out, dossier)
    summary = {'target': str(target), 'out': str(out), 'goal': goal,
               'mode': 'semantic_review' if provider else 'facts_only',
               'report': str(out / 'PRODUCT-REPORT.md'), 'site': site,
               'decision_counts': {kind: sum(row['kind'] == kind for row in dossier['decisions'])
                                   for kind in ('repair', 'investigate', 'retain')},
               'executable_repairs': sum(task.get('decision', {}).get('readiness') == 'ready' for task in dossier['tasks']),
               'output_spec_violations': violations,
               'status': 'REVIEW_REQUIRED' if not violations else 'OUTPUT_SPEC_VIOLATED'}
    write(out / 'product-review.json', summary)
    return summary

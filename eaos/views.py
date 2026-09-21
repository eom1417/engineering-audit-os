"""Keep every rendered view agreeing with the ledger, in one direction only.

A probe verdict, a semantic pass or a regenerated plan all change dossier.json. Whatever reads
from it has to be rebuilt afterwards, and the module that rebuilds everything must sit above the
modules it rebuilds — otherwise the dependency runs both ways and nothing can be changed alone.
"""
from pathlib import Path
from .dossier import refresh_views
from .workspace import read, write


def refresh(out, language='ar', target=None):
    out = Path(out)
    summary = refresh_views(out, language)
    dossier = read(out / 'dossier.json')
    if dossier.get('plan_contract_version') == 1 or (out / 'plan.json').is_file():
        from .plan import rebuild
        summary['tasks'] = rebuild(out, dossier, language, target)
        dossier = read(out / 'dossier.json')
        summary['refreshed'].append('PLAN/')
    if (out / 'PRODUCT-REPORT.md').is_file():
        from .compose.product_report import render
        render(out, dossier, language)
        summary['refreshed'].append('PRODUCT-REPORT.md')
    if (out / 'index.html').is_file():
        from .site import build
        build(out)
        summary['refreshed'].append('index.html')
    return summary

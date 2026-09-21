"""ENGINES.md: which external engines ran, what they could see, and where they disagree.

The disagreements are the point. A reader who only sees the agreements learns that four tools
found the same hotspots; a reader who sees the contradictions learns which claim needs settling.
"""
from .compose import Document

TITLE = {'ar': 'المحرّكات الخارجية', 'en': 'External engines'}
WORDS = {
    'ar': {'engine': 'المحرك', 'version': 'الإصدار', 'status': 'الحالة', 'evaluated': 'ما فحصه',
           'findings': 'النتائج', 'place': 'الموضع', 'kind': 'النوع', 'verdict': 'الحكم',
           'asserted': 'يؤكده', 'denied': 'ينفيه', 'engines': 'المحركات',
           'header': 'الأدلة هنا من محرّكات لم نكتب قواعدها؛ تدخل كأدلة استدلالية، والتعاضد يرفعها والفحص يحسمها.',
           'coverage': 'التغطية', 'contested': 'محل تنازع', 'clusters': 'المواضع المرتبطة',
           'none': 'لم يُشغَّل أي محرك خارجي في هذه الدورة.'},
    'en': {'engine': 'Engine', 'version': 'Version', 'status': 'Status', 'evaluated': 'Evaluated',
           'findings': 'Findings', 'place': 'Place', 'kind': 'Kind', 'verdict': 'Verdict',
           'asserted': 'Asserted by', 'denied': 'Denied by', 'engines': 'Engines',
           'header': 'This evidence comes from engines whose rules we did not write: it enters as heuristic, '
                     'corroboration raises it, and a probe settles it.',
           'coverage': 'Coverage', 'contested': 'Contested', 'clusters': 'Correlated places',
           'none': 'No external engine ran in this cycle.'},
}


def document(sets, language='ar'):
    from .correlate import clusters, CONTESTED, GRANULARITY_GAP
    words = WORDS.get(language, WORDS['ar'])
    doc = Document(TITLE.get(language, TITLE['ar']), language, budget_lines=200)
    external = sets.get('external') or {}
    summary = external.get('summary') or {}
    if not external.get('facts'):
        doc.text(words['none'])
        return doc
    doc.header([words['header']])
    doc.section(words['coverage'])
    evaluated = summary.get('evaluated_kinds', {})
    doc.table([words['engine'], words['evaluated'], words['findings']],
              [[name, ', '.join(f"{kind}:{detail['status']}@{detail['granularity']}"
                                if isinstance(detail, dict) else f'{kind}:{detail}'
                                for kind, detail in sorted(evaluated.get(name, {}).items())) or '—',
                str(summary.get('by_engine', {}).get(name, 0))]
               for name in summary.get('engines_observed', [])])
    if summary.get('engines_unavailable'):
        doc.bullets([f"{name}: {words['status']} unavailable" for name in summary['engines_unavailable']])
    built = clusters(sets)
    contested = [(cluster, kind, detail) for cluster in built
                 for kind, detail in sorted(cluster['corroboration'].items())
                 if detail['verdict'] in (CONTESTED, GRANULARITY_GAP)]
    if contested:
        doc.section(words['contested'])
        doc.table([words['place'], words['kind'], words['verdict'], words['asserted'], words['denied']],
                  [[cluster['place'], kind, detail['verdict'],
                    ', '.join(detail['asserted_by']) + '@' + (', '.join(detail['asserted_at']) or '?'),
                    ', '.join(detail['denied_by'] or detail['silent_at_another_resolution'])]
                   for cluster, kind, detail in contested], limit=20)
    doc.section(words['clusters'])
    doc.table([words['place'], words['engines'], words['kind']],
              [[cluster['place'], ', '.join(cluster['engines']), ', '.join(cluster['kinds'])]
               for cluster in built if len(cluster['engines']) > 1], limit=40)
    return doc

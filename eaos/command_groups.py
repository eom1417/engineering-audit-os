"""Which command belongs to which surface, so `eaos --help` reads as a map rather than a list.

Thirty-eight commands in one alphabetical block tell a reader nothing about which of them is the
one to run. These groups say what each surface is for and which workspace it operates in.
"""
GROUPS = (
    ('run', 'تشغيل التدقيق', 'Run an audit',
     ('audit', 'review-project', 'stages', 'engines')),
    ('inspect', 'استعلام عن مشروع', 'Ask a question about a project',
     ('facts', 'map', 'dossier', 'probe', 'verify', 'semantic', 'ask', 'impact-of', 'tasks', 'site')),
    ('assess', 'تقييم واتجاه', 'Assess and propose a direction',
     ('sustainability', 'transform-plan', 'target-architecture', 'executive', 'bundles',
      'simulate', 'guarantee', 'progress', 'review')),
    ('govern', 'حوكمة وانحراف', 'Govern and detect drift',
     ('policy', 'delta', 'api-diff', 'acceptance', 'decision-review', 'evaluate')),
    ('repair', 'إصلاح يقوده نموذج (مساحة عمل منفصلة عبر eaos init)', 'Model-driven repair (separate workspace via eaos init)',
     ('init', 'run', 'continue', 'implement', 'improve', 'packet', 'graph', 'impact', 'context')),
)


def group_of(command):
    for key, _, _, members in GROUPS:
        if command in members:
            return key
    return None


def epilog(language='ar'):
    lines = ['المجموعات:' if language == 'ar' else 'Command groups:']
    for _, arabic, english, members in GROUPS:
        lines.append(f"  {(arabic if language == 'ar' else english)}")
        lines.append('    ' + '  '.join(members))
    return '\n'.join(lines)

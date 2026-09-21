"""The one-page product report, rendered from the ledger like every other view."""
from pathlib import Path
from . import Document


def render(out, dossier, language='ar'):
    ar = language == 'ar'
    document = Document('تقرير فهم المشروع وخطة تطويره' if ar else 'Project understanding and development plan', language, 180)
    document.header([('هدف المراجعة: ' if ar else 'Review goal: ') + dossier.get('review_goal', 'evolution'),
                     ('فحص حتمي؛ الفهم الدلالي لم يُشغّل.' if ar else 'Deterministic review; semantic interpretation was not run.')
                     if not dossier['provenance'].get('model_calls') else
                     ('الاستنتاجات الدلالية تحتاج تحققًا مستقلًا.' if ar else 'Semantic interpretations need independent verification.')])
    document.section('1. القرار والخطوة التالية' if ar else '1. Decision and next action')
    tasks = dossier.get('tasks', [])
    decisions = dossier.get('decisions', [])
    if not tasks:
        document.text('لا يوجد تغيير مبرر ضمن نطاق الفحص؛ لا تعني هذه النتيجة سلامة الأجزاء غير المفحوصة.' if ar else
                      'No justified change in the examined scope; unexamined behavior remains unknown.')
    else:
        document.table(['#', 'النوع' if ar else 'Kind', 'الحالة' if ar else 'Readiness', 'التفصيل' if ar else 'Details'],
                       [[task['id'], task['decision']['kind'], task['decision']['readiness'],
                         f"[{task['title'][:100]}](PLAN/{task['id']}.md)"] for task in tasks], limit=10)
    document.section('2. كيف يعمل النظام' if ar else '2. How the system works')
    document.text(dossier['description'])
    document.bullets(['[SYSTEM-MAP.md](SYSTEM-MAP.md)', '[FLOWS.md](FLOWS.md)', '[CONTRACTS.md](CONTRACTS.md)'])
    document.section('3. ما نحتفظ به وما يحتاج تحقيقًا' if ar else '3. Preserve and investigate')
    document.text(('قرارات الإبقاء: ' if ar else 'Retain decisions: ') + str(sum(row['kind'] == 'retain' for row in decisions)))
    document.bullets(['[RISK-REGISTER.md](RISK-REGISTER.md)', '[DECISION-BRIEF.md](DECISION-BRIEF.md)'])
    document.section('4. ترتيب العمل والتحقق' if ar else '4. Work sequence and verification')
    document.text('[PLAN/WAVES.md](PLAN/WAVES.md) · [VERIFICATION-MAP.md](VERIFICATION-MAP.md)')
    document.text('التحقيق قد ينتهي بالإبقاء. مهام الإصلاح المحجوبة لا تُنفّذ قبل استكمال أدلتها وفحوصها.' if ar else
                  'Investigations may conclude no change. Blocked repairs need their evidence and checks completed.')
    # No truncation of blockers: detailed complete list remains a first-class artifact.
    blockers = [(task['id'], reason) for task in tasks for reason in task['decision']['blockers']]
    lines = ['# Blockers / عوائق الجاهزية', ''] + [f'- {task}: {reason}' for task, reason in blockers]
    if not blockers: lines.append('No recorded repair blockers / لا توجد عوائق إصلاح مسجلة')
    (Path(out) / 'BLOCKERS.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    document.text(f"[BLOCKERS.md](BLOCKERS.md): {len(blockers)}")
    document.section('5. حدود الثقة' if ar else '5. Confidence limits')
    document.bullets(dossier['coverage']['not_examined'])
    document.text('[PROVENANCE.md](PROVENANCE.md) · [dossier.json](dossier.json)')
    (Path(out) / 'PRODUCT-REPORT.md').write_text(document.render(), encoding='utf-8')

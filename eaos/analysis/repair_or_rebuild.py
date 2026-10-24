"""Repair or rebuild (M4.5, docs/NORTH-STAR.md journey 1): the decision, with the time and effort of each option.

    repair    fix the plan's open cards in batches (eaos/journeys/waves): the cards, their sizes (S/M/L), the files
              they touch, and the minutes of fixing them
    rebuild   write the code again from the ideal picture: every file of today's components, the minutes of writing
              each anew and proving it as a fix is proved

The decision stands on the target (target-architecture.json), not on the minutes: rebuild when the target itself
rebuilds or deletes most of today's files (REBUILD_SHARE); else repair, the rebuilt components done Strangler Fig as
the plan says. The minutes are a rough rule until this project's own fix runs measure it (`FIX_MINUTES`, also the fix
preview's, eaos/journeys/selection.py estimate); they are said as such, never as a measure.
"""
import json
from pathlib import Path

# minutes a card takes to fix behind every gate, low and high, and the safe copy prepared once (the rough rule)
FIX_MINUTES, PREPARE_MINUTES = (3, 8), (5, 15)
# writing a file anew from the ideal is about twice fixing one: there is no code to start from
REBUILD_FACTOR = 2
REBUILD_SHARE = 0.5
GONE = ('rebuild', 'delete')


def fix_minutes(count, factor=1):
    """(low, high) minutes of fixing `count` cards (or rebuilding as many files, `factor` 2) by the rough rule."""
    return (PREPARE_MINUTES[0] + factor * FIX_MINUTES[0] * count, PREPARE_MINUTES[1] + factor * FIX_MINUTES[1] * count)


def _read(path, empty):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return empty


def decide(report):
    """{recommend, share_gone, options: {repair, rebuild}, why: {ar, en}, basis: {ar, en}} of a report; None when it
    has no target yet."""
    report = Path(report)
    components = (_read(report / 'target-architecture.json', {}) or {}).get('current_components') or []
    if not components: return None
    files, gone = _files(components), _files(c for c in components if c.get('relation') in GONE)
    share = round(gone / files, 2) if files else 0.0
    recommend = 'rebuild' if share >= REBUILD_SHARE else 'repair'
    return {'recommend': recommend, 'share_gone': share,
            'options': {'repair': _repair(report),
                        'rebuild': {'components': len(components), 'files': files, 'minutes': fix_minutes(files, REBUILD_FACTOR)}},
            'why': _why(recommend, share, gone, files), 'basis': BASIS}


def _files(components):
    return sum(c.get('files') or 0 for c in components)


def _repair(report):
    """The repair option: the plan's open cards, their sizes, the files they touch and the minutes of fixing them."""
    tasks = [t for t in (_read(report / 'plan.json', {}) or {}).get('tasks') or [] if t.get('state', 'open') == 'open']
    sizes = [t.get('effort') for t in tasks]
    return {'cards': len(tasks), 'sizes': {size: sizes.count(size) for size in ('S', 'M', 'L')},
            'files': len({p for t in tasks for p in t.get('paths') or []}), 'minutes': fix_minutes(len(tasks))}


def _why(recommend, share, gone, files):
    percent = round(share * 100)
    if recommend == 'rebuild':
        return {'en': f'The target rebuilds or deletes {gone} of today\'s {files} files ({percent}%): writing the code again from the ideal is the shorter road.',
                'ar': f'البنية المستهدفة تعيد بناء أو تحذف {gone} من {files} ملفًا اليوم ({percent}%): كتابة الكود من جديد من الصورة المثالية أقصر طريق.'}
    return {'en': f'The target keeps or improves most of today\'s code: it rebuilds or deletes {gone} of {files} files ({percent}%), so repairing it is the shorter, safer road.',
            'ar': f'البنية المستهدفة تبقي أغلب الكود الحالي أو تحسّنه: تعيد بناء أو تحذف {gone} من {files} ملفًا ({percent}%)، فالإصلاح أقصر وأأمن.'}


BASIS = {'en': 'A rough rule, not a measure: 3 to 8 minutes a card, and twice that a file written anew, plus preparing the safe copy; '
               'it improves with your own fix runs.',
         'ar': 'تقدير تقريبي، لا قياس: من 3 إلى 8 دقائق للبطاقة، وضعفها لكل ملف يُكتب من جديد، مع تجهيز النسخة الآمنة؛ يتحسن مع تشغيلات الإصلاح عندك.'}

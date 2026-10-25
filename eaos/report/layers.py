"""The system in layers for people (M6.11): read from layers.json (eaos/analysis/layers/), computed nowhere here.

    critical(report, lang)   the broken critical boundaries (high), one red line each, for the top of START-HERE.md
    lines(report, lang)      each boundary with its state in plain words, and how the files sit in their layers
"""
import json
from pathlib import Path

from ..analysis.layers.catalog import BOUNDARIES

CRITICAL_SHOWN = 5


def read(report):
    try: return json.loads((Path(report) / 'layers.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


def _say(ar, arabic, english): return arabic if ar else english


def critical(report, lang):
    """The red lines: each high-severity finding of the layers, the most first-hand (live) ones first."""
    record, ar = read(report), lang == 'ar'
    if not record: return []
    high = sorted((f for f in record['findings'] if f['severity'] == 'high'), key=lambda f: (not f.get('live'), f['boundary']))
    if not high: return []
    shown = [f"- 🔴 {f['ar' if ar else 'en']}" for f in high[:CRITICAL_SHOWN]]
    more = len(high) - CRITICAL_SHOWN
    return ['## ' + _say(ar, '🔴 حدود حرجة مكسورة', '🔴 Broken critical boundaries'), '', *shown,
            *([_say(ar, f'- و{more} غيرها في قسم الطبقات أدناه.', f'- and {more} more in the layers section below.')] if more > 0 else []), '']


def _state(record, boundary, ar):
    found = [f for f in record['findings'] if f['boundary'] == boundary]
    if not found: return _say(ar, 'سليم: لم أجد شيئًا', 'sound: nothing found'), ''
    high = sum(f['severity'] == 'high' for f in found)
    said = _say(ar, f'{len(found)} ملاحظة' + (f'، منها {high} حرجة' if high else ''), f'{len(found)} finding(s)' + (f', {high} critical' if high else ''))
    return said, found[0]['ar' if ar else 'en']


def _map_line(record, ar):
    files, gaps = len(record['map']), len(record['gaps'])
    kind = record.get('type') or _say(ar, 'لا نوع مرجعي', 'no reference type')
    return _say(ar, f'نوع المشروع المرجعي: {kind}. وُضع {files - gaps} من {files} ملفًا في طبقته'
                    + (f'، و{gaps} بلا طبقة (فجوة مذكورة)' if gaps else '') + f'؛ {len(record["endpoints"])} نقطة طلب، {len(record["tables"])} جدولًا.',
                f'Reference type: {kind}. {files - gaps} of {files} files placed in their layer'
                + (f', {gaps} in none (a listed gap)' if gaps else '') + f'; {len(record["endpoints"])} endpoints, {len(record["tables"])} tables.')


def lines(report, lang):
    """The layers section of START-HERE.md: one row per boundary, the questions EAOS could not decide, the map's size."""
    record, ar = read(report), lang == 'ar'
    if not record: return []
    rows = [f"| {BOUNDARIES[b][1 if ar else 0]} | {state} | {first} |" for b in BOUNDARIES for state, first in [_state(record, b, ar)]]
    asked = [f"- {q['question_ar' if ar else 'question']}" for q in record['questions'][:5]]
    live = record.get('live')
    tried = (_say(ar, 'وجُرّبت الحدود على نسخة معزولة من تطبيقك.', 'The boundaries were also tried on an isolated copy of your app.') if live
             else _say(ar, 'لم تُجرَّب الحدود على التطبيق وهو يعمل: اختر «تجربة حدود الطبقات» في الفحص القادم.',
                       'The boundaries were not tried on the running app: choose "Try the layers" in the next check.'))
    return ['## ' + _say(ar, 'النظام طبقات', 'The system in layers'), '', _map_line(record, ar) + ' ' + tried, '',
            '| ' + _say(ar, 'الحد', 'Boundary') + ' | ' + _say(ar, 'حالته', 'State') + ' | ' + _say(ar, 'أول ما وجدت', 'First found') + ' |',
            '|---|---|---|', *rows, '',
            *(['### ' + _say(ar, 'أسئلة لم أستطع حسمها', 'Questions I could not decide'), '', *asked, ''] if asked else [])]

"""Render LOAD-MODEL.md from the load-model.json record."""
from pathlib import Path
import json


def render(record, language='en'):
    """Return the markdown body for LOAD-MODEL.md.

    The report is short on purpose: a table of entries ranked by load cost, then
    the worst five with their full detail, then what we could not measure and why.
    Every claim carries the fact IDs it came from so the reader can verify them.
    """
    entries = record.get('entry_points', [])
    # Sort by projection.cost_score descending; entries with no projection go to the end
    def _key(entry):
        p = entry.get('projection') or {}
        return -p.get('cost_score', -1e9)
    ranked = sorted(entries, key=_key)

    lines = ['# Load Model', '',
             '> A structural projection of how each entry point scales. This is not a performance '
             'test; the numbers are a stated heuristic that ranks entries and names bottlenecks. '
             'Every figure below carries the fact IDs that justify it.',
             '']

    if record.get('projection'):
        method = record['projection'].get('method', '')
        if method:
            lines += ['## Method', '', method, '']

    if not ranked:
        lines += ['## Entry points', '',
                  'No non-test entry point was detected in this project. The eight load-model '
                  'questions apply once entry points exist.', '']
        return '\n'.join(lines) + '\n'

    lines += ['## Entry points ranked by load risk', '',
              '| Rank | Entry | Surface | Path | Cost | Incomplete | Bottlenecks |',
              '| --- | --- | --- | --- | --- | --- | --- |']
    for index, entry in enumerate(ranked, start=1):
        projection = entry.get('projection') or {}
        cost = projection.get('cost_score')
        cost_str = f'{cost:.2f}' if isinstance(cost, (int, float)) else '—'
        incomplete = 'yes' if projection.get('incomplete') else 'no'
        bottlenecks = ', '.join(projection.get('bottlenecks') or []) or '—'
        # The label names the entry point. The fact id named the record, which told a reader
        # ranking their riskiest entry points nothing about which entry point it was.
        label = entry.get('label') or entry.get('handler') or entry.get('id', '?')
        lines.append(f'| {index} | {label} | {entry.get("surface", "—")} | `{entry.get("path", "?")}` '
                     f'| {cost_str} | {incomplete} | {bottlenecks} |')
    lines.append('')

    worst = ranked[:5]
    lines += ['## Worst five in detail', '']
    for entry in worst:
        lines.append(f"### {entry.get('id', '?')} — `{entry.get('path', '?')}`")
        lines.append('')
        projection = entry.get('projection') or {}
        if projection.get('interpretation'):
            lines.append(projection['interpretation'])
            lines.append('')
        if projection.get('incomplete'):
            lines.append('**This entry\'s projection is incomplete.** '
                         + "Unanswered questions: "
                         + ', '.join(projection.get('unanswered_questions', [])))
            lines.append('')
        lines += ['| Question | Status | Value | Evidence |', '| --- | --- | --- | --- |']
        for question, answer in (entry.get('answers') or {}).items():
            status = answer.get('status', '?')
            value = answer.get('value')
            if isinstance(value, dict):
                value = ', '.join(f'{k}={v}' for k, v in value.items())
            evidence = ', '.join(answer.get('evidence') or []) or '—'
            lines.append(f'| {question} | {status} | {value} | {evidence} |')
        lines.append('')

    # One line per unanswered question per entry point grows with the project: 342 lines on this
    # repository alone. The reasons repeat, so the document counts them and the record keeps each one.
    gaps = {}
    for entry in ranked:
        for question, answer in (entry.get('answers') or {}).items():
            if answer.get('status') in ('undetectable', 'not_applicable') and answer.get('reason'):
                key = (question, answer['reason'])
                gaps.setdefault(key, []).append(entry.get('id', '?'))
    lines += ['## What we could not measure and why', '']
    if not gaps:
        lines += ['Every question was answered for every entry point.', '']
    else:
        lines += ['| Question | Reason | Entry points |', '| --- | --- | --- |']
        for (question, reason), entries in sorted(gaps.items(), key=lambda row: (-len(row[1]), row[0])):
            shown = ', '.join(entries[:3]) + (f' and {len(entries) - 3} more' if len(entries) > 3 else '')
            lines.append(f'| {question} | {reason} | {len(entries)}: {shown} |')
        lines += ['', 'Every entry point and every reason is in `load-model.json`.', '']

    return '\n'.join(lines) + '\n'


def write(out, record, language='en'):
    Path(out, 'LOAD-MODEL.md').write_text(render(record, language=language), encoding='utf-8')
    Path(out, 'load-model.json').write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

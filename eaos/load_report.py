"""Render LOAD-MODEL.md from the load-model.json record."""
from pathlib import Path
import json


TABLE_ROWS = 40

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

    lines = _header(record)
    if not ranked:
        lines += ['## Entry points', '',
                  'No non-test entry point was detected in this project. The eight load-model '
                  'questions apply once entry points exist.', '']
        return '\n'.join(lines) + '\n'
    lines += _ranked_table(ranked)
    lines += ['## Worst five in detail', '']
    for entry in ranked[:5]: lines += _in_detail(entry)
    lines += _not_measured(ranked)
    return '\n'.join(lines) + '\n'


def _header(record):
    """The title, what the projection is, the runs measured under load and the method."""
    lines = ['# Load Model', '',
             '> A structural projection of how each entry point scales. This is not a performance '
             'test; the numbers are a stated heuristic that ranks entries and names bottlenecks. '
             'Every figure below carries the fact IDs that justify it.',
             '']
    for scenario in (record.get('measured') or {}).get('scenarios') or []:
        lines += [f"Measured under load ({scenario['id']}, k6 on the production build): p95 "
                  f"{scenario.get('p95_ms')} ms against a threshold of {scenario.get('threshold')} ms (live/baseline.json).", '']
    method = (record.get('projection') or {}).get('method', '')
    if method:
        lines += ['## Method', '', method, '']
    return lines


def _ranked_row(index, entry):
    projection = entry.get('projection') or {}
    cost = projection.get('cost_score')
    cost_str = f'{cost:.2f}' if isinstance(cost, (int, float)) else '—'
    incomplete = 'yes' if projection.get('incomplete') else 'no'
    bottlenecks = ', '.join(projection.get('bottlenecks') or []) or '—'
    # The label names the entry point. The fact id named the record, which told a reader
    # ranking their riskiest entry points nothing about which entry point it was.
    label = entry.get('label') or entry.get('handler') or entry.get('id', '?')
    return (f'| {index} | {label} | {entry.get("surface", "—")} | `{entry.get("path", "?")}` '
            f'| {cost_str} | {incomplete} | {bottlenecks} |')


def _ranked_table(ranked):
    lines = ['## Entry points ranked by load risk', '',
             '| Rank | Entry | Surface | Path | Cost | Incomplete | Bottlenecks |',
             '| --- | --- | --- | --- | --- | --- | --- |']
    # The table grows with the project; the riskiest entry points are what a reader ranks, and the record keeps all.
    lines += [_ranked_row(index, entry) for index, entry in enumerate(ranked[:TABLE_ROWS], start=1)]
    if len(ranked) > TABLE_ROWS:
        lines += ['', f'The {len(ranked) - TABLE_ROWS} entry points ranked below these are in `load-model.json`.']
    lines.append('')
    return lines


def _answer_row(question, answer):
    value = answer.get('value')
    if isinstance(value, dict):
        value = ', '.join(f'{k}={v}' for k, v in value.items())
    evidence = ', '.join(answer.get('evidence') or []) or '—'
    return f'| {question} | {answer.get("status", "?")} | {value} | {evidence} |'


def _in_detail(entry):
    """One of the worst entry points: what its projection says, and the answer to each question with its evidence."""
    lines = [f"### {entry.get('id', '?')} — `{entry.get('path', '?')}`", '']
    projection = entry.get('projection') or {}
    if projection.get('interpretation'):
        lines += [projection['interpretation'], '']
    if projection.get('incomplete'):
        lines += ['**This entry\'s projection is incomplete.** '
                  + "Unanswered questions: "
                  + ', '.join(projection.get('unanswered_questions', [])), '']
    lines += ['| Question | Status | Value | Evidence |', '| --- | --- | --- | --- |']
    lines += [_answer_row(question, answer) for question, answer in (entry.get('answers') or {}).items()]
    lines.append('')
    return lines


def _not_measured(ranked):
    # One line per unanswered question per entry point grows with the project: 342 lines on this
    # repository alone. The reasons repeat, so the document counts them and the record keeps each one.
    gaps = {}
    for entry in ranked:
        for question, answer in (entry.get('answers') or {}).items():
            if answer.get('status') in ('undetectable', 'not_applicable') and answer.get('reason'):
                gaps.setdefault((question, answer['reason']), []).append(entry.get('id', '?'))
    lines = ['## What we could not measure and why', '']
    if not gaps:
        return lines + ['Every question was answered for every entry point.', '']
    lines += ['| Question | Reason | Entry points |', '| --- | --- | --- |']
    for (question, reason), entries in sorted(gaps.items(), key=lambda row: (-len(row[1]), row[0])):
        shown = ', '.join(entries[:3]) + (f' and {len(entries) - 3} more' if len(entries) > 3 else '')
        lines.append(f'| {question} | {reason} | {len(entries)}: {shown} |')
    return lines + ['', 'Every entry point and every reason is in `load-model.json`.', '']


def write(out, record, language='en'):
    Path(out, 'LOAD-MODEL.md').write_text(render(record, language=language), encoding='utf-8')
    Path(out, 'load-model.json').write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

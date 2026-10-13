"""TARGET-ARCHITECTURE.md and target-architecture.json: the target architecture's record (eaos/target_architecture.py)
written for people. The component inventory belongs in the record; the document names the shape of the target.
"""
import json
from collections import defaultdict
from pathlib import Path

from .target_architecture import render_decisions

SHOWN_COMPONENTS = 12
SHOWN_DECISIONS = 8


def clip_why(text, limit=160):
    text = ' '.join(str(text or '').split())
    return text if len(text) <= limit else text[:limit - 1] + '…'


def render(out, target, language='ar'):
    """Render the target architecture as a Markdown document."""
    ar = language == 'ar'
    render_decisions(out, target['decisions'])
    lines = []
    if ar:
        lines += ['# البنية المستهدفة', '',
                  '> جرد المصدر منفصل عن التصميم المستهدف؛ ما لم يُحدد ويُراجع يبقى فجوة.', '']
    else:
        lines += ['# Target architecture', '',
                  '> Source inventory and reviewed target proposals are separate. Unspecified targets remain gaps.', '']
    if target.get('reference'): lines += _reference_section(target, ar)
    lines += _who_section(target, language, ar) + _components_section(target, language, ar) + _decisions_section(target, ar)
    lines += ['', '## ' + ('مصفوفة الفجوة' if ar else 'Gap matrix')]
    covered = sum(1 for row in target['gap_matrix'] if row['gap'] == 'covered')
    lines += [f"- {'مغطى' if ar else 'covered'}: {covered} / {len(target['gap_matrix'])}"]
    Path(out, 'TARGET-ARCHITECTURE.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    Path(out, 'target-architecture.json').write_text(json.dumps(target, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'markdown': str(Path(out, 'TARGET-ARCHITECTURE.md')),
            'json': str(Path(out, 'target-architecture.json'))}


def _reference_section(target, ar):
    """The reference type, its largest target components and the infrastructure decisions."""
    lines = ['## ' + ('النوع المرجعي والمكوّنات المستهدفة' if ar else 'Reference type and target components'), '',
             (f"النوع: `{target['reference']}` (وحدة واحدة معيارية). {len(target['target_components'])} مكوّنًا مستهدفًا، "
              f"و{target.get('forbidden_edges', 0)} استيرادًا ممنوعًا تزيله الخطة." if ar else
              f"Type: `{target['reference']}` (a modular monolith). {len(target['target_components'])} target components; "
              f"{target.get('forbidden_edges', 0)} forbidden imports the plan removes."), '',
             '| ' + (' | '.join(['المكوّن', 'الطبقة', 'الملفات', 'تنتقل إليه', 'استيرادات ممنوعة']) if ar else
                    ' | '.join(['Component', 'Layer', 'Files', 'Moving in', 'Forbidden imports'])) + ' |',
             '|---|---|---:|---:|---:|']
    shown = sorted(target['target_components'], key=lambda c: (-c.get('moves_in', 0), -c.get('files', 0), c['name']))[:15]
    for component in shown:
        lines.append(f"| `{component['name']}` | {component['layer']} | {component.get('files', 0)} | "
                     f"{component.get('moves_in', 0)} | {component.get('forbidden_edges_removed', 0)} |")
    if len(target['target_components']) > len(shown):
        lines += ['', (f"عُرض {len(shown)} من {len(target['target_components'])}؛ البقية في `target-architecture.json`." if ar else
                       f"Showing {len(shown)} of {len(target['target_components'])}; the rest are in `target-architecture.json`.")]
    lines += ['', '## ' + ('قرارات البنية التحتية' if ar else 'Infrastructure decisions'), '']
    for item in target.get('infrastructure') or []:
        mark = '✅' if item['present'] else '⬜'
        tool = item['tool'] or (('بلا أداة: ' if ar else 'no tool: ') + (item.get('tool_reason') or ''))
        lines.append(f"- {mark} **{item['area']}**: {item['decision']} ({tool}). "
                     + ('الدليل: ' if ar else 'Evidence: ') + item['evidence'])
    return lines + ['']


def _who_section(target, language, ar):
    """Who decided the target, and the first places where the rules and the assistant disagreed."""
    from .compose.labels import decided, who_decided
    lines = ['## ' + ('من قرر' if ar else 'Who decided'), '', who_decided(target, language), '']
    for row in (target.get('disagreements') or [])[:SHOWN_DECISIONS]:
        lines.append(f"- `{row['element']}`: " + (f"القواعد «{row['rule']}»، مساعدك «{row['assistant']}»، النهائي «{row['final']}» ({decided(row['label'], language)}). "
                                                   if ar else f"the rules \"{row['rule']}\", your assistant \"{row['assistant']}\", final "
                                                   f"\"{row['final']}\" ({decided(row['label'], language)}). ") + clip_why(row['why']))
    lines.append('')
    return lines


def _components_section(target, language, ar):
    """The retained structure, and today's components by relation, the first of each."""
    from .compose.labels import decided
    lines = ['## ' + ('البنية المحفوظة' if ar else 'Retained structure'), '']
    lines += [target['retained_structure']]
    lines += ['', '## ' + ('المكوّنات' if ar else 'Components')]
    by_relation = defaultdict(list)
    for component in target['components']:
        by_relation[component['relation']].append(component)
    for relation in ['unassessed', 'delete', 'rebuild', 'modify', 'retain', 'introduce', 'retire']:
        rows = by_relation.get(relation, [])
        if not rows: continue
        lines += ['', '### ' + relation.capitalize() + f' ({len(rows)})']
        for component in rows[:SHOWN_COMPONENTS]:
            where = f" → `{component['target_component']}`" if component.get('target_component') else ''
            who = f" · {decided(component['decided_by']['label'], language)}" if component.get('decided_by') else ''
            lines += [f"- `{component['id']}` ← `{component['origin']}`{where}: {component['name']}{who}"]
        if len(rows) > SHOWN_COMPONENTS:
            lines += [('- … البقية في `target-architecture.json`' if ar
                       else '- … the rest are in `target-architecture.json`')]
    return lines


def _decisions_section(target, ar):
    """The first architectural decisions: problem, options, choice and trade-offs."""
    lines = ['', '## ' + ('القرارات المعمارية' if ar else 'Architectural decisions')]
    for adr in target['decisions'][:SHOWN_DECISIONS]:
        lines += ['', f"### {adr['id']}: {adr.get('problem', '')}"]
        lines += ['- ' + ('المشكلة' if ar else 'problem') + f": {adr.get('problem', '')}"]
        lines += ['- ' + ('البدائل' if ar else 'options') + ":"]
        for option in adr.get('options', []): lines += [f"  - {option}"]
        lines += ['- ' + ('المختار' if ar else 'chosen') + f": {adr.get('chosen', '')}"]
        lines += ['- ' + ('المقايضة' if ar else 'tradeoffs') + f": {adr.get('tradeoffs', '')}"]
    if len(target['decisions']) > SHOWN_DECISIONS:
        lines += ['', (f"عُرض {SHOWN_DECISIONS} قرارًا من {len(target['decisions'])}؛ البقية في "
                       '`target-architecture.json`.' if ar else
                       f"Showing {SHOWN_DECISIONS} of {len(target['decisions'])} decisions; the rest are in "
                       '`target-architecture.json`.')]
    return lines

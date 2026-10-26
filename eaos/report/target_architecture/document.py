"""TARGET-ARCHITECTURE.md and target-architecture.json: the target architecture's record (eaos/report/target_architecture/picture.py)
written for people. The component inventory belongs in the record; the document names the shape of the target.
"""
import json
from collections import defaultdict
from pathlib import Path

from .picture import render_decisions

SHOWN_COMPONENTS = 12
SHOWN_DECISIONS = 8

# The document's words, in each language it is written in.
WORDS = {
    'ar': {'head': ['# البنية المستهدفة', '', '> جرد المصدر منفصل عن التصميم المستهدف؛ ما لم يُحدد ويُراجع يبقى فجوة.', ''],
           'gap': 'مصفوفة الفجوة', 'covered': 'مغطى', 'reference': 'النوع المرجعي والمكوّنات المستهدفة',
           'type': 'النوع: `{reference}` (وحدة واحدة معيارية). {components} مكوّنًا مستهدفًا، و{forbidden} استيرادًا ممنوعًا تزيله الخطة.',
           'columns': ['المكوّن', 'الطبقة', 'الملفات', 'تنتقل إليه', 'استيرادات ممنوعة'],
           'shown': 'عُرض {shown} من {total}؛ البقية في `target-architecture.json`.',
           'infrastructure': 'قرارات البنية التحتية', 'no_tool': 'بلا أداة: ', 'evidence': 'الدليل: ', 'who': 'من قرر',
           'disagreed': 'القواعد «{rule}»، مساعدك «{assistant}»، النهائي «{final}» ({label}). ',
           'retained': 'البنية المحفوظة', 'components': 'المكوّنات', 'rest': '- … البقية في `target-architecture.json`',
           'decisions': 'القرارات المعمارية', 'problem': 'المشكلة', 'options': 'البدائل', 'chosen': 'المختار', 'tradeoffs': 'المقايضة',
           'more_decisions': 'عُرض {shown} قرارًا من {total}؛ البقية في `target-architecture.json`.'},
    'en': {'head': ['# Target architecture', '',
                    '> Source inventory and reviewed target proposals are separate. Unspecified targets remain gaps.', ''],
           'gap': 'Gap matrix', 'covered': 'covered', 'reference': 'Reference type and target components',
           'type': 'Type: `{reference}` (a modular monolith). {components} target components; {forbidden} forbidden imports the plan removes.',
           'columns': ['Component', 'Layer', 'Files', 'Moving in', 'Forbidden imports'],
           'shown': 'Showing {shown} of {total}; the rest are in `target-architecture.json`.',
           'infrastructure': 'Infrastructure decisions', 'no_tool': 'no tool: ', 'evidence': 'Evidence: ', 'who': 'Who decided',
           'disagreed': 'the rules "{rule}", your assistant "{assistant}", final "{final}" ({label}). ',
           'retained': 'Retained structure', 'components': 'Components', 'rest': '- … the rest are in `target-architecture.json`',
           'decisions': 'Architectural decisions', 'problem': 'problem', 'options': 'options', 'chosen': 'chosen', 'tradeoffs': 'tradeoffs',
           'more_decisions': 'Showing {shown} of {total} decisions; the rest are in `target-architecture.json`.'},
}


def clip_why(text, limit=160):
    text = ' '.join(str(text or '').split())
    return text if len(text) <= limit else text[:limit - 1] + '…'


def render(out, target, language='ar'):
    """Render the target architecture as a Markdown document."""
    language = 'ar' if language == 'ar' else 'en'
    w = WORDS[language]
    render_decisions(out, target['decisions'])
    lines = list(w['head'])
    if target.get('reference'): lines += _reference_section(target, w)
    lines += _who_section(target, language, w) + _components_section(target, language, w) + _decisions_section(target, w)
    lines += ['', '## ' + w['gap']]
    covered = sum(1 for row in target['gap_matrix'] if row['gap'] == 'covered')
    lines += [f"- {w['covered']}: {covered} / {len(target['gap_matrix'])}"]
    Path(out, 'TARGET-ARCHITECTURE.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    Path(out, 'target-architecture.json').write_text(json.dumps(target, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'markdown': str(Path(out, 'TARGET-ARCHITECTURE.md')),
            'json': str(Path(out, 'target-architecture.json'))}


def _reference_section(target, w):
    """The reference type, its largest target components and the infrastructure decisions."""
    components = target['target_components']
    lines = ['## ' + w['reference'], '',
             w['type'].format(reference=target['reference'], components=len(components), forbidden=target.get('forbidden_edges', 0)), '',
             '| ' + ' | '.join(w['columns']) + ' |', '|---|---|---:|---:|---:|']
    shown = sorted(components, key=lambda c: (-c.get('moves_in', 0), -c.get('files', 0), c['name']))[:15]
    for component in shown:
        lines.append(f"| `{component['name']}` | {component['layer']} | {component.get('files', 0)} | "
                     f"{component.get('moves_in', 0)} | {component.get('forbidden_edges_removed', 0)} |")
    if len(components) > len(shown): lines += ['', w['shown'].format(shown=len(shown), total=len(components))]
    lines += ['', '## ' + w['infrastructure'], '']
    for item in target.get('infrastructure') or []:
        mark = '✅' if item['present'] else '⬜'
        tool = item['tool'] or (w['no_tool'] + (item.get('tool_reason') or ''))
        lines.append(f"- {mark} **{item['area']}**: {item['decision']} ({tool}). " + w['evidence'] + item['evidence'])
    return lines + ['']


def _who_section(target, language, w):
    """Who decided the target, and the first places where the rules and the assistant disagreed."""
    from ...core.language.words import decided, who_decided
    lines = ['## ' + w['who'], '', who_decided(target, language), '']
    for row in (target.get('disagreements') or [])[:SHOWN_DECISIONS]:
        said = w['disagreed'].format(rule=row['rule'], assistant=row['assistant'], final=row['final'], label=decided(row['label'], language))
        lines.append(f"- `{row['element']}`: " + said + clip_why(row['why']))
    lines.append('')
    return lines


def _components_section(target, language, w):
    """The retained structure, and today's components by relation, the first of each."""
    lines = ['## ' + w['retained'], '', target['retained_structure'], '', '## ' + w['components']]
    by_relation = defaultdict(list)
    for component in target['components']:
        by_relation[component['relation']].append(component)
    for relation in ['unassessed', 'delete', 'rebuild', 'modify', 'retain', 'introduce', 'retire']:
        rows = by_relation.get(relation, [])
        if not rows: continue
        lines += ['', '### ' + relation.capitalize() + f' ({len(rows)})'] + [_component_line(c, language) for c in rows[:SHOWN_COMPONENTS]]
        if len(rows) > SHOWN_COMPONENTS: lines.append(w['rest'])
    return lines


def _component_line(component, language):
    from ...core.language.words import decided
    where = f" → `{component['target_component']}`" if component.get('target_component') else ''
    who = f" · {decided(component['decided_by']['label'], language)}" if component.get('decided_by') else ''
    return f"- `{component['id']}` ← `{component['origin']}`{where}: {component['name']}{who}"


def _decisions_section(target, w):
    """The first architectural decisions: problem, options, choice and trade-offs."""
    lines = ['', '## ' + w['decisions']]
    for adr in target['decisions'][:SHOWN_DECISIONS]:
        lines += ['', f"### {adr['id']}: {adr.get('problem', '')}", f"- {w['problem']}: {adr.get('problem', '')}", f"- {w['options']}:"]
        lines += [f"  - {option}" for option in adr.get('options', [])]
        lines += [f"- {w['chosen']}: {adr.get('chosen', '')}", f"- {w['tradeoffs']}: {adr.get('tradeoffs', '')}"]
    if len(target['decisions']) > SHOWN_DECISIONS:
        lines += ['', w['more_decisions'].format(shown=SHOWN_DECISIONS, total=len(target['decisions']))]
    return lines

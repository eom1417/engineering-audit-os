"""The blueprint for a person (docs/BUILD-FROM-PLAN.md): BLUEPRINT.md in words, and BLUEPRINT.html in the look of the
report for people (eaos/report/human_report.py), with every milestone's progress. eaos/report/blueprint.py draws the blueprint; this
module only shows it."""


def document(spec, stack, built):
    """BLUEPRINT.md: the plan's target in words a person reads."""
    plan, lines = built['plan'], [f"# {spec['name']}: the blueprint", '', spec['summary'], '', '## The parts', '']
    for module in spec['modules']:
        lines.append(f"- **{module['name']}**: {module.get('responsibility') or ''}")
    lines += ['', '## The technologies, and how to change each later', '', '| Concern | Chosen | Why | To change it later |', '| --- | --- | --- | --- |']
    for concern, row in stack.items():
        lines.append(f"| {row['title']} | {row['name']} | {row['why']} | {row['switch']} |")
    lines += ['', '## The rules the structure keeps', '']
    lines += [f"- {rule['reason']}" for rule in built['policy']['rules']]
    lines += [f"- Only {' and '.join(f'`{home}`' for home in v['only_in'])} use {', '.join(v['packages'])}." for v in built['policy']['vendors'].values()]
    return '\n'.join(lines + ['', '## The build, in order', ''] + _build_lines(plan))


def _build_lines(plan):
    """The build in BLUEPRINT.md's words: each milestone, then its cards."""
    lines = []
    for milestone in plan['milestones']:
        lines.append(f"### {milestone['id']} · {milestone['name']}")
        for card_id in milestone['tasks']:
            card = next(c for c in plan['tasks'] if c['id'] == card_id)
            lines.append(f"- {card_id}: {card['title']}")
        lines.append('')
    return lines


BUILD_STATE = {'done': ('بُنيت ✓', 'Built ✓', 'good'), 'open': ('لم تُبنَ بعد', 'Not built yet', 'plain'),
               'skipped': ('تُركت: تحتاج قرارًا', 'Set aside: needs a decision', 'bad')}


def build_cards(built, progress):
    """Every build card with its state: built when a delivered milestone kept it, set aside when it skipped it."""
    done = _kept(progress)
    skipped, batch = _card_batches(progress)
    return [_card_row(c, done, skipped, batch) for c in built['plan']['tasks']]


def _kept(progress):
    """The build cards a delivered milestone kept."""
    return {card for record in progress or [] for card in record.get('kept') or []}


def _card_batches(progress):
    """({card set aside: why}, {card: the milestone run that kept or skipped it})."""
    skipped, batch = {}, {}
    for record in progress or []:
        gone = record.get('skipped') or {}
        skipped.update(gone if isinstance(gone, dict) else {card: '' for card in gone})
        for card in list(record.get('kept') or []) + list(gone): batch[card] = record.get('number')
    return skipped, batch


def _card_row(c, done, skipped, batch):
    """One build card as the report's card block draws it: its state, its batch and its acceptance."""
    from html import escape
    from ..core.markup import both as T
    state = 'done' if c['id'] in done else 'skipped' if c['id'] in skipped else 'open'
    checks = ''.join(f'<li>{escape(str(a))}</li>' for a in c.get('acceptance') or [])
    extra = f'<p class="small"><b>{T("يُقبل حين:", "Accepted when:")}</b></p><ul class="small">{checks}</ul>' if checks else ''
    return {'id': c['id'], 'key': c['id'], 'title': c['title'], 'pattern': None, 'milestone': c.get('milestone'), 'paths': c.get('paths') or [],
            'before': '', 'after': '', 'state': state, 'new': False, 'batch': batch.get(c['id']), 'at': None,
            'why': skipped.get(c['id']) or '', 'commit': None, 'module': c.get('module'), 'extra': extra}


def layer_map(built, cards):
    """The target's layers as rows of boxes, from what uses to what is used, each with the build cards in its folders."""
    from ..analysis.arch_map import feedback_edges, layer_of
    from .human_report.target import target_rows
    policy, rules = built['policy'], {r['allow_only']['from']: r['reason'] for r in built['policy']['rules']}
    names = [name for name in policy['layers'] if not name.startswith('_')]
    edges = _target_edges(built, names)
    weights = {(e['from'], e['to']): 1 for e in edges}
    tier = layer_of(names, [e for e in weights if e not in feedback_edges(names, weights)])
    progress = {name: _layer_progress(policy['layers'][name], cards) for name in names}
    comps = [_layer_box(name, tier[name], rules.get(name), progress[name][1]) for name in names]
    return target_rows(comps, sorted({c['layer'] for c in comps}, key=int)), edges, progress


def _target_edges(built, names):
    """The target's edges between two of the drawn layers `names`."""
    return [e for e in built['architecture'].get('target_edges') or [] if e.get('from') in names and e.get('to') in names]


def _layer_progress(globs, cards):
    """(cards built, cards) of the build cards whose paths are in a layer's folders."""
    homes = [g.split('*')[0] for g in globs if not g.startswith('*')]
    mine = [c for c in cards if any(p.startswith(h) for p in c['paths'] for h in homes if h)]
    return sum(c['state'] == 'done' for c in mine), len(mine)


def _layer_box(name, tier, reason, count):
    return {'name': name, 'layer': f'{tier + 1}', 'responsibility': reason or '', 'files': 0,
            'sub': (f'البطاقات {count}', f'{count} card' + ('' if count == 1 else 's'))}


def _milestone_card(milestone, done, delivered, cards, rtl):
    """One milestone: its name, how many of its cards are built (or its branch once delivered) and each card."""
    from html import escape
    ids = milestone['tasks']
    share = round(100 * sum(c in done for c in ids) / len(ids)) if ids else 0
    badge = ('✅ ' + escape(delivered[milestone['id']])) if milestone['id'] in delivered else f'{sum(c in done for c in ids)} / {len(ids)}'
    items = ''.join(f'<li>{"✅" if c in done else "⬜"} {escape(cards[c]["title"])}</li>' for c in ids)
    return (f'<div class="card"><h4>{escape(milestone.get("name_ar") if rtl else milestone["name"])} '
            f'<span class="muted small" data-meaning="cards built of this milestone">{badge}</span></h4>'
            f'<div style="height:8px;background:var(--surface-2);border-radius:99px;overflow:hidden;margin:8px 0">'
            f'<div style="width:{share}%;height:100%;background:var(--good)"></div></div><ul class="small">{items}</ul></div>')


def _layers(built, cards):
    """The target's layers drawn in both reading directions, or nothing when they cannot be drawn."""
    from ..core.markup import both as T
    from .human_report.target import target_svg
    try:
        rows, edges, layer_progress = layer_map(built, cards)
        return (f'<div class="card graph-wrap" data-part="target-map"><p class="muted small">{T("كل صف طبقة: الأعلى يستخدم ما تحته ولا يستخدم ما فوقه. الشريط: كم بُني من بطاقات مجلداتها. مرّر المؤشر على طبقة لترى ما يُسمح لها باستخدامه.", "Each row is a tier: a layer uses what is below it, never what is above. The bar: how many of the cards in its folders are built. Hover a layer to see what it may use.")}</p>'
                  f'<div class="graph-scroll">{target_svg(rows, edges, layer_progress, True, ("بُني", "built"))}{target_svg(rows, edges, layer_progress, False, ("بُني", "built"))}</div></div>')
    except Exception:           # the drawing is extra: without it the page still lists the parts and the build
        return ''


def _parts(spec, cards):
    """The parts, each with its features and how many of its build cards are built."""
    from html import escape
    return ''.join(f'<div class="card"><h4>{escape(m["name"])}</h4><p class="muted small">{escape(m.get("responsibility") or "")}</p>'
                   f'<p class="small">{escape(", ".join(f["name"] for f in spec["features"] if f.get("module") == m["id"]))}</p>{_module_bar(cards, m["id"])}</div>'
                   for m in spec['modules'])


def _module_bar(cards, module):
    """How many of a part's build cards are built, as a bar and a count."""
    from ..core.markup import both as T
    from .human_report.cards import bar
    mine = [c for c in cards if c.get('module') == module]
    finished = sum(c['state'] == 'done' for c in mine)
    count = f'{finished} / {len(mine)}'
    return (f'{bar(100 * finished / len(mine) if mine else 0, "thin")}<p class="muted small">'
            f'<span data-meaning="build cards built of this part">{count}</span> {T("بطاقات بُنيت", "cards built")}</p>')


def _groups(built, cards):
    """((Arabic name, English name), milestone id, its build cards) of every milestone, as the card block takes them."""
    return [((m.get('name_ar') or m['name'], m['name']), m['id'], [c for c in cards if c['milestone'] == m['id']]) for m in built['plan']['milestones']]


def page(spec, stack, built, progress=None):
    """BLUEPRINT.html: the blueprint for a person, in the look of the report for people (eaos/report/human_report.py),
    with every milestone's progress when `progress` (the state's `built` list) is given: the target's layers, the parts,
    and every build card with its state, reusing that page's drawings."""
    from html import escape
    from .human_report.assets import CSS, MAP_JS
    from .human_report.cards import cards_block
    done = _kept(progress)
    delivered = {record['milestone']: record.get('branch') for record in progress or []}
    rtl = any('؀' <= ch <= 'ۿ' for ch in spec.get('name', '') + spec.get('summary', ''))
    cards = build_cards(built, progress)
    parts, layers = _parts(spec, cards), _layers(built, cards)
    groups = _groups(built, cards)
    rows = ''.join(f'<tr><td><b>{escape(row["title"])}</b></td><td>{escape(row["name"])}</td><td>{escape(row["why"])}</td>'
                   f'<td class="small">{escape(row["switch"])}</td></tr>' for row in stack.values())
    rules = ''.join(f'<li>{escape(rule["reason"])}</li>' for rule in built['policy']['rules'])
    by_id = {c['id']: c for c in built['plan']['tasks']}
    stages = [_milestone_card(milestone, done, delivered, by_id, rtl) for milestone in built['plan']['milestones']]
    label = (lambda ar, en: ar if rtl else en)
    lang, side = ('ar', 'rtl') if rtl else ('en', 'ltr')
    return f"""<!doctype html><html lang="{lang}" dir="{side}" data-lang="{lang}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(spec['name'])}</title>
<style>{CSS} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}} table{{width:100%;border-collapse:collapse}}
td,th{{border-bottom:1px solid var(--line);padding:10px;text-align:start;vertical-align:top}}</style></head>
<body><header class="top"><div class="wrap top-in"><div><div class="kicker">EAOS · {label('مخطط البناء', 'Blueprint')}</div>
<h1>{escape(spec['name'])}</h1></div></div></header><main class="wrap">
<p>{escape(spec['summary'])}</p>
<h3>{label('البنية المستهدفة، طبقة طبقة', 'The target structure, layer by layer')}</h3>{layers}
<h3>{label('الأجزاء', 'The parts')}</h3><div class="grid">{parts}</div>
<h3>{label('التقنيات، ولماذا، وكيف تُغيَّر لاحقًا', 'The technologies, why, and how to change each later')}</h3>
<div class="card"><table><tr><th>{label('الجانب', 'Concern')}</th><th>{label('المختار', 'Chosen')}</th><th>{label('لماذا', 'Why')}</th><th>{label('لتغييره لاحقًا', 'To change it later')}</th></tr>{rows}</table></div>
<h3>{label('القواعد التي يحفظها الهيكل', 'The rules the structure keeps')}</h3><div class="card"><ul>{rules}</ul></div>
<h3>{label('البناء، مرحلة مرحلة', 'The build, milestone by milestone')}</h3><div class="grid">{''.join(stages)}</div>
<h3>{label('كل بطاقات البناء', 'Every build card')}</h3>{cards_block(groups, BUILD_STATE)}
</main><script>{MAP_JS}</script></body></html>"""

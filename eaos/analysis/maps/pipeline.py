"""studio/pipeline.json: the pipeline map, current, ideal and gap (contract v2, docs/STUDIO.md D9).

Built from facts/pipeline.json (eaos/facts/declared_pipelines/detect.py), the cards and the fix plan; the Studio computes no position and
no number. Each stage gets its layer and its order inside the layer from EAOS's own layered layout (eaos/analysis/maps/layout.py),
so a stage keeps its place between the Current, Ideal and Gap views and between runs on the same code.

The ideal is derived by the rules of eaos/data/pipeline-rules.json, each with its source: one gap entry per broken
rule, with its evidence, the card on that file and its plan step where one exists, and the operation that closes it.
Nothing is invented: a dispatch EAOS could not follow stays an unresolved step, drawn as a gap and counted.
"""
import json
from collections import defaultdict
from pathlib import Path

from .layout import feedback_edges, layer_of, order_columns
from ...facts.declared_pipelines import detect as facts_pipeline

RULES = Path(__file__).resolve().parents[2] / 'data' / 'pipeline-rules.json'
STRUCTURAL = ('router', 'fork', 'join', 'source', 'sink')
SAFE = __import__('re').compile(r'^(?![/\\~])(?![A-Za-z]:)(?!(.*/)?\.\.(/|$)).+')
MARKED = {'slow', 'risky', 'ai', 'external'}


def _site(where, fact=None):
    where = where or {}
    path = str(where.get('path') or '').replace('\\', '/')
    return {'path': path if path and SAFE.match(path) else None,
            'line': where.get('line') if isinstance(where.get('line'), int) else None,
            'fact': fact or where.get('fact'), 'text': (where.get('text') or None)}


def _count(value, src):
    return {'value': value if isinstance(value, int) and value >= 0 else None, 'src': src, 'unit': 'count'}


def rules():
    return json.loads(RULES.read_text(encoding='utf-8'))


def _pairs(stage_ids, edges):
    """The distinct links between two different stages, sorted."""
    return sorted({(a, b) for a, b in edges if a in stage_ids and b in stage_ids and a != b})


def layout(stage_ids, edges):
    """{stage: (layer, order)}: layers by the longest path after setting cycle edges aside, then barycentre sweeps."""
    pairs = _pairs(stage_ids, edges)
    weights = {pair: 1 for pair in pairs}
    loops = feedback_edges(stage_ids, weights) if pairs else set()
    acyclic = [pair for pair in pairs if pair not in loops]
    layer = layer_of(stage_ids, acyclic)
    columns = order_columns(layer, acyclic) if layer else []
    return {stage: (index, position) for index, column in enumerate(columns) for position, stage in enumerate(column)}


def _cards_on(card_rows):
    out = defaultdict(list)
    for card in card_rows or []:
        for path in card.get('paths') or []: out[path].append(card)
    return out


def section(record, cards=(), plan=None, lang='en'):
    """The body of studio/pipeline.json (without its header) from one scan record."""
    on_file = _cards_on(cards)
    out = {name: [] for name in ('pipelines', 'stages', 'edges', 'routers', 'fans', 'control', 'errors', 'hidden', 'unresolved')}
    for p in record['pipelines']: _add_pipeline(p, on_file, out)
    pipelines, stages, edges = out['pipelines'], out['stages'], out['edges']
    by_stage = {s['id']: s for s in stages}
    gap, ideal = _gap(record, by_stage, edges, out, on_file)
    product = [p for p in pipelines if p['role'] == 'product']
    real = [s for s in stages if s['kind'] not in STRUCTURAL]
    return {'detected': bool(record['detected']), 'confidence': _confidence(record),
            'verdict': verdict(record, product, real, lang), 'kinds': list(record['kinds']),
            'evidence': [_site(e) for e in record.get('evidence') or []], 'looked_for': _looked_for(record),
            'pipelines': pipelines, 'stages': stages, 'edges': edges, 'routers': out['routers'], 'fans': out['fans'],
            'control': out['control'], 'error_lanes': out['errors'], 'hidden': out['hidden'], 'unresolved': out['unresolved'],
            'rules': _rule_rows(gap), 'views': {'current': _current_view(stages, edges), 'ideal': ideal, 'gap': gap},
            'counts': _counts(out, product, real, gap), 'src': {'record': 'facts/pipeline.json', 'rules': 'eaos/data/pipeline-rules.json',
                                                                'layout': 'eaos/analysis/maps/layout.py feedback_edges, layer_of, order_columns'}}


def _rule_rows(gap):
    """Every rule of eaos/data/pipeline-rules.json with how many times the code breaks it."""
    return [{**rule, 'broken': sum(g['rule'] == rule['id'] for g in gap)} for rule in rules()]


def _current_view(stages, edges):
    return {'stages': [s['id'] for s in stages], 'edges': [e['id'] for e in edges]}


def _confidence(record):
    confidence = record.get('confidence')
    return {'value': round(confidence, 4) if isinstance(confidence, (int, float)) else None,
            'src': 'facts/pipeline.json#pipeline[role=product].confidence (highest)'}


def _looked_for(record):
    """What the scan looked for: each kind, its label, whether it was found and how."""
    return [{k: row[k] for k in ('kind', 'label', 'found', 'how')} for row in record['looked_for']]


def _counts(out, product, real, gap):
    pipelines, routers = out['pipelines'], out['routers']
    return {'pipelines': _count(len(pipelines), 'facts/pipeline.json#pipeline'),
            'product': _count(len(product), 'facts/pipeline.json#pipeline[role=product]'),
            'tooling': _count(len(pipelines) - len(product), 'facts/pipeline.json#pipeline[role=tooling]'),
            'stages': _count(len(real), 'facts/pipeline.json#pipeline_stage[kind not router, fork, join]'),
            'edges': _count(len(out['edges']), 'facts/pipeline.json#pipeline_edge'),
            'routers': _count(len(routers), 'facts/pipeline.json#pipeline_router'),
            'branches': _count(sum(len(r['branches']) for r in routers), 'facts/pipeline.json#pipeline_router.branches'),
            'fans': _count(len(out['fans']), 'facts/pipeline.json#pipeline_fan'),
            'error_lanes': _count(len(out['errors']), 'facts/pipeline.json#pipeline_error'),
            'hidden': _count(len(out['hidden']), 'facts/pipeline.json#pipeline_hidden'),
            'unresolved': _count(len(out['unresolved']), 'facts/pipeline.json#pipeline_unresolved'),
            'gaps': _count(len(gap), 'pipeline.json#views.gap: one per broken rule of eaos/data/pipeline-rules.json')}


def _router_targets(p, places):
    """{router stage: the layers its branches lead to}."""
    targets = defaultdict(list)
    for router in p['routers']:
        targets[router['stage']] += [places[branch['to']][0] for branch in router['branches'] if branch['to'] in places]
    return targets


def _stage_places(p):
    """(the real stage ids, {stage: (layer, order)}, each layer's width, each router's target layers)."""
    real = [s['id'] for s in p['stages'] if s['kind'] not in STRUCTURAL]
    places = layout(real, [(e['from'], e['to']) for e in p['edges']])
    width = defaultdict(int)
    for layer, order in places.values(): width[layer] = max(width[layer], order + 1)
    return real, places, width, _router_targets(p, places)


def _place_of(s, places, width, targets):
    """A stage's place; a structural one goes beside the layer its branches lead to, after the others."""
    if s['id'] in places: return places[s['id']]
    layer = min(targets.get(s['id']) or [0])
    order = width[layer]
    width[layer] += 1
    return layer, order


def _stage_row(s, p, place, on_file):
    stage_cards = list(on_file.get(s['entry'].get('path'), []))
    return {'id': s['id'], 'pipeline': p['id'], 'label': s['label'], 'kind': s['kind'],
            'entry': _site(s['entry'], s.get('fact')), 'symbol': s.get('symbol'), 'tools': s.get('tools') or [],
            **_stage_contract(s),
            'optional': bool(s.get('optional')), 'marks': [m for m in s.get('marks') or [] if m in MARKED],
            'sub_pipeline': s.get('sub_pipeline'),
            'coverage': 'partial' if any(u['stage'] == s['id'] for u in p['unresolved']) else 'measured',
            'layer': place[0], 'order': place[1],
            **_stage_cards(stage_cards)}


def _stage_contract(s):
    """A stage's inputs, outputs and side effects, twelve of each at most."""
    return {'inputs': [_port(i) for i in s.get('inputs') or []][:12],
            'outputs': [_port(o) for o in s.get('outputs') or []][:12],
            'side_effects': [{**_site(e), 'kind': e['kind'], 'name': str(e['name'])[:120]} for e in s.get('side_effects') or []][:12]}


def _stage_cards(stage_cards):
    """The cards on a stage's file and the plan steps they are in."""
    return {'cards': [c['id'] for c in stage_cards][:20],
            'steps': sorted({c['milestone'] for c in stage_cards if c.get('milestone')})[:10]}


def _edge_row(e, pid):
    return {'id': e['id'], 'pipeline': pid, 'from': e['from'], 'to': e['to'], 'kind': e['kind'],
            'data': {'names': [str(n)[:120] for n in e['data']['names']][:8], 'shape': e['data'].get('shape')},
            'matched_by': e['matched_by'], 'condition': e.get('condition'), 'evidence': _site(e['evidence'], e.get('fact'))}


def _router_row(r, pid):
    return {'id': r['id'], 'pipeline': pid, 'stage': r['stage'], 'kind': r['kind'], 'table': r.get('table'),
            'on': r['on'], 'entry': _site(r['entry'], r.get('fact')),
            'branches': [{'condition': b['condition'], 'to': b['to'], 'evidence': _site(b['evidence'])} for b in r['branches']],
            'total': r['total'], 'default': r.get('default'), 'unhandled': list(r.get('unhandled') or [])}


def _pipeline_row(p, real):
    return {'id': p['id'], 'title': p['title'], 'kind': p['kind'], 'role': p['role'], 'confidence': p['confidence'],
            'entry': _site(p['entry'], p.get('fact')), 'evidence': [_site(e) for e in p.get('evidence') or []],
            'parent': p.get('parent'), 'stages': [s['id'] for s in p['stages']],
            'counts': {'stages': len(real), 'edges': len(p['edges']), 'routers': len(p['routers']),
                       'branches': sum(len(r['branches']) for r in p['routers']), 'unresolved': len(p['unresolved'])}}


def _add_elements(p, out):
    pid = p['id']
    out['fans'] += [{**{k: f[k] for k in ('id', 'fork', 'join', 'branches', 'matched', 'kind')}, 'pipeline': pid,
                     'evidence': _site(f['evidence'], f.get('fact'))} for f in p['fans']]
    out['control'] += [{'id': c['id'], 'pipeline': pid, 'stage': c['stage'], 'kind': c['kind'], 'condition': c.get('condition'),
                        'evidence': _site(c['evidence'], c.get('fact'))} for c in p['control']]
    out['errors'] += [{'id': e['id'], 'pipeline': pid, 'from': e['from'], 'to': str(e['to']), 'kind': e['kind'],
                       'condition': e.get('condition'), 'evidence': _site(e['evidence'], e.get('fact'))} for e in p['error_lanes']]
    out['hidden'] += [{'id': h['id'], 'pipeline': pid, 'kind': h['kind'], 'channel': h.get('channel'), 'name': str(h['name']),
                       'stages': h['stages'], 'evidence': _site(h['evidence'], h.get('fact'))} for h in p['hidden']]
    out['unresolved'] += [{'id': u['id'], 'pipeline': pid, 'stage': u['stage'], 'call': u['call'], 'reason': u['reason'],
                           'evidence': _site(u['evidence'], u.get('fact'))} for u in p['unresolved']]


def _add_pipeline(p, on_file, out):
    """One pipeline of the record into the section's lists."""
    real, places, width, targets = _stage_places(p)
    out['stages'] += [_stage_row(s, p, _place_of(s, places, width, targets), on_file) for s in p['stages']]
    out['edges'] += [_edge_row(e, p['id']) for e in p['edges']]
    out['routers'] += [_router_row(r, p['id']) for r in p['routers']]
    _add_elements(p, out)
    out['pipelines'].append(_pipeline_row(p, real))


def _port(row):
    return {'name': str(row['name'])[:120], 'kind': row.get('kind') or 'value', 'shape': row.get('shape')}


def verdict(record, product, stages, lang):
    ar = lang == 'ar'
    tooling = [p for p in record['pipelines'] if p['role'] == 'tooling']
    if product:
        names = ('، ' if ar else ', ').join(p['title'] for p in product[:3])
        return (f'هذا المشروع خط معالجة: وجد EAOS خطوط معالجة عددها {len(product)}، فيها {len(stages)} مرحلة ({names}).' if ar else
                f'This project is a pipeline: EAOS found {len(product)} pipelines with {len(stages)} stages ({names}).')
    looked = len(record['looked_for'])
    if tooling:
        return (f'لا خط معالجة في المنتج: بحث EAOS عن {looked} نوعًا، ووجد فقط سلاسل البناء والفحص ({len(tooling)}).' if ar else
                f'No pipeline in the product: EAOS looked for {looked} kinds and found only build and CI chains ({len(tooling)}).')
    return (f'لا خط معالجة في هذا المشروع: بحث EAOS عن {looked} نوعًا ولم يجد أيًّا منها.' if ar else
            f'No pipeline in this project: EAOS looked for {looked} kinds and found none.')


def _gap(record, by_stage, edges, out, on_file):
    """One entry per broken rule, and the ideal it implies: each stage's operation, the new stages and edges. `out` is
    the map's rows (its hidden channels, routers and fans read here)."""
    gap = _GapBuilder(by_stage, on_file)
    raw = {p['id']: p for p in record['pipelines']}
    _shared_symbols(record, by_stage, gap)
    for pid, p in raw.items(): _contract_rules(pid, p, by_stage, gap)
    for h in out['hidden']: _hidden_rule(h, gap)
    for r in out['routers']: _router_rule(r, gap)
    for f in out['fans']:
        if not f['matched']: _gather(f, gap)
    _budget_rules(raw, by_stage, gap)
    for g in gap.entries:   # the evidence of a pipeline-level entry may lack a line; a stage's entry always has one
        if not g['evidence'].get('path'): g['evidence'] = {'path': None, 'line': None, 'fact': None, 'text': None}
    return gap.entries, _ideal(by_stage, edges, gap)


class _GapBuilder:
    """The gap being built: its entries, each stage's operation and why, and the new stages and edges of the ideal."""

    def __init__(self, by_stage, on_file):
        self.entries, self.new_stages, self.new_edges = [], [], []
        self.ops = {s: 'retain' for s in by_stage}
        self.why = {}
        self.on_file = on_file

    def card_of(self, where):
        cards = self.on_file.get((where or {}).get('path')) or []
        return (cards[0]['id'], cards[0].get('milestone')) if cards else (None, None)

    def add(self, rule, pipeline, subject, kind, op, detail, where, stages=()):  # limits: parameters -- the fields of one gap entry
        card, step = self.card_of(where)
        self.entries.append({'id': f'gap:{rule}:{subject}', 'rule': rule, 'pipeline': pipeline, 'subject': subject, 'subject_kind': kind,
                             'operation': op, 'detail': detail[:300], 'evidence': where, 'card': card, 'step': step})
        for stage in stages:
            if stage in self.ops and self.ops[stage] == 'retain': self.ops[stage], self.why[stage] = op, (rule, detail[:200])


def _product_symbols(record):
    """{symbol: the product pipelines whose real stages run it}."""
    symbols = defaultdict(set)
    for p in record['pipelines']:
        if p['role'] != 'product': continue
        for s in p['stages']:
            if s['kind'] not in STRUCTURAL and s.get('symbol'): symbols[s['symbol']].add(p['id'])
    return symbols


def _shared_symbols(record, by_stage, gap):
    """P1: one function run by more than one pipeline."""
    for symbol, owners in sorted(_product_symbols(record).items()):
        if len(owners) <= 1: continue
        first = sorted(owners)[0]
        stage = next(s for s in by_stage.values() if s['pipeline'] == first and s['symbol'] == symbol)
        gap.add('P1', first, stage['id'], 'stage', 'merge', f'{symbol} is run by {len(owners)} pipelines: one entry should own it',
                stage['entry'], [stage['id']])


def _undeclared_contracts(pid, p, real, by_stage, gap):
    """P2: stages whose inputs and outputs no contract declares."""
    lacking = [s for s in real if not s.get('outputs') and not s.get('annotated')]
    if p['kind'] == 'registry_loop':
        gap.add('P2', pid, pid, 'pipeline', 'refactor', f'{len(real)} stages take their inputs from an accumulator by an if-chain on the '
                f'stage name, not from a declared contract', _site(p['entry']), [s['id'] for s in real])
    elif lacking and p['role'] == 'product':
        gap.add('P2', pid, pid, 'pipeline', 'refactor', f'{len(lacking)} of {len(real)} stages declare neither their outputs nor typed '
                f'inputs and outputs', by_stage[lacking[0]['id']]['entry'], [s['id'] for s in lacking])


def _failure_lane(pid, p, gap):
    """P7: a product pipeline that routes no failure anywhere gets a failure lane."""
    gap.new_stages.append({'id': f'{pid}/failure-lane', 'op': 'new', 'label': 'failure lane', 'pipeline': pid,
                           'why': 'every failure needs a route', 'rule': 'P7',
                           'contract': {'inputs': ['failed stage', 'error'], 'outputs': ['recorded failure']}, 'marks': []})
    gap.add('P7', pid, pid, 'pipeline', 'new', 'no stage of this pipeline routes its failures anywhere: a failure stops the run unnamed',
            _site(p['entry']))


def _shared_context(pid, p, real, by_stage, gap):
    """P6: stages of a product pipeline that take one shared, mutable context."""
    shared = [s for s in real if s.get('shared_context')]
    if shared and p['role'] == 'product':
        gap.add('P6', pid, pid, 'pipeline', 'refactor', f'{len(shared)} stages take one shared, mutable context, so none can run '
                f'alone without rebuilding it', by_stage[shared[0]['id']]['entry'], [s['id'] for s in shared])


def _contract_rules(pid, p, by_stage, gap):
    """P2, P6 and P7 for one pipeline."""
    real = [s for s in p['stages'] if s['kind'] not in STRUCTURAL]
    if not real: return
    _undeclared_contracts(pid, p, real, by_stage, gap)
    _shared_context(pid, p, real, by_stage, gap)
    if not p['error_lanes'] and p['role'] == 'product': _failure_lane(pid, p, gap)


def _hidden_rule(h, gap):
    """P3: a side channel becomes declared edges; P8: what is written and never read, or never reached, goes."""
    if h['kind'] != 'side_channel':
        gap.add('P8', h['pipeline'], h['id'], 'hidden', 'delete', (f"{h['name']} is written and never read" if h['kind'] == 'unread_output'
                                                                   else f"{h['name']} is registered, but no run reaches it"), h['evidence'])
        return
    gap.add('P3', h['pipeline'], h['id'], 'hidden', 'refactor', f"{h['name']} carries data between {len(h['stages'])} stages beside the "
            f'declared edges', h['evidence'], h['stages'])
    writer = h['stages'][0]
    gap.new_edges += [{'from': writer, 'to': reader, 'op': 'new', 'pipeline': h['pipeline'], 'rule': 'P3'} for reader in h['stages'][1:]]


def _router_rule(r, gap):
    """P4: a router with a value no branch handles, or that cannot be told complete and has no default."""
    if r['total'] is False or r['unhandled']:
        gap.add('P4', r['pipeline'], r['id'], 'router', 'refactor', f"{r['on']}: no branch for " + (', '.join(r['unhandled'][:5]) or 'some values'),
                r['entry'], [r['stage']])
    elif r['total'] is None and not r['default']:
        gap.add('P4', r['pipeline'], r['id'], 'router', 'refactor', f"{r['on']}: EAOS cannot tell whether every value has a branch, and "
                f'there is no default branch', r['entry'], [r['stage']])


def _gather(f, gap):
    """P5: a fan-out nothing gathers gets a join stage."""
    join = f"{f['pipeline']}/join-{f['id'].rsplit(':', 1)[-1]}"
    gap.new_stages.append({'id': join, 'op': 'new', 'label': 'gather results', 'pipeline': f['pipeline'], 'why': 'a fan-out needs its fan-in',
                           'rule': 'P5', 'contract': {'inputs': ['branch results'], 'outputs': ['gathered result']}, 'marks': []})
    gap.new_edges += [{'from': b, 'to': join, 'op': 'new', 'pipeline': f['pipeline'], 'rule': 'P5'} for b in f['branches']]
    gap.add('P5', f['pipeline'], f['id'], 'fan', 'new', f"{len(f['branches'])} branches fan out and nothing gathers their results",
            f['evidence'])


def _unbudgeted(s):
    return s['kind'] not in STRUCTURAL and bool(set(s.get('marks') or []) & {'slow', 'risky', 'ai'}) and not s.get('timeout')


def _budget_rules(raw, by_stage, gap):
    """P9: a slow, risky or AI stage of a product pipeline with no timeout or budget."""
    for pid, p in raw.items():
        if p['role'] != 'product': continue
        for s in (s for s in p['stages'] if _unbudgeted(s)):
            gap.add('P9', pid, s['id'], 'stage', 'refactor', f"{s['label']} is {', '.join(sorted(set(s['marks']) & MARKED))} and declares no "
                    f'timeout or budget', by_stage[s['id']]['entry'], [s['id']])


def _ideal(by_stage, edges, gap):
    ideal_stages = [{'id': s, 'op': gap.ops[s], 'label': by_stage[s]['label'], 'pipeline': by_stage[s]['pipeline'],
                     'why': gap.why.get(s, (None, None))[1], 'rule': gap.why.get(s, (None, None))[0],
                     'contract': {'inputs': [i['name'] for i in by_stage[s]['inputs']], 'outputs': [o['name'] for o in by_stage[s]['outputs']]},
                     'marks': by_stage[s]['marks']} for s in by_stage] + gap.new_stages
    ideal_edges = [{'from': e['from'], 'to': e['to'], 'op': 'retain', 'pipeline': e['pipeline'], 'rule': None} for e in edges] + gap.new_edges
    return {'stages': ideal_stages, 'edges': ideal_edges, 'made_by': 'rules'}


def from_report(report, cards=(), plan=None, lang='ar'):
    """The section of a report, or None when its check wrote no facts/pipeline.json."""
    record = facts_pipeline.read(report)
    return None if record is None else section(record, cards, plan, lang)

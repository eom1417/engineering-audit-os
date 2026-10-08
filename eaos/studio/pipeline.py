"""studio/pipeline.json: the pipeline map, current, ideal and gap (contract v2, docs/STUDIO.md D9).

Built from facts/pipeline.json (eaos/facts/pipeline.py), the cards and the fix plan; the Studio computes no position and
no number. Each stage gets its layer and its order inside the layer from EAOS's own layered layout (eaos/arch_map.py),
so a stage keeps its place between the Current, Ideal and Gap views and between runs on the same code.

The ideal is derived by the rules of eaos/data/pipeline-rules.json, each with its source: one gap entry per broken
rule, with its evidence, the card on that file and its plan step where one exists, and the operation that closes it.
Nothing is invented: a dispatch EAOS could not follow stays an unresolved step, drawn as a gap and counted.
"""
import json
from collections import defaultdict
from pathlib import Path

from .. import arch_map
from ..facts import pipeline as facts_pipeline

RULES = Path(__file__).resolve().parent.parent / 'data' / 'pipeline-rules.json'
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


def layout(stage_ids, edges):
    """{stage: (layer, order)}: layers by the longest path after setting cycle edges aside, then barycentre sweeps."""
    pairs = sorted({(a, b) for a, b in edges if a in stage_ids and b in stage_ids and a != b})
    weights = {pair: 1 for pair in pairs}
    loops = arch_map.feedback_edges(stage_ids, weights) if pairs else set()
    acyclic = [pair for pair in pairs if pair not in loops]
    layer = arch_map.layer_of(stage_ids, acyclic)
    columns = arch_map.order_columns(layer, acyclic) if layer else []
    return {stage: (index, position) for index, column in enumerate(columns) for position, stage in enumerate(column)}


def _cards_on(card_rows):
    out = defaultdict(list)
    for card in card_rows or []:
        for path in card.get('paths') or []: out[path].append(card)
    return out


def section(record, cards=(), plan=None, lang='en'):
    """The body of studio/pipeline.json (without its header) from one scan record."""
    on_file = _cards_on(cards)
    pipelines, stages, edges, routers, fans, control, errors, hidden, unresolved = [], [], [], [], [], [], [], [], []
    for p in record['pipelines']:
        real = [s['id'] for s in p['stages'] if s['kind'] not in STRUCTURAL]
        places = layout(real, [(e['from'], e['to']) for e in p['edges']])
        width = defaultdict(int)
        for layer, order in places.values(): width[layer] = max(width[layer], order + 1)
        targets = defaultdict(list)
        for router in p['routers']:
            for branch in router['branches']:
                if branch['to'] in places: targets[router['stage']].append(places[branch['to']][0])
        for s in p['stages']:
            if s['id'] in places: layer, order = places[s['id']]
            else:
                layer = min(targets.get(s['id']) or [0])
                order = width[layer]; width[layer] += 1
            entry_path = s['entry'].get('path')
            stage_cards = [c for c in on_file.get(entry_path, [])]
            stages.append({'id': s['id'], 'pipeline': p['id'], 'label': s['label'], 'kind': s['kind'],
                           'entry': _site(s['entry'], s.get('fact')), 'symbol': s.get('symbol'), 'tools': s.get('tools') or [],
                           'inputs': [_port(i) for i in s.get('inputs') or []][:12],
                           'outputs': [_port(o) for o in s.get('outputs') or []][:12],
                           'side_effects': [{**_site(e), 'kind': e['kind'], 'name': str(e['name'])[:120]} for e in s.get('side_effects') or []][:12],
                           'optional': bool(s.get('optional')), 'marks': [m for m in s.get('marks') or [] if m in MARKED],
                           'sub_pipeline': s.get('sub_pipeline'),
                           'coverage': 'partial' if any(u['stage'] == s['id'] for u in p['unresolved']) else 'measured',
                           'layer': layer, 'order': order,
                           'cards': [c['id'] for c in stage_cards][:20],
                           'steps': sorted({c['milestone'] for c in stage_cards if c.get('milestone')})[:10]})
        for e in p['edges']:
            edges.append({'id': e['id'], 'pipeline': p['id'], 'from': e['from'], 'to': e['to'], 'kind': e['kind'],
                          'data': {'names': [str(n)[:120] for n in e['data']['names']][:8], 'shape': e['data'].get('shape')},
                          'matched_by': e['matched_by'], 'condition': e.get('condition'), 'evidence': _site(e['evidence'], e.get('fact'))})
        for r in p['routers']:
            routers.append({'id': r['id'], 'pipeline': p['id'], 'stage': r['stage'], 'kind': r['kind'], 'table': r.get('table'),
                            'on': r['on'], 'entry': _site(r['entry'], r.get('fact')),
                            'branches': [{'condition': b['condition'], 'to': b['to'], 'evidence': _site(b['evidence'])} for b in r['branches']],
                            'total': r['total'], 'default': r.get('default'), 'unhandled': list(r.get('unhandled') or [])})
        fans += [{**{k: f[k] for k in ('id', 'fork', 'join', 'branches', 'matched', 'kind')}, 'pipeline': p['id'],
                  'evidence': _site(f['evidence'], f.get('fact'))} for f in p['fans']]
        control += [{'id': c['id'], 'pipeline': p['id'], 'stage': c['stage'], 'kind': c['kind'], 'condition': c.get('condition'),
                     'evidence': _site(c['evidence'], c.get('fact'))} for c in p['control']]
        errors += [{'id': e['id'], 'pipeline': p['id'], 'from': e['from'], 'to': str(e['to']), 'kind': e['kind'],
                    'condition': e.get('condition'), 'evidence': _site(e['evidence'], e.get('fact'))} for e in p['error_lanes']]
        hidden += [{'id': h['id'], 'pipeline': p['id'], 'kind': h['kind'], 'channel': h.get('channel'), 'name': str(h['name']),
                    'stages': h['stages'], 'evidence': _site(h['evidence'], h.get('fact'))} for h in p['hidden']]
        unresolved += [{'id': u['id'], 'pipeline': p['id'], 'stage': u['stage'], 'call': u['call'], 'reason': u['reason'],
                        'evidence': _site(u['evidence'], u.get('fact'))} for u in p['unresolved']]
        pipelines.append({'id': p['id'], 'title': p['title'], 'kind': p['kind'], 'role': p['role'], 'confidence': p['confidence'],
                          'entry': _site(p['entry'], p.get('fact')), 'evidence': [_site(e) for e in p.get('evidence') or []],
                          'parent': p.get('parent'), 'stages': [s['id'] for s in p['stages']],
                          'counts': {'stages': len(real), 'edges': len(p['edges']), 'routers': len(p['routers']),
                                     'branches': sum(len(r['branches']) for r in p['routers']), 'unresolved': len(p['unresolved'])}})
    by_stage = {s['id']: s for s in stages}
    gap, ideal = _gap(record, by_stage, edges, routers, fans, errors, hidden, on_file)
    rule_rows = [{**rule, 'broken': sum(g['rule'] == rule['id'] for g in gap)} for rule in rules()]
    product = [p for p in pipelines if p['role'] == 'product']
    real = [s for s in stages if s['kind'] not in STRUCTURAL]
    counts = {'pipelines': _count(len(pipelines), 'facts/pipeline.json#pipeline'),
              'product': _count(len(product), 'facts/pipeline.json#pipeline[role=product]'),
              'tooling': _count(len(pipelines) - len(product), 'facts/pipeline.json#pipeline[role=tooling]'),
              'stages': _count(len(real), 'facts/pipeline.json#pipeline_stage[kind not router, fork, join]'),
              'edges': _count(len(edges), 'facts/pipeline.json#pipeline_edge'),
              'routers': _count(len(routers), 'facts/pipeline.json#pipeline_router'),
              'branches': _count(sum(len(r['branches']) for r in routers), 'facts/pipeline.json#pipeline_router.branches'),
              'fans': _count(len(fans), 'facts/pipeline.json#pipeline_fan'),
              'error_lanes': _count(len(errors), 'facts/pipeline.json#pipeline_error'),
              'hidden': _count(len(hidden), 'facts/pipeline.json#pipeline_hidden'),
              'unresolved': _count(len(unresolved), 'facts/pipeline.json#pipeline_unresolved'),
              'gaps': _count(len(gap), 'pipeline.json#views.gap: one per broken rule of eaos/data/pipeline-rules.json')}
    confidence = record.get('confidence')
    return {'detected': bool(record['detected']),
            'confidence': {'value': round(confidence, 4) if isinstance(confidence, (int, float)) else None,
                           'src': 'facts/pipeline.json#pipeline[role=product].confidence (highest)'},
            'verdict': verdict(record, product, real, lang), 'kinds': list(record['kinds']),
            'evidence': [_site(e) for e in record.get('evidence') or []],
            'looked_for': [{k: row[k] for k in ('kind', 'label', 'found', 'how')} for row in record['looked_for']],
            'pipelines': pipelines, 'stages': stages, 'edges': edges, 'routers': routers, 'fans': fans, 'control': control,
            'error_lanes': errors, 'hidden': hidden, 'unresolved': unresolved, 'rules': rule_rows,
            'views': {'current': {'stages': [s['id'] for s in stages], 'edges': [e['id'] for e in edges]}, 'ideal': ideal, 'gap': gap},
            'counts': counts, 'src': {'record': 'facts/pipeline.json', 'rules': 'eaos/data/pipeline-rules.json',
                                      'layout': 'eaos/arch_map.py feedback_edges, layer_of, order_columns'}}


def _port(row):
    return {'name': str(row['name'])[:120], 'kind': row.get('kind') or 'value', 'shape': row.get('shape')}


def verdict(record, product, stages, lang):
    ar = lang == 'ar'
    tooling = [p for p in record['pipelines'] if p['role'] == 'tooling']
    if product:
        names = '، '.join(p['title'] for p in product[:3]) if ar else ', '.join(p['title'] for p in product[:3])
        return (f'هذا المشروع خط معالجة: وجد EAOS {len(product)} خط معالجة فيها {len(stages)} مرحلة ({names}).' if ar else
                f'This project is a pipeline: EAOS found {len(product)} pipelines with {len(stages)} stages ({names}).')
    looked = len(record['looked_for'])
    if tooling:
        return (f'لا خط معالجة في المنتج: بحث EAOS عن {looked} نوعًا، ووجد فقط سلاسل البناء والفحص ({len(tooling)}).' if ar else
                f'No pipeline in the product: EAOS looked for {looked} kinds and found only build and CI chains ({len(tooling)}).')
    return (f'لا خط معالجة في هذا المشروع: بحث EAOS عن {looked} نوعًا ولم يجد أيًّا منها.' if ar else
            f'No pipeline in this project: EAOS looked for {looked} kinds and found none.')


def _gap(record, by_stage, edges, routers, fans, errors, hidden, on_file):
    """One entry per broken rule, and the ideal it implies: each stage's operation, the new stages and edges."""
    gap = []
    ops = {s: 'retain' for s in by_stage}
    why = {}
    new_stages, new_edges = [], []

    def card_of(where):
        cards = on_file.get((where or {}).get('path')) or []
        return (cards[0]['id'], cards[0].get('milestone')) if cards else (None, None)

    def add(rule, pipeline, subject, kind, op, detail, where, stages=()):
        card, step = card_of(where)
        gap.append({'id': f'gap:{rule}:{subject}', 'rule': rule, 'pipeline': pipeline, 'subject': subject, 'subject_kind': kind,
                    'operation': op, 'detail': detail[:300], 'evidence': where, 'card': card, 'step': step})
        for stage in stages:
            if stage in ops and ops[stage] == 'retain': ops[stage], why[stage] = op, (rule, detail[:200])

    raw = {p['id']: p for p in record['pipelines']}
    symbols = defaultdict(set)
    for p in record['pipelines']:
        if p['role'] != 'product': continue
        for s in p['stages']:
            if s['kind'] not in STRUCTURAL and s.get('symbol'): symbols[s['symbol']].add(p['id'])
    for symbol, owners in sorted(symbols.items()):
        if len(owners) > 1:
            first = sorted(owners)[0]
            stage = next(s for s in by_stage.values() if s['pipeline'] == first and s['symbol'] == symbol)
            add('P1', first, stage['id'], 'stage', 'merge', f'{symbol} is run by {len(owners)} pipelines: one entry should own it',
                stage['entry'], [stage['id']])
    for pid, p in raw.items():
        real = [s for s in p['stages'] if s['kind'] not in STRUCTURAL]
        if not real: continue
        lacking = [s for s in real if not s.get('outputs') and not s.get('annotated')]
        if p['kind'] == 'registry_loop':
            lacking = real
            add('P2', pid, pid, 'pipeline', 'refactor', f'{len(real)} stages take their inputs from an accumulator by an if-chain on the '
                f'stage name, not from a declared contract', _site(p['entry']), [s['id'] for s in lacking])
        elif lacking and p['role'] == 'product':
            add('P2', pid, pid, 'pipeline', 'refactor', f'{len(lacking)} of {len(real)} stages declare neither their outputs nor typed '
                f'inputs and outputs', by_stage[lacking[0]['id']]['entry'], [s['id'] for s in lacking])
        shared = [s for s in real if s.get('shared_context')]
        if shared and p['role'] == 'product':
            add('P6', pid, pid, 'pipeline', 'refactor', f'{len(shared)} stages take one shared, mutable context, so none can run '
                f'alone without rebuilding it', by_stage[shared[0]['id']]['entry'], [s['id'] for s in shared])
        if not p['error_lanes'] and p['role'] == 'product':
            lane = f'{pid}/failure-lane'
            new_stages.append({'id': lane, 'op': 'new', 'label': 'failure lane', 'pipeline': pid, 'why': 'every failure needs a route',
                               'rule': 'P7', 'contract': {'inputs': ['failed stage', 'error'], 'outputs': ['recorded failure']}, 'marks': []})
            add('P7', pid, pid, 'pipeline', 'new', 'no stage of this pipeline routes its failures anywhere: a failure stops the run unnamed',
                _site(p['entry']))
    for h in hidden:
        if h['kind'] == 'side_channel':
            add('P3', h['pipeline'], h['id'], 'hidden', 'refactor', f"{h['name']} carries data between {len(h['stages'])} stages beside the "
                f'declared edges', h['evidence'], h['stages'])
            writer = h['stages'][0]
            for reader in h['stages'][1:]:
                new_edges.append({'from': writer, 'to': reader, 'op': 'new', 'pipeline': h['pipeline'], 'rule': 'P3'})
        else:
            add('P8', h['pipeline'], h['id'], 'hidden', 'delete', (f"{h['name']} is written and never read" if h['kind'] == 'unread_output'
                                                                   else f"{h['name']} is registered, but no run reaches it"), h['evidence'])
    for r in routers:
        if r['total'] is False or r['unhandled']:
            add('P4', r['pipeline'], r['id'], 'router', 'refactor', f"{r['on']}: no branch for " + (', '.join(r['unhandled'][:5]) or 'some values'),
                r['entry'], [r['stage']])
        elif r['total'] is None and not r['default']:
            add('P4', r['pipeline'], r['id'], 'router', 'refactor', f"{r['on']}: EAOS cannot tell whether every value has a branch, and "
                f'there is no default branch', r['entry'], [r['stage']])
    for f in fans:
        if not f['matched']:
            join = f"{f['pipeline']}/join-{f['id'].rsplit(':', 1)[-1]}"
            new_stages.append({'id': join, 'op': 'new', 'label': 'gather results', 'pipeline': f['pipeline'], 'why': 'a fan-out needs its fan-in',
                               'rule': 'P5', 'contract': {'inputs': ['branch results'], 'outputs': ['gathered result']}, 'marks': []})
            new_edges += [{'from': b, 'to': join, 'op': 'new', 'pipeline': f['pipeline'], 'rule': 'P5'} for b in f['branches']]
            add('P5', f['pipeline'], f['id'], 'fan', 'new', f"{len(f['branches'])} branches fan out and nothing gathers their results",
                f['evidence'])
    for pid, p in raw.items():
        if p['role'] != 'product': continue
        for s in p['stages']:
            if s['kind'] in STRUCTURAL or not (set(s.get('marks') or []) & {'slow', 'risky', 'ai'}) or s.get('timeout'): continue
            add('P9', pid, s['id'], 'stage', 'refactor', f"{s['label']} is {', '.join(sorted(set(s['marks']) & MARKED))} and declares no "
                f'timeout or budget', by_stage[s['id']]['entry'], [s['id']])
    for g in gap:   # the evidence of a pipeline-level entry may lack a line; a stage's entry always has one
        if not g['evidence'].get('path'): g['evidence'] = {'path': None, 'line': None, 'fact': None, 'text': None}
    ideal_stages = [{'id': s, 'op': ops[s], 'label': by_stage[s]['label'], 'pipeline': by_stage[s]['pipeline'],
                     'why': why.get(s, (None, None))[1], 'rule': why.get(s, (None, None))[0],
                     'contract': {'inputs': [i['name'] for i in by_stage[s]['inputs']], 'outputs': [o['name'] for o in by_stage[s]['outputs']]},
                     'marks': by_stage[s]['marks']} for s in by_stage] + new_stages
    ideal_edges = [{'from': e['from'], 'to': e['to'], 'op': 'retain', 'pipeline': e['pipeline'], 'rule': None} for e in edges] + new_edges
    return gap, {'stages': ideal_stages, 'edges': ideal_edges, 'made_by': 'rules'}


def from_report(report, cards=(), plan=None, lang='ar'):
    """The section of a report, or None when its check wrote no facts/pipeline.json."""
    record = facts_pipeline.read(report)
    return None if record is None else section(record, cards, plan, lang)

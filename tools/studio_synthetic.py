"""A synthetic Studio data folder at scale: every section of contracts v1 and v2, valid, linked, and deterministic.

The Studio is built and gated against real reports, but none of them is large. This writes the folder EAOS would
write for a project of N cards and M components (default 5,000 and 1,000, STUDIO-COMPLETE.md), so the pages, the
search and the screen gates are tested at the scale a company project reaches. Every id a section cites exists in
the section it points to: a card's evidence, a function's callers, a gap's operations, an operation's step.

    python tools/studio_synthetic.py --out DIR [--cards 5000] [--components 1000] [--seed 7]

DIR then holds <section>.json, its .js twin and manifest.json, exactly as eaos/report/studio/export.py lays them out; give it
to the screen gate with `python tools/studio_gates.py --studio --data DIR`. The maps are made in studio_synthetic_maps.py,
from what studio_synthetic_base.py holds for every part.
"""
import argparse
import hashlib
import random
import sys
from pathlib import Path

from studio_synthetic_base import DOMAINS, HEAD, LAYERS, V2, WHEN, measure, ratio
from studio_synthetic_maps import data_maps, maps, synthetic_paths, synthetic_pipeline
from eaos.core.contracts import artifact_rules as artifact_contracts  # noqa: E402
from eaos.report.studio import coverage as coverage_section  # noqa: E402
from eaos.report.studio import export  # noqa: E402

SEVERITIES = ('critical', 'high', 'medium', 'low', 'info')
KINDS = ('complexity', 'dead_code', 'literal_duplication', 'secret', 'missing_rls', 'layer_violation', 'cycle', 'unused_dependency')
OPERATIONS = ('retain', 'refactor', 'rebuild', 'merge', 'delete', 'new')
STATES = ('open', 'open', 'open', 'in_batch', 'on_branch', 'done', 'resolved', 'skipped')
TASK_STATE = export.TASK_STATE
WHY = {'complexity': ('دالة معقّدة يصعب اختبارها ويكثر فيها الخطأ عند التعديل.', 'A complex function is hard to test and easy to break when changed.'),
       'dead_code': ('كود لا يشغّله أحد يبقى يُقرأ ويُصان.', 'Code nobody runs is still read and maintained.'),
       'literal_duplication': ('نسختان من القاعدة نفسها تتباعدان مع الوقت.', 'Two copies of one rule drift apart over time.'),
       'secret': ('مفتاح سرّي في الكود يصل إلى كل من يقرأ المستودع.', 'A secret in the code reaches everyone who reads the repository.'),
       'missing_rls': ('جدول بلا أمان صفوف يقرؤه أي مستخدم.', 'A table without row security is readable by any user.'),
       'layer_violation': ('طبقة تتجاوز أخرى فيصعب تغيير أيّ منهما وحدها.', 'A layer that skips another makes either hard to change alone.'),
       'cycle': ('حلقة استيراد تمنع فصل الوحدتين.', 'An import cycle keeps the two modules from being separated.'),
       'unused_dependency': ('مكتبة لا تُستعمل تكبّر البناء وتزيد الثغرات المحتملة.', 'An unused library grows the build and the attack surface.')}

# What a node's synthetic run says: decided by an assistant (True) or by the rules alone (False).
NODE_RUNS = {True: {'state': 'decided', 'method': 'model', 'assistant': 'Claude Code', 'model': 'synthetic', 'seconds': 420.0,
                    'cost_usd': 1.2, 'why': None},
             False: {'state': 'rules_only', 'method': 'rules', 'assistant': None, 'model': None, 'seconds': 0.1, 'cost_usd': None,
                     'why': 'No assistant is installed and logged in here, so the rules decided alone.'}}
CHOICES = ('confirm', 'confirm', 'confirm', 'doubt', 'reject')


def _synthetic_decisions(node, card_rows, model):
    """The assistant's decision on each of 500 cards, each citing its card; or the rules' one decision."""
    shared = {'options': [r.decision for r in node.routes][:-1], 'open_questions': [], 'detail': {}}
    if model:
        return [{'subject': c['id'], 'decision': CHOICES[i % 5], 'evidence': [c['id']], 'confidence': 0.8, 'why': 'Its evidence shows it.',
                 'source': 'model', **shared} for i, c in enumerate(card_rows[:500])]
    return [{'subject': 'plan' if node.name == 'plan_orderer' else node.name, 'decision': 'rules only', 'evidence': ['RULE-plan-order'],
             'confidence': 0.5, 'why': 'The rules decided alone.', 'source': 'rules', **shared}]


def _synthetic_node(node, card_rows):
    from eaos.ai import nodes
    from eaos.ai.nodes import view
    model = node.name == 'card_triage'
    run, decisions, taken = NODE_RUNS[model], _synthetic_decisions(node, card_rows, model), {}
    for d in decisions: taken[d['decision']] = taken.get(d['decision'], 0) + 1
    return {'id': node.name, 'title': {'en': node.title, 'ar': nodes.TITLES_AR[node.name]}, 'kind': 'ai', 'passes': list(node.passes),
            'requires': list(node.requires),
            'routes': [{'decision': r.decision, 'to': r.to, 'when': {'en': r.when, 'ar': view.WHEN_AR[(node.name, r.decision)]},
                        'subjects': taken.get(r.decision, 0)} for r in node.routes],
            **run, 'at': WHEN, 'cached': False, 'summary': None, 'decisions': decisions,
            'dropped': [{'subject': card_rows[i]['id'], 'decision': 'confirm', 'evidence': ['FACT-invented'],
                         'why': 'no evidence id resolves to a fact, claim, card or rule of this report'} for i in range(3)] if model else [],
            'log': [{'at': WHEN, 'state': run['state'], 'assistant': run['assistant'], 'model': run['model'],
                     'prompt': 'synthetic' if model else None, 'inputs': 'synthetic', 'cached': False, 'seconds': 1.0, 'cost_usd': None}]}


def synthetic_nodes(card_rows):
    """studio/nodes.json at scale: every declared AI node, the card triage decided by an assistant on 500 cards (each
    citing its own card), a few dropped, the others decided by the rules alone, each with its run log."""
    from eaos.ai import nodes
    rows = [_synthetic_node(node, card_rows) for node in nodes.NODES]
    count = lambda value: measure(value, 'synthetic')
    return {**V2, 'nodes': rows, 'sinks': [{'id': k, 'title': {'en': en, 'ar': ar}} for k, (en, ar) in nodes.SINKS.items()], 'questions': [],
            'counts': {'nodes': count(len(rows)), 'ran': count(len(rows)), 'by_model': count(1),
                       'decisions': count(sum(len(r['decisions']) for r in rows)), 'dropped': count(3)}}


def synthetic_ideal(comps, layer, card_rows):
    """studio/ideal.json at scale: every view's rules target, the system and the plan order planned, each planned element
    citing cards and facts that exist, and the rest of the views on the rules with their plain "not planned" state."""
    from eaos.ai.ideal import base as ideal_base
    by_comp = {}
    for card in card_rows: by_comp.setdefault(card['paths'][0].split('/')[2], []).append(card)
    message = {'en': 'Planned by Claude Code (synthetic) on top of the rules.', 'ar': 'خطّطه Claude Code (اصطناعي) فوق القواعد.'}
    def element(i, c, operation, cites):
        return {'id': f'{c}', 'kind': 'component', 'title': c, 'operation': operation, 'subject': c, 'detail': f'{layer[c]} part', 'cites': cites}
    rules_system = [{**element(i, c, 'refactor', [card['evidence'][0] for card in by_comp.get(c, [])[:2]]), 'rules': ['RULE-disposition-modify']}
                    for i, c in enumerate(comps)]
    planned_system = [{**element(i, c, ('retain', 'refactor', 'merge', 'rebuild')[i % 4], [card['id'] for card in by_comp.get(c, [])[:3]]),
                       'id': f'plan-{c}'} for i, c in enumerate(comps) if by_comp.get(c)][:300]
    questions = [{'id': f'q{i + 1}', 'view': 'system', 'question': f'Keep {comps[i]} apart from {comps[i + 1]}?', 'options': ['yes', 'no'],
                  'recommendation': 'yes', 'why': 'the facts do not decide it'} for i in range(min(5, len(comps) - 1))]
    planned = _planned_provenance(message, planned_system, questions)
    views = {name: _ideal_view(name, rules_system, planned_system, planned) for name in ideal_base.VIEWS}
    return {**V2, 'state': 'planned', 'message': message, 'provenance': planned, 'views': views,
            'evidence': {'share': ratio(1.0, 'synthetic'), 'raw_share': ratio(0.98, 'synthetic'), 'elements': measure(len(planned_system), 'synthetic'),
                         'dropped': [{'view': 'system', 'id': 'invented-1', 'title': 'An invented part', 'why': 'no citation resolves'}]},
            'critique': {'missed': [], 'risks': [], 'order': []}, 'questions': questions,
            'runs': [{'at': WHEN, 'state': 'planned', 'assistant': 'Claude Code', 'model': 'synthetic', 'seconds': 120.0,
                      'passes': ['plan', 'critique'], 'message': f'{len(planned_system)} elements'}]}


def _planned_provenance(message, planned_system, questions):
    """How the system view was planned: by the assistant, its departures from the rules and its open questions."""
    return {'method': 'planned', 'state': 'planned', 'assistant': 'Claude Code', 'model': 'synthetic', 'at': WHEN, 'confidence': 0.7,
            'message': message, 'inputs': 'synthetic',
            'departures': [{'rule_says': f'modify {e["subject"]}', 'plan_chose': e['operation'], 'because': 'its cards share one owner',
                            'element': e['id'], 'cites': e['cites'][:1]} for e in planned_system[:10]],
            'open_questions': [{'id': q['id'], 'question': q['question'], 'recommendation': q['recommendation']} for q in questions]}


def _ideal_view(name, rules_system, planned_system, planned):
    """One view of the ideal: the system planned on top of its rules' target, every other view on the rules alone."""
    rows = rules_system if name == 'system' else []
    mine = planned_system if name == 'system' else []
    return {'provenance': planned if mine else _rules_provenance(),
            'rules': {'summary': f'The rules\' {name} target.', 'elements': rows[:400], 'count': measure(len(rows), 'synthetic')},
            'planned': {'summary': 'One owner per component.', 'confidence': 0.7, 'elements': mine,
                        'count': measure(len(mine), 'synthetic')} if mine else None,
            'differences': [{'element': e['id'], 'kind': 'changed' if e['operation'] != 'refactor' else 'same', 'subject': e['subject'],
                             'rules': 'refactor', 'planned': e['operation']} for e in mine]}


def _rules_provenance():
    return {'method': 'rules', 'state': 'not_planned', 'assistant': None, 'model': None, 'at': None, 'confidence': None,
            'message': {'en': "The rules' target only.", 'ar': 'هدف القواعد فقط.'}, 'departures': [], 'open_questions': []}


def build(cards=5000, components=1000, seed=7, functions_per_module=2, modules_per_component=3):
    """{section: data} for a synthetic project; nothing is written."""
    rng = random.Random(seed)
    comps, layer, modules, fns = _project(components, functions_per_module, modules_per_component)
    facts, card_rows = _card_rows(rng, cards, modules)
    by_comp = {}
    for card in card_rows: by_comp.setdefault(card.pop('_component'), []).append(card)
    steps = _steps(card_rows)
    ops, gaps = _ops_and_gaps(comps, layer, by_comp, modules_per_component)
    scans = _scans(cards)
    images, screens = _screens(comps, components)
    total, done = len(card_rows), sum(c['state'] in ('done', 'resolved') for c in card_rows)
    sections = {
        'meta': {**HEAD, 'languages': [{'name': 'TypeScript', 'files': len(modules), 'share': 1.0}],
                 'files': measure(len(modules), 'synthetic'), 'lines': measure(len(modules) * 120, 'synthetic', 'lines'),
                 'stages': [{'id': 'S01', 'title': 'S01', 'state': 'done'}]},
        'head': {**HEAD, 'scanned': {'commit': f'{29:07x}', 'branch': 'main', 'at': WHEN},
                 'eaos': {'version': 'synthetic', 'commit': 'synthetic', 'digest': 'synthetic'}, 'freshness': 'fresh',
                 'verdict': f'{total} problems; EAOS fixes {sum(c["fixable"] for c in card_rows)} of them by itself.',
                 'next': {'action': 'Start a fix batch', 'tool': 'fix_start'}},
        'health': _health(total, scans),
        'cards': {**HEAD, 'cards': card_rows},
        'evidence': {**HEAD, 'facts': facts},
        'story': _story(comps, layer, gaps, components, modules_per_component),
        'docs': {**HEAD, 'docs': _docs()},
        'plans': {**HEAD, 'plans': [{'id': 'fix', 'title': 'Fix plan', 'kind': 'fix', 'parent': None, 'state': 'active', 'goal': '', 'indicators': [],
                                     'steps': steps, 'progress': ratio(round(done / total, 4) if total else None, 'ledger')}]},
        'decisions': {**HEAD, 'decisions': _decisions(comps, by_comp, components)},
        'media': {**HEAD, 'images': images},
        'functions': {**V2, 'modules': [{'id': path, 'component': comp, 'language': 'TypeScript', 'functions': functions_per_module}
                                        for path, comp in modules], 'functions': _function_rows(fns)},
        'screens': {**V2, 'screens': screens},
        'gaps': {**V2, 'gaps': gaps},
        'operations': {**V2, 'operations': ops},
        'history': _history(scans, cards),
    }
    sections['paths'] = synthetic_paths(comps, layer, modules, card_rows)
    sections.update(maps(comps, layer, card_rows))
    data_paths, infra = data_maps(comps, layer, modules, rng)
    sections.update(data_paths={**V2, **data_paths}, infra={**V2, **infra})
    sections['pipeline'] = synthetic_pipeline(stages=max(components, 50))
    sections['ideal'] = synthetic_ideal(comps, layer, card_rows)
    sections['nodes'] = synthetic_nodes(card_rows)

    written = list(sections)
    sections['coverage'] = {**V2, **coverage_section.coverage(Path('.'), sections, written, [], 'en')}
    return sections


def _project(components, functions_per_module, modules_per_component):
    """(components, their layer, modules, functions) of the synthetic project."""
    comps = [f'{DOMAINS[i % len(DOMAINS)]}-{i // len(DOMAINS) + 1}' for i in range(components)]
    layer = {name: LAYERS[i % len(LAYERS)] for i, name in enumerate(comps)}
    modules = [(f'src/{layer[c]}/{c}/m{j}.ts', c) for c in comps for j in range(modules_per_component)]
    fns = [(f'{path}#fn{k}', f'fn{k}', path, c) for path, c in modules for k in range(functions_per_module)]
    return comps, layer, modules, fns


def _card_rows(rng, cards, modules):
    """The synthetic facts and cards, each card on a module of a component (its `_component`, taken out by build)."""
    facts, card_rows = [], []
    for i in range(cards):
        path, comp = modules[rng.randrange(len(modules))]
        kind, severity = KINDS[i % len(KINDS)], SEVERITIES[min(int(rng.random() ** 2 * 5), 4)]
        fact = f'FACT-{i:06d}'
        line = 1 + rng.randrange(400)
        facts.append({'id': fact, 'kind': 'engine_finding', 'engine': ('enola', 'jscpd', 'semgrep', 'knip')[i % 4], 'path': path,
                      'line': line, 'summary': f'{kind.replace("_", " ")} in {path}', 'sites': [{'path': path, 'line': 1}],
                      'code': {'start': max(1, line - 2), 'line': line, 'hidden': [],
                               'lines': [f'const v{n} = step{n}(input)  // m{i % 3}' for n in range(max(1, line - 2), line + 3)]}})
        card_rows.append({'id': f'TASK-{i + 1:05d}', 'key': f'k{i:06d}', 'title': f'{kind.replace("_", " ").capitalize()} in {comp} (m{i % 3})',
                          'kind': kind, 'category': ('structure', 'security', 'performance', 'cleanup')[i % 4], 'severity': severity,
                          'fixable': i % 3 == 0, 'needs_decision': i % 11 == 0, 'scope': 'group' if i % 17 == 0 else 'place',
                          'place': path, 'paths': [path], 'evidence': [fact], 'state': STATES[i % len(STATES)],
                          'milestone': f'M{i % 12 + 1}', 'confidence': (1.0, 0.7, 0.4)[i % 3], '_component': comp,
                          'why': dict(zip(('ar', 'en'), WHY[kind]))})
    return facts, card_rows


def _steps(card_rows):
    """The fix plan's twelve steps, each with the cards of its milestone."""
    steps = []
    for n in range(12):
        tasks = [c for c in card_rows if c['milestone'] == f'M{n + 1}']
        steps.append({'id': f'M{n + 1}', 'title': f'Step {n + 1}', 'state': 'active' if n < 3 else 'todo', 'weight': len(tasks),
                      'gate': f'Every card of step {n + 1} closed', 'depends_on': [f'M{n}'] if n else [], 'sub_plan': None,
                      'tasks': [{'id': c['id'], 'title': c['title'], 'state': TASK_STATE[c['state']], 'acceptance': None, 'depends_on': []}
                                for c in tasks]})
    return steps


def _ops_and_gaps(comps, layer, by_comp, files):
    """An operation and a gap per component, its cards with them."""
    closed = lambda rows: sum(c['state'] in ('done', 'resolved') for c in rows)
    ops, gaps = [], []
    for i, comp in enumerate(comps):
        op = OPERATIONS[i % len(OPERATIONS)]
        rows = by_comp.get(comp, [])
        ops.append({'id': f'op-{i + 1}', 'op': op, 'subject': comp, 'subject_kind': 'component', 'target': f'{layer[comp]}/{comp}',
                    'reason': f'{op.capitalize()} {comp} toward the target structure.', 'plan': 'fix', 'step': f'M{i % 12 + 1}', 'order': i + 1,
                    'after': [f'op-{i}'] if i % 5 else [], 'gap': f'gap-{comp}', 'cards': [c['id'] for c in rows[:20]],
                    'branch': None, 'state': 'todo'})
        gaps.append({'id': f'gap-{comp}', 'component': comp, 'operation': op, 'to': f'{layer[comp]}/{comp}', 'responsibility': f'Owns {comp}.',
                     'files': files, 'cards': [c['id'] for c in rows], 'cards_closed': closed(rows),
                     'steps': [f'M{i % 12 + 1}'], 'operations': [f'op-{i + 1}'], 'decision': None,
                     'closed': ratio(round(closed(rows) / len(rows), 4) if rows else None, 'cards_closed / cards')})
    return ops, gaps


def _function_rows(fns):
    """Each synthetic function, calling two others and called by those that call it."""
    callers = {fid: [] for fid, *_ in fns}
    function_rows = []
    for index, (fid, name, path, comp) in enumerate(fns):
        callees = [fns[(index + step) % len(fns)][0] for step in (1, 7) if len(fns) > 1]
        for callee in callees: callers[callee].append(fid)
        function_rows.append({'id': fid, 'name': name, 'module': path, 'line': 10, 'end_line': 30, 'language': 'TypeScript', 'kind': 'function',
                              'signature': f'{name}(input: unknown): void', 'summary': None, 'exported': index % 2 == 0,
                              'lines': measure(21, 'synthetic', 'lines'), 'complexity': measure(1 + index % 15, 'synthetic'),
                              'callers': [], 'callees': callees, 'reads': [], 'writes': [{'kind': 'table', 'name': comp.replace('-', '_')}],
                              'cards': []})
    for row in function_rows: row['callers'] = callers[row['id']][:20]
    return function_rows


def _scans(cards):
    """Thirty earlier checks, the open cards falling as they go."""
    return [{'id': f'scan{n:02d}', 'commit': f'{n:07x}', 'branch': 'main', 'at': f'2026-09-{n % 30 + 1:02d}T09:00:00+00:00',
                      'score': round(0.4 + n / 100, 3), 'open': {s: cards // (5 * (1 + n // 10)) for s in SEVERITIES},
             'added': None if n == 0 else 10, 'resolved': None if n == 0 else 25, 'open_keys': []} for n in range(30)]


def _screens(comps, components):
    """(the screen images, the screens): up to 200 screens, each shot once with one unlabelled field."""
    images = [{'id': f'screens/s{i}.png', 'path': f'screens/s{i}.png', 'title': f'Screen {i}', 'kind': 'screen', 'batch': None, 'phase': 'baseline',
               'route': f'/{DOMAINS[i % len(DOMAINS)]}', 'viewport': '390', 'pair': None} for i in range(40)]
    screens = [{'id': f'screen-{i}', 'route': f'/{DOMAINS[i % len(DOMAINS)]}/{i}', 'title': f'Screen {i}', 'component': comps[i % len(comps)],
                'file': f'src/pages/Screen{i}.tsx', 'shots': [{'path': f'screens/s{i % 40}.png', 'width': 390, 'phase': 'baseline', 'batch': None}],
                'inputs': [{'id': 'q', 'label': None, 'kind': 'text', 'labelled': False, 'validated': None, 'required': False}],
                'issues': [{'id': f'screen-{i}-1', 'rule': 'label', 'severity': 'high', 'summary': 'A field has no label.', 'element': 'input#q',
                            'width': 390, 'box': {'x': 16, 'y': 100, 'w': 358, 'h': 44}, 'card': None, 'state': 'open'}]}
               for i in range(min(200, components))]
    return images, screens


def _health(total, scans):
    return {**HEAD, 'score': ratio(0.69, 'synthetic'), 'formula': 'synthetic',
            'domains': [{'id': area, 'name': area, 'score': ratio(0.7, 'synthetic'), 'cards': total // 4}
                        for area in ('structure', 'security', 'performance', 'cleanup')],
            'history': [{'at': s['at'], 'commit': s['commit'], 'score': s['score']} for s in scans]}


def _story(comps, layer, gaps, components, files):
    return {**HEAD, 'current': {'summary': f'{components} components.',
                                'components': [{'name': c, 'layer': layer[c], 'files': files} for c in comps]},
            'target': {'summary': 'The same components, one owner each.',
                       'components': [{'name': f'{layer[c]}/{c}', 'responsibility': f'Owns {c}.', 'layer': layer[c]} for c in comps]},
            'gap': [{'component': g['component'], 'relation': 'modify', 'to': g['to'], 'files': g['files'], 'cards': g['cards'][:50],
                     'closed': g['cards_closed']} for g in gaps],
            'indicators': [{'id': 'S1', 'name': 'S1', 'today': measure(0.6, 'synthetic'), 'expected': measure(0.8, 'synthetic'),
                            'target': measure(0.9, 'synthetic')}]}


def _docs():
    return [{'id': f'docs/D{i}.md', 'title': f'Document {i}', 'path': f'docs/D{i}.md', 'group': ('start', 'story', 'plan', 'technical')[i % 4],
             'bytes': 4000, 'order': i} for i in range(100)]


def _decisions(comps, by_comp, components):
    return [{'id': f'decision-{i}', 'question': f'Approve the operation on {comps[i]}?',
             'recommendation': 'Yes.', 'options': [{'id': 'yes', 'label': 'Yes'}, {'id': 'later', 'label': 'Later'}],
             'blocks': [c['id'] for c in by_comp.get(comps[i], [])], 'state': 'waiting', 'answer': None,
             'plan': 'fix', 'asked': WHEN, 'tool': None} for i in range(min(20, components))]


def _history(scans, cards):
    return {**V2, 'scans': scans, 'events': [{'at': s['at'], 'kind': 'scan', 'title': f'Check {s["id"]}', 'ref': s['commit']} for s in scans],
            'progress': [{'at': s['at'], 'event': 'recheck' if n else 'baseline', 'closed': min(cards, 25 * n), 'total': cards,
                          'percent': round(min(cards, 25 * n) / cards, 4), 'commit': s['commit']} for n, s in enumerate(scans)]}


def write(folder, sections, name='synthetic'):
    """Write every section, checked against its contract, then the manifest; returns the problems found (none expected)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    contracts, problems, entries = artifact_contracts.contracts(), [], []
    for section, data in sections.items():
        problems += [f'{section}: {line}' for line in artifact_contracts.validate(data, contracts[f'studio-{section}'])[:5]]
        blob = export._write(folder, section, data)
        entries.append({'name': section, 'file': f'{section}.json', 'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob)})
    manifest = {**HEAD, 'revision': export.REVISION,
                'built': {'version': 'synthetic', 'commit': 'synthetic', 'digest': 'synthetic', 'studio_digest': 'synthetic', 'built': WHEN},
                'project': {'name': name}, 'scanned': sections['head']['scanned'], 'sections': entries}
    problems += [f'manifest: {line}' for line in artifact_contracts.validate(manifest, contracts['studio-manifest'])[:5]]
    export._write(folder, 'manifest', manifest)
    return problems


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--out', required=True)
    parser.add_argument('--cards', type=int, default=5000)
    parser.add_argument('--components', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=7)
    args = parser.parse_args(argv)
    problems = write(args.out, build(args.cards, args.components, args.seed))
    for line in problems: print(line, file=sys.stderr)
    print(f'wrote {args.out}: {args.cards} cards, {args.components} components' + (f'; {len(problems)} contract problems' if problems else ''))
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

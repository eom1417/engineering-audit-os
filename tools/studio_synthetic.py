"""A synthetic Studio data folder at scale: every section of contracts v1 and v2, valid, linked, and deterministic.

The Studio is built and gated against real reports, but none of them is large. This writes the folder EAOS would
write for a project of N cards and M components (default 5,000 and 1,000, STUDIO-COMPLETE.md), so the pages, the
search and the screen gates are tested at the scale a company project reaches. Every id a section cites exists in
the section it points to: a card's evidence, a function's callers, a gap's operations, an operation's step.

    python tools/studio_synthetic.py --out DIR [--cards 5000] [--components 1000] [--seed 7]

DIR then holds <section>.json, its .js twin and manifest.json, exactly as eaos/studio/export.py lays them out; give it
to the screen gates with `node studio/scripts/gates.mjs --data DIR`.
"""
import argparse
import hashlib
import json
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from eaos import artifact_contracts  # noqa: E402
from eaos.studio import coverage as coverage_section  # noqa: E402
from eaos.studio import data_paths as data_map  # noqa: E402
from eaos.studio import infra as infra_map  # noqa: E402
from eaos.studio import export  # noqa: E402

DOMAINS = ('work-orders', 'assets', 'vehicles', 'drivers', 'invoices', 'payments', 'inventory', 'reports', 'auth', 'users',
           'billing', 'routes', 'maintenance', 'fuel', 'alerts', 'audit', 'settings', 'notifications', 'contracts', 'suppliers')
LAYERS = ('pages', 'features', 'shared', 'data-access', 'config')
SEVERITIES = ('critical', 'high', 'medium', 'low', 'info')
KINDS = ('complexity', 'dead_code', 'literal_duplication', 'secret', 'missing_rls', 'layer_violation', 'cycle', 'unused_dependency')
OPERATIONS = ('retain', 'refactor', 'rebuild', 'merge', 'delete', 'new')
STATES = ('open', 'open', 'open', 'in_batch', 'on_branch', 'done', 'resolved', 'skipped')
TASK_STATE = export.TASK_STATE
HEAD = {'schema_version': 1, 'contract': export.CONTRACT}
V2 = {**HEAD, 'revision': export.REVISION}
WHEN = '2026-10-08T09:00:00+00:00'


def measure(value, src, unit='count'):
    return {'value': value, 'src': src, 'unit': unit}


def ratio(value, src):
    return {'value': value, 'src': src}


def maps(comps, layer, modules, rng):
    """The data paths and infrastructure sections, made by EAOS's own exporters from synthetic records: each module
    either writes one of its component's two tables or reads any table, and one write in twenty lands in another
    component's table, so some tables have several writers."""
    tables = [f'{c.replace("-", "_")}_{k}' for c in comps for k in ('items', 'log')]
    access, n = [], 0
    for i, (path, comp) in enumerate(modules):
        own = [f'{comp.replace("-", "_")}_items', f'{comp.replace("-", "_")}_log']
        calls = [(own[i % 2], ('insert', 'update')[i % 2]) if rng.random() > 0.05 else (tables[rng.randrange(len(tables))], 'update')]
        if i % 3 == 2: calls = [(tables[rng.randrange(len(tables))], 'select')]
        for table, op in calls:
            n += 1
            value = {'client': 'supabase', 'target': table, 'operation': op, 'bounded': None, 'category': 'source'}
            if op != 'select' and rng.random() < 0.6: value.update(keys=sorted(rng.sample(('name', 'state', 'owner', 'due', 'amount'), 2)), keys_partial=False)
            access.append({'id': f'FACT-DA-{n:06d}', 'kind': 'data_access', 'location': {'path': path, 'start_line': 1 + n % 300}, 'value': value})
    runtime = [{'id': 'FACT-R-1', 'kind': 'deployment_target', 'location': {'path': 'vercel.json'}, 'value': {'kind': 'hosting', 'host': 'Vercel'}},
               {'id': 'FACT-R-2', 'kind': 'ci_step', 'location': {'path': '.github/workflows/ci.yml'}, 'value': {'name': 'test'}}]
    runtime += [{'id': f'FACT-R-H{i}', 'kind': 'integration_target', 'location': {'path': modules[i][0]}, 'value': {'host': f'api.{d}.example-service.io'}}
                for i, d in enumerate(DOMAINS)]
    target = {'reference': 'react-vite-spa-rest',
              'current_components': [{'name': f'src/{layer[c]}/{c}', 'target_component': f'{layer[c]}/{c}', 'paths': []} for c in comps],
              'target_components': [{'name': f'{layer[c]}/{c}'} for c in comps],
              'infrastructure': [{'area': 'hosting', 'present': True, 'decision': 'Keep: declared.', 'tool': None, 'evidence': 'vercel.json'},
                                 {'area': 'observability', 'present': False, 'decision': 'Introduce: errors reported.', 'tool': 'OpenTelemetry', 'evidence': '0'}]}
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        (out / 'facts').mkdir()
        (out / 'facts/entrypoints.json').write_text(json.dumps({'facts': access}), encoding='utf-8')
        (out / 'facts/runtime.json').write_text(json.dumps({'facts': runtime}), encoding='utf-8')
        (out / 'target-architecture.json').write_text(json.dumps(target), encoding='utf-8')
        return data_map.data_paths(out, 'en'), infra_map.infra(out, 'en')


def build(cards=5000, components=1000, seed=7, functions_per_module=2, modules_per_component=3):
    """{section: data} for a synthetic project; nothing is written."""
    rng = random.Random(seed)
    comps = [f'{DOMAINS[i % len(DOMAINS)]}-{i // len(DOMAINS) + 1}' for i in range(components)]
    layer = {name: LAYERS[i % len(LAYERS)] for i, name in enumerate(comps)}
    modules = [(f'src/{layer[c]}/{c}/m{j}.ts', c) for c in comps for j in range(modules_per_component)]
    fns = [(f'{path}#fn{k}', f'fn{k}', path, c) for path, c in modules for k in range(functions_per_module)]

    facts, card_rows = [], []
    for i in range(cards):
        path, comp = modules[rng.randrange(len(modules))]
        kind, severity = KINDS[i % len(KINDS)], SEVERITIES[min(int(rng.random() ** 2 * 5), 4)]
        fact = f'FACT-{i:06d}'
        facts.append({'id': fact, 'kind': 'engine_finding', 'engine': ('enola', 'jscpd', 'semgrep', 'knip')[i % 4], 'path': path,
                      'line': 1 + rng.randrange(400), 'summary': f'{kind.replace("_", " ")} in {path}', 'sites': [{'path': path, 'line': 1}]})
        card_rows.append({'id': f'TASK-{i + 1:05d}', 'key': f'k{i:06d}', 'title': f'{kind.replace("_", " ").capitalize()} in {comp} (m{i % 3})',
                          'kind': kind, 'category': ('structure', 'security', 'performance', 'cleanup')[i % 4], 'severity': severity,
                          'fixable': i % 3 == 0, 'needs_decision': i % 11 == 0, 'scope': 'group' if i % 17 == 0 else 'place',
                          'place': path, 'paths': [path], 'evidence': [fact], 'state': STATES[i % len(STATES)],
                          'milestone': f'M{i % 12 + 1}', 'confidence': (1.0, 0.7, 0.4)[i % 3], '_component': comp})
    by_comp = {}
    for card in card_rows: by_comp.setdefault(card.pop('_component'), []).append(card)
    closed = lambda rows: sum(c['state'] in ('done', 'resolved') for c in rows)

    steps = []
    for n in range(12):
        tasks = [c for c in card_rows if c['milestone'] == f'M{n + 1}']
        steps.append({'id': f'M{n + 1}', 'title': f'Step {n + 1}', 'state': 'active' if n < 3 else 'todo', 'weight': len(tasks),
                      'gate': f'Every card of step {n + 1} closed', 'depends_on': [f'M{n}'] if n else [], 'sub_plan': None,
                      'tasks': [{'id': c['id'], 'title': c['title'], 'state': TASK_STATE[c['state']], 'acceptance': None, 'depends_on': []}
                                for c in tasks]})
    ops, gaps = [], []
    for i, comp in enumerate(comps):
        op = OPERATIONS[i % len(OPERATIONS)]
        rows = by_comp.get(comp, [])
        ops.append({'id': f'op-{i + 1}', 'op': op, 'subject': comp, 'subject_kind': 'component', 'target': f'{layer[comp]}/{comp}',
                    'reason': f'{op.capitalize()} {comp} toward the target structure.', 'plan': 'fix', 'step': f'M{i % 12 + 1}', 'order': i + 1,
                    'after': [f'op-{i}'] if i % 5 else [], 'gap': f'gap-{comp}', 'cards': [c['id'] for c in rows[:20]],
                    'branch': None, 'state': 'todo'})
        gaps.append({'id': f'gap-{comp}', 'component': comp, 'operation': op, 'to': f'{layer[comp]}/{comp}', 'responsibility': f'Owns {comp}.',
                     'files': modules_per_component, 'cards': [c['id'] for c in rows], 'cards_closed': closed(rows),
                     'steps': [f'M{i % 12 + 1}'], 'operations': [f'op-{i + 1}'], 'decision': None,
                     'closed': ratio(round(closed(rows) / len(rows), 4) if rows else None, 'cards_closed / cards')})
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
    scans = []
    for n in range(30):
        scans.append({'id': f'scan{n:02d}', 'commit': f'{n:07x}', 'branch': 'main', 'at': f'2026-09-{n % 30 + 1:02d}T09:00:00+00:00',
                      'score': round(0.4 + n / 100, 3), 'open': {s: cards // (5 * (1 + n // 10)) for s in SEVERITIES},
                      'added': None if n == 0 else 10, 'resolved': None if n == 0 else 25, 'open_keys': []})
    images = [{'id': f'screens/s{i}.png', 'path': f'screens/s{i}.png', 'title': f'Screen {i}', 'kind': 'screen', 'batch': None, 'phase': 'baseline',
               'route': f'/{DOMAINS[i % len(DOMAINS)]}', 'viewport': '390', 'pair': None} for i in range(40)]
    screens = [{'id': f'screen-{i}', 'route': f'/{DOMAINS[i % len(DOMAINS)]}/{i}', 'title': f'Screen {i}', 'component': comps[i % len(comps)],
                'file': f'src/pages/Screen{i}.tsx', 'shots': [{'path': f'screens/s{i % 40}.png', 'width': 390, 'phase': 'baseline', 'batch': None}],
                'inputs': [{'id': 'q', 'label': None, 'kind': 'text', 'labelled': False, 'validated': None, 'required': False}],
                'issues': [{'id': f'screen-{i}-1', 'rule': 'label', 'severity': 'high', 'summary': 'A field has no label.', 'element': 'input#q',
                            'width': 390, 'box': {'x': 16, 'y': 100, 'w': 358, 'h': 44}, 'card': None, 'state': 'open'}]}
               for i in range(min(200, components))]
    total, done = len(card_rows), sum(c['state'] in ('done', 'resolved') for c in card_rows)
    sections = {
        'meta': {**HEAD, 'languages': [{'name': 'TypeScript', 'files': len(modules), 'share': 1.0}],
                 'files': measure(len(modules), 'synthetic'), 'lines': measure(len(modules) * 120, 'synthetic', 'lines'),
                 'stages': [{'id': 'S01', 'title': 'S01', 'state': 'done'}]},
        'head': {**HEAD, 'scanned': {'commit': f'{29:07x}', 'branch': 'main', 'at': WHEN},
                 'eaos': {'version': 'synthetic', 'commit': 'synthetic', 'digest': 'synthetic'}, 'freshness': 'fresh',
                 'verdict': f'{total} problems; EAOS fixes {sum(c["fixable"] for c in card_rows)} of them by itself.',
                 'next': {'action': 'Start a fix batch', 'tool': 'fix_start'}},
        'health': {**HEAD, 'score': ratio(0.69, 'synthetic'), 'formula': 'synthetic',
                   'domains': [{'id': area, 'name': area, 'score': ratio(0.7, 'synthetic'), 'cards': total // 4}
                               for area in ('structure', 'security', 'performance', 'cleanup')],
                   'history': [{'at': s['at'], 'commit': s['commit'], 'score': s['score']} for s in scans]},
        'cards': {**HEAD, 'cards': card_rows},
        'evidence': {**HEAD, 'facts': facts},
        'story': {**HEAD, 'current': {'summary': f'{components} components.',
                                      'components': [{'name': c, 'layer': layer[c], 'files': modules_per_component} for c in comps]},
                  'target': {'summary': 'The same components, one owner each.',
                             'components': [{'name': f'{layer[c]}/{c}', 'responsibility': f'Owns {c}.', 'layer': layer[c]} for c in comps]},
                  'gap': [{'component': g['component'], 'relation': 'modify', 'to': g['to'], 'files': g['files'], 'cards': g['cards'][:50],
                           'closed': g['cards_closed']} for g in gaps],
                  'indicators': [{'id': 'S1', 'name': 'S1', 'today': measure(0.6, 'synthetic'), 'expected': measure(0.8, 'synthetic'),
                                  'target': measure(0.9, 'synthetic')}]},
        'docs': {**HEAD, 'docs': [{'id': f'docs/D{i}.md', 'title': f'Document {i}', 'path': f'docs/D{i}.md', 'group': ('start', 'story', 'plan', 'technical')[i % 4],
                                   'bytes': 4000, 'order': i} for i in range(100)]},
        'plans': {**HEAD, 'plans': [{'id': 'fix', 'title': 'Fix plan', 'kind': 'fix', 'parent': None, 'state': 'active', 'goal': '', 'indicators': [],
                                     'steps': steps, 'progress': ratio(round(done / total, 4) if total else None, 'ledger')}]},
        'decisions': {**HEAD, 'decisions': [{'id': f'decision-{i}', 'question': f'Approve the operation on {comps[i]}?',
                                             'recommendation': 'Yes.', 'options': [{'id': 'yes', 'label': 'Yes'}, {'id': 'later', 'label': 'Later'}],
                                             'blocks': [c['id'] for c in by_comp.get(comps[i], [])], 'state': 'waiting', 'answer': None,
                                             'plan': 'fix', 'asked': WHEN, 'tool': None} for i in range(min(20, components))]},
        'media': {**HEAD, 'images': images},
        'functions': {**V2, 'modules': [{'id': path, 'component': comp, 'language': 'TypeScript', 'functions': functions_per_module}
                                        for path, comp in modules], 'functions': function_rows},
        'screens': {**V2, 'screens': screens},
        'gaps': {**V2, 'gaps': gaps},
        'operations': {**V2, 'operations': ops},
        'history': {**V2, 'scans': scans, 'events': [{'at': s['at'], 'kind': 'scan', 'title': f'Check {s["id"]}', 'ref': s['commit']} for s in scans]},
        'quality': {**V2, 'detectors': [{'id': f'{k}', 'name': k, 'engine': None, 'applies': True, 'precision': ratio(0.9, 'synthetic'),
                                         'recall': ratio(None, 'not measured'), 'labelled': None} for k in KINDS],
                    'capabilities': [{'id': 'C2', 'name': 'Current state', 'value': ratio(0.6, 'synthetic')}],
                    'indicators': [{'id': 'S1', 'name': 'S1', 'value': ratio(0.88, 'synthetic'), 'target': 0.8}]},
    }
    data_paths, infra = maps(comps, layer, modules, rng)
    sections.update(data_paths={**V2, **data_paths}, infra={**V2, **infra})
    written = list(sections)
    sections['coverage'] = {**V2, **coverage_section.coverage(Path('.'), sections, written, [], 'en')}
    return sections


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

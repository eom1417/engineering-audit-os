"""The report's maps: today's parts and their imports, files, functions and pages; the target; the gap closed; every card."""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import dev_paths  # noqa: E402

from eaos import arch_map, blueprint, human_report
from eaos.human_report import readability_problems
from test_human_report import report, section

CHIEF = dev_paths.MEASURE / 'mcp/chief-ops/EAOS/project/technical'


def node(path, depends, group=None):
    return {'kind': 'graph_node', 'location': {'path': path},
            'value': {'depends_on': depends, 'fan_in': 0, 'fan_out': len(depends), 'cycle_group': group}}


def facts(out):
    """Imports: src/a <-> src/api/users (a loop across two parts), src/b -> src/a; functions and calls; one page."""
    (out / 'facts').mkdir(exist_ok=True)
    graph = [node('src/a.ts', ['src/api/users.ts'], 0), node('src/api/users.ts', ['src/a.ts'], 0),
             node('src/b.ts', ['src/a.ts']), node('src/old.ts', []),
             {'kind': 'graph_cycle', 'location': {'path': 'src/a.ts'}, 'value': {'members': ['src/a.ts', 'src/api/users.ts']}}]
    scopes = [('src/a.ts', 'helper'), ('src/a.ts', 'save'), ('src/api/users.ts', 'listUsers'), ('src/b.ts', 'main')]
    structure = [{'kind': 'scope', 'location': {'path': p, 'symbol': f'<module>.{n}'}, 'value': {'name': n, 'kind': 'function'}} for p, n in scopes]
    structure += [{'kind': 'call_site', 'location': {'path': p, 'symbol': s}, 'value': {'callee': c, 'attribute': False}}
                  for p, s, c in (('src/b.ts', '<module>.main', 'save'), ('src/a.ts', '<module>.<module>.save.<anon>', 'helper'),
                                  ('src/a.ts', '<module>.save', 'listUsers'), ('src/b.ts', '<module>.main', 'nowhere'))]
    flow = {'kind': 'flow', 'location': {'path': 'src/api/users.ts', 'symbol': 'listUsers'},
            'value': {'flow_id': 'FLOW-001', 'entry': {'surface': 'endpoint', 'route': '/users', 'http_method': 'GET',
                                                       'path': 'src/api/users.ts', 'handler': 'listUsers'},
                      'steps': [{'from': 'listUsers', 'from_path': 'src/api/users.ts', 'callee': 'save', 'resolution': 'imported',
                                 'to_path': 'src/a.ts', 'to_symbol': 'save', 'depth': 0},
                                {'from': 'save', 'from_path': 'src/a.ts', 'callee': 'mystery', 'resolution': 'unresolved',
                                 'to_path': None, 'to_symbol': None, 'depth': 1}]}}
    for name, rows in (('graph', graph), ('structure', structure), ('flows', [flow])):
        (out / 'facts' / f'{name}.json').write_text(json.dumps({'facts': rows}), encoding='utf-8')


def ledger():
    cards = [{'key': 'k1', 'id': 'TASK-1', 'title': 't1', 'pattern': 'upgrade_dependency', 'milestone': 'M01', 'paths': ['package-lock.json'],
              'state': 'done', 'new': False, 'batch': 1, 'at': '2026-09-28T10:00:00+00:00', 'why': '', 'commit': 'abc1234'},
             {'key': 'k3', 'id': 'TASK-3', 'title': 't3', 'pattern': 'remove_dead', 'milestone': 'M01', 'paths': ['src/old.ts'],
              'state': 'on_branch', 'new': False, 'batch': 2, 'at': None, 'why': '', 'commit': None},
             {'key': 'k6', 'id': 'TASK-6', 'title': 't6', 'pattern': 'hotspot', 'milestone': 'M02', 'paths': ['src/api/users.ts'],
              'state': 'skipped', 'new': False, 'batch': None, 'at': None, 'why': 'a public name changes', 'commit': None},
             {'key': 'gone0001', 'id': None, 'title': 'Unused helper removed from src/gone.ts', 'pattern': 'remove_dead', 'milestone': 'M01',
              'paths': ['src/gone.ts'], 'state': 'resolved', 'new': False, 'batch': None, 'at': '2026-09-27T09:00:00+00:00', 'why': '', 'commit': None}]
    return {'schema_version': 1, 'updated': '2026-09-29T10:00:00+00:00', 'commit': 'abc',
            'totals': {'total': 7, 'closed': 2, 'done': 1, 'resolved': 1, 'on_branch': 1, 'in_batch': 0, 'open': 4, 'skipped': 1, 'new': 0, 'percent': 28.6},
            'cards': cards, 'history': [{'at': '2026-09-20T10:00:00+00:00', 'event': 'baseline', 'closed': 0, 'total': 6, 'percent': 0.0, 'batch': None},
                                        {'at': '2026-09-29T10:00:00+00:00', 'event': 'merged', 'closed': 2, 'total': 7, 'percent': 28.6, 'batch': 1}]}


def overlaps(nodes, width, height):
    return [(a['id'], b['id']) for i, a in enumerate(nodes) for b in nodes[i + 1:]
            if a['x'] < b['x'] + width and b['x'] < a['x'] + width and a['y'] < b['y'] + height and b['y'] < a['y'] + height]


class MapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = report(self.tmp.name)
        facts(self.out)

    def test_the_parts_are_laid_out_without_overlap_and_the_loop_is_marked(self):
        cmap = arch_map.component_map(self.out)
        self.assertEqual(overlaps(cmap['nodes'], arch_map.NODE_W, arch_map.NODE_H), [])
        edges = {(e['from'], e['to']): e for e in cmap['edges']}
        self.assertTrue(edges[('T-src', 'T-api')]['cycle'] and edges[('T-api', 'T-src')]['cycle'])
        self.assertEqual(sum(e['back'] for e in cmap['edges']), 1, 'one edge of the loop is set aside to layer the rest')
        src = next(n for n in cmap['nodes'] if n['id'] == 'T-src')
        self.assertEqual((src['inside'], src['ce'], src['cohesion']), (1, 1, 50))

    def test_the_drill_down_resolves_calls_by_name_and_skips_what_it_cannot(self):
        drill = arch_map.drill_data(self.out, arch_map.component_map(self.out))
        files = drill['files']
        calls = {(files[a], f, files[b], g) for a, f, b, g, _ in drill['calls']}
        self.assertEqual(calls, {('src/b.ts', 'main', 'src/a.ts', 'save'), ('src/a.ts', 'save', 'src/a.ts', 'helper'),
                                 ('src/a.ts', 'save', 'src/api/users.ts', 'listUsers')})

    def test_a_flow_is_drawn_to_where_the_trace_stops(self):
        flow = arch_map.flow_charts(self.out)[0]
        kinds = [n['kind'] for n in flow['nodes']]
        self.assertEqual(kinds, ['entry', 'handler', 'fn', 'stop'])
        self.assertEqual(len({(n['x'], n['y']) for n in flow['nodes']}), 4)

    def test_the_page_embeds_parseable_maps_and_every_card_collapsed(self):
        page = human_report.write(self.out, 'ar', progress={'waves': [], 'ledger': ledger()}).read_text(encoding='utf-8')
        self.assertEqual(readability_problems(page), [])
        for part in ('cards', 'arch-map', 'arch-drill', 'flows', 'target-map', 'target-mapping', 'progress-history'):
            self.assertIn(f'data-part="{part}"', page)
        drill = json.loads(re.search(r'<script type="application/json" id="eaos-drill">(.*?)</script>', page, re.S).group(1))
        self.assertEqual(len(drill['comps']), 2)
        json.loads(re.search(r'<script type="application/json" id="eaos-flows">(.*?)</script>', page, re.S).group(1))
        self.assertRegex(page, r'<details class="card allcards" id="allcards" data-part="cards">')
        cards = section(page, 'plan')
        self.assertIn('Unused helper removed from src/gone.ts', cards, 'a card the plan no longer has still shows')
        self.assertIn('a public name changes', cards)
        self.assertIn('>29%<', section(page, 'summary'), 'the ledger percent, in whole percents above ten')
        self.assertIn('class="edge cyc', section(page, 'structure'))

    def test_only_merged_or_resolved_cards_close_a_milestone(self):
        page = human_report.write(self.out, 'en', progress={'waves': [], 'ledger': ledger()}).read_text(encoding='utf-8')
        plan = section(page, 'plan')
        # M01: TASK-1 done and the resolved ledger-only card, of four cards; TASK-3 is only on a branch
        self.assertIn('aria-valuenow="50"', plan)

    def test_the_page_works_without_a_ledger_and_with_nothing(self):
        page = human_report.write(self.out, 'en').read_text(encoding='utf-8')
        self.assertEqual(readability_problems(page), [])
        self.assertIn('data-part="cards"', page)
        text = human_report.render(human_report.empty(), 'shop', 'en')
        self.assertEqual(readability_problems(text), [])
        self.assertNotIn('<!-- ', text)
        shutil.rmtree(self.out / 'facts')
        page = human_report.write(self.out, 'en').read_text(encoding='utf-8')
        self.assertIn('Not available in this report.', section(page, 'structure'))
        self.assertEqual(readability_problems(page), [])


class BlueprintMapTests(unittest.TestCase):
    def test_the_blueprint_draws_its_layers_and_lists_every_card_with_its_state(self):
        from test_blueprint import spec
        stack = blueprint.choose_stack(spec())
        built = blueprint.design(spec(), stack)
        ids = [c['id'] for c in built['plan']['tasks']]
        text = blueprint.page(spec(), stack, built, [{'number': 1, 'milestone': 'M01', 'branch': 'eaos/build-1', 'kept': ids[:1], 'skipped': {ids[1]: 'refused'}}])
        self.assertIn('data-part="target-map"', text)
        self.assertEqual(text.count('class="tcard"'), len(ids))
        self.assertEqual(text.count('data-state="done"'), 2, 'the built card, and its chip')
        self.assertIn('refused', text)


@unittest.skipUnless((CHIEF / 'facts' / 'graph.json').is_file(), 'the chief-ops report is not on this machine')
class ChiefOpsTests(unittest.TestCase):
    def test_a_real_report_reads_well(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / 'facts').mkdir()
            for name in ('plan.json', 'dossier.json', 'debt-register.json', 'run-manifest.json', 'target-architecture.json', 'gap-matrix.json'):
                shutil.copy(CHIEF / name, out / name)
            for name in ('graph', 'flows', 'structure'):
                shutil.copy(CHIEF / 'facts' / f'{name}.json', out / 'facts' / f'{name}.json')
            cmap = arch_map.component_map(out)
            self.assertEqual(overlaps(cmap['nodes'], arch_map.NODE_W, arch_map.NODE_H), [])
            page = human_report.write(out, 'ar', progress={'waves': [], 'ledger': ledger()}).read_text(encoding='utf-8')
        self.assertEqual(readability_problems(page), [])
        self.assertNotRegex(page, r'<!-- \w+ -->', 'no section fell back to "not available"')


if __name__ == '__main__':
    unittest.main()

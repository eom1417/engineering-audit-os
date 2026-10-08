"""studio/system.json: the territory maps of today and the target, read from the scan's records and laid out by EAOS."""
import json
import math
import tempfile
import unittest
from pathlib import Path

from eaos import artifact_contracts
from eaos.studio import system, territory

FLEET = ['(root)', 'DbTest', 'DbTest/obj/Debug/net8.0', 'src', 'src/Service', 'src/components', 'src/components/auth',
         'src/components/drivers', 'src/components/drivers/tabs', 'src/components/fuel', 'src/components/maintenance',
         'src/components/maintenance/hooks', 'src/components/shops', 'src/components/sync', 'src/components/tolls',
         'src/components/trailer', 'src/components/vehicle', 'src/components/workorder', 'src/contexts', 'src/hooks',
         'src/lib', 'src/pages', 'src/pages/settings', 'src/pages/unused', 'src/types', 'unused-archive',
         'unused-archive/supabase-integrations']


def component(name, relation, target, paths, cid=None):
    return {'id': cid or f'T-{name}', 'name': name, 'kind': 'package', 'relation': relation, 'target_component': target,
            'files': len(paths), 'paths': paths, 'fan_in': 1, 'fan_out': 2, 'reason': 'Because. (2 file(s))'}


def write_report(folder):
    folder = Path(folder)
    target = {
        'current_components': [
            component('src', 'modify', 'app', ['src/main.ts']),
            component('src/api', 'rebuild', 'api-client', ['src/api/a.ts', 'src/api/b.ts']),
            component('src/ui', 'retain', 'features', ['src/ui/x.tsx', 'src/ui/y.tsx', 'src/ui/z.tsx']),
            component('src/ui/old', 'delete', 'features', ['src/ui/old/w.tsx']),
        ],
        'target_components': [{'name': 'app', 'layer': 'app', 'files': 1, 'responsibility': 'Start the app'},
                              {'name': 'api-client', 'layer': 'api-client', 'files': 2, 'responsibility': 'Talk to the server'},
                              {'name': 'features', 'layer': 'features', 'files': 4, 'responsibility': 'Screens'},
                              {'name': 'lib', 'layer': 'lib', 'files': 0, 'responsibility': 'Shared helpers'}],
        'target_edges': [{'from': 'app', 'to': 'features', 'imports': 3}, {'from': 'features', 'to': 'api-client', 'imports': 2}],
        'decisions': [{'id': 'ADR-001', 'component_id': 'T-src/api', 'chosen': 'Rebuild it behind one client.'}],
    }
    nodes = [('src/main.ts', ['src/ui/x.tsx', 'src/api/a.ts']), ('src/ui/x.tsx', ['src/api/a.ts', 'src/ui/y.tsx']),
             ('src/ui/y.tsx', ['src/api/b.ts']), ('src/api/a.ts', ['src/ui/z.tsx']), ('src/ui/old/w.tsx', ['src/ui/x.tsx'])]
    graph = {'facts': [{'kind': 'graph_node', 'location': {'path': p}, 'value': {'depends_on': d}} for p, d in nodes]}
    (folder / 'facts').mkdir(parents=True, exist_ok=True)
    (folder / 'facts' / 'graph.json').write_text(json.dumps(graph), encoding='utf-8')
    (folder / 'target-architecture.json').write_text(json.dumps(target), encoding='utf-8')
    cards = [{'id': 'T1', 'severity': 'high', 'paths': ['src/ui/old/w.tsx'], 'state': 'open'},
             {'id': 'T2', 'severity': 'low', 'paths': ['src/ui/x.tsx', 'src/api/a.ts'], 'state': 'open'},
             {'id': 'T3', 'severity': 'medium', 'paths': ['README.md'], 'state': 'done'}]
    return cards


class Regions(unittest.TestCase):
    def test_folders_split_until_no_region_holds_most_components(self):
        region_of, regions = system.group(FLEET)
        ids = {r['id'] for r in regions}
        self.assertEqual(ids, {'dir:src/components', 'dir:src/pages', 'rest:src', 'top:'})
        self.assertEqual(region_of['src/components/drivers/tabs'], 'dir:src/components')
        self.assertEqual(region_of['src/lib'], 'rest:src')          # a single-folder child joins its parent's rest
        self.assertEqual(region_of['src'], 'rest:src')
        self.assertEqual(region_of['DbTest'], 'top:')              # small top-level folders share one region
        self.assertLessEqual(len(regions), territory.MAX_REGIONS)

    def test_known_folder_names_are_translated_and_others_stay_identifiers(self):
        self.assertEqual(system.region_name('dir', 'src/components'), {'ar': 'مكونات الواجهة', 'en': 'Components', 'ident': False})
        self.assertTrue(system.region_name('dir', 'app/zebra')['ident'])

    def test_a_dot_is_labelled_without_its_regions_folder(self):
        region = {'folder': 'src/components'}
        self.assertEqual(system.short('src/components/drivers/tabs', region), 'drivers/tabs')
        self.assertEqual(system.short('src/components', region), 'components')


class Section(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cards = write_report(self.tmp.name)
        self.out = system.system(self.tmp.name, self.cards)
        self.nodes = {n['id']: n for n in self.out['current']['nodes']}

    def tearDown(self):
        self.tmp.cleanup()

    def test_it_meets_its_contract(self):
        data = {'schema_version': 1, 'contract': 1, **self.out}
        self.assertEqual(artifact_contracts.validate(data, artifact_contracts.contracts()['studio-system']), [])

    def test_imports_are_counted_between_the_components_owning_both_files(self):
        edges = {(e['from'], e['to']): e['imports'] for e in self.out['current']['edges']}
        self.assertEqual(edges[('src/ui', 'src/api')], 2)            # x.tsx -> a.ts, y.tsx -> b.ts; y.tsx -> x is inside
        self.assertEqual(edges[('src', 'src/ui')], 1)
        self.assertNotIn(('src/ui', 'src/ui'), edges)
        self.assertEqual(self.out['counts']['imports']['value'], sum(edges.values()))
        cycle = {(e['from'], e['to']): e['cycle'] for e in self.out['current']['edges']}
        self.assertTrue(cycle[('src/ui', 'src/api')] and cycle[('src/api', 'src/ui')])
        self.assertFalse(cycle[('src', 'src/ui')])

    def test_a_card_counts_in_the_deepest_component_of_its_first_path(self):
        self.assertEqual(self.nodes['src/ui/old']['findings']['high'], 1)
        self.assertEqual(self.nodes['src/ui']['findings']['total'], 1)
        self.assertEqual(self.nodes['src/api']['findings']['total'], 0)
        self.assertEqual(sum(n['findings']['total'] for n in self.nodes.values()), 2)   # README.md has no component here

    def test_each_target_says_how_it_comes_about(self):
        ops = {n['id']: n['op'] for n in self.out['target']['nodes']}
        self.assertEqual(ops, {'app': 'modify', 'api-client': 'rebuild', 'features': 'merge', 'lib': 'introduce'})
        features = next(n for n in self.out['target']['nodes'] if n['id'] == 'features')
        self.assertEqual(features['sources'], ['src/ui', 'src/ui/old'])
        self.assertEqual(self.nodes['src/ui']['merged_with'], 1)
        self.assertEqual(self.out['operations']['merge']['value'], 1)
        self.assertEqual(self.out['operations']['delete']['value'], 1)

    def test_the_structure_decision_is_attached_to_its_component(self):
        self.assertEqual(self.nodes['src/api']['decision'], {'id': 'ADR-001', 'chosen': 'Rebuild it behind one client.'})
        self.assertEqual(self.nodes['src/api']['reason'], 'Because.')

    def test_the_layout_is_deterministic_and_inside_the_world(self):
        again = system.system(self.tmp.name, self.cards)
        self.assertEqual(json.dumps(again, sort_keys=True), json.dumps(self.out, sort_keys=True))
        for view in (self.out['current'], self.out['target']):
            for n in view['nodes']:
                self.assertTrue(0 <= n['x'] - n['r'] and n['x'] + n['r'] <= territory.W, n['id'])
                self.assertTrue(0 <= n['y'] - n['r'] and n['y'] + n['r'] <= territory.H, n['id'])
            for r in view['regions']:
                self.assertTrue(r['land'], r['id'])
                self.assertTrue(all(l['d'].startswith('M') and l['d'].endswith('Z') for l in r['land']))
            x, y, w, h = view['bounds']
            self.assertTrue(w > 0 and h > 0 and x + w <= territory.W and y + h <= territory.H)

    def test_a_large_folder_is_always_labelled(self):
        many = [component(f'src/f{i}', 'retain', 'app', [f'src/f{i}/{j}.ts' for j in range(30 if i < 3 else 1)]) for i in range(40)]
        nodes = [{'id': c['name'], 'short': c['name'], 'files': c['files'], 'region': 'r'} for c in many]
        pic = territory.draw(nodes, [], [{'id': 'r', 'name': {'ar': 'س', 'en': 'Source', 'ident': False}}])
        for c in many[:3]:
            self.assertTrue(pic['nodes'][c['name']]['label']['placed'], c['name'])

    def test_no_dots_overlap(self):
        nodes = self.out['current']['nodes']
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                self.assertGreater(((a['x'] - b['x']) ** 2 + (a['y'] - b['y']) ** 2) ** .5, a['r'] + b['r'], (a['id'], b['id']))

    def test_a_report_without_the_records_gives_empty_maps_and_unmeasured_imports(self):
        with tempfile.TemporaryDirectory() as empty:
            out = system.system(empty, [])
        self.assertEqual(out['current']['nodes'], [])
        self.assertIsNone(out['counts']['imports']['value'])
        data = {'schema_version': 1, 'contract': 1, **out}
        self.assertEqual(artifact_contracts.validate(data, artifact_contracts.contracts()['studio-system']), [])


class Geometry(unittest.TestCase):
    def test_squarify_fills_the_room_with_every_weight(self):
        rects = territory.squarify([6, 6, 4, 3, 2, 2, 1], 0, 0, 600, 400)
        self.assertEqual(len(rects), 7)
        self.assertAlmostEqual(sum(w * h for _, _, w, h in rects), 600 * 400, places=3)

    def test_a_crowded_map_shrinks_its_dots(self):
        self.assertEqual(territory.radius_scale([3] * 10), 1.0)
        files = [400] * 150
        scale = territory.radius_scale(files)
        self.assertLess(scale, 1.0)
        covered = sum(math.pi * territory.radius(f, scale) ** 2 for f in files)
        self.assertLessEqual(covered, territory.W * territory.H / 3)

    def test_squarify_keeps_the_order_of_its_weights(self):
        rects = territory.squarify([8, 4, 2, 1], 0, 0, 400, 300)
        areas = [w * h for _, _, w, h in rects]
        self.assertEqual(areas, sorted(areas, reverse=True))
        self.assertAlmostEqual(areas[0] / areas[1], 2, places=6)

    def test_the_geometry_is_pure_python_and_direction_neutral(self):
        source = Path(territory.__file__).read_text(encoding='utf-8')
        self.assertNotIn('numpy', source.split('"""', 2)[2])
        drawing = (Path(__file__).resolve().parents[1] / 'studio/src/map/TerritoryMap.tsx').read_text(encoding='utf-8')
        self.assertIn('preserveAspectRatio="xMidYMid meet" direction="ltr"', drawing)


if __name__ == '__main__':
    unittest.main()

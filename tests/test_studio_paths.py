"""studio/paths.json: the code paths through their layers, with evidence, gaps instead of invented links, the target of
every step, the layout EAOS computes, the clustered overview and the plan's timeline (eaos/studio/paths.py)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from shared_fixture import Workspace

from eaos import artifact_contracts
from eaos.studio import export, paths

ROOT = Path(__file__).resolve().parent.parent


def fact(fid, kind, path, line, value, symbol=None, resolution='RESOLVED'):
    return {'id': fid, 'kind': kind, 'location': {'path': path, 'start_line': line, 'symbol': symbol}, 'value': value,
            'resolution': resolution}


def symbol(path, name, start, end, kind='function', parent=None):
    return {'kind': 'symbol', 'location': {'path': path, 'start_line': start, 'end_line': end, 'symbol': name},
            'value': {'name': name, 'kind': kind, 'parent': parent, 'exported': True}}


def write_report(folder):
    """A small project: two pages and a server. /orders calls GET /api/orders (answered by a server route whose
    handler uses the db part and defines the orders table) and POST /api/audit (no server route: a gap); /about's
    component cannot be found; the orders page's flow stops twice."""
    folder = Path(folder)
    (folder / 'facts').mkdir(parents=True, exist_ok=True)
    entry = lambda fid, path, line, surface, route, handler, method=None: fact(fid, 'entry_point', path, line, {
        'surface': surface, 'route': route, 'http_method': method, 'handler': handler, 'framework': 'x', 'category': 'source'})
    records = {
        'entrypoints': [entry('F-page', 'src/App.tsx', 10, 'page', '/orders', 'OrdersPage'),
                        entry('F-about', 'src/App.tsx', 11, 'page', '/about', 'AboutPage'),
                        entry('F-route', 'server/routes/orders.ts', 4, 'http', '/api/orders', 'listOrders', 'GET'),
                        fact('F-call1', 'data_access', 'src/api/orders.ts', 7, {'client': 'http', 'target': '/api/orders', 'operation': 'get'}, 'api'),
                        fact('F-call2', 'data_access', 'src/api/orders.ts', 12, {'client': 'http', 'target': '/api/audit', 'operation': 'post'}, 'api')],
        'syntax': [symbol('src/pages/OrdersPage.tsx', 'OrdersPage', 1, 40), symbol('src/api/orders.ts', 'fetchOrders', 5, 9),
                   symbol('src/api/orders.ts', 'audit', 11, 14), symbol('server/routes/orders.ts', 'listOrders', 3, 20),
                   symbol('server/db/store.ts', 'query', 1, 9),
                   {'kind': 'import_edge', 'location': {'path': 'server/db/store.ts'}, 'value': {'module': 'pg', 'style': 'absolute'}}],
        'graph': [{'kind': 'graph_node', 'location': {'path': p}, 'value': {'depends_on': d}} for p, d in (
            ('src/App.tsx', ['src/pages/OrdersPage.tsx']), ('src/pages/OrdersPage.tsx', ['src/api/orders.ts']),
            ('server/routes/orders.ts', ['server/db/store.ts']), ('server/db/store.ts', []), ('src/api/orders.ts', []))],
        'flows': [fact('F-flow', 'flow', 'src/App.tsx', 10, {
            'flow_id': 'FLOW-001', 'entry': {'surface': 'page', 'route': '/orders', 'path': 'src/App.tsx', 'handler': 'OrdersPage'},
            'steps': [{'from': 'OrdersPage', 'from_path': 'src/pages/OrdersPage.tsx', 'callee': 'fetchOrders', 'line': 12,
                       'resolution': 'imported', 'to_path': 'src/api/orders.ts', 'to_symbol': 'fetchOrders', 'depth': 0},
                      {'from': 'OrdersPage', 'from_path': 'src/pages/OrdersPage.tsx', 'callee': 'setRows', 'line': 14,
                       'resolution': 'unresolved', 'to_path': None, 'to_symbol': None, 'depth': 0},
                      {'from': 'OrdersPage', 'from_path': 'src/pages/OrdersPage.tsx', 'callee': 'pick', 'line': 15,
                       'resolution': 'ambiguous', 'to_path': None, 'to_symbol': None, 'depth': 0}],
            'unresolved_steps': 2}),
            fact('F-flow2', 'flow', 'server/routes/orders.ts', 4, {
                'flow_id': 'FLOW-002', 'entry': {'surface': 'http', 'route': '/api/orders', 'path': 'server/routes/orders.ts', 'handler': 'listOrders'},
                'steps': [{'from': 'listOrders', 'from_path': 'server/routes/orders.ts', 'callee': 'query', 'line': 6,
                           'resolution': 'imported', 'to_path': 'server/db/store.ts', 'to_symbol': 'query', 'depth': 0}],
                'unresolved_steps': 0})],
        'domain': [fact('F-table', 'data_table', 'server/db/store.ts', 2, {'name': 'orders'})],
    }
    for name, rows in records.items():
        (folder / 'facts' / f'{name}.json').write_text(json.dumps({'facts': rows}), encoding='utf-8')
    comp = lambda name, relation, target, files: {'id': f'T-{name}', 'name': name, 'relation': relation, 'target_component': target,
                                                  'files': len(files), 'paths': files}
    (folder / 'target-architecture.json').write_text(json.dumps({
        'current_components': [comp('src', 'modify', 'app', ['src/App.tsx']),
                               comp('src/pages', 'rebuild', 'features', ['src/pages/OrdersPage.tsx']),
                               comp('src/api', 'retain', 'features', ['src/api/orders.ts']),
                               comp('server/routes', 'modify', 'api', ['server/routes/orders.ts']),
                               comp('server/db', 'delete', 'data', ['server/db/store.ts'])],
        'target_components': [{'name': n, 'layer': n} for n in ('app', 'features', 'api', 'data', 'audit')]}), encoding='utf-8')
    plan = {'tasks': [{'id': 'T1', 'paths': ['src/api/orders.ts']}, {'id': 'T2', 'paths': ['src/api/orders.ts', 'x.ts']},
                      {'id': 'T3', 'paths': ['y.ts'], 'prerequisites': [{'task_id': 'T1', 'reason': 'the client first'}]},
                      {'id': 'T4', 'paths': ['z.ts']}],
            'milestones': [{'id': 'M01', 'goal': 'Stabilise', 'name': 'stabilize', 'tasks': ['T1', 'T2']},
                           {'id': 'M02', 'goal': 'Rebuild', 'name': 'build', 'tasks': ['T3', 'T4']}],
            'waves': [{'wave': 1, 'tasks': ['T1', 'T4']}, {'wave': 2, 'tasks': ['T2', 'T3']}]}
    cards = [{'id': 'T1', 'title': 'Fix the client', 'paths': ['src/api/orders.ts'], 'milestone': 'M01', 'state': 'open'},
             {'id': 'T2', 'title': 'Split it', 'paths': ['src/api/orders.ts'], 'milestone': 'M01', 'state': 'done'}]
    return cards, plan


class Paths(Workspace):
    def setUp(self):
        super().setUp()
        self.cards, self.plan = write_report(self.tmp)
        self.body = paths.paths(self.tmp, self.cards, self.plan, 'en')
        self.nodes = {n['id']: n for n in self.body['nodes']}
        self.path = {p['id']: p for p in self.body['paths']}

    def walked(self, pid):
        return [(e['from'], e['to'], e['how']) for e in (self.body['edges'][i] for i in self.path[pid]['steps'])]

    def test_a_page_walks_its_layers_and_every_link_carries_its_evidence(self):
        steps = self.walked('orders-orderspage')
        self.assertEqual(steps[:4], [
            ('S:/orders OrdersPage', 'C:src/pages/OrdersPage.tsx', 'route'),
            ('C:src/pages/OrdersPage.tsx', 'H:src/api/orders.ts#fetchOrders', 'call'),
            ('H:src/api/orders.ts#fetchOrders', 'A:GET /api/orders', 'request'),
            ('A:GET /api/orders', 'E:server/routes/orders.ts#listOrders', 'route')])
        self.assertIn(('E:server/routes/orders.ts#listOrders', 'M:server/db', 'call'), steps)
        self.assertIn(('E:server/routes/orders.ts#listOrders', 'T:orders', 'defines'), steps)
        self.assertIn(('E:server/routes/orders.ts#listOrders', 'X:PostgreSQL database', 'package'), steps)
        edges = {(e['from'], e['to']): e for e in self.body['edges']}
        self.assertEqual((edges[('H:src/api/orders.ts#fetchOrders', 'A:GET /api/orders')]['fact'],
                          edges[('H:src/api/orders.ts#fetchOrders', 'A:GET /api/orders')]['line']), ('F-call1', 7))
        self.assertEqual(edges[('C:src/pages/OrdersPage.tsx', 'H:src/api/orders.ts#fetchOrders')]['fact'], 'F-flow')
        self.assertEqual(self.nodes['A:GET /api/orders']['fact'], 'F-call1')
        self.assertEqual(self.nodes['H:src/api/orders.ts#audit']['label'], 'audit')    # the function holding the call
        self.assertEqual(self.nodes['T:orders']['fact'], 'F-table')

    def test_where_the_records_stop_the_path_draws_a_gap_never_an_invented_link(self):
        steps = self.walked('orders-orderspage')
        self.assertIn(('A:POST /api/audit', 'G:endpoint:POST /api/audit', 'gap'), steps)
        gap = self.nodes['G:endpoint:POST /api/audit']
        self.assertEqual((gap['kind'], gap['lane'], gap['reason'], gap['component']), ('gap', 'endpoint', 'no_server_route', None))
        self.assertFalse([s for s in steps if s[0] == 'G:endpoint:POST /api/audit'], 'nothing follows a gap')
        about = self.walked('about-aboutpage')
        self.assertEqual(about, [('S:/about AboutPage', 'G:component:about-aboutpage', 'route')])
        self.assertEqual(self.nodes['G:component:about-aboutpage']['reason'], 'component_not_found')
        trace = self.nodes['G:trace:orders-orderspage']
        self.assertEqual((trace['reason'], trace['detail']), ('trace_stopped', '2'))
        self.assertEqual([(i['callee'], i['line']) for i in trace['items']], [('setRows', 14), ('pick', 15)])
        counts = {k: v['value'] for k, v in self.body['counts'].items()}
        self.assertEqual((counts['gaps'], counts['no_server_route'], counts['component_not_found'], counts['trace_stopped']), (3, 1, 1, 1))
        self.assertEqual(counts['unresolved_steps'], 2)
        self.assertTrue(all(v['src'] for v in self.body['counts'].values()))

    def test_every_step_names_its_part_its_operation_and_its_target(self):
        parts = self.body['components']
        self.assertEqual(parts['src/pages'], {'op': 'rebuild', 'target': 'features', 'layer': 'features'})
        self.assertEqual(parts['src/api']['op'], 'merge')           # two parts of today feed `features`
        self.assertEqual(parts['server/db']['op'], 'delete')
        self.assertEqual(self.body['new'], ['audit'])
        self.assertEqual(self.nodes['H:src/api/orders.ts#fetchOrders']['component'], 'src/api')
        self.assertEqual(self.nodes['H:src/api/orders.ts#fetchOrders']['cards'], ['T1', 'T2'])
        self.assertEqual(self.nodes['H:src/api/orders.ts#fetchOrders']['steps'], ['M01'])

    def test_the_layout_puts_each_node_once_in_its_lane_and_does_not_move_between_runs(self):
        again = paths.paths(self.tmp, self.cards, self.plan, 'en')
        for path, other in zip(self.body['paths'], again['paths']):
            self.assertEqual(path['columns'], other['columns'])
            placed = [n for column in path['columns'] for n in column]
            self.assertEqual(len(placed), len(set(placed)))
            for lane, column in zip(paths.LANES, path['columns']):
                self.assertTrue(all(self.nodes[n]['lane'] == lane for n in column), lane)
            ends = {self.body['edges'][i][end] for i in path['steps'] for end in ('from', 'to')} | {path['entry']}
            self.assertEqual(set(placed), ends)

    def test_the_overview_clusters_parts_and_cuts_them_to_folders_when_there_are_too_many(self):
        overview = self.body['overview']
        ids = {c['id'] for c in overview['clusters']}
        self.assertIn('K:endpoint:no_server_route:/api/audit', ids)
        self.assertEqual(sum(c['size'] for c in overview['clusters']), len(self.body['nodes']))
        self.assertTrue(overview['all'])
        many = [{'id': f'n{i}', 'lane': 'handler', 'kind': 'step', 'component': f'src/area{i % 4}/part{i}', 'reason': None,
                 'group': None, 'label': f'n{i}'} for i in range(paths.MAX_CLUSTERS + 50)]
        cut = paths.overview(many, [])
        self.assertEqual((cut['level'], len(cut['clusters'])), (1, 4))
        self.assertEqual(paths._folder('src', 3), 'src')            # never below the first folder

    def test_the_timeline_runs_by_waves_and_says_what_each_task_waits_for(self):
        tl = self.body['timeline']
        self.assertEqual([w['wave'] for w in tl['waves']], [1, 2])
        rows = {t['id']: t for t in tl['tasks']}
        self.assertEqual(rows['T2']['waits'], [{'task': 'T1', 'why': 'same_file', 'detail': 'src/api/orders.ts'}])
        self.assertEqual(rows['T3']['waits'], [{'task': 'T1', 'why': 'prerequisite', 'detail': 'the client first'}])
        self.assertEqual((rows['T1']['waits'], rows['T4']['waits']), ([], []))   # tasks of one wave never wait on each other
        self.assertEqual([(s['id'], s['first'], s['last']) for s in tl['steps']], [('M01', 1, 2), ('M02', 1, 2)])
        self.assertEqual(rows['T1']['title'], 'Fix the client')
        self.assertIsNone(paths.timeline({}, [], 'en'))

    def test_the_section_meets_its_contract_and_its_coverage_counts_the_gaps(self):
        contracts = artifact_contracts.contracts()
        data = {'schema_version': 1, 'contract': 1, 'revision': 2, **self.body}
        self.assertEqual(artifact_contracts.validate(data, contracts['studio-paths']), [])
        source = (ROOT / 'tests/fixtures/studio/v2/paths.json').read_bytes()
        self.assertEqual(artifact_contracts.validate(json.loads(source), contracts['studio-paths']), [])
        # the Studio's gallery draws the same fixture, mirrored byte for byte inside studio/
        self.assertEqual((ROOT / 'studio/src/pages/paths/fixture.json').read_bytes(), source)


class Export(unittest.TestCase):
    def test_the_exporter_writes_paths_as_a_v2_section_listed_in_the_manifest_and_counted_in_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            write_report(folder)
            result = export.export(folder, 'en', name='demo')
            self.assertIn('paths', result['written'], result['errors'])
            data = json.loads((Path(folder) / 'studio/paths.json').read_text(encoding='utf-8'))
            self.assertEqual((data['contract'], data['revision']), (1, 2))
            manifest = json.loads((Path(folder) / 'studio/manifest.json').read_text(encoding='utf-8'))
            self.assertIn('paths', [s['name'] for s in manifest['sections']])
            row = next(r for r in json.loads((Path(folder) / 'studio/coverage.json').read_text(encoding='utf-8'))['sections']
                       if r['section'] == 'paths')
            self.assertEqual(row['state'], 'measured')
            parts = {p['id']: p['state'] for p in row['parts']}
            self.assertEqual(parts, {'links': 'measured', 'no_server_route': 'not_measured', 'trace_stopped': 'not_measured',
                                     'component_not_found': 'not_measured'})


class Synthetic(unittest.TestCase):
    def test_the_synthetic_project_has_paths_past_the_cluster_threshold(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        import studio_synthetic
        body = studio_synthetic.build(cards=600, components=300)['paths']
        self.assertGreater(len(body['nodes']), paths.CLUSTER_AT)
        self.assertFalse(body['overview']['all'])
        self.assertLessEqual(len(body['overview']['clusters']), paths.MAX_CLUSTERS)


if __name__ == '__main__':
    unittest.main()

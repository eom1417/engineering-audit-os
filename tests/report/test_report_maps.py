"""The report's maps: the current parts and their imports, files, functions and flows, and the system map (pages, APIs,
server handlers, parts, data)."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.analysis.maps import architecture as arch_map, system as system_map

def _task(number, pattern, claim, paths, ready=True):
    return {'id': f'TASK-{number}', 'claim_id': claim, 'pattern': pattern, 'title': f'{pattern} in {paths[0]}',
            'kind': 'remediate' if ready else 'investigate', 'paths': paths, 'effort': 'S', 'priority': 0.1 * number,
            'decision': {'readiness': 'ready' if ready else 'needs_review',
                         'allowed_outcomes': [] if ready else ['repair', 'retain', 'blocked_missing_requirement']},
            'options': [{'option': 'Extract the shared part', 'cost': 'medium', 'verdict': 'chosen by default'}]}


def report(root):
    """A small report: six cards in four areas, one failed stage, a two-part target."""
    out = Path(root)
    tasks = [_task(1, 'upgrade_dependency', 'CLM-1', ['package-lock.json']),
             _task(2, 'layer_boundary', 'CLM-2', ['src/api/users.ts'], ready=False),
             _task(3, 'remove_dead', 'CLM-3', ['src/old.ts']),
             _task(4, 'canonicalize', 'CLM-4', ['src/a.ts', 'src/b.ts']),
             _task(5, 'import_cycle', 'CLM-5', ['src/a.ts', 'src/api/users.ts']),
             _task(6, 'hotspot', 'CLM-6', ['src/api/users.ts'], ready=False)]
    plan = {'tasks': tasks, 'milestones': [
        {'id': 'M01', 'name': 'stabilize', 'goal': 'Nothing broken.', 'goal_ar': 'لا شيء مكسور.', 'exit': 'All pass.',
         'exit_ar': 'كل شيء يمر.', 'tasks': ['TASK-1', 'TASK-2', 'TASK-3']},
        {'id': 'M02', 'name': 'boundaries', 'goal': 'No cycle.', 'goal_ar': 'لا دورة.', 'exit': 'No cycle.',
         'exit_ar': 'لا دورة.', 'tasks': ['TASK-4', 'TASK-5', 'TASK-6']}]}
    confidence = {'CLM-2': 'LIKELY', 'CLM-4': 'LIKELY'}
    claims = [{'id': f'CLM-{n}', 'statement': f'claim {n}', 'confidence': confidence.get(f'CLM-{n}', 'CONFIRMED'),
               'assessment': {'before': f'before {n}', 'after': f'after {n}'}} for n in range(1, 7)]
    dossier = {'claims': claims, 'coverage': {'source_files': 50, 'files_parsed': 50, 'executed_verification': False,
                                              'runtime_confirmation': 0, 'semantic_review': False},
               'provenance': {'generated_at': '2026-09-27T00:00:00'}}
    register = {'items': [{'claim_id': 'CLM-1', 'severity': 'medium', 'category': 'supply_chain'},
                          {'claim_id': 'CLM-2', 'severity': 'critical', 'category': 'security'}]}     # an open table (M6)
    manifest = {'target': '/x/shop', 'stages': {'facts': {'status': 'ok'}, 'load': {'status': 'failed'},
                                                 'measure': {'status': 'ok'}, 'verify': {'status': 'unavailable'}}}
    target = {'root': '', 'forbidden_edges': 2,
              'current_components': [{'id': 'T-src', 'name': 'src', 'relation': 'modify', 'files': 3, 'target_component': 'lib',
                                      'paths': ['src/a.ts', 'src/b.ts', 'src/old.ts']},
                                     {'id': 'T-api', 'name': 'src/api', 'relation': 'rebuild', 'files': 1, 'target_component': 'routes',
                                      'paths': ['src/api/users.ts']}],
              'target_components': [{'name': 'routes', 'layer': 'routes', 'files': 1}, {'name': 'lib', 'layer': 'lib', 'files': 3}],
              'gap_matrix': [{'component': 'T-src', 'current_origin': 'src', 'current': {'relation': 'modify'}, 'gap': 'partial',
                              'target_component': 'lib', 'files_to_move': 1, 'forbidden_imports': 0}]}
    for name, record in (('plan.json', plan), ('dossier.json', dossier), ('debt-register.json', register),
                         ('run-manifest.json', manifest), ('target-architecture.json', target)):
        (out / name).write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
    return out


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


def overlaps(nodes, width, height):
    return [(a['id'], b['id']) for i, a in enumerate(nodes) for b in nodes[i + 1:]
            if a['x'] < b['x'] + width and b['x'] < a['x'] + width and a['y'] < b['y'] + height and b['y'] < a['y'] + height]


def fact(kind, path, value, symbol=None):
    return {'kind': kind, 'location': {'path': path, 'symbol': symbol}, 'value': value}


def system(out):
    """Two pages; /users calls its own APIs and, with /settings, the shared web/shared/api.ts; one API has no handler.
    GET and POST /api/users are file-routed (server/routes/users.ts exports GET and POST); GET /api/me is a declared
    route; both reach server/data/users-db.ts (tables users, sessions), which imports pg. A test file's call is left
    out."""
    out = Path(out)
    (out / 'facts').mkdir(exist_ok=True)
    rows = {
        'entrypoints': [fact('entry_point', 'web/App.tsx', {'surface': 'page', 'route': '/users', 'handler': 'UsersPage'}),
                        fact('entry_point', 'web/App.tsx', {'surface': 'page', 'route': '/settings', 'handler': 'Settings'}),
                        fact('entry_point', 'server/routes/me.ts', {'surface': 'http', 'route': '/api/me', 'http_method': 'GET', 'handler': 'getMe'}),
                        fact('data_access', 'web/pages/UsersPage.tsx', {'client': 'http', 'target': '/api/users', 'operation': 'get', 'category': 'source'}),
                        fact('data_access', 'web/pages/UsersPage.tsx', {'client': 'http', 'target': '/api/users?page=${n}', 'operation': 'post', 'category': 'source'}),
                        fact('data_access', 'web/shared/api.ts', {'client': 'http', 'target': '/api/me', 'operation': 'get', 'category': 'source'}),
                        fact('data_access', 'web/pages/Settings.tsx', {'client': 'http', 'target': '/api/nowhere', 'operation': 'get', 'category': 'source'}),
                        fact('data_access', 'tests/users.test.ts', {'client': 'http', 'target': '/api/users', 'operation': 'delete', 'category': 'test'})],
        'syntax': [fact('symbol', 'web/pages/UsersPage.tsx', {'name': 'UsersPage', 'exported': True, 'kind': 'function'}),
                   fact('symbol', 'web/pages/Settings.tsx', {'name': 'Settings', 'exported': True, 'kind': 'function'}),
                   fact('symbol', 'server/routes/users.ts', {'name': 'GET', 'exported': True, 'kind': 'function'}),
                   fact('symbol', 'server/routes/users.ts', {'name': 'POST', 'exported': True, 'kind': 'function'}),
                   fact('import_edge', 'server/db.ts', {'module': 'pg', 'style': 'absolute'})],
        'graph': [fact('graph_node', p, {'depends_on': d}) for p, d in (
            ('web/App.tsx', ['web/pages/UsersPage.tsx', 'web/pages/Settings.tsx']), ('web/pages/UsersPage.tsx', ['web/shared/api.ts']),
            ('web/pages/Settings.tsx', ['web/shared/api.ts']), ('web/shared/api.ts', []),
            ('server/routes/users.ts', ['server/data/users-db.ts']), ('server/routes/me.ts', ['server/data/users-db.ts']),
            ('server/data/users-db.ts', ['server/db.ts']), ('server/db.ts', []))],
        'domain': [fact('data_table', 'server/data/users-db.ts', {'name': n}) for n in ('users', 'sessions', 'IF')],
    }
    for name, records in rows.items():
        (out / 'facts' / f'{name}.json').write_text(json.dumps({'facts': records}), encoding='utf-8')
    (out / 'features.json').write_text(json.dumps({'features': [
        {'name': 'users', 'surfaces': ['/users'], 'endpoints': ['GET /api/users', 'POST /api/users', 'GET /api/me'], 'files': []},
        {'name': 'settings', 'surfaces': ['/settings'], 'endpoints': ['GET /api/me'], 'files': []}]}), encoding='utf-8')
    target = json.loads((out / 'target-architecture.json').read_text(encoding='utf-8'))
    target['current_components'] += [
        {'id': 'T-web', 'name': 'web', 'relation': 'modify', 'files': 4, 'paths': ['web/App.tsx', 'web/pages/UsersPage.tsx', 'web/pages/Settings.tsx', 'web/shared/api.ts']},
        {'id': 'T-routes', 'name': 'server/routes', 'relation': 'retain', 'files': 2, 'paths': ['server/routes/users.ts', 'server/routes/me.ts']},
        {'id': 'T-data', 'name': 'server/data', 'relation': 'retain', 'files': 2, 'paths': ['server/data/users-db.ts', 'server/db.ts']}]
    (out / 'target-architecture.json').write_text(json.dumps(target), encoding='utf-8')
    return out


class MapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = report(self.tmp.name)
        facts(self.out)

    def test_parts_files_and_flows_are_drawn_from_the_facts(self):
        cmap = arch_map.component_map(self.out)
        self.assertEqual(overlaps(cmap['nodes'], arch_map.NODE_W, arch_map.NODE_H), [])
        edges = {(e['from'], e['to']): e for e in cmap['edges']}
        self.assertTrue(edges[('T-src', 'T-api')]['cycle'] and edges[('T-api', 'T-src')]['cycle'])
        self.assertEqual(sum(e['back'] for e in cmap['edges']), 1, 'one edge of the loop is set aside to layer the rest')
        src = next(n for n in cmap['nodes'] if n['id'] == 'T-src')
        self.assertEqual((src['inside'], src['ce'], src['cohesion']), (1, 1, 50))
        # The drill-down resolves calls by name and skips what it cannot; a flow is drawn to where the trace stops.
        drill = arch_map.drill_data(self.out, arch_map.component_map(self.out))
        files = drill['files']
        calls = {(files[a], f, files[b], g) for a, f, b, g, _ in drill['calls']}
        self.assertEqual(calls, {('src/b.ts', 'main', 'src/a.ts', 'save'), ('src/a.ts', 'save', 'src/a.ts', 'helper'),
                                 ('src/a.ts', 'save', 'src/api/users.ts', 'listUsers')})
        flow = arch_map.flow_charts(self.out)[0]
        kinds = [n['kind'] for n in flow['nodes']]
        self.assertEqual(kinds, ['entry', 'handler', 'fn', 'stop'])
        self.assertEqual(len({(n['x'], n['y']) for n in flow['nodes']}), 4)

class SystemMapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = system(report(self.tmp.name))
        self.sm = system_map.build(self.out)

    def test_each_api_is_mapped_to_its_server_code_and_a_page_lights_all_it_reaches(self):
        apis = {a['key']: a for a in self.sm['apis']}
        self.assertEqual(set(apis), {'GET /api/users', 'POST /api/users', 'GET /api/me', 'GET /api/nowhere'})
        self.assertEqual(apis['GET /api/users']['handlers'], [{'path': 'server/routes/users.ts', 'function': 'GET', 'how': 'file routing'}])
        self.assertEqual(apis['POST /api/users']['handlers'][0]['function'], 'POST', 'the query and template are cut off the call')
        self.assertEqual(apis['GET /api/me']['handlers'], [{'path': 'server/routes/me.ts', 'function': 'getMe', 'how': 'entry point'}])
        self.assertEqual((apis['GET /api/nowhere']['handlers'], self.sm['unknown']), ([], 1))
        self.assertEqual(apis['GET /api/users']['callers'], ['web/pages/UsersPage.tsx'], 'a test file is not a caller')
        self.assertEqual(apis['GET /api/users']['tables'], ['sessions', 'users'], 'IF is a word of SQL, not a table')
        self.assertEqual(system_map.route_of_file('app/server/routes/auth/google-start.ts'), 'auth/google-start')
        self.assertTrue(system_map.same_route('/api/users/:id', '/api/users/[id]'))
        users = set(self.sm['related']['P:/users UsersPage'])
        self.assertLessEqual({'A:GET /api/users', 'A:POST /api/users', 'C:web/shared/api.ts', 'A:GET /api/me', 'H:server/routes/users.ts',
                              'H:server/routes/me.ts', 'M:T-data', 'T:users', 'T:sessions', 'S:PostgreSQL database'}, users)
        settings = set(self.sm['related']['P:/settings Settings'])
        self.assertIn('T:users', settings, 'through the shared file and GET /api/me')
        self.assertNotIn('A:GET /api/users', settings)
        self.assertLessEqual({'P:/users UsersPage', 'P:/settings Settings', 'A:GET /api/me'}, set(self.sm['related']['T:users']))
        kinds = {(e['from'], e['to']): e['kind'] for e in self.sm['edges']}
        self.assertEqual(kinds[('P:/users UsersPage', 'A:GET /api/users')], 'call')
        self.assertEqual(kinds[('P:/users UsersPage', 'C:web/shared/api.ts')], 'uses')
        self.assertEqual(kinds[('C:web/shared/api.ts', 'A:GET /api/me')], 'call')
        self.assertEqual(kinds[('M:T-data', 'T:users')], 'data')


if __name__ == '__main__':
    unittest.main()

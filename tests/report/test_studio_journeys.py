"""studio/journeys.json and studio/hidden.json: the user's journeys between screens, and what runs unseen behind them,
read from the scan's facts with their evidence, never invented (eaos/report/studio/user_journeys/, hidden.py)."""
import json
import unittest
from pathlib import Path

from eaos.core.contracts import artifact_rules as artifact_contracts
from eaos.report.studio import coverage, hidden, user_journeys as journeys
from tests.shared_fixture import TemporaryWorkspace

R = 'src/App.tsx'


def fact(kind, path, line, value, fid=None, symbol=None):
    loc = {'path': path, 'start_line': line}
    if symbol: loc['symbol'] = symbol
    return {'id': fid or f'FACT-{kind}-{path}-{line}'.replace('/', '_'), 'kind': kind, 'location': loc, 'value': value}


def page(route, handler, line, declared=None):
    v = {'surface': 'page', 'route': route, 'handler': handler, 'framework': 'react_router', 'category': 'source'}
    if declared: v['declared'] = declared
    return fact('entry_point', R, line, v, symbol=handler)


def nav(path, line, target, via='link', symbol=None, relative=False):
    return fact('navigation', path, line, {'target': target, 'via': via, 'dynamic': ':param' in target, 'relative': relative,
                                            'category': 'source'}, symbol=symbol)


def write_report(folder):
    """A small app: a public start that redirects into a layout under /app, a sidebar menu, a list and its detail, a
    create form, a dialog, a duplicate route, a screen no link reaches, a broken link and a link in dead code."""
    folder = Path(folder)
    (folder / 'facts').mkdir(parents=True, exist_ok=True)
    entry = [
        page('/', 'Root', 10), page('/terms', 'Terms', 11), page('/app/*', 'Shell', 12),
        page('/app', 'Home', 13, '/'), page('/app/items', 'Items', 14, '/items'), page('/app/items/new', 'CreateItemPage', 15, '/items/new'),
        page('/app/items/:id', 'Item', 16, '/items/:id'), page('/app/old', 'Items', 17, '/old'), page('/app/lost', 'Lost', 18, '/lost'),
        page('/app/*', 'NotFound', 19, '*'), page('*', 'NotFound', 20),
        nav(R, 30, '/app', 'redirect', symbol='Root'),
        nav('src/nav/menu.ts', 3, '/app/items', 'menu'),
        nav('src/pages/Items.tsx', 40, '/app/items/new'),
        nav('src/pages/Items.tsx', 41, '/app/items/:param', 'navigate'),
        nav('src/pages/Item.tsx', 50, '/app/missing'),
        nav('src/dead/Widget.tsx', 5, '/app/lost'),
        fact('data_access', 'src/api/items.ts', 9, {'client': 'http', 'target': '/items', 'operation': 'post', 'category': 'source'}),
        fact('data_access', 'src/dead/Widget.tsx', 7, {'client': 'http', 'target': '/widgets', 'operation': 'delete', 'category': 'source'}),
        fact('entry_point', 'jobs/nightly.py', 4, {'surface': 'job', 'route': 'nightly', 'handler': 'nightly', 'framework': 'celery', 'category': 'source'}),
    ]
    files = {R: ['src/pages/Home.tsx', 'src/pages/Items.tsx', 'src/pages/CreateItemPage.tsx', 'src/pages/Item.tsx', 'src/pages/Lost.tsx',
                 'src/pages/Terms.tsx', 'src/pages/NotFound.tsx', 'src/Sidebar.tsx'],
             'src/Sidebar.tsx': ['src/nav/menu.ts'], 'src/pages/Items.tsx': ['src/items/EditItemDialog.tsx', 'src/api/items.ts'],
             'src/pages/CreateItemPage.tsx': ['src/api/items.ts'], 'src/items/EditItemDialog.tsx': [], 'src/api/items.ts': [],
             'src/pages/Item.tsx': [], 'src/pages/Home.tsx': [], 'src/pages/Lost.tsx': [], 'src/pages/Terms.tsx': [],
             'src/pages/NotFound.tsx': [], 'src/nav/menu.ts': [], 'src/dead/Widget.tsx': []}
    graph = [fact('graph_node', p, 1, {'depends_on': d}) for p, d in files.items()]
    names = {'Home': './pages/Home', 'Items': './pages/Items', 'CreateItemPage': './pages/CreateItemPage', 'Item': './pages/Item',
             'Lost': './pages/Lost', 'Terms': './pages/Terms', 'NotFound': './pages/NotFound'}
    syntax = [fact('import_edge', R, 1, {'module': m, 'names': [n]}) for n, m in names.items()]
    syntax.append(fact('symbol', R, 5, {'name': 'Root'}))
    dead = [fact('engine_finding', 'src/dead/Widget.tsx', 1, {'rule': 'unreachable-module', 'kind': 'dead_code'})]
    runtime = [fact('integration_target', 'src/api/items.ts', 2, {'host': 'api.example.com'})]
    for name, rows in (('entrypoints', entry), ('graph', graph), ('syntax', syntax), ('deadcode', dead), ('runtime', runtime)):
        (folder / 'facts' / f'{name}.json').write_text(json.dumps({'facts': rows}), encoding='utf-8')
    target = {'current_components': [
        {'id': 'T-src', 'name': 'src', 'relation': 'modify', 'target_component': 'app', 'paths': [R, 'src/Sidebar.tsx']},
        {'id': 'T-src.pages', 'name': 'src/pages', 'relation': 'rebuild', 'target_component': 'pages',
         'paths': [p for p in files if p.startswith('src/pages/')]},
        {'id': 'T-src.dead', 'name': 'src/dead', 'relation': 'delete', 'target_component': None, 'paths': ['src/dead/Widget.tsx']}],
        'target_components': [{'name': 'pages', 'paths': ['src/pages/Items.tsx']}]}
    (folder / 'target-architecture.json').write_text(json.dumps(target), encoding='utf-8')
    (folder / 'features.json').write_text(json.dumps({'features': [{'name': 'items', 'surfaces': ['/app/items']}]}), encoding='utf-8')
    return folder


class Journeys(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.report = write_report(cls.workspace().name)
        cls.j = journeys.build(cls.report, media=[])
        cls.s = {s['id']: s for s in cls.j['screens']}
        cls.edges = {(e['from'], e['to']): e for e in cls.j['edges']}

    def test_screens_links_broken_links_and_flags_come_from_the_records_with_their_evidence(self):
        self.assertEqual(self.s['/app/items']['file'], 'src/pages/Items.tsx')
        self.assertEqual((self.s['/app/*#Shell']['kind'], self.s['/app/*#NotFound']['kind'], self.s['*']['kind']), ('layout', 'fallback', 'fallback'))
        self.assertEqual(self.s['/app/items']['fact'], 'FACT-entry_point-src_App.tsx-14')
        self.assertEqual(self.edges[('/', '/app')]['via'], 'redirect')                   # the handler Root holds it
        self.assertIn(('menu:src/App.tsx', '/app/items'), self.edges)                   # the sidebar, reached from the router
        self.assertIn(('/app', 'menu:src/App.tsx'), self.edges)                         # the menu hangs under the layout's root
        self.assertIn(('/app/items', '/app/items/:id'), self.edges)                     # a :param link opens a :param route
        site = self.edges[('/app/items', '/app/items/new')]['evidence'][0]
        self.assertEqual((site['file'], site['line']), ('src/pages/Items.tsx', 40))
        self.assertEqual([(b['from'], b['target']) for b in self.j['broken']], [('/app/items/:id', '/app/missing')])
        self.assertEqual([(u['file'], u['dead']) for u in self.j['unowned']], [('src/dead/Widget.tsx', True)])
        self.assertNotIn(('src/dead/Widget.tsx', '/app/lost'), self.edges, 'a link in dead code is counted, not drawn')
        for screen, flag in (('/app/lost', 'no_way_in'), ('/terms', 'no_way_in'), ('/terms', 'dead_end'), ('/app/old', 'duplicate'),
                             ('/app/items/:id', 'broken_link')):
            self.assertIn(flag, self.s[screen]['flags'], (screen, flag))
        self.assertEqual(self.s['/app/old']['twins'], ['/app/items'])
        self.assertNotIn('dead_end', self.s['/app/items/:id']['flags'])                  # it has the menu

    def test_tasks_targets_and_a_stable_layout_meet_the_contract(self):
        tasks = {t['id']: t for t in self.j['tasks']}
        self.assertEqual(tasks['task:create:item']['path'], ['/', '/app', 'menu:src/App.tsx', '/app/items', '/app/items/new'])
        self.assertEqual((tasks['task:edit:item']['kind'], tasks['task:edit:item']['screen']), ('dialog', '/app/items'))
        self.assertEqual((self.s['/app/items']['op'], self.s['/app/items']['target'], self.s['/app/items']['decided']), ('rebuild', 'pages', False))
        self.assertEqual(self.s['/']['component'], 'src')                                # defined in the router
        gaps = {g['id']: g for g in self.j['missing']}
        self.assertEqual(gaps['screen_target']['count']['value'], self.j['counts']['screens']['value'])
        self.assertIn('shots', gaps)
        self.assertEqual((self.s['/']['col'], self.s['/app']['col']), (0, 1))
        previous = {'screens': [{**s, 'col': 9, 'row': 9} if s['id'] == '/app/items' else s for s in self.j['screens']], 'menus': self.j['menus']}
        moved = {s['id']: (s['col'], s['row']) for s in journeys.build(self.report, previous, media=[])['screens']}
        self.assertEqual(moved['/app/items'], (9, 9), 'a screen keeps its cell across scans')
        self.assertEqual(moved['/'], (self.s['/']['col'], self.s['/']['row']))
        data = {'schema_version': 1, 'contract': 1, 'revision': 2, **self.j}
        self.assertEqual(artifact_contracts.validate(data, artifact_contracts.contracts()['studio-journeys']), [])


class Hidden(TemporaryWorkspace):
    def test_unseen_work_is_grouped_with_its_evidence_linked_to_its_screens_and_counted_per_component(self):
        report = write_report(self.workspace().name)
        j = journeys.build(report, media=[])
        h = hidden.build(report, j, [{'id': 'TASK-1', 'evidence': ['FACT-data_access-src_dead_Widget.tsx-7']}])
        items = {i['id']: i for i in h['items']}
        groups = {g['id']: g['count']['value'] for g in h['groups']}
        self.assertEqual((groups['triggers'], groups['screens'], groups['writes'], groups['outside'], groups['dead']), (1, 3, 2, 1, 1))
        job = next(i for i in h['items'] if i['kind'] == 'job')
        self.assertEqual((job['file'], job['line']), ('jobs/nightly.py', 4))
        self.assertEqual(items['writes:http:/items']['areas'], ['area:items', 'area:old'])          # /app/old renders the same file
        self.assertFalse(items['writes:http:/items']['no_screen'])
        self.assertTrue(items['writes:http:/widgets']['no_screen'], 'a write no screen reaches is flagged')
        self.assertEqual(items['writes:http:/widgets']['card'], 'TASK-1')
        self.assertIn({'from': 'area:items', 'to': 'writes', 'count': 1, 'items': ['writes:http:/items']}, h['links'])
        self.assertEqual(h['components']['src/dead'], {'writes': 1, 'dead': 1})
        data = {'schema_version': 1, 'contract': 1, 'revision': 2, **h}
        self.assertEqual(artifact_contracts.validate(data, artifact_contracts.contracts()['studio-hidden']), [])
        rows = {r['section']: r for r in coverage.coverage(report, {'journeys': j, 'hidden': h}, ['journeys', 'hidden'], [], 'en')['sections']}
        self.assertEqual(rows['journeys']['state'], 'partial')
        self.assertEqual([p['id'] for p in rows['hidden']['parts']], ['controls'])


if __name__ == '__main__':
    unittest.main()

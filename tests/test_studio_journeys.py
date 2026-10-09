"""studio/journeys.json and studio/hidden.json: the user's journeys between screens, and what runs unseen behind them,
read from the scan's facts with their evidence, never invented (eaos/studio/journeys.py, hidden.py)."""
import json
import unittest
from pathlib import Path

from eaos import artifact_contracts
from eaos.studio import coverage, hidden, journeys
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

    def test_screens_are_the_full_routes_with_their_component_file_and_kind(self):
        self.assertEqual(self.s['/app/items']['file'], 'src/pages/Items.tsx')
        self.assertEqual((self.s['/app/*#Shell']['kind'], self.s['/app/*#NotFound']['kind'], self.s['*']['kind']),
                         ('layout', 'fallback', 'fallback'))
        self.assertEqual(self.s['/app/items']['fact'], 'FACT-entry_point-src_App.tsx-14')

    def test_a_link_belongs_to_the_screens_rendering_its_file_and_the_menu_to_the_layout(self):
        self.assertEqual(self.edges[('/', '/app')]['via'], 'redirect')                   # the handler Root holds it
        self.assertIn(('menu:src/App.tsx', '/app/items'), self.edges)                   # the sidebar, reached from the router
        self.assertIn(('/app', 'menu:src/App.tsx'), self.edges)                         # the menu hangs under the layout's root
        self.assertIn(('/app/items', '/app/items/:id'), self.edges)                     # a :param link opens a :param route
        site = self.edges[('/app/items', '/app/items/new')]['evidence'][0]
        self.assertEqual((site['file'], site['line']), ('src/pages/Items.tsx', 40))

    def test_a_link_to_no_screen_is_broken_and_a_link_in_dead_code_is_counted_not_drawn(self):
        self.assertEqual([(b['from'], b['target']) for b in self.j['broken']], [('/app/items/:id', '/app/missing')])
        self.assertEqual([(u['file'], u['dead']) for u in self.j['unowned']], [('src/dead/Widget.tsx', True)])
        self.assertNotIn(('src/dead/Widget.tsx', '/app/lost'), self.edges)

    def test_the_flags_say_what_is_wrong_with_each_screen(self):
        self.assertIn('no_way_in', self.s['/app/lost']['flags'])
        self.assertIn('no_way_in', self.s['/terms']['flags'])
        self.assertIn('dead_end', self.s['/terms']['flags'])
        self.assertIn('duplicate', self.s['/app/old']['flags'])                         # Items serves two routes
        self.assertEqual(self.s['/app/old']['twins'], ['/app/items'])
        self.assertIn('broken_link', self.s['/app/items/:id']['flags'])
        self.assertNotIn('dead_end', self.s['/app/items/:id']['flags'])                  # it has the menu

    def test_tasks_are_paths_from_the_start(self):
        tasks = {t['id']: t for t in self.j['tasks']}
        self.assertEqual(tasks['task:create:item']['path'], ['/', '/app', 'menu:src/App.tsx', '/app/items', '/app/items/new'])
        self.assertEqual((tasks['task:edit:item']['kind'], tasks['task:edit:item']['screen']), ('dialog', '/app/items'))

    def test_each_screen_takes_its_folder_operation_and_the_missing_screen_decision_is_counted(self):
        self.assertEqual((self.s['/app/items']['op'], self.s['/app/items']['target'], self.s['/app/items']['decided']), ('rebuild', 'pages', False))
        self.assertEqual(self.s['/']['component'], 'src')                                # defined in the router
        gaps = {g['id']: g for g in self.j['missing']}
        self.assertEqual(gaps['screen_target']['count']['value'], self.j['counts']['screens']['value'])
        self.assertIn('shots', gaps)

    def test_columns_are_clicks_from_the_start_and_a_screen_keeps_its_cell_across_scans(self):
        self.assertEqual((self.s['/']['col'], self.s['/app']['col']), (0, 1))
        previous = {'screens': [{**s, 'col': 9, 'row': 9} if s['id'] == '/app/items' else s for s in self.j['screens']], 'menus': self.j['menus']}
        again = journeys.build(self.report, previous, media=[])
        moved = {s['id']: (s['col'], s['row']) for s in again['screens']}
        self.assertEqual(moved['/app/items'], (9, 9))
        self.assertEqual(moved['/'], (self.s['/']['col'], self.s['/']['row']))

    def test_the_section_meets_its_contract(self):
        data = {'schema_version': 1, 'contract': 1, 'revision': 2, **self.j}
        self.assertEqual(artifact_contracts.validate(data, artifact_contracts.contracts()['studio-journeys']), [])


class Hidden(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.report = write_report(cls.workspace().name)
        cls.j = journeys.build(cls.report, media=[])
        cls.h = hidden.build(cls.report, cls.j, [{'id': 'TASK-1', 'evidence': ['FACT-data_access-src_dead_Widget.tsx-7']}])
        cls.items = {i['id']: i for i in cls.h['items']}

    def test_unseen_work_is_grouped_with_its_evidence(self):
        groups = {g['id']: g['count']['value'] for g in self.h['groups']}
        self.assertEqual((groups['triggers'], groups['screens'], groups['writes'], groups['outside'], groups['dead']), (1, 3, 2, 1, 1))
        job = next(i for i in self.h['items'] if i['kind'] == 'job')
        self.assertEqual((job['file'], job['line']), ('jobs/nightly.py', 4))

    def test_a_write_a_screen_sets_in_motion_is_linked_and_one_no_screen_reaches_is_flagged(self):
        items = self.items['writes:http:/items']
        self.assertEqual(items['areas'], ['area:items', 'area:old'])          # /app/old renders the same file
        self.assertFalse(items['no_screen'])
        widgets = self.items['writes:http:/widgets']
        self.assertTrue(widgets['no_screen'])
        self.assertEqual(widgets['card'], 'TASK-1')
        self.assertIn({'from': 'area:items', 'to': 'writes', 'count': 1, 'items': ['writes:http:/items']}, self.h['links'])

    def test_each_component_counts_the_unseen_work_it_holds(self):
        self.assertEqual(self.h['components']['src/dead'], {'writes': 1, 'dead': 1})

    def test_the_section_meets_its_contract_and_coverage_says_what_is_missing(self):
        data = {'schema_version': 1, 'contract': 1, 'revision': 2, **self.h}
        self.assertEqual(artifact_contracts.validate(data, artifact_contracts.contracts()['studio-hidden']), [])
        rows = {r['section']: r for r in coverage.coverage(self.report, {'journeys': self.j, 'hidden': self.h}, ['journeys', 'hidden'], [], 'en')['sections']}
        self.assertEqual((rows['journeys']['state'], rows['journeys']['step']), ('partial', 'NS44.T1'))
        self.assertEqual([p['id'] for p in rows['hidden']['parts']], ['controls'])


if __name__ == '__main__':
    unittest.main()

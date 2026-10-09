"""studio/functions.json and studio/screens.json: the function explorer and the screens gallery, read from the scan's
facts and the user's journeys, never invented (eaos/studio/functions.py, screens.py)."""
import json
import unittest
from pathlib import Path

from eaos import artifact_contracts
from eaos.studio import coverage, export, functions, screens
from tests.shared_fixture import TemporaryWorkspace


def fact(kind, path, line, value, symbol=None, end=None, fid=None):
    loc = {'path': path, 'start_line': line}
    if end is not None: loc['end_line'] = end
    if symbol is not None: loc['symbol'] = symbol
    return {'id': fid or f'FACT-{kind}-{path}-{line}-{symbol}'.replace('/', '_'), 'kind': kind, 'location': loc, 'value': value}


def symbol(path, name, start, end, kind='function', parameters=(), exported=True, qualified=None):
    return fact('symbol', path, start, {'name': name, 'kind': kind, 'parent': None, 'exported': exported,
                                         'signature': {'parameters': list(parameters)}}, symbol=qualified or name, end=end)


def call(path, line, caller, callee, attribute=False):
    return fact('call_edge', path, line, {'callee': callee, 'attribute': attribute}, symbol=caller)


def source(path, language, status='OBSERVED'):
    return fact('source_file', path, None, {'language': language, 'parse_status': status})


def external(path, line, symbol_name, engine, **measurements):
    return {'id': f'FACT-ext-{engine}-{path}-{line}-{symbol_name}', 'kind': 'symbol_metric_external',
            'location': {'path': path, 'line': line, 'symbol': symbol_name},
            'value': {'engine': engine, 'granularity': 'symbol', **measurements}}


API, PAGE, OLD = 'src/api/orders.ts', 'src/pages/Orders.tsx', 'legacy/Program.cs'


def write_report(folder):
    """A page component that loads orders through an API module; a helper called twice; a C# file the parser does not
    read but Lizard measured; a JavaScript file with no function."""
    folder = Path(folder)
    (folder / 'facts').mkdir(parents=True, exist_ok=True)
    syntax = [
        source(API, 'typescript'), source(PAGE, 'tsx'), source(OLD, 'csharp', 'UNSUPPORTED'), source('vite.config.js', 'javascript'),
        symbol(API, 'createOrder', 10, 30, parameters=['input']), symbol(API, 'toRow', 32, 40, exported=False, parameters=['order']),
        symbol(API, 'listOrders', 42, 50),
        symbol(PAGE, 'OrdersPage', 5, 60), symbol(PAGE, 'handleSave', 20, 28, kind='method', qualified='OrdersPage.handleSave'),
        symbol(PAGE, 'useOrders', 62, 70),
        call(API, 12, 'createOrder', 'toRow'), call(API, 44, 'listOrders', 'toRow'), call(API, 13, 'createOrder', 'fetch'),
        call(PAGE, 22, 'OrdersPage.handleSave', 'createOrder'), call(PAGE, 8, 'OrdersPage', 'useOrders'),
        call(PAGE, 64, 'useOrders', 'listOrders'), call(PAGE, 9, 'OrdersPage', 'mystery'),
        fact('import_edge', PAGE, 1, {'module': '../api/orders', 'names': ['createOrder', 'listOrders']}),
    ]
    resolve = [{**fact('module_edge', PAGE, 1, {'module': '../api/orders', 'to_path': API}), 'resolution': 'RESOLVED'}]
    entry = [fact('data_access', API, 15, {'client': 'supabase', 'target': 'orders', 'operation': 'insert', 'category': 'source'}),
             fact('data_access', API, 45, {'client': 'http', 'target': '/orders', 'operation': 'get', 'category': 'source'})]
    config = [fact('env_read', API, 11, {'name': 'VITE_API_URL'})]
    metrics = [fact('metric', API, 10, {'scope': 'function', 'lines': 21, 'branches': 3}, symbol='createOrder'),
               fact('metric', API, 32, {'scope': 'function', 'lines': 9, 'branches': 0}, symbol='toRow')]
    engines = [external(API, 9, 'createOrder', 'lizard', cyclomatic_complexity=7, nloc=19, end_line=30),
               external(OLD, 3, 'Program::Main', 'lizard', cyclomatic_complexity=2, nloc=5, end_line=9),
               external(PAGE, None, 'OrdersPage', 'react-docgen', record='react_component',
                        props=[{'name': 'limit', 'type': 'number', 'required': False}, {'name': 'title', 'type': 'string', 'required': True}])]
    graph = [fact('graph_node', p, 1, {'depends_on': []}) for p in (API, PAGE, OLD, 'vite.config.js')]
    for name, rows in (('syntax', syntax), ('resolve', resolve), ('entrypoints', entry), ('config', config), ('metrics', metrics),
                       ('external', engines), ('graph', graph)):
        (folder / 'facts' / f'{name}.json').write_text(json.dumps({'facts': rows}), encoding='utf-8')
    (folder / 'target-architecture.json').write_text(json.dumps({'current_components': [
        {'name': 'src', 'paths': [API, PAGE]}, {'name': 'src/api', 'paths': [API]}]}), encoding='utf-8')
    return folder


class Functions(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.report = write_report(cls.workspace().name)
        cards = [{'id': 'TASK-001', 'evidence': ['FACT-1']}, {'id': 'TASK-002', 'evidence': ['FACT-2']}]
        evidence = [{'id': 'FACT-1', 'path': API, 'line': 25, 'sites': []}, {'id': 'FACT-2', 'path': 'src/elsewhere.ts', 'line': 3, 'sites': []}]
        cls.body = functions.functions(cls.report, cards, evidence)
        cls.by_id = {f['id']: f for f in cls.body['functions']}

    def test_calls_resolve_within_the_file_and_through_imports_and_nothing_is_guessed(self):
        self.assertEqual(self.by_id[f'{API}#createOrder']['callees'], [f'{API}#toRow'])
        self.assertEqual(self.by_id[f'{API}#toRow']['callers'], [f'{API}#createOrder', f'{API}#listOrders'])
        self.assertEqual(self.by_id[f'{PAGE}#OrdersPage.handleSave']['callees'], [f'{API}#createOrder'])
        self.assertEqual(self.by_id[f'{PAGE}#OrdersPage']['callees'], [f'{PAGE}#useOrders'])      # `mystery` resolves nowhere: left out
        self.assertEqual(self.body['counts']['calls']['value'], 5)
        self.assertEqual(self.body['counts']['call_sites']['value'], 7)

    def test_complexity_is_lizards_where_it_ran_else_the_lexical_count_and_says_which(self):
        create, row = self.by_id[f'{API}#createOrder'], self.by_id[f'{API}#toRow']
        self.assertEqual((create['complexity']['value'], create['lines']['value']), (7, 19))
        self.assertIn('lizard', create['complexity']['src'])
        self.assertEqual(row['complexity']['value'], 1)
        self.assertIn('lexical', row['complexity']['src'])
        self.assertIsNone(self.by_id[f'{API}#listOrders']['complexity']['value'])     # neither: null, never 0

    def test_kinds_signatures_reads_writes_and_cards(self):
        page = self.by_id[f'{PAGE}#OrdersPage']
        self.assertEqual((page['kind'], page['signature']), ('component', 'OrdersPage({ limit?, title })'))
        self.assertEqual(self.by_id[f'{PAGE}#useOrders']['kind'], 'hook')
        self.assertEqual(self.by_id[f'{PAGE}#OrdersPage.handleSave']['kind'], 'handler')
        create = self.by_id[f'{API}#createOrder']
        self.assertEqual(create['signature'], 'createOrder(input)')
        self.assertEqual(create['writes'], [{'kind': 'table', 'name': 'orders'}])
        self.assertEqual(create['reads'], [{'kind': 'env', 'name': 'VITE_API_URL'}])
        self.assertEqual(self.by_id[f'{API}#listOrders']['reads'], [{'kind': 'network', 'name': 'GET /orders'}])
        self.assertEqual(create['cards'], ['TASK-001'])
        self.assertEqual({m['id']: m['component'] for m in self.body['modules']}, {API: 'src/api', PAGE: 'src', OLD: None})

    def test_a_language_without_function_facts_is_named_not_left_as_an_empty_list(self):
        states = {row['id']: row['state'] for row in self.body['languages']}
        self.assertEqual(states, {'C#': 'partial', 'JavaScript': 'measured', 'TypeScript': 'measured'})
        self.assertEqual(self.by_id[f'{OLD}#Program::Main']['callers'], [])
        self.assertEqual([m['id'] for m in self.body['missing']], ['calls:C#'])

    def test_the_section_meets_its_contract_and_its_coverage_row_names_each_language(self):
        data = {'schema_version': 1, 'contract': 1, 'revision': 2, **self.body}
        self.assertEqual(artifact_contracts.validate(data, artifact_contracts.contracts()['studio-functions']), [])
        rows = coverage.coverage(self.report, {'functions': self.body}, ['functions'], [], 'en')['sections']
        row = next(r for r in rows if r['section'] == 'functions')
        self.assertEqual((row['state'], row['step']), ('partial', 'NS40.T3'))
        self.assertEqual([p['id'] for p in row['parts']], ['C#', 'JavaScript', 'TypeScript'])


class Screens(unittest.TestCase):
    JOURNEYS = {'screens': [
        {'id': '/orders#Orders', 'route': '/orders', 'title': 'Orders', 'kind': 'page', 'file': PAGE, 'component': 'src',
         'router': 'src/App.tsx', 'line': 12, 'fact': 'FACT-9', 'flags': ['dead_end']},
        {'id': '/#Root', 'route': '/', 'title': 'Root', 'kind': 'redirect', 'file': None, 'router': 'src/App.tsx', 'flags': []}]}

    def test_every_page_is_a_screen_and_what_was_not_captured_is_named(self):
        body = screens.screens(self.JOURNEYS, [{'kind': 'screen', 'path': 'public/logo.png', 'route': None}])
        self.assertEqual([s['id'] for s in body['screens']], ['/orders#Orders'])      # a logo is not a screen shot
        self.assertEqual(body['screens'][0]['shots'], [])
        self.assertEqual([m['id'] for m in body['missing']], ['shots', 'issues', 'inputs'])
        self.assertIsNone(body['counts']['issues']['value'])                           # not checked, not "no issues"
        data = {'schema_version': 1, 'contract': 1, 'revision': 2, **body}
        self.assertEqual(artifact_contracts.validate(data, artifact_contracts.contracts()['studio-screens']), [])

    def test_a_shot_of_the_route_is_used_and_no_journeys_writes_nothing(self):
        body = screens.screens(self.JOURNEYS, [{'kind': 'screen', 'path': 'screens/orders-390.png', 'route': '/orders',
                                                'viewport': 390, 'phase': 'baseline', 'batch': None}])
        self.assertEqual(body['screens'][0]['shots'], [{'path': 'screens/orders-390.png', 'width': 390, 'phase': 'baseline', 'batch': None}])
        self.assertEqual([m['id'] for m in body['missing']], ['inputs'])
        self.assertEqual(body['counts']['issues']['value'], 0)
        self.assertIsNone(screens.screens(None))

    def test_a_project_with_no_pages_has_an_empty_measured_screens_section(self):
        body = screens.screens({'screens': []})
        self.assertEqual((body['screens'], body['missing']), ([], []))


class Export(unittest.TestCase):
    def test_nothing_read_is_not_measured_rather_than_empty(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'facts').mkdir()
            self.assertIsNone(functions.functions(folder))
        self.assertIsNone(screens.screens({'screens': []}, read=False))

    def test_the_exporter_lists_both_sections_in_the_manifest(self):
        self.assertIn('functions', export.SECTIONS_V2)
        self.assertIn('screens', export.SECTIONS_V2)


if __name__ == '__main__':
    unittest.main()

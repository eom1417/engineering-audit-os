"""studio/data_paths.json and studio/infra.json: the data paths and infrastructure maps, from records only, gaps counted."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from eaos import artifact_contracts
from eaos.studio import coverage
from eaos.studio.data_paths import MAX_LANE, data_paths, route_key
from eaos.studio.infra import MAX_LANE_NODES, infra, package_of

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / 'tests/fixtures/studio/v2'


def _fact(kind, path, line, value, fid, resolution=None):
    out = {'id': fid, 'kind': kind, 'location': {'path': path, 'start_line': line}, 'value': value}
    if resolution: out['resolution'] = resolution
    return out


def _access(n, path, client, target, op, keys=None):
    value = {'client': client, 'target': target, 'operation': op, 'bounded': None, 'category': 'source'}
    if keys is not None: value.update(keys=keys, keys_partial=False)
    return _fact('data_access', path, 10 + n, value, f'FACT-DA-{n}')


def shop(root, target=True):
    """A small shop: a web client writing to its own API (one endpoint from two modules, one payload a variable), a
    server route with a flow that inserts into a table, a Supabase table written from two modules, a declared table
    nobody calls, and the runtime around it."""
    out = Path(root)
    (out / 'facts').mkdir(parents=True)
    write = lambda name, facts: (out / 'facts' / f'{name}.json').write_text(json.dumps({'facts': facts}), encoding='utf-8')
    write('entrypoints', [
        _access(1, 'web/src/lib/ordersApi.ts', 'http', '/orders', 'post', ['item', 'qty']),
        _access(2, 'web/src/pages/Checkout.tsx', 'http', '/orders', 'post', ['item', 'qty', 'coupon']),
        _access(3, 'web/src/lib/ordersApi.ts', 'http', '/orders/{}', 'put'),
        _access(4, 'web/src/lib/ordersApi.ts', 'http', '/orders', 'get'),
        _access(5, 'web/src/lib/notesApi.ts', 'http', '/notes', 'post', ['text']),
        _access(6, 'web/src/lib/stock.ts', 'supabase', 'stock', 'update', ['count']),
        _access(7, 'web/src/pages/Admin.tsx', 'supabase', 'stock', 'insert', ['count', 'sku']),
        _access(8, 'web/src/pages/Admin.tsx', 'supabase', 'stock', 'select'),
        _access(9, 'server/orders.ts', 'supabase', 'orders', 'insert', ['item', 'qty', 'user_id']),
        _access(10, 'web/src/x.test.ts', 'http', '/orders', 'post', ['item']) | {'value': {
            'client': 'http', 'target': '/orders', 'operation': 'post', 'category': 'test'}},
        _fact('entry_point', 'server/orders.ts', 4, {'surface': 'http', 'route': '/orders/:id', 'http_method': 'PUT',
                                                      'handler': 'updateOrder', 'category': 'source'}, 'FACT-EP-1'),
    ])
    write('flows', [_fact('flow', 'server/orders.ts', 4, {'flow_id': 'FLOW-1', 'entry': {'surface': 'http', 'route': '/orders/:id',
                                                                                          'http_method': 'PUT'},
                                                           'touched_files': ['server/orders.ts']}, 'FACT-FL-1')])
    write('domain', [_fact('data_table', 'db/schema.sql', 1, {'name': 'public.stock', 'rls_enabled': True}, 'FACT-T-1'),
                     _fact('data_table', 'db/schema.sql', 9, {'name': 'public.audit_log', 'rls_enabled': False}, 'FACT-T-2')])
    write('runtime', [
        _fact('deployment_target', 'vercel.json', None, {'kind': 'hosting', 'host': 'Vercel'}, 'FACT-R-1'),
        _fact('deployment_target', 'tests/fixtures/Dockerfile', None, {'kind': 'dockerfile', 'port': '1'}, 'FACT-R-2'),
        _fact('ci_step', '.github/workflows/ci.yml', None, {'name': 'test'}, 'FACT-R-3'),
        _fact('ci_step', 'package.json', None, {'name': 'npm:build'}, 'FACT-R-4'),
        _fact('integration_target', 'web/src/lib/pay.ts', None, {'host': 'api.stripe.com'}, 'FACT-R-5'),
        _fact('integration_target', 'web/src/lib/x.ts', None, {'host': 'www.w3.org'}, 'FACT-R-6'),
        _fact('integration_target', 'web/src/env.ts', None, {'host': 'shop-staging.example.app'}, 'FACT-R-7'),
        _fact('resilience_policy', 'web/src/lib/pay.ts', None, {'host': 'api.stripe.com', 'has_timeout': True, 'has_retry': False}, 'FACT-R-8'),
        _fact('observability_signal', 'server/log.ts', None, {'kind': 'log'}, 'FACT-R-9'),
    ])
    write('config', [_fact('env_read', 'server/env.ts', 3, {'name': 'DATABASE_URL', 'has_default': False, 'secret_shaped': True}, 'FACT-C-1'),
                     _fact('env_read', 'server/env.ts', 4, {'name': 'PORT', 'has_default': True, 'secret_shaped': False}, 'FACT-C-2')])
    write('resolve', [_fact('module_edge', 'server/db.ts', 1, {'module': 'pg'}, 'FACT-M-1', 'EXTERNAL'),
                      _fact('module_edge', 'server/jobs.ts', 1, {'module': 'bullmq'}, 'FACT-M-2', 'EXTERNAL'),
                      _fact('module_edge', 'web/src/main.tsx', 1, {'module': '@sentry/react'}, 'FACT-M-3', 'EXTERNAL'),
                      _fact('module_edge', 'web/src/main.tsx', 2, {'module': './App'}, 'FACT-M-4', 'EXTERNAL')])
    if target:
        (out / 'target-architecture.json').write_text(json.dumps({
            'reference': 'react-vite-node-api',
            'current_components': [
                {'name': 'web/src/lib', 'target_component': 'api-client', 'paths': []},
                {'name': 'web/src/pages', 'target_component': 'features', 'paths': []},
                {'name': 'server', 'target_component': 'routes', 'paths': []}],
            'target_components': [{'name': 'api-client'}, {'name': 'features'}, {'name': 'routes'}],
            'infrastructure': [{'area': 'hosting', 'present': True, 'decision': 'Keep: declared.', 'tool': None, 'evidence': 'vercel.json'},
                               {'area': 'observability', 'present': False, 'decision': 'Introduce: errors reported.', 'tool': 'OpenTelemetry', 'evidence': '0'}],
        }), encoding='utf-8')
    return out


class DataPaths(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.body = data_paths(shop(self.tmp.name))
        self.stores = {s['id']: s for s in self.body['stores']}
        self.endpoints = {e['id']: e for e in self.body['endpoints']}

    def tearDown(self):
        self.tmp.cleanup()

    def test_routes_have_one_spelling(self):
        self.assertEqual({route_key(r) for r in ('/orders/:id', '/orders/{id}', '/orders/<int:id>', '/Orders/${id}/', '/orders/*')},
                         {'/orders/{}'})

    def test_every_store_with_its_writers_and_readers_and_a_declared_table_nobody_calls(self):
        self.assertEqual(sorted(self.stores), ['api:/notes', 'api:/orders', 'table:audit_log', 'table:orders', 'table:stock'])
        stock = self.stores['table:stock']
        self.assertEqual((stock['writers'], stock['readers'], stock['multi_writer']),
                         (['web/src/lib/stock.ts', 'web/src/pages/Admin.tsx'], ['web/src/pages/Admin.tsx'], True))
        self.assertEqual(stock['declared']['path'], 'db/schema.sql')
        self.assertEqual((self.stores['table:audit_log']['writers'], self.stores['table:audit_log']['sites']), ([], 0))

    def test_test_files_are_not_writers(self):
        self.assertNotIn('web/src/x.test.ts', self.stores['api:/orders']['writers'])

    def test_an_endpoint_written_from_two_modules_and_a_table_written_from_two_are_violations(self):
        self.assertEqual({(v['kind'], v['subject']) for v in self.body['violations']},
                         {('endpoint', 'ep:POST /orders'), ('table', 'table:stock')})
        self.assertEqual(self.endpoints['ep:POST /orders']['keys'], ['coupon', 'item', 'qty'])
        self.assertEqual(self.body['counts']['multi_writer_endpoints']['value'], 1)

    def test_each_write_is_a_path_whose_unreached_tiers_are_gaps_with_their_step(self):
        paths = {(p['site']['path'], p['endpoint']): p['steps'] for p in self.body['paths']}
        put = paths[('web/src/lib/ordersApi.ts', 'ep:PUT /orders/{}')]
        self.assertEqual((put['field']['state'], put['field']['reason']), ('gap', 'no_ui_extractor'))
        self.assertEqual((put['key']['state'], put['key']['reason']), ('gap', 'payload_not_literal'))
        self.assertEqual((put['handler']['state'], put['handler']['handler']), ('known', 'updateOrder'))
        self.assertEqual((put['column']['stores'], put['column']['columns']), (['table:orders'], ['item', 'qty', 'user_id']))
        notes = paths[('web/src/lib/notesApi.ts', 'ep:POST /notes')]
        self.assertEqual(notes['handler']['reason'], 'no_matching_route', 'the repository has server routes, none for this one')
        stock = paths[('web/src/lib/stock.ts', 'ep:supabase:update stock')]
        self.assertEqual((stock['handler']['state'], stock['column']['columns']), ('direct', ['count']))
        tiers = {t['id']: t for t in self.body['tiers']}
        self.assertEqual(tiers['field']['state'], 'not_measured')
        self.assertEqual(tiers['caller']['state'], 'measured')
        self.assertEqual({g['step'] for t in tiers.values() for g in t['gaps']} - {'NS40.T1', 'NS40.T2'}, set())
        self.assertEqual(self.body['counts']['gaps']['value'],
                         sum(s['state'] == 'gap' for p in self.body['paths'] for s in p['steps'].values()))

    def test_the_target_puts_each_writer_where_its_component_goes(self):
        stock = self.stores['table:stock']
        self.assertEqual((stock['target']['components'], stock['change']), (['api-client', 'features'], 'still_multiple'))
        self.assertEqual(self.stores['api:/notes']['change'], 'single_already')

    def test_the_stores_keep_their_place_in_the_target_view(self):
        self.assertEqual(self.body['current']['lanes']['store'], self.body['target']['lanes']['store'])
        for store in self.body['current']['lanes']['store']:
            self.assertEqual(self.body['current']['place'][store], self.body['target']['place'][store])

    def test_without_a_target_the_target_is_not_measured_rather_than_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            body = data_paths(shop(tmp, target=False))
        self.assertIsNone(body['target'])
        self.assertIsNone(body['counts']['single_in_target']['value'])
        self.assertTrue(all(s['target'] is None and s['change'] is None for s in body['stores']))

    def test_a_crowded_lane_is_clustered(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = shop(tmp)
            facts = [_access(100 + i, f'web/src/m{i}.ts', 'supabase', f'table_{i:03d}', 'insert') for i in range(MAX_LANE * 3)]
            (out / 'facts/entrypoints.json').write_text(json.dumps({'facts': facts}), encoding='utf-8')
            body = data_paths(out)
        self.assertLessEqual(len(body['current']['lanes']['store']), MAX_LANE)
        members = {m for c in body['current']['clusters'] if c['lane'] == 'store' for m in c['members']}
        self.assertEqual(len(members), MAX_LANE * 3 + 2)

    def test_the_section_meets_its_contract(self):
        data = {'schema_version': 1, 'contract': 1, 'revision': 2, **self.body}
        self.assertEqual(artifact_contracts.validate(data, artifact_contracts.contracts()['studio-data_paths']), [])

    def test_its_coverage_row_is_partial_while_the_form_tiers_are_unmeasured(self):
        row = next(r for r in coverage.coverage(Path(self.tmp.name), {'data_paths': self.body}, ['data_paths'], [], 'en')['sections']
                   if r['section'] == 'data_paths')
        self.assertEqual((row['state'], row['reason'], row['step']), ('partial', 'some_parts_missing', 'NS40.T2'))
        self.assertEqual([p['id'] for p in row['parts']], ['field', 'form', 'key', 'caller', 'endpoint', 'handler', 'column'])


class Infra(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.body = infra(shop(self.tmp.name))
        self.lanes = {lane['id']: lane for lane in self.body['lanes']}
        self.names = {lane: {n['name'] for n in self.lanes[lane]['nodes']} for lane in self.lanes}

    def tearDown(self):
        self.tmp.cleanup()

    def test_each_lane_from_its_records(self):
        self.assertEqual(self.names['hosting'], {'Vercel'}, 'a test fixture\'s Dockerfile is not where the project runs')
        self.assertEqual(self.names['ci'], {'GitHub Actions · ci', 'npm scripts'})
        self.assertEqual(self.names['databases'], {'Supabase', 'PostgreSQL', 'Tables declared in code'})
        self.assertEqual(self.names['queues'], {'BullMQ'})
        self.assertEqual(self.names['services'], {'api.stripe.com', 'shop-staging.example.app'}, 'an XML namespace is not a service')
        self.assertEqual(self.names['observability'], {'log', 'Sentry'})
        self.assertEqual(self.names['environments'], {'Environment variables', 'staging'})
        variables = next(n for n in self.lanes['environments']['nodes'] if n['id'] == 'env:variables')
        self.assertEqual((variables['detail']['variables'], variables['detail']['secret_shaped'], variables['items']),
                         (2, 1, ['DATABASE_URL', 'PORT']))
        stripe = next(n for n in self.lanes['services']['nodes'])
        self.assertEqual((stripe['detail']['timeout'], stripe['detail']['retry'], stripe['sites'][0]['path']), (True, False, 'web/src/lib/pay.ts'))

    def test_packages_are_named_by_their_own_name_or_scope(self):
        self.assertEqual([package_of(m) for m in ('@aws-sdk/client-sqs/dist', 'celery.app', './x', 'node:fs', 'pg')],
                         ['@aws-sdk/client-sqs', 'celery', None, None, 'pg'])

    def test_the_target_decides_where_it_speaks_and_is_not_measured_where_it_is_silent(self):
        target = {lane['id']: lane for lane in self.body['target']['lanes']}
        self.assertEqual([i['op'] for i in target['hosting']['items']], ['keep'])
        self.assertEqual([i['op'] for i in target['observability']['items']], ['introduce'])
        self.assertEqual((target['queues']['state'], target['queues']['reason']), ('not_measured', 'target_silent'))
        self.assertEqual((self.body['counts']['keep']['value'], self.body['counts']['introduce']['value']), (1, 1))

    def test_without_a_target_nothing_is_said_about_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            body = infra(shop(tmp, target=False))
        self.assertIsNone(body['target'])
        self.assertIsNone(body['counts']['introduce']['value'])

    def test_a_lane_with_nothing_found_is_empty_with_its_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = shop(tmp)
            (out / 'facts/resolve.json').write_text(json.dumps({'facts': []}), encoding='utf-8')
            body = infra(out)
        queues = next(lane for lane in body['lanes'] if lane['id'] == 'queues')
        self.assertEqual((queues['state'], queues['reason'], queues['count']['value']), ('empty', 'no_known_queue_library', 0))

    def test_a_crowded_lane_folds(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = shop(tmp)
            facts = [_fact('integration_target', f'web/s{i}.ts', None, {'host': f'api{i}.service.io'}, f'F{i}') for i in range(20)]
            (out / 'facts/runtime.json').write_text(json.dumps({'facts': facts}), encoding='utf-8')
            body = infra(out)
        services = next(lane for lane in body['lanes'] if lane['id'] == 'services')
        self.assertEqual((len(services['nodes']), len(services['nodes']) + len(services['folded'])), (MAX_LANE_NODES - 1, 20))

    def test_the_section_meets_its_contract(self):
        data = {'schema_version': 1, 'contract': 1, 'revision': 2, **self.body}
        self.assertEqual(artifact_contracts.validate(data, artifact_contracts.contracts()['studio-infra']), [])


class Fixtures(unittest.TestCase):
    def test_the_fixtures_are_the_small_shop_as_exported(self):
        """tests/fixtures/studio/v2/{data_paths,infra}.json are written by `python -m tests.test_studio_data_map --write-fixtures`."""
        with tempfile.TemporaryDirectory() as tmp:
            out = shop(tmp)
            for name, body in (('data_paths', data_paths(out)), ('infra', infra(out))):
                expected = {'schema_version': 1, 'contract': 1, 'revision': 2, **body}
                self.assertEqual(json.loads((FIXTURES / f'{name}.json').read_text(encoding='utf-8')), expected, name)


def write_fixtures():
    with tempfile.TemporaryDirectory() as tmp:
        out = shop(tmp)
        for name, body in (('data_paths', data_paths(out)), ('infra', infra(out))):
            text = json.dumps({'schema_version': 1, 'contract': 1, 'revision': 2, **body}, ensure_ascii=False, indent=1)
            (FIXTURES / f'{name}.json').write_text(text + '\n', encoding='utf-8')


if __name__ == '__main__':
    if sys.argv[1:] == ['--write-fixtures']: write_fixtures()
    else: unittest.main()

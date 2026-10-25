"""The layers tried (M6.6, M6.7): the migrations applied to a database of the run's own and tried with pgTAP as no one
and as another user; Schemathesis' report read as findings with their request and response; the OpenAPI EAOS derives
from the endpoint table."""
import json
import shutil
from pathlib import Path

from eaos.core.local_db import binaries
from eaos.live import api_trial, data_trial
from shared_fixture import Workspace

FIXTURES = Path(__file__).parent / 'fixtures'
MIGRATION = ['supabase/migrations/20261025000000_orders.sql']


class DataTrialTests(Workspace):
    def test_the_planted_policies_fail_their_tests_and_the_clean_twin_passes_every_one(self):
        if binaries() is None or data_trial.pgtap() is None: self.skipTest('PostgreSQL or pgTAP is not installed here')
        planted = data_trial.trial(Path(self.tmp) / 'one', FIXTURES / 'baseline-app', MIGRATION)
        failed = sorted(test['test'] for test in planted['tests'] if test['passed'] is False)
        self.assertEqual(failed, ['another user changes none of the rows of orders', 'no one signed in reads notes'])
        clean = data_trial.trial(Path(self.tmp) / 'two', FIXTURES / 'baseline-clean', MIGRATION)
        self.assertTrue(clean['tests'] and all(test['passed'] for test in clean['tests']), clean['tests'])


SCENARIO = {'ScenarioFinished': {'recorder': {
    'label': 'GET /api/notes/{id}',
    'checks': {'c1': [{'name': 'object_level_authorization', 'status': 'failure',
                       'failure_info': {'failure': {'title': 'Object-level authorization bypass',
                                                    'message': '`b` received the `Note` that `a` owns'}}},
                      {'name': 'not_a_server_error', 'status': 'success'}]},
    'interactions': {'c1': {'request': {'method': 'GET', 'uri': 'http://127.0.0.1:3000/api/notes/3'},
                            'response': {'status_code': 200, 'content': {'$base64': 'eyJpZCI6M30='}}}}}}}


class ApiTrialTests(Workspace):
    def test_a_failed_check_is_a_finding_with_its_request_and_response(self):
        report = Path(self.tmp) / 'run.ndjson'
        report.write_text(json.dumps({'Initialize': {}}) + '\n' + json.dumps(SCENARIO) + '\n')
        [failure] = api_trial.failures(report)
        self.assertEqual((failure['check'], failure['method'], failure['path'], failure['status']),
                         ('object_level_authorization', 'GET', '/api/notes/{id}', 200))
        self.assertIn('/api/notes/3', failure['request'])
        self.assertEqual(failure['response'], '{"id":3}')

    def test_the_derived_openapi_names_each_route_its_parameters_and_its_sign_in(self):
        rows = [{'route': '/api/orders/:id', 'method': 'GET', 'framework': 'express_like', 'authentication': 'requireAuth'},
                {'route': '/api/orders', 'method': 'POST', 'framework': 'express_like', 'authentication': None},
                {'route': 'action:deleteProduct', 'method': 'POST', 'framework': 'nextjs_action', 'authentication': None}]
        spec = api_trial.derived(rows)
        self.assertEqual(sorted(spec['paths']), ['/api/orders', '/api/orders/{id}'])
        read = spec['paths']['/api/orders/{id}']['get']
        self.assertEqual((read['parameters'][0]['name'], read['security']), ('id', [{'session': []}]))
        self.assertIn('requestBody', spec['paths']['/api/orders']['post'])
        self.assertTrue(spec['info']['x-eaos-derived'])

    def test_a_session_becomes_the_request_headers_of_its_account(self):
        state = Path(self.tmp) / 'state.json'
        token = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhIn0.c2ln'
        state.write_text(json.dumps({'cookies': [{'name': 'sid', 'value': 'abc'}],
                                     'origins': [{'origin': 'http://x', 'localStorage': [{'name': 'sb-x-auth-token', 'value': json.dumps({'access_token': token})}]}]}))
        self.assertEqual(api_trial.headers(state), {'Cookie': 'sid=abc', 'Authorization': f'Bearer {token}'})

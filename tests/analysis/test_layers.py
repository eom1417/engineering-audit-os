"""The system in layers: every boundary defect planted in tests/fixtures/baseline-app is found with its evidence, and
nothing is found on its clean twin (tests/fixtures/baseline-clean), from the facts alone."""
import shutil
from pathlib import Path

from eaos.analysis import layers
from eaos.analysis.claims.recheck import recheck
from eaos.facts.run import collect
from shared_fixture import TemporaryWorkspace

FIXTURES = Path(__file__).parents[1] / 'fixtures'
PLANTED = {('ui-database', 'web/Orders.jsx'), ('secret-in-browser', 'web/payments.js'), ('key-in-built-output',
    'dist/assets/index-7c1e2a.js'),
           ('unguarded-write', 'server.js'), ('unowned-row', 'server.js'), ('browser-only-rule', 'server.js'),
           ('table-without-rls', 'supabase/migrations/20261025000000_orders.sql'),
           ('open-write-policy', 'supabase/migrations/20261025000000_orders.sql'), ('untested-write', 'server.js')}


def _read(root, name):
    target, out = Path(root) / name, Path(root) / f'{name}-out'
    shutil.copytree(FIXTURES / f'baseline-{name}', target)
    collect(target, out, None)
    return layers.check(target, out)


class LayersTests(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        root = cls.workspace().name
        cls.app, cls.clean, cls.app_root = _read(root, 'app'), _read(root, 'clean'), Path(root) / 'app'

    def test_every_planted_boundary_defect_is_found_and_none_on_the_clean_twin(self):
        found = {(f['rule'], f['path']) for f in self.app['findings']}
        self.assertEqual(PLANTED - found, set())
        self.assertEqual([f['en'] for f in self.clean['findings']], [])
        unguarded = next(f for f in self.app['findings'] if f['rule'] == 'unguarded-write')
        self.assertEqual((unguarded['line'], unguarded['boundary'], unguarded['severity']), (61, 'endpoints', 'high'))
        self.assertIn('sign-in', unguarded['fix_en'])

    def test_each_file_is_placed_with_its_side_and_reason(self):
        rows = {row['path']: row for row in self.app['map']}
        self.assertEqual(rows['web/Orders.jsx']['side'], 'browser')
        self.assertEqual(rows['server.js']['side'], 'server')
        self.assertEqual(rows['supabase/migrations/20261025000000_orders.sql']['layer'], 'database')
        # in no layer of the generic type: a listed gap, never a guess
        self.assertIn('server.js', self.app['gaps'])

    def test_the_endpoint_table_reads_each_guard(self):
        rows = {(row['method'], row['route']): row for row in self.app['endpoints']}
        removal = rows[('DELETE', '/api/orders/:id')]
        self.assertEqual((removal['authentication'], removal['authorisation'], removal['writes']), ('signedIn', 'owner',
            True))
        self.assertIsNone(rows[('POST', '/api/orders')]['authentication'])
        self.assertTrue(rows[('ANY', '/health')]['public'])

    def test_a_change_that_breaks_a_boundary_is_refused_by_the_fix_gate(self):
        # the clean twin changed into the planted app: every broken boundary is named, a missing test is not one
        broke = layers.introduced(self.clean, self.app)
        self.assertTrue(any('writes with no sign-in check' in said for said in broke), broke)
        self.assertFalse(any('no test reaches it' in said for said in broke))
        self.assertEqual(layers.introduced(self.app, self.app), [])

    def test_fastapi_sign_in_dependencies_are_guards(self):
        # A FastAPI template signs in with `Depends(get_current_active_superuser)` and `user: CurrentUser`; both are
        # sign-ins. A current time is still no sign-in.
        from eaos.analysis.layers import guards
        signed_in = lambda text: guards.read(text)['authentication']
        self.assertIsNotNone(signed_in('@router.patch(\n    "/{user_id}",\n    '
                                       'dependencies=[Depends(get_current_active_superuser)],\n)\n'
                                       'def update_user(*, session: SessionDep, user_in: UserUpdate):\n    ...'))
        self.assertIsNotNone(signed_in('def create_item(*, session: SessionDep, user: CurrentUser, item_in: '
                                       'ItemCreate):'))
        self.assertIsNone(signed_in('def f():\n    now = get_current_time()\n'))

    def test_a_route_after_an_interpolated_prefix_is_named_by_the_test(self):
        # A FastAPI template's tests write `f"{settings.API_V1_STR}/items/{item.id}"`: the route must be found anywhere
        # in the string, not only right after a quote.
        from eaos.analysis.layers import operations
        self.assertTrue(operations._named({'route': '/items/{id}', 'handler': 'delete_item'},
                                          'client.delete(f"{settings.API_V1_STR}/items/{item.id}")'))

    def test_a_finding_the_code_alone_cannot_show_again_is_never_taken_for_gone(self):
        # a layer card's recheck reads the code again: failing tests and live findings are never in it, so it cannot say
        # "gone"
        failing = {'rule': 'tests-failing', 'path': '*', 'params': {'failed': 3, 'total': 40,
                                                                    'command': 'npm run test'}}
        built = {'rule': 'key-in-built-output', 'path': 'web/payments.js', 'params': {}, 'live': True}
        for specification in (failing, built):
            spec = {'probe_type': 'graph_query', 'specification': {'query': 'boundary_finding_present',
                                                                   **specification}}
            self.assertEqual(recheck(self.app_root, spec)[0], 'INCONCLUSIVE', specification['rule'])

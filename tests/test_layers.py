"""The system in layers (M6): every boundary defect planted in tests/fixtures/baseline-app is found with its evidence, and
nothing is found on its clean twin (tests/fixtures/baseline-clean), from the facts alone."""
import shutil
from pathlib import Path

from eaos.analysis import layers
from eaos.facts.run import collect
from shared_fixture import TemporaryWorkspace

FIXTURES = Path(__file__).parent / 'fixtures'
PLANTED = {('ui-database', 'web/Orders.jsx'), ('secret-in-browser', 'web/payments.js'), ('key-in-built-output', 'dist/assets/index-7c1e2a.js'),
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
        cls.app, cls.clean = _read(root, 'app'), _read(root, 'clean')

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
        self.assertIn('server.js', self.app['gaps'])        # in no layer of the generic type: a listed gap, never a guess

    def test_the_endpoint_table_reads_each_guard(self):
        rows = {(row['method'], row['route']): row for row in self.app['endpoints']}
        removal = rows[('DELETE', '/api/orders/:id')]
        self.assertEqual((removal['authentication'], removal['authorisation'], removal['writes']), ('signedIn', 'owner', True))
        self.assertIsNone(rows[('POST', '/api/orders')]['authentication'])
        self.assertTrue(rows[('ANY', '/health')]['public'])

    def test_a_change_that_breaks_a_boundary_is_refused_by_the_fix_gate(self):
        # the clean twin changed into the planted app: every broken boundary is named, a missing test is not one
        broke = layers.introduced(self.clean, self.app)
        self.assertTrue(any('writes with no sign-in check' in said for said in broke), broke)
        self.assertFalse(any('no test reaches it' in said for said in broke))
        self.assertEqual(layers.introduced(self.app, self.app), [])

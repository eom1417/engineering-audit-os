"""Real data written in the code (M12): the tables and records sorted on their evidence, and the cards they earn."""
import tempfile
import unittest
from pathlib import Path

from eaos.analysis.assessments import real_data
from eaos.analysis.claims import from_real_data
from eaos.engines.code import ast_grep
from eaos.engines.security import presidio
from shared_fixture import scratch

BASELINE = Path(__file__).resolve().parents[1] / 'fixtures/baseline-app'


def metric(path, line, **value):
    return {'id': f'F-{path}-{line}-{value.get("entity") or value["record"]}', 'kind': 'symbol_metric_external',
            'location': {'path': path, 'line': line}, 'value': value}


def personal(path, line, entity, digest='d', placeholder=False):
    return metric(path, line, record='personal_value', entity=entity, digest=digest, placeholder=placeholder, masked='x')


def table(path, line, end_line, record='data_table'):
    return metric(path, line, record=record, end_line=end_line)


def sets(*facts, graph=()):
    return {'external': {'facts': list(facts)},
            'graph': {'facts': [{'kind': 'graph_node', 'location': {'path': p}, 'value': {'depends_on': d}} for p, d in graph]}}


class SortedOnEvidence(unittest.TestCase):
    def setUp(self):
        self.root = Path(scratch('eaos-real-data-'))
        (self.root / 'src').mkdir()
        (self.root / 'src/menu.js').write_text("export const M = [\n{ path: '/a', label: 'A' },\n{ path: '/b', label: 'B' },\n{ path: '/c', label: 'C' }];\n")
        (self.root / 'src/products.js').write_text("export const P = [\n{ name: 'Tea', price: 3, stock: 9 },\n{ name: 'Milk', price: 2, stock: 4 },\n{ name: 'Rice', price: 5, stock: 1 }];\n")

    def test_a_table_with_personal_values_is_personal_and_one_of_placeholders_or_of_links_is_nothing(self):
        found = real_data.findings(sets(table('src/staff.js', 2, 7), personal('src/staff.js', 3, 'SA_PHONE'), personal('src/staff.js', 4, 'AR_NAME'),
                                        table('src/menu.js', 1, 4), table('src/empty.js', 1, 5), personal('src/empty.js', 2, 'EMAIL_ADDRESS', placeholder=True),
                                        table('src/products.js', 1, 4)), self.root)
        kinds = {row['path']: (row['kind'], row['entities']) for row in found}
        self.assertEqual(kinds['src/staff.js'], ('personal', {'AR_NAME': 1, 'SA_PHONE': 1}))
        self.assertEqual(kinds['src/products.js'][0], 'domain')
        self.assertNotIn('src/menu.js', kinds)
        self.assertNotIn('src/empty.js', kinds)

    def test_tables_of_one_kind_in_one_file_are_one_finding_from_the_first_to_the_last(self):
        (self.root / 'src/more.js').write_text('\n'.join(["const A = [", "{ name: 'Tea', price: 3, stock: 1 },"] * 2 + ["];"] * 2) + '\n' * 9)
        found = real_data.findings(sets(table('src/more.js', 1, 2), table('src/more.js', 3, 4)), self.root)
        self.assertEqual([(r['line'], r['end_line'], len(r['fact_ids'])) for r in found], [(1, 4, 2)])

    def test_a_record_alone_needs_two_kinds_or_an_id_and_a_lone_name_or_e_mail_is_nothing(self):
        found = real_data.findings(sets(personal('server.js', 9, 'PERSON'), personal('server.js', 9, 'EMAIL_ADDRESS'),
                                        personal('about.js', 3, 'EMAIL_ADDRESS'), personal('pay.js', 5, 'IBAN_CODE')), self.root)
        self.assertEqual(sorted(row['path'] for row in found), ['pay.js', 'server.js'])

    def test_where_it_sits_decides_tests_hold_domain_fixtures_and_a_seed_names_the_database(self):
        facts = (table('tests/rows.js', 1, 5), table('src/products.js', 1, 4), table('src/staff.js', 1, 5),
                 personal('src/staff.js', 2, 'SA_NATIONAL_ID', digest='same'), personal('supabase/seed.sql', 4, 'SA_NATIONAL_ID', digest='same'),
                 personal('src/only-tests.js', 1, 'IBAN_CODE'))
        graph = [('tests/a.test.js', ['src/only-tests.js']), ('src/App.jsx', ['src/staff.js'])]
        found = {row['path']: row for row in real_data.findings(sets(*facts, graph=graph), self.root)}
        self.assertNotIn('tests/rows.js', found)                                # domain records in tests are fixtures
        self.assertEqual(found['src/staff.js']['in_database'], ['supabase/seed.sql'])
        self.assertEqual((found['src/only-tests.js']['place'], found['supabase/seed.sql']['place']), ('test', 'seed'))

    def test_each_finding_is_one_card_in_both_languages_that_says_where_the_data_goes_and_its_probe_closes_it(self):
        claims = []
        facts = sets(table('src/staff.js', 2, 7), personal('src/staff.js', 3, 'SA_PHONE'), personal('tests/x.test.js', 1, 'IBAN_CODE'))
        from_real_data.real_data(facts, lambda statement, *a, **extra: claims.append({'statement': statement, **extra}), self.root)
        by_path = {c['render']['params']['path']: c for c in claims}
        staff, test = by_path['src/staff.js']['render']['params'], by_path['tests/x.test.js']['render']['params']
        self.assertEqual((staff['severity'], test['severity']), ('high', 'low'))
        self.assertEqual((staff['place'], staff['reached']), ('src/staff.js', 'product'))   # a card's place is its file (the plan's paths)
        self.assertIn('holds 1 mobile number', staff['en']); self.assertIn('أرقام جوال (1)', staff['ar'])
        self.assertIn('database', staff['fix_en']); self.assertIn('placeholders', test['fix_en'])
        spec = by_path['src/staff.js']['probe_spec']['specification']
        self.assertEqual(from_real_data.present(spec, facts)[0], 'CONFIRMED')
        self.assertEqual(from_real_data.present(spec, sets(personal('other.js', 1, 'PERSON')))[0], 'REFUTED')


def _installed(module):
    return module.version() == module.PINNED


class TheBaselineApp(unittest.TestCase):
    def test_presidio_and_ast_grep_find_what_was_planted_and_leave_what_must_stay(self):
        if not (_installed(presidio) and _installed(ast_grep)): self.skipTest('Presidio or ast-grep is not installed at its pin')
        with tempfile.TemporaryDirectory(prefix='eaos-real-data-') as work:
            metrics = [m for engine in (presidio, ast_grep) for m in engine.analyze(BASELINE, Path(work)).metrics]
        facts = [metric(m['path'], m['line'], **m['measurements']) for m in metrics]
        found = {(row['path'], row['kind']) for row in real_data.findings(sets(*facts), BASELINE)}
        self.assertTrue({('web/staff.js', 'personal'), ('server.js', 'personal')} <= found, found)
        self.assertTrue(any(path == 'web/staff.js' and kind == 'domain' for path, kind in found), found)
        self.assertFalse({path for path, _ in found} & {'web/menu.js', 'app.test.js'}, found)


if __name__ == '__main__':
    unittest.main()

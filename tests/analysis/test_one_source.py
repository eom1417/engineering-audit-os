"""One source per pattern, sorted into cards: near copies joined into clusters and ways of working written by hand, each
with every place and its home."""
import json
import unittest
from pathlib import Path

from eaos.features.one_source.analysis import one_source
from eaos.features.claims.analysis import from_one_source
from eaos.features.plan.analysis.ranking import claim_paths
from eaos.features.engines.adapters.code import jscpd
from shared_fixture import scratch

CONTRACTS = Path(__file__).resolve().parents[1] / 'contracts'


def record(path, line, **value):
    return {'id': f'F-{path}-{line}', 'kind': 'symbol_metric_external', 'location': {'path': path, 'line': line},
            'value': {'engine': value.pop('engine', 'jscpd'), **value}}


def near(first, second, kind='renamed', lines=8):
    return record(first[0], first[1], record='near_copy', kind=kind, lines=lines, end_line=first[1] + lines - 1,
                  other={'path': second[0], 'line': second[1], 'end_line': second[1] + lines - 1})


def sets(*facts):
    return {'external': {'facts': list(facts), 'summary': {'engines_observed': ['jscpd', 'ast-grep']}}}


class NearCopies(unittest.TestCase):
    def test_jscpds_pairs_are_records_of_their_kind_and_likeness(self):
        report = json.loads((CONTRACTS / 'jscpd.json').read_text(encoding='utf-8'))['jscpd-report.json']
        rows = [jscpd._record(clone) for clone in report['duplicates']]
        self.assertEqual({r['measurements']['record'] for r in rows}, {'near_copy'})
        self.assertEqual({r['measurements']['kind'] for r in rows}, {'renamed', 'similar'})
        self.assertTrue(all(r['measurements']['other']['path'] for r in rows))
        self.assertIn('--similarity', jscpd.NEAR_MODES)

    def test_a_list_of_imports_alike_is_no_copy_and_code_is(self):
        imports = (
            "  said, t, tn, L, num, esc,\n  client, contract, ac,\n} from 'eaos';\n\n/* ====\n   S-47 ONE BRANCH\n"
            "   ==== */\nconst enc = encodeURIComponent;"
        )
        self.assertTrue(jscpd.imports_only(imports))
        self.assertFalse(jscpd.imports_only('for x in xs:\n    if x:\n        break\n    else:\n        pass\n    y(a, '
                                            'b)'))

    def test_pairs_sharing_a_place_are_one_cluster_whose_source_is_the_fullest_copy(self):
        found = one_source.near_copies(sets(near(('a.py', 10), ('b.py', 40), lines=12), near(('b.py', 42), ('c.py', 5),
            'similar', 6),
                                            near(('x.py', 1), ('y.py', 1)), near(('tests/t1.py', 1), ('tests/t2.py',
                                                1))))
        self.assertEqual(len(found), 2, 'the tests alone are no card')
        three = next(f for f in found if f['evidence']['copies'] == 3)
        self.assertEqual((three['place'], three['severity'], three['evidence']['kinds']), ('a.py', 'medium', ['renamed',
            'similar']))


class ThreeConditions(unittest.TestCase):
    """A likeness is a card only when its copies belong together, cost upkeep, and one source is simpler; else a
    note."""
    def test_copies_in_one_part_that_already_differ_are_a_card_and_alike_shapes_apart_are_a_note(self):
        drifted = sets(near(('src/billing/a.js', 1), ('src/billing/b.js', 1), 'similar'))
        self.assertEqual(len(one_source.findings(None, drifted)[0]), 1)
        self.assertTrue(all(one_source.findings(None, drifted)[0][0]['evidence']['why'].values()))
        apart = sets(near(('src/billing/a.js', 1), ('src/reports/b.js', 1), 'similar'))
        self.assertEqual((one_source.findings(None, apart)[0], len(one_source.likenesses(None, apart))), ([], 1))
        idle = sets(near(('src/billing/a.js', 1), ('src/billing/b.js', 1)))      # the same, in one part, never touched
        self.assertEqual(one_source.findings(None, idle)[0], [])

    def test_the_history_says_which_copies_belong_together_and_keep_costing(self):
        history = {'facts': [{'kind': 'history_churn', 'location': {'path': p}, 'value': {'commits': 5,
            'fix_commits': 0}}
                             for p in ('src/billing/a.js', 'src/billing/b.js')]}
        busy = {**sets(near(('src/billing/a.js', 1), ('src/billing/b.js', 1))), 'history': history}
        self.assertEqual(len(one_source.findings(None, busy)[0]), 1, 'two copies whose files keep changing cost upkeep')


    def test_the_history_alone_decides_nothing_yet_copies_in_two_parts_stay_a_note(self):
        # A known limit: "simpler" asks for one shared part, so copies in two parts are a note even when they changed
        # together; the history is said as a reason, never the verdict.
        history = {'facts': [{'kind': 'history_cochange', 'location': {'path': 'src/billing/a.js',
            'paired_path': 'src/orders/b.js'}, 'value': {}}]}
        apart = {**sets(near(('src/billing/a.js', 1), ('src/orders/b.js', 1), 'similar')), 'history': history}
        note = one_source.likenesses(None, apart)
        self.assertEqual(one_source.findings(None, apart)[0], [])
        self.assertEqual((note[0]['evidence']['why']['belongs'], note[0]['evidence']['why']['simpler']),
                         ('they changed together in the history', None))

    def test_copies_renamed_in_one_part_are_proposed_only_when_keeping_them_costs(self):
        renamed = near(('src/billing/total.js', 1), ('src/billing/sum.js', 1), 'renamed')
        self.assertEqual(one_source.findings(None, sets(renamed))[0], [], 'the same, never touched: a note')
        churn = {'facts': [{'kind': 'history_churn', 'location': {'path': p}, 'value': {'commits': 4, 'fix_commits': 0}}
                           for p in ('src/billing/total.js', 'src/billing/sum.js')]}
        self.assertEqual(len(one_source.findings(None, {**sets(renamed), 'history': churn})[0]), 1)

    def test_one_mass_commit_never_makes_files_change_together(self):
        from eaos.features.code_reading.facts.code import history
        def commit(paths): return {'files': [(1, 1, p) for p in paths], 'fix': False, 'author': 'a',
                                   'date': '2026-10-28'}
        _, pairs = history._tally([commit([f'src/f{i}.js' for i in range(60)])], history.Settings().bulk_limit)
        self.assertEqual(dict(pairs), {}, 'a reformat of sixty files is no pair')
        _, pairs = history._tally([commit(['src/a.js', 'src/b.js'])], 50)
        self.assertLess(pairs[('src/a.js', 'src/b.js')], history.Settings().min_support,
                        'one commit of two is under the support')

    def test_a_proposal_from_shape_and_folder_is_kept_aside_by_the_packaged_verdicts(self):
        # Two responsibilities alike in one folder: the rules propose a card, nobody is told to merge them.
        import os
        from unittest import mock
        from eaos.features.claims.analysis import ledger
        claims = from_one_source.one_source_claims(None, sets(near(('src/billing/tax.js', 1), ('src/billing/fee.js', 1),
                                                                   'similar')), None, 0)
        with mock.patch.dict(os.environ, {'EAOS_DETECTOR_VERDICTS': str(ledger.VERDICTS)}):
            self.assertEqual(ledger.withhold(claims)[0], [])


class Idioms(unittest.TestCase):
    def test_an_idiom_written_three_times_is_one_card_with_its_home_and_twice_is_none(self):
        def idiom(path, line, rule='eaos.idiom.date-format'):
            return record(path, line, engine='ast-grep', record='idiom', form='date_format', rule=rule)
        three = sets(idiom('src/pages/A.tsx', 3), idiom('src/pages/A.tsx', 5), idiom('src/pages/B.tsx', 9),
                     idiom('src/components/C.tsx', 2, 'eaos.idiom.date-format-tsx'))
        found = one_source.idioms(three, {'src', 'src/lib', 'src/pages', 'src/components'})
        self.assertEqual(len(found), 1, 'two records two lines apart are one place')
        self.assertEqual((found[0]['evidence']['count'], found[0]['evidence']['home']), (3, 'src/lib'))
        self.assertEqual(one_source.idioms(sets(idiom('a.ts', 1), idiom('b.ts', 1)), set()), [])
        self.assertEqual(one_source.idioms(sets(*(idiom('src/lib/dates.ts', n) for n in (1, 10, 20))), set()), [],
                         'the home itself')
        self.assertEqual(len(one_source.idioms(sets(*(idiom('api/routes.js', n) for n in (1, 10, 20))), set())), 1,
                         'three in one file')

    def test_a_guard_repeated_in_routes_calls_for_a_middleware(self):
        guards = [record(f'server/routes/{n}.js', 4, engine='ast-grep', record='idiom', form='route_guard',
                         rule='eaos.idiom.route-guard')
                  for n in ('orders', 'users', 'billing')]
        found = one_source.idioms(sets(*guards), {'server', 'server/routes'})
        self.assertEqual((found[0]['severity'], found[0]['evidence']['home']), ('medium', 'server/routes/middleware'))


class Cards(unittest.TestCase):
    def test_every_finding_is_one_card_in_both_languages_whose_probe_reads_the_code_again(self):
        idioms = [record(f'src/p{n}.js', 1, engine='ast-grep', record='idiom', form='json_read',
                         rule='eaos.idiom.json-read') for n in range(3)]
        facts = sets(near(('a.py', 1), ('b.py', 1), 'similar'), *idioms)
        claims = from_one_source.one_source_claims(None, facts, None, 0)
        self.assertEqual(sorted(c['render']['params']['kind'] for c in claims), ['idiom:json_read', 'near_copy'])
        self.assertTrue(all(c['render']['params']['ar'] and c['render']['params']['fix_ar'] for c in claims))
        spec = next(c for c in claims if c['render']['params']['kind'] == 'near_copy')['probe_spec']['specification']
        self.assertEqual(from_one_source.present(spec, facts)[0], 'CONFIRMED')
        self.assertEqual(from_one_source.present(spec, sets())[0], 'REFUTED')
        idiom = next(c for c in claims if c['render']['params']['kind'] == 'idiom:json_read')
        self.assertEqual(claim_paths(idiom, {}), ['src/p0.js', 'src/p1.js', 'src/p2.js'],
                         'the card is about every place')


class KeptAside(unittest.TestCase):
    def test_a_card_of_a_detector_under_its_bar_is_kept_aside_with_its_reason(self):
        import os
        from unittest import mock
        from eaos.features.claims.analysis import ledger
        claims = from_one_source.one_source_claims(None, sets(near(('a.py', 1), ('b.py', 1), 'similar')), None, 0)
        verdicts = Path(scratch('eaos-verdicts-')) / 'verdicts.json'
        verdicts.write_text(json.dumps({'hidden': {'one_source:near_copy': 'precision under the bar'}, 'shown': []}),
                            encoding='utf-8')
        with mock.patch.dict(os.environ, {'EAOS_DETECTOR_VERDICTS': str(verdicts)}):
            shown, withheld = ledger.withhold(claims)
        self.assertEqual((shown, withheld[0]['withheld']['detector']), ([], 'one_source:near_copy'))
        said = ledger.withheld_said(withheld + withheld, ar=False)
        self.assertEqual(said,
                         ['an experimental detector kept aside until it is measured precise: one_source:near_copy '
                                '(2 results not shown: precision under the bar)'],
                         'the report says what it kept aside and why')


if __name__ == '__main__':
    unittest.main()

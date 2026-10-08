"""The labelled precision set (tools/precision.py, NS38.T1): matching, scoring, seeds, verdicts and the indicators."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import precision  # noqa: E402
import precision_seeds  # noqa: E402
from eaos import claims as ledger  # noqa: E402


def item(id_, cls, label, *sites, **extra):
    return {'id': id_, 'class': cls, 'label': label,
            'sites': [{'path': p, 'start': s, 'end': e} for p, s, e in sites], 'reason': 'test', **extra}


def output(detector, *sites):
    return {'detector': detector, 'ref': 'x', 'statement': 'x', 'sites': list(sites)}


class MatchingTests(unittest.TestCase):

    def test_a_group_needs_two_of_its_sites_and_half_of_the_output(self):
        group = item('D1', 'duplication', 'positive', ('a.ts', 10, 30), ('b.ts', 5, 25))
        self.assertTrue(precision.matches(output('structural_duplicate', ('a.ts', 12, 20), ('b.ts', 6, 9)), group, 'duplication'))
        self.assertFalse(precision.matches(output('structural_duplicate', ('a.ts', 12, 20), ('c.ts', 6, 9)), group, 'duplication'),
                         'one copy is not the group')
        noisy = output('structural_duplicate', ('a.ts', 12, 20), ('b.ts', 6, 9), ('c.ts', 1, 2), ('d.ts', 1, 2), ('e.ts', 1, 2))
        self.assertFalse(precision.matches(noisy, group, 'duplication'), 'a cluster mostly elsewhere is not this group')

    def test_a_single_site_class_matches_on_any_overlap_and_a_whole_file_covers_its_lines(self):
        dead = item('X1', 'dead_code', 'positive', ('m.py', 3, 9))
        self.assertTrue(precision.matches(output('dead_code', ('m.py', 5, 5)), dead, 'dead_code'))
        self.assertTrue(precision.matches(output('dead_code', ('m.py', None, None)), dead, 'dead_code'))
        self.assertFalse(precision.matches(output('dead_code', ('m.py', 10, 12)), dead, 'dead_code'))

    def test_a_negative_or_an_exhaustive_scope_makes_a_false_positive_and_anything_else_is_not_judged(self):
        items = [item('M1', 'data_model', 'positive', ('types.ts', 1, 1)),
                 item('M2', 'data_model', 'negative', ('types.ts', 8, 8))]
        scopes = [{'class': 'data_model', 'paths': ['types.ts', 'src/models/']}]
        self.assertEqual(precision.judge(output('data_model', ('types.ts', 1, 1)), items, scopes), ('tp', ['M1']))
        self.assertEqual(precision.judge(output('data_model', ('types.ts', 8, 8)), items, scopes)[0], 'fp')
        self.assertEqual(precision.judge(output('data_model', ('types.ts', 20, 20)), items, scopes)[0], 'fp')
        self.assertEqual(precision.judge(output('data_model', ('src/models/a.ts', 2, 2)), items, scopes)[0], 'fp')
        self.assertEqual(precision.judge(output('data_model', ('other.ts', 2, 2)), items, scopes)[0], None)
        self.assertEqual(precision.judge(output('trace_gap', ('types.ts', 1, 1)), items, scopes)[0], None,
                         'a detector with no labelled class is never judged')

    def test_a_site_is_read_from_every_shape_the_facts_use(self):
        self.assertEqual(precision.as_site({'path': 'a', 'start_line': 3, 'end_line': 4}), ('a', 3, 4))
        self.assertEqual(precision.as_site({'path': 'a', 'line': 3}), ('a', 3, 3))
        self.assertEqual(precision.as_site(['a', 3]), ('a', 3, 3))
        self.assertEqual(precision.as_site('a'), ('a', None, None))
        fact = {'location': {'path': 'x', 'start_line': 1}, 'value': {'occurrences': [{'path': 'a', 'start_line': 2, 'end_line': 5}]}}
        self.assertEqual(precision.fact_sites(fact), [('a', 2, 5)])
        self.assertEqual(precision.fact_sites({'location': {'path': 'x', 'start_line': 1}, 'value': {}}), [('x', 1, 1)])


class RegistryTests(unittest.TestCase):

    def test_every_card_the_ledger_can_write_has_a_detector_entry(self):
        source = (ROOT / 'eaos/claims.py').read_text(encoding='utf-8') + (ROOT / 'eaos/dossier.py').read_text(encoding='utf-8')
        keys = set(re.findall(r"'key': '([a-z_]+)'", source)) - {'access_gap_', 'engine_cluster'}
        keys |= {'access_gap_no_rls', 'access_gap_open_write', 'import_cycle', 'dead_code_review', 'unattributed'}
        from eaos.engines.contract import KINDS
        keys |= {'engine_cluster:' + kind for kind in KINDS if kind != 'vulnerability' and not kind.endswith('_external')}
        self.assertEqual(sorted(keys - set(precision.DETECTORS)), [], 'a detector the precision set does not know is shown unmeasured')

    def test_detector_of_names_the_card_key_the_engine_kind_and_the_cycle_check(self):
        self.assertEqual(ledger.detector_of({'render': {'key': 'dead_code'}}), 'dead_code')
        self.assertEqual(ledger.detector_of({'render': {'key': 'engine_cluster', 'params': {'kind': 'complexity'}}}),
                         'engine_cluster:complexity')
        self.assertEqual(ledger.detector_of({'statement': 'Import cycle between: a, b'}), 'import_cycle')


class WithholdTests(unittest.TestCase):

    def test_a_claim_of_a_hidden_detector_is_set_aside_with_its_reason(self):
        claims = [{'id': 'C1', 'statement': 's', 'render': {'key': 'structural_duplicate'}},
                  {'id': 'C2', 'statement': 's', 'render': {'key': 'dead_code'}}]
        with mock.patch.object(ledger, 'hidden_detectors', return_value={'structural_duplicate': 'precision 0.1 < 0.8'}):
            shown, withheld = ledger.withhold(claims)
            kinds = ledger.shown_kinds({'data_model', 'data_table'})
        self.assertEqual([c['id'] for c in shown], ['C2'])
        self.assertEqual(withheld[0]['withheld'], {'detector': 'structural_duplicate', 'why': 'precision 0.1 < 0.8'})
        self.assertEqual(kinds, {'data_model', 'data_table'})

    def test_the_verdicts_in_force_are_the_packaged_file_unless_the_environment_names_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp) / 'verdicts.json'
            other.write_text(json.dumps({'hidden': {'hotspot': 'below bar'}}))
            with mock.patch.dict('os.environ', {'EAOS_DETECTOR_VERDICTS': str(other)}):
                self.assertEqual(ledger.hidden_detectors(), {'hotspot': 'below bar'})
            with mock.patch.dict('os.environ', {'EAOS_DETECTOR_VERDICTS': ''}):
                self.assertIsNone(ledger.verdicts_path())
                self.assertEqual(ledger.hidden_detectors(), {})
            with mock.patch.dict('os.environ', clear=True):
                self.assertEqual(ledger.verdicts_path(), ledger.VERDICTS)

    def test_the_verdict_file_the_product_reads_agrees_with_the_record(self):
        record = json.loads((ROOT / 'docs/engine-precision.json').read_text(encoding='utf-8')).get('precision')
        if not record: self.skipTest('the precision set has not been scored on this checkout')
        verdicts = json.loads(ledger.VERDICTS.read_text(encoding='utf-8'))
        self.assertEqual(sorted(verdicts['hidden']), sorted(r['detector'] for r in record['detectors'] if not r['shown']))
        self.assertEqual(sorted(verdicts['shown']), sorted(r['detector'] for r in record['detectors'] if r['shown']))
        for row in record['detectors']:
            if row['shown']:
                self.assertGreaterEqual(row['precision'], precision.BAR['precision'], row['detector'])
                self.assertGreaterEqual(row['recall'], precision.BAR['recall'], row['detector'])
                self.assertGreaterEqual(row['judged'], precision.BAR['judged'], row['detector'])

    def test_the_sustainability_indicator_is_not_measured_while_its_detector_is_hidden(self):
        from eaos import sustainability
        sets = {'domain': {'facts': [{'kind': 'mutable_global', 'value': {'name': 'X'}, 'location': {'path': p}} for p in ('a', 'b')]}}
        self.assertEqual(sustainability.writers(sets), {'X': ['a', 'b']})
        with mock.patch.object(ledger, 'hidden_detectors', return_value={'data_owners': 'precision 0.0 < 0.8'}):
            self.assertIs(sustainability._indicator_data_owners(sets)['measured'], False)
        with mock.patch.object(ledger, 'hidden_detectors', return_value={}):
            self.assertEqual(sustainability._indicator_data_owners(sets)['value'], 1)


class SeedTests(unittest.TestCase):

    def test_every_planted_site_resolves_and_every_seeded_file_is_labelled_for_every_class(self):
        for language, files in (('typescript', precision_seeds.typescript_files('src/eaos-seed')),
                                ('python', precision_seeds.python_files('eaos_seed'))):
            items, scopes = precision_seeds.items(files, language)
            for row in items:
                for site in row['sites']:
                    self.assertLessEqual(site['start'], site['end'])
                    self.assertLessEqual(site['end'], len(files[site['path']].splitlines()), row['subject'])
                for detector in row['detectors']:
                    self.assertEqual(precision.DETECTORS[detector], row['class'], f"{detector} is not a {row['class']} detector")
            self.assertTrue(all(sorted(files) == scope['paths'] for scope in scopes))
            dead = {row['sites'][0]['path'] for row in items if row['class'] == 'dead_code'}
            self.assertEqual(dead, set(files), 'every planted module is unreachable and labelled so')

    def test_seeding_never_writes_into_the_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'p'
            (source / 'eaos_seed').mkdir(parents=True)
            (source / 'eaos_seed' / 'state.py').write_text('original\n')
            spec = {'x': {'source': source, 'language': 'python', 'seed_base': 'eaos_seed'}}
            with mock.patch.object(precision, 'PROJECTS', spec), mock.patch.object(precision, 'WORK', Path(tmp) / 'w'), \
                    mock.patch.object(precision, 'TRUTH', Path(tmp) / 't'):
                with self.assertRaises(SystemExit):
                    precision.seed()
            self.assertEqual((source / 'eaos_seed' / 'state.py').read_text(), 'original\n')


class ScoreTests(unittest.TestCase):

    def report(self, tmp):
        out = Path(tmp) / 'out'
        (out / 'facts').mkdir(parents=True)
        facts = [{'id': 'F1', 'kind': 'duplicate_cluster', 'location': {'path': 'a.py', 'start_line': 1},
                  'value': {'occurrences': [{'path': 'a.py', 'start_line': 1, 'end_line': 9},
                                            {'path': 'b.py', 'start_line': 1, 'end_line': 9}]}},
                 {'id': 'F2', 'kind': 'duplicate_cluster', 'location': {'path': 'a.py', 'start_line': 20},
                  'value': {'occurrences': [{'path': 'a.py', 'start_line': 20, 'end_line': 22},
                                            {'path': 'c.py', 'start_line': 1, 'end_line': 3}]}}]
        (out / 'facts' / 'fingerprint.json').write_text(json.dumps({'facts': facts}))
        claims = [{'id': 'CLM-001', 'statement': 'dup', 'render': {'key': 'structural_duplicate'}, 'fact_ids': ['F1']},
                  {'id': 'CLM-002', 'statement': 'dup', 'render': {'key': 'structural_duplicate'}, 'fact_ids': ['F2']}]
        (out / 'dossier.json').write_text(json.dumps({'claims': claims[:1], 'withheld_claims': claims[1:]}))
        return out

    def test_precision_and_recall_are_measured_from_cards_shown_or_withheld(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.report(tmp)
            truth = {'eaos': {'items': [item('E1', 'duplication', 'positive', ('a.py', 1, 9), ('b.py', 1, 9)),
                                        item('E2', 'duplication', 'positive', ('d.py', 1, 9), ('e.py', 1, 9))],
                              'scopes': [{'class': 'duplication', 'paths': ['a.py']}], 'files': []}}
            rows, classes = precision.score(truth, report_dirs={('eaos', 'original'): (out, tmp)})
        row = next(r for r in rows if r['detector'] == 'structural_duplicate')
        self.assertEqual((row['true_positives'], row['false_positives'], row['precision']), (1, 1, 0.5))
        self.assertEqual((row['recall_on_labels'], row['labelled_positives']), (0.5, 2))
        self.assertEqual(row['status'], 'not_measured', 'two judged outputs are too few for a verdict')
        self.assertFalse(row['shown'])
        self.assertEqual(classes['duplication']['recall_of_all_detectors'], 0.5)

    def test_a1_counts_only_what_the_product_shows_and_needs_the_whole_set(self):
        record = {'summary': {'labelled_items': 160, 'projects': sorted(precision.PROJECTS)},
                  'detectors': [{'detector': 'dead_code', 'status': 'meets_bar'}, {'detector': 'hotspot', 'status': 'below_bar'}]}
        hidden = {d: 'x' for d in precision.DETECTORS if d not in ('dead_code', 'hotspot')}
        self.assertEqual(precision.a1_value(record, hidden)[0], 0.5)
        self.assertEqual(precision.a1_value(record, {**hidden, 'hotspot': 'below bar'})[0], 1.0)
        small = {**record, 'summary': {**record['summary'], 'labelled_items': 20}}
        self.assertEqual(precision.a1_value(small, hidden)[0], 0.0)

    def test_score_refuses_truth_edited_added_or_removed_after_the_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'seeded').mkdir()
            (tmp / 'eaos.A.json').write_text(json.dumps({'project': 'eaos', 'items': []}))
            (tmp / 'seeded' / 'eaos.json').write_text(json.dumps({'project': 'eaos', 'items': []}))
            with mock.patch.object(precision, 'TRUTH', tmp), mock.patch.object(precision, 'SEAL', tmp / 'seal.json'):
                self.assertEqual(precision.unsealed(precision.load_truth()), ['no seal recorded'])
                with mock.patch('builtins.print'): precision.seal()
                self.assertEqual(precision.unsealed(precision.load_truth()), [])
                (tmp / 'seeded' / 'eaos.json').write_text(json.dumps({'project': 'eaos', 'items': [{}]}))
                self.assertEqual(precision.unsealed(precision.load_truth()), ['seeded/eaos.json'])
                (tmp / 'eaos.A.json').unlink()
                self.assertEqual(precision.unsealed(precision.load_truth()), ['eaos.A.json', 'seeded/eaos.json'])


class AdoptionTests(unittest.TestCase):

    def test_a_record_names_its_task_and_is_complete_only_with_candidates_licence_maintenance_and_decision(self):
        import north_star_measure
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'a.md').write_text('Task: NS1.T1\n## Candidates\n| Licence | Maintenance |\n## Decision\nbuild\n')
            Path(tmp, 'b.md').write_text('Task: NS2.T1, NS2.T2\n## Candidates\n')
            records = north_star_measure.adoption_records(tmp)
        self.assertTrue(records['NS1.T1'][1])
        self.assertFalse(records['NS2.T2'][1])

    def test_a_record_names_its_task_by_file_name_and_the_studio_form_is_complete(self):
        import north_star_measure
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'ns9-t2-shell.md').write_text('## Icons\n**Candidates**\n| Licence | Maintenance |\n**Decision**: adopt\n')
            records = north_star_measure.adoption_records(tmp)
        self.assertTrue(records['NS9.T2'][1])

    def test_w2_counts_a_task_from_its_own_commits_and_its_studio_packages_from_records_before_the_studio(self):
        import subprocess
        import north_star_measure
        record = {'milestones': [{'tasks': [
            {'id': 'NS1.T1', 'status': 'todo', 'steps': ['docs/adoption/'], 'files': ['shared.py']},
            {'id': 'NS2.T1', 'status': 'todo', 'steps': ['docs/adoption/'], 'files': ['shared.py', 'studio/src/']}]}]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def commit(message, files):
                for name, body in files.items():
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(body)
                subprocess.run(['git', 'add', '-A'], cwd=root, check=True)
                subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', message], cwd=root, check=True)

            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            commit('plan', {'docs/north-star.json': '"id": "NS1.T1" "id": "NS2.T1"'})
            commit('another capability edits a shared file', {'shared.py': 'x = 1\n'})
            section = '**Candidates**\n| Licence | Maintenance |\n**Decision**: adopt\n**Pinned**: `a@1.0.0`\n'
            commit('NS2.T1: adoption record', {'docs/adoption/ns2-t1-ui.md': '# NS2.T1\n\n## UI\n' + section})
            commit('NS2.T1: code', {'studio/src/a.ts': '1', 'studio/package.json': '{"dependencies": {"a": "1.0.0"}}'})
            with mock.patch.object(north_star_measure, 'ROOT', root):
                value, evidence = north_star_measure.adoption_value(record)
                self.assertEqual(value, 1.0, evidence)   # NS1.T1 has not begun: the shared file's commit is not its own
                commit('NS2.T1: a package added later', {'studio/package.json': '{"dependencies": {"a": "1.0.0", "b": "2.0.0"}}'})
                value, evidence = north_star_measure.adoption_value(record)
        self.assertEqual(value, 0.0)
        self.assertIn('NS2.T1: Studio packages without a record', evidence)
        self.assertIn(': b', evidence)

    def test_the_precision_set_has_its_adoption_record(self):
        import north_star_measure
        path, complete = north_star_measure.adoption_records()['NS38.T1']
        self.assertTrue(complete, path.name)


if __name__ == '__main__':
    unittest.main()

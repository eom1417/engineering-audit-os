"""Deterministic history facts: reproducible, target-safe, and free of commit text."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from eaos.facts import history
from eaos.facts.run import collect


def git(repo, *args):
    subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True,
                   env={'PATH': '/usr/bin:/bin', 'HOME': str(repo), 'GIT_AUTHOR_EMAIL': 'a@example.invalid',
                        'GIT_COMMITTER_EMAIL': 'a@example.invalid', 'GIT_AUTHOR_NAME': 'Fixture',
                        'GIT_COMMITTER_NAME': 'Fixture'})


class HistoryFactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name); self.repo = self.base / 'repo'; self.repo.mkdir()
        git(self.repo, 'init', '-q', '-b', 'main')
        git(self.repo, 'config', 'user.email', 'a@example.invalid')
        git(self.repo, 'config', 'user.name', 'Fixture')
        # a.py and b.py always move together; c.py moves alone.
        for step in range(3):
            (self.repo / 'a.py').write_text(f'a = {step}\n')
            (self.repo / 'b.py').write_text(f'b = {step}\n')
            git(self.repo, 'add', 'a.py', 'b.py'); git(self.repo, 'commit', '-q', '-m', f'change pair {step}')
        (self.repo / 'c.py').write_text('c = 0\n')
        git(self.repo, 'add', 'c.py'); git(self.repo, 'commit', '-q', '-m', 'fix rounding in c')

    def facts(self, out='facts-out'):
        collect(self.repo, self.base / out, ['history'])
        return json.loads((self.base / out / 'facts/history.json').read_text())

    def row(self, data, kind, path):
        return next(f for f in data['facts'] if f['kind'] == kind and f['location']['path'] == path)

    def test_churn_and_fix_classification(self):
        data = self.facts()
        self.assertEqual(self.row(data, 'history_churn', 'a.py')['value']['commits'], 3)
        self.assertEqual(self.row(data, 'history_churn', 'c.py')['value']['fix_commits'], 1)
        self.assertEqual(self.row(data, 'history_churn', 'a.py')['value']['fix_commits'], 0)
        self.assertTrue(self.row(data, 'history_churn', 'a.py')['value']['exists_in_working_tree'])

    def test_cochange_pairs_files_that_move_together(self):
        data = self.facts()
        pairs = {(f['location']['path'], f['location']['paired_path']): f['value'] for f in data['facts'] if f['kind'] == 'history_cochange'}
        self.assertEqual(pairs[('a.py', 'b.py')]['support'], 3)
        self.assertEqual(pairs[('a.py', 'b.py')]['confidence'], 1.0)
        self.assertNotIn(('a.py', 'c.py'), pairs)

    def test_ownership_reports_single_author_concentration(self):
        value = self.row(self.facts(), 'history_ownership', 'a.py')['value']
        self.assertTrue(value['single_author'])
        self.assertEqual(value['top_author'], 'Fixture')
        self.assertEqual(value['top_author_share'], 1.0)

    def test_two_runs_produce_identical_bytes(self):
        self.facts('run-a'); self.facts('run-b')
        self.assertEqual((self.base / 'run-a/facts/history.json').read_bytes(),
                         (self.base / 'run-b/facts/history.json').read_bytes())

    def test_commit_subjects_never_enter_the_fact_set(self):
        (self.repo / 'a.py').write_text('a = 9\n')
        git(self.repo, 'add', 'a.py')
        git(self.repo, 'commit', '-q', '-m', 'fix token=SUBJECT_SENTINEL leak')
        text = (self.base / 'facts-out').as_posix()
        collect(self.repo, text, ['history'])
        raw = (Path(text) / 'facts/history.json').read_text()
        self.assertNotIn('SUBJECT_SENTINEL', raw)
        self.assertEqual(self.row(json.loads(raw), 'history_churn', 'a.py')['value']['fix_commits'], 1)

    def test_target_is_never_written_to(self):
        before = {p.relative_to(self.repo).as_posix(): p.read_bytes() for p in self.repo.rglob('*')
                  if p.is_file() and '.git/' not in p.relative_to(self.repo).as_posix()}
        self.facts()
        after = {p.relative_to(self.repo).as_posix(): p.read_bytes() for p in self.repo.rglob('*')
                 if p.is_file() and '.git/' not in p.relative_to(self.repo).as_posix()}
        self.assertEqual(before, after)

    def test_facts_cannot_be_written_inside_the_target(self):
        with self.assertRaisesRegex(ValueError, 'read-only'):
            collect(self.repo, self.repo / 'facts', ['history'])

    def test_repository_without_git_declares_unavailability_instead_of_failing(self):
        plain = self.base / 'plain'; plain.mkdir(); (plain / 'x.py').write_text('x = 1\n')
        collect(plain, self.base / 'plain-out', ['history'])
        data = json.loads((self.base / 'plain-out/facts/history.json').read_text())
        self.assertFalse(data['available'])
        self.assertIn('No git work tree', data['reason'])
        self.assertEqual(data['facts'], [])

    def test_extractor_declares_its_own_blind_spots(self):
        self.assertTrue(any('Renames are not followed' in limit for limit in history.LIMITATIONS))
        self.assertTrue(any('not defect probability' in limit for limit in history.LIMITATIONS))

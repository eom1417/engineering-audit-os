"""Security findings reach cards: agreed ones as LIKELY, lone ones as a HYPOTHESIS the triage decides, none dropped."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.analysis.assessments import weaknesses
from eaos.engines.security import codeql
from eaos.analysis.claims.probe_queries import run_graph_query


def fact(id_, engine, path, line, rule, cwe=(), kind='vulnerability', severity='high', confidence=None):
    return {'id': id_, 'kind': 'engine_finding', 'location': {'path': path, 'line': line},
            'value': {'engine': engine, 'rule': rule, 'kind': kind, 'cwe': list(cwe), 'subject_kind': 'file',
                      'engine_confidence': confidence, 'measurements': [{'name': 'severity', 'value': severity}]}}


def sets(*facts, observed=('semgrep', 'bandit', 'gitleaks')):
    return {'external': {'facts': list(facts), 'summary': {'engines_observed': list(observed)}}}


class WeaknessTests(unittest.TestCase):
    def test_every_finding_reaches_a_card_and_two_engines_on_one_line_corroborate(self):
        # EAOS on itself, 2026-10-14: 82 Semgrep security findings, none a card, the security score 100.
        found = sets(fact('A', 'semgrep', 'app/db.py', 10, 'sql', ['CWE-89']),
                     fact('B', 'bandit', 'app/db.py', 11, 'B608', ['CWE-89']),
                     fact('C', 'semgrep', 'app/run.py', 5, 'exec', ['CWE-78']),
                     fact('D', 'semgrep', 'app/x.py', 1, 'audit', ['CWE-78'], confidence='low'),
                     fact('E', 'semgrep', 'app/y.py', 1, 'audit', ['CWE-78'], confidence='low'),
                     fact('F', 'bandit', 'tests/test_db.py', 3, 'B608', ['CWE-89']),
                     fact('G', 'gitleaks', 'tests/test_keys.py', 3, 'aws-key', kind='secret'))
        made = []
        weaknesses.claims(found, lambda *args, **extra: made.append((args[2], extra['fact_ids'], extra['render']['params']['place'])), None)
        self.assertEqual(sorted(made), sorted([
            ('LIKELY', ['A', 'B'], 'app/db.py'),               # agreed: same file, a line apart
            ('HYPOTHESIS', ['C'], 'app/run.py'),               # alone: the triage reads the code
            ('HYPOTHESIS', ['D', 'E'], '2 files'),             # audit hints: one card for the project
            ('HYPOTHESIS', ['G'], 'tests/test_keys.py'),       # a key leaks from a test file too; F does not ship
        ]))

    def test_a_card_is_never_passed_by_an_engine_that_did_not_run(self):
        spec = {'query': 'weakness_present', 'labels': ['CWE-89'], 'paths': ['app/db.py'], 'engines': ['semgrep', 'bandit']}
        self.assertEqual(run_graph_query(spec, sets(observed=('bandit',)))[0], 'INCONCLUSIVE')
        self.assertEqual(run_graph_query(spec, sets())[0], 'REFUTED')
        with tempfile.TemporaryDirectory() as tmp:
            before, after = Path(tmp, 'before'), Path(tmp, 'after')
            for folder, rows in ((before, []), (after, [fact('B', 'bandit', 'app/db.py', 11, 'B608', ['CWE-89'])])):
                (folder / 'facts').mkdir(parents=True)
                (folder / 'facts/external.json').write_text(json.dumps(sets(*rows)['external']))
            self.assertEqual(weaknesses.new(before, after, {'app/db.py'}), [('bandit', 'B608', 'app/db.py')])
            self.assertEqual(weaknesses.new(before, after, {'app/other.py'}), [])

    def test_a_comment_hides_only_a_weakness_the_project_already_had_and_is_never_a_card(self):
        # A fix that brought an unsafe call with `# nosemgrep: rule -- why` passed the gate; a justified finding is no card.
        justified = {**fact('J', 'semgrep', 'app/db.py', 11, 'sql', ['CWE-89']), 'kind': 'engine_finding_justified'}
        with tempfile.TemporaryDirectory() as tmp:
            had, before, after = Path(tmp, 'had'), Path(tmp, 'before'), Path(tmp, 'after')
            for folder, rows in ((had, [fact('A', 'semgrep', 'app/db.py', 10, 'sql')]), (before, []), (after, [justified])):
                (folder / 'facts').mkdir(parents=True)
                (folder / 'facts/external.json').write_text(json.dumps(sets(*rows)['external']))
            self.assertEqual(weaknesses.new(before, after, {'app/db.py'}), [('semgrep', 'sql', 'app/db.py')])
            self.assertEqual(weaknesses.new(had, after, {'app/db.py'}), [])
        made = []
        weaknesses.claims(sets(justified), lambda *args, **extra: made.append(args), None)
        self.assertEqual(made, [])

    def test_codeql_runs_only_on_open_source_code_public_on_github(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(codeql.allowed(tmp)[0])
            Path(tmp, 'LICENSE').write_text('MIT License\n\nPermission is hereby granted, free of charge, to any person')
            with mock.patch.object(codeql, 'public_repository', return_value=None):
                self.assertFalse(codeql.allowed(tmp)[0])
            with mock.patch.object(codeql, 'public_repository', return_value='owner/app'):
                self.assertEqual(codeql.allowed(tmp), (True, 'MIT license, public on GitHub.com as owner/app'))

"""Probes and execution evidence: confidence that is earned, and gaps that stay visible."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos import probes
from eaos.dossier import assemble
from eaos.facts.run import collect
from eaos.facts.store import read_set
from eaos.verify import run as verify_run

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


class ProbeTests(unittest.TestCase):
    def test_a_duplicated_rule_claim_is_confirmed_by_re_derivation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            result = probes.run_all(FIXTURE, out)
            self.assertEqual(result['by_status']['CONFIRMED'], 1)
            rows = json.loads((out / 'probes.json').read_text())
            self.assertEqual(rows[0]['probe_type'], 'absence_search')
            self.assertIn('defined in 3 files', rows[0]['result'])

    def test_a_probe_that_fails_refutes_its_claim_and_keeps_it_in_the_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'a.py').write_text('from b import helper\n\n\ndef run():\n    return helper()\n')
            (repo / 'b.py').write_text('import a\n\n\ndef helper():\n    return a\n')
            out = Path(tmp) / 'out'
            assemble(repo, out)
            dossier = json.loads((out / 'dossier.json').read_text())
            cycle_claim = next(claim for claim in dossier['claims'] if 'cycle' in claim['statement'].lower())
            # Break the cycle in the snapshot the probe re-derives from.
            (repo / 'b.py').write_text('def helper():\n    return 1\n')
            collect(repo, out, ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'domain', 'graph', 'flows'])
            probes.run_all(repo, out)
            updated = json.loads((out / 'dossier.json').read_text())
            refuted = next(claim for claim in updated['claims'] if claim['id'] == cycle_claim['id'])
            self.assertEqual(refuted['confidence'], 'REFUTED')
            self.assertEqual(refuted['status'], 'withdrawn')
            self.assertTrue(refuted['refuted_by'])

    def test_execution_probes_are_blocked_unless_explicitly_allowed(self):
        row = probes.probe(1, 'CLM-001', 'execution', {'command': 'pytest'}, requires_execution=True)
        self.assertEqual(row['status'], 'not_run')
        self.assertTrue(row['requires_execution'])


class VerificationTests(unittest.TestCase):
    def test_declared_coverage_is_reported_without_running_anything(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            collect(FIXTURE, out, ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'history', 'graph'])
            result = verify_run(FIXTURE, out, execute=False)
            self.assertFalse(result['executed'])
            self.assertIn('Execution was not requested', result['reason'])

    def test_running_a_real_suite_produces_coverage_and_uncovered_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; (repo / 'tests').mkdir(parents=True)
            (repo / 'used.py').write_text('def add(a, b):\n    return a + b\n')
            (repo / 'never_run.py').write_text('import used\n\n\ndef unused():\n    return used.add(1, 2)\n')
            (repo / 'main.py').write_text('import argparse\nimport used\n\n\ndef main():\n'
                                          '    argparse.ArgumentParser(prog="demo")\n    return used.add(1, 1)\n')
            (repo / 'tests/test_used.py').write_text('import unittest\nimport used\n\n\n'
                                                     'class T(unittest.TestCase):\n    def test_add(self):\n'
                                                     '        self.assertEqual(used.add(1, 2), 3)\n')
            out = Path(tmp) / 'out'
            result = verify_run(repo, out, command=['python', '-m', 'unittest', 'discover', '-s', 'tests'], execute=True)
            self.assertTrue(result['executed'], result.get('reason'))
            self.assertIn('used.py', result['coverage'])
            self.assertGreater(result['overall_percent'], 0)
            self.assertIn('tests/test_used.py', result['test_files'])
            facts = read_set(out, 'verification')
            self.assertTrue(facts['available'])
            self.assertTrue(any(fact['value']['executed'] for fact in facts['facts']))

    def test_execution_evidence_becomes_a_runtime_confirmed_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; (repo / 'tests').mkdir(parents=True)
            (repo / 'used.py').write_text('def add(a, b):\n    return a + b\n')
            (repo / 'orphan.py').write_text('import used\n\n\ndef never_called():\n    return used.add(0, 0)\n')
            (repo / 'main.py').write_text('import argparse\nimport orphan\n\n\ndef main():\n'
                                          '    argparse.ArgumentParser(prog="demo")\n    return orphan.never_called()\n')
            (repo / 'tests/test_used.py').write_text('import unittest\nimport used\n\n\n'
                                                     'class T(unittest.TestCase):\n    def test_add(self):\n'
                                                     '        self.assertEqual(used.add(1, 2), 3)\n')
            out = Path(tmp) / 'out'
            verify_run(repo, out, command=['python', '-m', 'unittest', 'discover', '-s', 'tests'], execute=True)
            result = assemble(repo, out)
            dossier = json.loads((out / 'dossier.json').read_text())
            runtime = [claim for claim in dossier['claims'] if 'test_evidence' in claim['method']]
            self.assertTrue(runtime)
            self.assertEqual(runtime[0]['confidence'], 'CONFIRMED')
            self.assertTrue(runtime[0]['fact_ids'])
            self.assertEqual(dossier['coverage']['runtime_confirmation'], len(runtime))
            self.assertTrue((out / 'VERIFICATION-MAP.md').is_file())
            self.assertEqual(result['status'], 'READY')

    def test_the_target_is_never_modified_by_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; (repo / 'tests').mkdir(parents=True)
            (repo / 'used.py').write_text('def add(a, b):\n    return a + b\n')
            (repo / 'tests/test_used.py').write_text('import unittest\nimport used\n\n\n'
                                                     'class T(unittest.TestCase):\n    def test_add(self):\n'
                                                     '        self.assertEqual(used.add(1, 2), 3)\n')
            before = {path.relative_to(repo).as_posix(): path.read_bytes() for path in repo.rglob('*') if path.is_file()}
            verify_run(repo, Path(tmp) / 'out', command=['python', '-m', 'unittest', 'discover', '-s', 'tests'], execute=True)
            after = {path.relative_to(repo).as_posix(): path.read_bytes() for path in repo.rglob('*') if path.is_file()}
            self.assertEqual(before, after)

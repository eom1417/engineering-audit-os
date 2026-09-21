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
            self.assertGreaterEqual(result['by_status']['CONFIRMED'], 1)
            rows = json.loads((out / 'probes.json').read_text())
            derivation = next(row for row in rows if row['probe_type'] == 'absence_search')
            self.assertIn('parsed as a definition in 3 files', derivation['result'])

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

    def test_a_mention_inside_a_test_string_cannot_withdraw_a_true_finding(self):
        """Regression: a text search matched an import written inside a test's string literal and refuted a true claim."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; (repo / 'tests').mkdir(parents=True)
            (repo / 'api.py').write_text('VAT_RATE = 0.15\n\n\ndef total(x):\n    return x * (1 + VAT_RATE)\n')
            (repo / 'export.py').write_text('VAT_RATE = 0.14\n\n\ndef report(x):\n    return x * (1 + VAT_RATE)\n')
            (repo / 'tests/test_case.py').write_text(
                'CASE = "from api import VAT_RATE"\n\n\ndef test_case():\n    assert CASE\n')
            out = Path(tmp) / 'out'
            assemble(repo, out)
            probes.run_all(repo, out)
            rows = json.loads((out / 'probes.json').read_text())
            self.assertTrue(rows)
            self.assertNotIn('REFUTED', [row['status'] for row in rows],
                             'a mention inside a test string must never withdraw a finding')
            claims = json.loads((out / 'dossier.json').read_text())['claims']
            self.assertTrue(all(claim['confidence'] != 'REFUTED' for claim in claims))

    def test_an_import_with_uncaptured_names_is_inconclusive_not_a_refutation(self):
        from eaos.probes import linking_import
        sets = {'syntax': {'facts': [{'id': 'F1', 'kind': 'import_edge', 'value': {'names': []}}]},
                'resolve': {'facts': [{'resolution': 'RESOLVED', 'location': {'path': 'a.ts'},
                                       'value': {'to_path': 'b.ts', 'import_fact_id': 'F1'}}]}}
        self.assertTrue(linking_import('RATE', ['a.ts', 'b.ts'], sets).startswith('UNKNOWN: '))

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

    def test_default_commands_use_a_real_interpreter_not_a_bare_name(self):
        """A system with only python3 must still produce execution evidence."""
        import sys
        from eaos import verify
        self.assertTrue(all(Path(command[0]).is_absolute() for command in verify.DEFAULT_COMMANDS),
                        'default commands must not depend on a bare python on PATH')
        self.assertEqual(verify.coverage_command(['python', '-m', 'unittest'])[0], sys.executable)
        self.assertEqual(verify.coverage_command(['node', 'test.js']), None)

    def test_a_project_whose_tests_run_only_under_python3_still_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; (repo / 'tests').mkdir(parents=True)
            (repo / 'used.py').write_text('def add(a, b):\n    return a + b\n')
            (repo / 'tests/test_used.py').write_text('import unittest\nimport used\n\n\n'
                                                     'class T(unittest.TestCase):\n    def test_add(self):\n'
                                                     '        self.assertEqual(used.add(1, 2), 3)\n')
            result = verify_run(repo, Path(tmp) / 'out', execute=True)
            self.assertTrue(result['executed'], result.get('reason'))
            self.assertGreater(result['overall_percent'], 0)

    def test_a_one_way_claim_is_not_refuted_by_the_reverse_edge(self):
        """Regression: a claim that A must not import B was refuted because B imports A."""
        from eaos.probes import run_graph_query
        sets = {'graph': {'facts': [
            {'kind': 'graph_node', 'location': {'path': 'a.py'}, 'value': {'depends_on': []}},
            {'kind': 'graph_node', 'location': {'path': 'b.py'}, 'value': {'depends_on': ['a.py']}}]}}
        status, detail = run_graph_query({'query': 'no_code_dependency', 'left': 'a.py', 'right': 'b.py',
                                          'direction': 'one_way'}, sets)
        self.assertEqual(status, 'CONFIRMED')
        self.assertIn('reverse edge', detail)
        symmetric, _ = run_graph_query({'query': 'no_code_dependency', 'left': 'a.py', 'right': 'b.py'}, sets)
        self.assertEqual(symmetric, 'REFUTED')

    def test_a_static_probe_cannot_confirm_a_causal_claim(self):
        """Regression: a branch-count probe raised a claim about *why* the branches exist to CONFIRMED."""
        from eaos import claims as ledger
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            branches = '\n'.join(f'    if value == {n}:\n        return {n}' for n in range(70))
            (repo / 'core.py').write_text(f'def decide(value):\n{branches}\n    return 0\n')
            (repo / 'main.py').write_text('import argparse\nimport core\n\n\ndef main():\n'
                                          '    argparse.ArgumentParser(prog="demo").parse_args()\n    return core.decide(1)\n')
            out = Path(tmp) / 'out'
            assemble(repo, out)
            dossier = json.loads((out / 'dossier.json').read_text())
            hotspot = next(claim for claim in dossier['claims'] if 'branches over' in claim['statement'])
            causal = ledger.make(900, 'The branching comes from inlined validation rather than the problem itself',
                                 'cause', 'HYPOTHESIS', ['model_inference'], [], 'Extracting the validation and measuring no change',
                                 fact_ids=hotspot['fact_ids'], probe_spec=hotspot['probe_spec'])
            dossier['claims'].append(causal)
            (out / 'dossier.json').write_text(json.dumps(dossier, ensure_ascii=False))
            probes.run_all(repo, out)
            updated = json.loads((out / 'dossier.json').read_text())
            decided = next(claim for claim in updated['claims'] if claim['claim_type'] == 'cause')
            self.assertEqual(decided['confidence'], 'LIKELY')
            rows = json.loads((out / 'probes.json').read_text())
            partial = [row for row in rows if row['status'] == 'PARTIAL']
            self.assertTrue(partial)
            self.assertIn('cannot establish a cause claim', partial[0]['result'])

"""Probes: confidence that is earned, and refutations that are real."""
import json
from pathlib import Path
import tempfile
import unittest
import shared_fixture  # noqa: F401  (runs without measured detector verdicts)
from eaos.analysis import probe_queries, probes
from eaos.analysis.dossier import assemble
from eaos.facts.run import collect

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

    def test_a_probe_never_settles_more_than_it_can_see(self):
        from eaos.analysis.probes import linking_import, run_graph_query
        # An import whose names were not captured is inconclusive, not a refutation.
        sets = {'syntax': {'facts': [{'id': 'F1', 'kind': 'import_edge', 'value': {'names': []}}]},
                'resolve': {'facts': [{'resolution': 'RESOLVED', 'location': {'path': 'a.ts'},
                                       'value': {'to_path': 'b.ts', 'import_fact_id': 'F1'}}]}}
        self.assertTrue(linking_import('RATE', ['a.ts', 'b.ts'], sets).startswith('UNKNOWN: '))
        # Execution probes are blocked unless explicitly allowed.
        row = probes.probe(1, 'CLM-001', 'execution', {'command': 'pytest'}, requires_execution=True)
        self.assertEqual((row['status'], row['requires_execution']), ('not_run', True))
        # Regression: a claim that A must not import B was refuted because B imports A.
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
        from eaos.analysis import claims as ledger
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            branches = '\n'.join(f'    if value == {n}:\n        return {n}' for n in range(70))
            (repo / 'core.py').write_text(f'def decide(value):\n{branches}\n    return 0\n')
            (repo / 'main.py').write_text('import argparse\nimport core\n\n\ndef main():\n'
                                          '    argparse.ArgumentParser(prog="demo").parse_args()\n    return core.decide(1)\n')
            out = Path(tmp) / 'out'
            assemble(repo, out)
            dossier = json.loads((out / 'dossier.json').read_text())
            hotspot = next(claim for claim in dossier['claims'] if 'has complexity' in claim['statement'])
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


    def test_a_complexity_card_clears_exactly_its_finish_line_each_judged_by_one_ruler(self):
        # EAOS, 2026-10-15: one card mixed seven kinds of finding, judged the whole file by any engine; six cards of a
        # batch could not pass whatever the assistant changed
        from eaos.analysis import finish_line
        def engine(rule, symbol, value=20):
            return {'id': rule + symbol, 'value': {'kind': 'complexity', 'engine': rule.split('.')[0], 'rule': rule,
                    'measurements': [{'value': value, 'threshold': 15}]}, 'location': {'path': 'a.py', 'symbol': symbol}}
        def counted(**branches):
            return {'facts': [{'value': {'scope': 'function', 'branches': n}, 'location': {'path': 'a.py', 'symbol': f}}
                              for f, n in branches.items()]}
        found = [engine('reforge.codebase.complex_function', 'python:function:a.py::run:arity:1', 40),   # EAOS counts 12
                 engine('lizard.ccn', 'a.py::decide'),                                                       # EAOS counts 19
                 engine('reforge.codebase.many_parameters', 'python:function:a.py::Job::start:arity:7'),
                 engine('reforge.codebase.large_type', 'python:type:a.py::Job:declaration')]                # a split's work
        sets = {'metrics': counted(run=12, decide=19), 'external': {'facts': found}}
        wanted = finish_line.targets(found, sets)
        self.assertEqual([(t['rule'], t['name']) for t in wanted], [('branches', 'decide'), ('reforge.codebase.many_parameters', 'start')])
        spec = {'query': 'engine_cluster_present', 'place': 'a.py', 'kind': 'complexity', 'targets': wanted}
        self.assertEqual(probe_queries._engine_cluster(spec, sets)[0], 'CONFIRMED')
        fixed = {'metrics': counted(run=12, decide=9), 'external': {'facts': [found[0], found[3]]}}     # what is left is not its
        self.assertEqual(probe_queries._engine_cluster(spec, fixed), ('REFUTED', 'every target is cleared'))
        moved = {'metrics': {'facts': [{'value': {'scope': 'function', 'branches': 19}, 'location': {'path': 'b.py', 'symbol': 'decide'}}]},
                 'external': {'facts': []}}
        self.assertIn('`decide` in a.py', probe_queries._engine_cluster(spec, moved)[1], 'moving it to another file does not clear it')

    def test_a_function_with_no_name_is_judged_in_its_file_and_a_name_follows_only_where_it_was_not(self):
        # TASK-131 of a React project (2026-10-24): a target named <anonymous> was looked for in the whole project, and
        # every arrow function anywhere kept the card standing whatever its own file became
        from eaos.analysis import finish_line
        def ccn(path, symbol, line=1):
            return {'id': path + symbol, 'value': {'kind': 'complexity', 'engine': 'lizard', 'rule': 'ccn',
                    'measurements': [{'value': 30, 'threshold': 15}]}, 'location': {'path': path, 'symbol': symbol, 'line': line}}
        made = [ccn('shell.tsx', 'shell.tsx::<anonymous>', 12), ccn('shell.tsx', 'shell.tsx::pageDetails'), ccn('other.tsx', 'other.tsx::pageDetails')]
        wanted = finish_line.targets(made[:2], {'external': {'facts': made}})
        self.assertEqual([(t['name'], t.get('line'), t.get('also_in')) for t in wanted],
                         [('<anonymous>', 12, None), ('pageDetails', None, ['other.tsx'])])
        self.assertIn('the function with no name at line 12 in shell.tsx', finish_line.said(wanted[0]))
        elsewhere = {'external': {'facts': [ccn('other.tsx', 'other.tsx::<anonymous>'), made[2]]}}
        self.assertEqual(finish_line.left(wanted, elsewhere), [], 'what other files hold, and held then, is not this card')
        moved = {'external': {'facts': [ccn('new.tsx', 'new.tsx::pageDetails')]}}
        self.assertEqual([t['name'] for t in finish_line.left(wanted, moved)], ['pageDetails'], 'moved to a new file, it still stands')
        self.assertEqual([t['name'] for t in finish_line.left(wanted, {'external': {'facts': made[:1]}})], ['<anonymous>'])


class VerificationTests(unittest.TestCase):
    """The project's own tests, run in an isolated copy with coverage (eaos/live/verify.py), restored in 0.0.9."""

    def project(self, tmp):
        repo = Path(tmp) / 'repo'
        (repo / 'tests').mkdir(parents=True)
        (repo / 'used.py').write_text('def add(a, b):\n    return a + b\n')
        (repo / 'never_run.py').write_text('import used\n\n\ndef unused():\n    return used.add(1, 2)\n')
        (repo / 'tests/test_used.py').write_text('import unittest\nimport used\n\n\nclass T(unittest.TestCase):\n'
                                                 '    def test_add(self):\n        self.assertEqual(used.add(1, 2), 3)\n')
        return repo

    def test_a_real_suite_gives_coverage_facts_and_leaves_the_target_untouched(self):
        from eaos.facts.store import read_set
        from eaos.live.verify import run as verify_run
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.project(tmp)
            before = {p.relative_to(repo).as_posix(): p.read_bytes() for p in repo.rglob('*') if p.is_file()}
            result = verify_run(repo, Path(tmp) / 'out', command=['python', '-m', 'unittest', 'discover', '-s', 'tests'])
            self.assertTrue(result['executed'], result.get('reason'))
            self.assertGreater(result['coverage']['used.py']['percent'], 0)
            self.assertTrue(read_set(Path(tmp) / 'out', 'verification')['available'])
            self.assertEqual(before, {p.relative_to(repo).as_posix(): p.read_bytes() for p in repo.rglob('*') if p.is_file()})

    def test_the_check_runs_the_test_command_of_the_run_profile_not_its_lint(self):
        """The verify stage takes the test command from the run profile's checks and runs it in the sandbox copy."""
        import shutil
        import subprocess
        import sys
        from unittest import mock
        from eaos.live import verify

        ran = []

        class FakeRun:
            PROFILE = {'checks': [['npm', 'run', 'lint'], ['python', '-m', 'unittest', 'discover', '-s', 'tests']]}

            def __init__(self, target, runtime, stage, apart=""):
                self.profile = self.PROFILE
                self.sandbox = mock.Mock(copy=Path(runtime) / 'copy')
                shutil.copytree(target, self.sandbox.copy)

            def setup(self): pass
            def stop(self): pass
            def record(self, name): pass

            def run(self, argv, timeout=900, env=None, at_root=False):
                ran.append([str(a) for a in argv])
                argv = [sys.executable if a == 'python' else a for a in argv]
                done = subprocess.run(argv, cwd=self.sandbox.copy, capture_output=True, text=True)
                return done.returncode, done.stdout, done.stderr

        with tempfile.TemporaryDirectory() as tmp, mock.patch('eaos.live.run.LiveRun', FakeRun), \
                mock.patch('eaos.live.run.load_profile', lambda runtime: FakeRun.PROFILE):
            repo, runtime = self.project(tmp), Path(tmp) / 'runtime'
            result = verify.run_profile(repo, Path(tmp) / 'out', runtime)
        self.assertNotIn(['npm', 'run', 'lint'], ran)
        self.assertIn(['python', '-m', 'coverage', 'run', '--rcfile=.eaos-coveragerc', '-m', 'unittest', 'discover', '-s', 'tests'], ran)
        self.assertTrue(result['passed'])
        self.assertGreater(result['coverage']['used.py']['percent'], 0)
        self.assertEqual(result['coverage'].get('never_run.py', {}).get('percent', 0), 0)

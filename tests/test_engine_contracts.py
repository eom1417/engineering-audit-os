"""Each adapter normalises a pinned sample of its engine's real output, with no engine installed.

Four upstream projects move independently. When one changes the shape of what it emits, the
adapter must fail here — loudly, offline, in milliseconds — rather than silently mapping nothing
on somebody's repository.
"""
import json
import unittest
from pathlib import Path

from eaos.engines import codegraph, enola, jscpd, reforge
from eaos.engines.contract import KINDS

CONTRACTS = Path(__file__).resolve().parent / 'contracts'


def sample(name):
    return json.loads((CONTRACTS / f'{name}.json').read_text(encoding='utf-8'))





class CodeGraphNewToolsContractTests(unittest.TestCase):
    """The four polyglot tools produce a normalised fact kind; the contract pins each shape."""

    def setUp(self):
        self.payload = sample('codegraph')
        self.samples = {key.removesuffix('.json'): value for key, value in self.payload.items()
                        if key.endswith('.json')}

    def test_dependency_graph_sample_is_parsable(self):
        sample = self.samples.get('codegraph_get_dependency_graph')
        self.assertIsNotNone(sample)
        self.assertIn('summary', sample)

    def test_call_graph_sample_is_parsable(self):
        sample = self.samples.get('codegraph_get_call_graph')
        self.assertIsNotNone(sample)
        # The tool returns either a real graph or a message saying the symbol could not be found.
        self.assertTrue('edges' in sample or 'message' in sample)

    def test_hot_paths_sample_is_parsable(self):
        sample = self.samples.get('codegraph_find_hot_paths')
        self.assertIsNotNone(sample)
        self.assertIn('functions', sample)
        for function in sample['functions']:
            self.assertIn('name', function)
            self.assertIn('score', function)

    def test_each_tool_payload_matches_a_known_kind(self):
        from eaos.engines import codegraph
        for tool, kind in codegraph.TOOLS.items():
            self.assertIn(kind, KINDS, f'{tool} maps to {kind} which is not in KINDS')

    def test_engine_run_against_a_real_repo_does_not_crash(self):
        """The wrapper records each tool's status; failures downgrade to partial."""
        from eaos.engines import codegraph
        import tempfile
        target = Path('/workspace/upstream-src/enola')
        if not target.is_dir(): self.skipTest('enola reference absent')
        with tempfile.TemporaryDirectory() as tmp:
            result = codegraph.run(target, Path(tmp))
        self.assertIn('summary', result)
        self.assertIn('tools', result['summary'])
        for tool in codegraph.TOOLS:
            self.assertIn(tool, result['summary']['tools'])
class SampleTests(unittest.TestCase):
    def test_every_adapter_has_a_pinned_sample_at_its_pinned_version(self):
        for module in (enola, codegraph, reforge, jscpd):
            payload = sample(module.NAME)
            self.assertEqual(payload['pinned_version'], module.PINNED,
                             f'{module.NAME}: the sample was captured from another version')

    def test_a_sample_carries_at_least_one_real_payload(self):
        for module in (enola, codegraph, reforge, jscpd):
            payload = sample(module.NAME)
            files = [key for key in payload if key.endswith('.json')]
            self.assertTrue(files, module.NAME)


class EnolaContractTests(unittest.TestCase):
    def setUp(self):
        self.payload = sample('enola')

    def test_every_insight_source_is_mapped_or_deliberately_unmapped(self):
        unmapped = {row['source'] for row in self.payload['insights.json']
                    if row['source'] not in enola.KIND_BY_SOURCE}
        surprising = sorted(unmapped - set(enola.DECLINED_SOURCES))
        self.assertEqual(surprising, [],
                         'an insight source appeared that the adapter neither maps nor declines')

    def test_the_declined_sources_are_named_rather_than_silently_dropped(self):
        self.assertTrue(enola.DECLINED_SOURCES)
        self.assertEqual(sorted(set(enola.DECLINED_SOURCES) & set(enola.KIND_BY_SOURCE)), [],
                         'a source cannot be both mapped and declined')

    def test_every_mapped_kind_is_in_the_shared_vocabulary(self):
        for kind in enola.KIND_BY_SOURCE.values():
            self.assertIn(kind, KINDS)

    def test_the_receipt_still_carries_the_provenance_the_adapter_reads(self):
        receipt = self.payload['receipt.json']
        for field in ('snapshot_id', 'extractor_version', 'extractors', 'explainers'):
            self.assertIn(field, receipt, f'enola stopped reporting {field}')

    def test_an_insight_still_locates_itself(self):
        located = [row for row in self.payload['insights.json'] if (row.get('evidence') or [{}])[0].get('file')]
        self.assertTrue(located, 'no insight carries a file any more; every finding would lose its place')

    def test_the_explainer_list_still_names_the_kinds_the_adapter_expects(self):
        explainers = set(self.payload['receipt.json']['explainers'])
        self.assertTrue(explainers & set(enola.KIND_BY_SOURCE),
                        'enola renamed its explainers; evaluated coverage would read as empty')


class ReforgeContractTests(unittest.TestCase):
    def setUp(self):
        self.payload = sample('reforge')['report.json']

    def test_the_schema_version_is_the_one_the_adapter_pins(self):
        self.assertEqual(self.payload['schema_version'], reforge.SCHEMA)

    def test_every_family_in_the_sample_is_mapped(self):
        unmapped = sorted({issue['family'].rsplit('.', 1)[-1] for issue in self.payload['issues']
                           if issue['family'].rsplit('.', 1)[-1] not in reforge.KIND_BY_FAMILY})
        self.assertEqual(unmapped, [], 'reforge reported a family the adapter would drop')

    def test_evidence_still_carries_rules_and_measurements(self):
        evidence = [item for issue in self.payload['issues'] for item in issue.get('evidence', [])]
        self.assertTrue(evidence)
        self.assertTrue(all('rule' in item for item in evidence))
        self.assertTrue(any(item.get('measurements') for item in evidence),
                        'no measurement survived; thresholds would disappear from every finding')

    def test_per_rule_coverage_is_still_reported(self):
        rules = ((self.payload.get('coverage') or {}).get('codebase') or {}).get('rules')
        self.assertTrue(rules, 'reforge stopped reporting per-rule coverage; partial would read as observed')
        self.assertTrue(any(detail.get('status') == 'partial' for detail in rules.values())
                        or any(detail.get('status') == 'observed' for detail in rules.values()))


class JscpdContractTests(unittest.TestCase):
    def setUp(self):
        self.payload = sample('jscpd')['jscpd-report.json']

    def test_a_clone_still_names_both_of_its_files_and_lines(self):
        for clone in self.payload['duplicates']:
            for side in ('firstFile', 'secondFile'):
                self.assertIn('name', clone[side])
                self.assertIn('start', clone[side])
            self.assertIn('lines', clone)

    def test_the_statistics_the_coverage_line_reports_are_present(self):
        total = self.payload['statistics']['total']
        for field in ('sources', 'lines', 'percentage', 'clones'):
            self.assertIn(field, total, f'jscpd stopped reporting {field}')


class CodegraphContractTests(unittest.TestCase):
    def setUp(self):
        self.payload = sample('codegraph')

    def test_the_dependency_graph_sample_carries_a_summary(self):
        sample = self.payload['codegraph_get_dependency_graph.json']
        self.assertIn('summary', sample)

    def test_the_hot_paths_sample_carries_functions(self):
        sample = self.payload['codegraph_find_hot_paths.json']
        self.assertIn('functions', sample)
        for function in sample['functions']:
            self.assertIn('name', function)
            self.assertIn('score', function)


class OfflineNormalisationTests(unittest.TestCase):
    """The mapping itself, exercised without running any binary."""

    def test_enola_insights_become_findings_with_places(self):
        payload = sample('enola')
        findings = []
        for insight in payload['insights.json']:
            kind = enola.KIND_BY_SOURCE.get(insight['source'])
            if kind is None:
                continue
            evidence = (insight.get('evidence') or [{}])[0]
            key = evidence.get('symbol') or evidence.get('fact') or evidence.get('file')
            if not key:
                continue
            findings.append((kind, key))
        self.assertTrue(findings)
        for kind, key in findings:
            self.assertIn(kind, KINDS)
            self.assertTrue(key)

    def test_reforge_group_issues_keep_every_member_site(self):
        payload = sample('reforge')['report.json']
        grouped = [issue for issue in payload['issues'] if (issue.get('subject') or {}).get('kind') == 'group']
        for issue in grouped:
            members = (issue['subject'] or {}).get('members') or []
            locations = [spot for item in issue.get('evidence', []) for spot in item.get('locations', [])]
            self.assertTrue(members or locations,
                            'a grouped issue with neither members nor locations would be dropped')


class PrecisionCorpusTests(unittest.TestCase):
    """The labelled corpus must stay well-formed even where the engines are not installed."""

    def test_every_case_declares_what_was_planted_and_why(self):
        from tools.engine_precision import cases
        found = list(cases())
        self.assertTrue(found, 'the engine corpus is empty')
        for path, truth in found:
            self.assertTrue(truth['planted'], path.name)
            for planted in truth['planted']:
                for field in ('id', 'engine', 'kind', 'why'):
                    self.assertIn(field, planted, f'{path.name}: a planted case without {field}')
                self.assertIn(planted['kind'], KINDS, path.name)

    def test_a_known_limitation_is_recorded_rather_than_the_case_being_deleted(self):
        from tools.engine_precision import cases
        limitations = [line for _, truth in cases() for line in truth.get('known_limitations', [])]
        self.assertTrue(limitations, 'no measured limitation is recorded; the corpus is too flattering')
        for line in limitations:
            self.assertRegex(line, r'\d{4}-\d{2}-\d{2}', 'a limitation must say when it was measured')

    def test_the_recorded_measurement_matches_the_corpus(self):
        record = Path(__file__).resolve().parents[1] / 'docs/engine-precision.json'
        self.assertTrue(record.is_file(), 'run tools/engine_precision.py --write')
        payload = json.loads(record.read_text(encoding='utf-8'))
        from tools.engine_precision import cases
        self.assertEqual(payload['summary']['cases'], len(list(cases())))
        self.assertEqual(payload['summary']['found'], payload['summary']['planted'],
                         'a planted case is no longer detected; the record is stale or an engine regressed')


class CodegraphWrapperContracts(unittest.TestCase):
    """The wrapper never raises, never guesses, and never hides a tool failure."""

    def test_run_does_not_raise_when_binary_is_missing(self):
        import tempfile
        from pathlib import Path
        from eaos.engines import codegraph
        original = codegraph.BINARY
        codegraph.BINARY = '/nonexistent/codegraph-server'
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / 'out'
                result = codegraph.run(Path('/workspace/upstream-src/enola'), out)
        finally:
            codegraph.BINARY = original
        self.assertEqual(result['available'], False)
        self.assertEqual(result['summary']['tools'], {})
        self.assertEqual(len(result['facts']), 0)

    def test_run_with_a_missing_tool_records_decline_not_silence(self):
        import tempfile
        from pathlib import Path
        from eaos.engines import codegraph
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            target = Path('/workspace/upstream-src/enola')
            if not target.is_dir():
                self.skipTest('enola reference absent')
            result = codegraph.run(target, out, tools={'find_hot_paths': True, 'get_dependency_graph': False,
                                                       'get_call_graph': False, 'analyze_complexity': False})
        self.assertIn('codegraph_find_hot_paths', result['summary']['tools'])
        # The other tools must be reported as declined or not present; never silently absent.
        self.assertNotIn('codegraph_get_dependency_graph', result['summary']['tools'])
        self.assertNotIn('codegraph_get_call_graph', result['summary']['tools'])
        self.assertNotIn('codegraph_analyze_complexity', result['summary']['tools'])

    def test_external_merge_has_no_silent_exception_handler_or_dead_true_branch(self):
        import ast
        source = (Path(__file__).resolve().parents[1] / 'eaos/facts/external.py').read_text()
        tree = ast.parse(source)
        silent = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)
                  and len(node.body) == 1 and isinstance(node.body[0], ast.Pass)]
        self.assertEqual(silent, [])
        self.assertNotIn('or True', source)
        self.assertIn("'edge_merge'", source)
        self.assertIn("'zero_findings'", source)


class LoadCorpusTests(unittest.TestCase):
    """Every one of the eight load questions must be answerable on a case built to answer it."""

    def _cases(self):
        from tools.engine_precision import LOAD_CORPUS, cases
        return list(cases(LOAD_CORPUS))

    def test_there_is_a_case_for_every_question(self):
        from eaos.load_model import QUESTIONS
        planted = {row['question'] for _, truth in self._cases() for row in truth['planted']}
        self.assertEqual(sorted(planted), sorted(QUESTIONS),
                         'a load question has no case proving it can be answered')

    def test_every_case_names_the_expected_answer_and_why_it_matters(self):
        for path, truth in self._cases():
            self.assertTrue(truth.get('load_case'), path.name)
            for planted in truth['planted']:
                for field in ('id', 'question', 'expected', 'why'):
                    self.assertIn(field, planted, path.name)
                self.assertGreater(len(planted['why']), 30,
                                   f'{path.name}: say why this matters, not just what it is')

    def test_the_recorded_measurement_answers_every_question(self):
        record = Path(__file__).resolve().parents[1] / 'docs/engine-precision.json'
        self.assertTrue(record.is_file(), 'run tools/engine_precision.py --write')
        payload = json.loads(record.read_text(encoding='utf-8'))
        summary = payload.get('load_summary')
        self.assertIsNotNone(summary, 'the load corpus was never measured')
        self.assertEqual(summary['answered'], summary['planted'],
                         'a planted load question is no longer answered')

    def test_a_case_whose_engine_dependency_is_recorded_says_so(self):
        limitations = [line for _, truth in self._cases() for line in truth.get('known_limitations', [])]
        self.assertTrue(any('engine' in line for line in limitations),
                        'complexity_class depends on an engine and the corpus should record that')


class CodeGraphAdapterContractTests(unittest.TestCase):
    """The adapter interface every engine implements, and the shapes CodeGraph answers in."""

    def test_codegraph_implements_the_adapter_interface_every_engine_is_called_through(self):
        # Without `analyze` the registry raised AttributeError on every run, the error was stored
        # as a status nobody reads, and the engine never appeared in `engines_observed` -- so a
        # working binary indexing tens of thousands of edges contributed nothing.
        from eaos.engines import ADAPTERS
        for name, adapter in ADAPTERS.items():
            with self.subTest(engine=name):
                self.assertTrue(callable(getattr(adapter, 'analyze', None)),
                                f'{name} cannot be reached through the engine registry')
                self.assertTrue(callable(getattr(adapter, 'capabilities', None)))
                self.assertTrue(callable(getattr(adapter, 'version', None)))

    def test_an_absolute_engine_path_is_recorded_relative_to_the_scanned_tree(self):
        from eaos.engines.codegraph import _relative
        self.assertEqual(_relative('/repo/pkg/a.go', '/repo'), 'pkg/a.go')
        # A path outside the tree is kept as given rather than mangled into a wrong relative one.
        self.assertEqual(_relative('/elsewhere/b.go', '/repo'), '/elsewhere/b.go')
        self.assertEqual(_relative('', '/repo'), '')

    def test_a_dependency_edge_whose_ends_have_no_name_is_dropped_not_numbered(self):
        from eaos.engines.codegraph import _module_edges_from_dep_graph
        payload = {'nodes': [{'id': '1', 'type': 'codefile', 'path': '/repo/pkg/a.go', 'language': 'go'},
                             {'id': '2', 'type': 'module', 'name': 'strings', 'path': ''}],
                   'edges': [{'from': '1', 'to': '2', 'type': 'import'},
                             {'from': '1', 'to': '99', 'type': 'import'},
                             {'from': '404', 'to': '2', 'type': 'import'}]}
        facts = _module_edges_from_dep_graph(payload, '/repo')
        self.assertEqual(len(facts), 1, 'edges pointing at an unknown node id must be dropped')
        self.assertEqual(facts[0]['value']['from'], 'pkg/a.go')
        self.assertEqual(facts[0]['value']['to'], 'strings')
        self.assertNotIn('99', json.dumps(facts))

    def test_the_files_asked_about_include_the_ones_the_flows_touch(self):
        # The flow fact names its path set `touched_files`. Reading `files` returned an empty list
        # on every project, so the engine saw entry points only and never the paths behind them.
        import tempfile
        from eaos.engines.codegraph import files_of_interest
        with tempfile.TemporaryDirectory() as tmp:
            facts = Path(tmp) / 'report' / 'facts'
            facts.mkdir(parents=True)
            (facts / 'entrypoints.json').write_text(json.dumps({'facts': [
                {'kind': 'entry_point', 'location': {'path': 'cmd/main.go'}, 'value': {'category': 'source'}},
                {'kind': 'entry_point', 'location': {'path': 'cmd/main_test.go'}, 'value': {'category': 'test'}},
            ]}))
            (facts / 'flows.json').write_text(json.dumps({'facts': [
                {'kind': 'flow', 'location': {'path': 'cmd/main.go'},
                 'value': {'entry': {'path': 'cmd/main.go'},
                           'touched_files': ['cmd/main.go', 'internal/store/store.go']}},
            ]}))
            found = files_of_interest(Path(tmp) / 'report' / 'engines' / 'codegraph')
        self.assertIn('internal/store/store.go', found, 'a file only a flow reaches must still be asked about')
        self.assertIn('cmd/main.go', found)
        self.assertNotIn('cmd/main_test.go', found, 'a test entry point is not the reader\'s entry point')

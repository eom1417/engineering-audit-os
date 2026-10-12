"""Each adapter normalises a pinned sample of its engine's real output, with no engine installed.

Four upstream projects move independently. When one changes the shape of what it emits, the
adapter must fail here — loudly, offline, in milliseconds — rather than silently mapping nothing
on somebody's repository.
"""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.engines import codegraph, enola, jscpd, reforge
from eaos.engines.contract import KINDS

CONTRACTS = Path(__file__).resolve().parent / 'contracts'


def sample(name):
    return json.loads((CONTRACTS / f'{name}.json').read_text(encoding='utf-8'))


class SampleTests(unittest.TestCase):
    def test_every_adapter_has_a_real_sample_at_its_pinned_version_and_maps_into_the_shared_kinds(self):
        for module in (enola, codegraph, reforge, jscpd):
            payload = sample(module.NAME)
            self.assertEqual(payload['pinned_version'], module.PINNED, f'{module.NAME}: captured from another version')
            self.assertTrue([key for key in payload if key.endswith('.json')], module.NAME)
        kinds = list(enola.KIND_BY_SOURCE.values()) + list(reforge.KIND_BY_FAMILY.values()) + list(codegraph.TOOLS.values())
        for kind in kinds:
            self.assertIn(kind, KINDS)

    def test_every_adapter_is_reachable_through_the_engine_registry(self):
        # Without `analyze` the registry raised AttributeError on every run and a working engine contributed nothing.
        from eaos.engines import ADAPTERS
        for name, adapter in ADAPTERS.items():
            with self.subTest(engine=name):
                for method in ('analyze', 'capabilities', 'version'):
                    self.assertTrue(callable(getattr(adapter, method, None)), f'{name} has no {method}')


class EnolaContractTests(unittest.TestCase):
    def test_every_insight_source_is_mapped_or_deliberately_declined_and_still_locates_itself(self):
        payload = sample('enola')
        unmapped = {row['source'] for row in payload['insights.json'] if row['source'] not in enola.KIND_BY_SOURCE}
        self.assertEqual(sorted(unmapped - set(enola.DECLINED_SOURCES)), [],
                         'an insight source appeared that the adapter neither maps nor declines')
        self.assertTrue(enola.DECLINED_SOURCES)
        self.assertEqual(sorted(set(enola.DECLINED_SOURCES) & set(enola.KIND_BY_SOURCE)), [])
        receipt = payload['receipt.json']
        for field in ('snapshot_id', 'extractor_version', 'extractors', 'explainers'):
            self.assertIn(field, receipt, f'enola stopped reporting {field}')
        self.assertTrue(set(receipt['explainers']) & set(enola.KIND_BY_SOURCE), 'enola renamed its explainers')
        located = [row for row in payload['insights.json']
                   if row['source'] in enola.KIND_BY_SOURCE and (row.get('evidence') or [{}])[0].get('file')]
        self.assertTrue(located, 'no mapped insight carries a file any more; every finding would lose its place')


class ReforgeContractTests(unittest.TestCase):
    def test_every_family_is_mapped_with_its_rules_measurements_coverage_and_group_sites(self):
        payload = sample('reforge')['report.json']
        self.assertEqual(payload['schema_version'], reforge.SCHEMA)
        unmapped = sorted({issue['family'].rsplit('.', 1)[-1] for issue in payload['issues']
                           if issue['family'].rsplit('.', 1)[-1] not in reforge.KIND_BY_FAMILY})
        self.assertEqual(unmapped, [], 'reforge reported a family the adapter would drop')
        evidence = [item for issue in payload['issues'] for item in issue.get('evidence', [])]
        self.assertTrue(evidence and all('rule' in item for item in evidence))
        self.assertTrue(any(item.get('measurements') for item in evidence), 'thresholds would disappear from every finding')
        rules = ((payload.get('coverage') or {}).get('codebase') or {}).get('rules')
        self.assertTrue(rules, 'reforge stopped reporting per-rule coverage; partial would read as observed')
        for issue in payload['issues']:
            if (issue.get('subject') or {}).get('kind') == 'group':
                members = issue['subject'].get('members') or []
                locations = [spot for item in issue.get('evidence', []) for spot in item.get('locations', [])]
                self.assertTrue(members or locations, 'a grouped issue with neither members nor locations would be dropped')


class JscpdAndCodegraphContractTests(unittest.TestCase):
    def test_jscpd_clones_and_statistics_and_codegraph_tool_payloads_keep_their_shape(self):
        report = sample('jscpd')['jscpd-report.json']
        for clone in report['duplicates']:
            for side in ('firstFile', 'secondFile'):
                self.assertLessEqual({'name', 'start'}, set(clone[side]))
            self.assertIn('lines', clone)
        self.assertLessEqual({'sources', 'lines', 'percentage', 'clones'}, set(report['statistics']['total']))
        payload = sample('codegraph')
        self.assertIn('summary', payload['codegraph_get_dependency_graph.json'])
        calls = payload['codegraph_get_call_graph.json']
        self.assertTrue('edges' in calls or 'message' in calls)
        for function in payload['codegraph_find_hot_paths.json']['functions']:
            self.assertLessEqual({'name', 'score'}, set(function))


class CodegraphAdapterTests(unittest.TestCase):
    """The wrapper never raises, never guesses, and never hides a tool failure."""

    def test_a_missing_binary_is_reported_unavailable_not_raised(self):
        original = codegraph.BINARY
        codegraph.BINARY = '/nonexistent/codegraph-server'
        try:
            with tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / 'src').mkdir()
                (Path(tmp) / 'src/a.go').write_text('package a\n')
                result = codegraph.run(Path(tmp) / 'src', Path(tmp) / 'out')
        finally:
            codegraph.BINARY = original
        self.assertEqual((result['available'], result['summary']['tools'], result['facts']), (False, {}, []))

    def test_engine_paths_are_relative_nameless_edges_are_dropped_and_flow_files_are_asked_about(self):
        from eaos.engines.codegraph import _relative, _module_edges_from_dep_graph, files_of_interest
        self.assertEqual(_relative('/repo/pkg/a.go', '/repo'), 'pkg/a.go')
        # A path outside the tree is kept as given rather than mangled into a wrong relative one.
        self.assertEqual(_relative('/elsewhere/b.go', '/repo'), '/elsewhere/b.go')
        self.assertEqual(_relative('', '/repo'), '')
        payload = {'nodes': [{'id': '1', 'type': 'codefile', 'path': '/repo/pkg/a.go', 'language': 'go'},
                             {'id': '2', 'type': 'module', 'name': 'strings', 'path': ''}],
                   'edges': [{'from': '1', 'to': '2', 'type': 'import'}, {'from': '1', 'to': '99', 'type': 'import'},
                             {'from': '404', 'to': '2', 'type': 'import'}]}
        facts = _module_edges_from_dep_graph(payload, '/repo')
        self.assertEqual([(f['value']['from'], f['value']['to']) for f in facts], [('pkg/a.go', 'strings')])
        self.assertNotIn('99', json.dumps(facts))
        # The flow fact names its path set `touched_files`; a file only a flow reaches must still be asked about.
        with tempfile.TemporaryDirectory() as tmp:
            facts_dir = Path(tmp) / 'report' / 'facts'
            facts_dir.mkdir(parents=True)
            (facts_dir / 'entrypoints.json').write_text(json.dumps({'facts': [
                {'kind': 'entry_point', 'location': {'path': 'cmd/main.go'}, 'value': {'category': 'source'}},
                {'kind': 'entry_point', 'location': {'path': 'cmd/main_test.go'}, 'value': {'category': 'test'}}]}))
            (facts_dir / 'flows.json').write_text(json.dumps({'facts': [
                {'kind': 'flow', 'location': {'path': 'cmd/main.go'},
                 'value': {'entry': {'path': 'cmd/main.go'}, 'touched_files': ['cmd/main.go', 'internal/store/store.go']}}]}))
            found = files_of_interest(Path(tmp) / 'report' / 'engines' / 'codegraph')
        self.assertTrue({'internal/store/store.go', 'cmd/main.go'} <= set(found))
        self.assertNotIn('cmd/main_test.go', found, "a test entry point is not the reader's entry point")

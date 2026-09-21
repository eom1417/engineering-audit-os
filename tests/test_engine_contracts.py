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
        self.payload = sample('codegraph')['codegraph_find_circular_deps.json']

    def test_the_cycle_tool_still_answers_in_the_shape_the_adapter_reads(self):
        for field in ('cycles', 'total_cycles'):
            self.assertIn(field, self.payload)

    def test_a_warning_in_the_payload_is_what_downgrades_the_coverage(self):
        """The sample is the warning case: the engine saying its own answer may be incomplete."""
        self.assertIn('warning', self.payload)
        self.assertIn('indexed', self.payload['warning'])


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

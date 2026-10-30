"""Each adapter normalises a pinned sample of its engine's real output, with no engine installed.

Four upstream projects move independently. When one changes the shape of what it emits, the
adapter must fail here — loudly, offline, in milliseconds — rather than silently mapping nothing
on somebody's repository.
"""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.engines.code import reforge
from eaos.engines.contract import KINDS

CONTRACTS = Path(__file__).resolve().parents[1] / 'contracts'


def sample(name):
    return json.loads((CONTRACTS / f'{name}.json').read_text(encoding='utf-8'))


# The engines with no captured sample: each writes SARIF, read by sarif.py and its tests (test_sarif).
UNSAMPLED = ('bandit', 'gitleaks', 'codeql')


class SampleTests(unittest.TestCase):
    def test_every_adapter_of_the_registry_is_its_module_pinned_with_its_sample_and_maps_into_the_shared_kinds(self):
        # The one contract every engine holds (it was asked in three files, each of a few engines). Without `analyze`
        # the registry raised AttributeError on every run and a working engine contributed nothing.
        import importlib
        from eaos.engines import ADAPTERS, tool
        for name, adapter in ADAPTERS.items():
            with self.subTest(engine=name):
                self.assertEqual((adapter.__name__.rsplit('.', 1)[-1], importlib.import_module(adapter.__name__)), (name.replace('-', '_'), adapter))
                for method in ('analyze', 'capabilities'):
                    self.assertTrue(callable(getattr(adapter, method, None)), f'{name} has no {method}')
                # its version is read from its binary (tool.version_of), or by its own reader
                self.assertTrue(callable(getattr(adapter, 'version', None)) or getattr(adapter, 'BINARY', None), f'{name} has no version reader')
                self.assertEqual(adapter.PINNED, tool.pinned(name), 'the adapter and the registry pin one version')
                if name not in UNSAMPLED:
                    self.assertEqual(sample(name)['pinned_version'], adapter.PINNED, f'{name}: captured from another version')
                for capability in adapter.capabilities(): self.assertIn(capability.kind, KINDS)
        for kind in reforge.KIND_BY_FAMILY.values():
            self.assertIn(kind, KINDS)


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


class JscpdContractTests(unittest.TestCase):
    def test_jscpd_clones_and_statistics_keep_their_shape(self):
        report = sample('jscpd')['jscpd-report.json']
        for clone in report['duplicates']:
            for side in ('firstFile', 'secondFile'):
                self.assertLessEqual({'name', 'start'}, set(clone[side]))
            self.assertIn('lines', clone)
        self.assertLessEqual({'sources', 'lines', 'percentage', 'clones'}, set(report['statistics']['total']))

"""Each adapter normalises a pinned sample of its engine's real output, with no engine installed.

Four upstream projects move independently. When one changes the shape of what it emits, the
adapter must fail here — loudly, offline, in milliseconds — rather than silently mapping nothing
on somebody's repository.
"""
import json
import unittest
from pathlib import Path

from eaos.engines.contract import KINDS

CONTRACTS = Path(__file__).resolve().parents[1] / 'contracts'


def sample(name):
    return json.loads((CONTRACTS / f'{name}.json').read_text(encoding='utf-8'))


# The engines with no captured sample: each writes SARIF, read by sarif.py and its tests (test_sarif).
UNSAMPLED = ('gitleaks',)


class SampleTests(unittest.TestCase):
    def test_every_adapter_of_the_registry_is_its_module_pinned_with_its_sample_and_maps_into_the_shared_kinds(self):
        # The one contract every engine holds. Without `analyze` the registry raises AttributeError on every run and a
        # working engine contributes nothing.
        import importlib
        from eaos.engines import ADAPTERS, tool
        for name, adapter in ADAPTERS.items():
            with self.subTest(engine=name):
                self.assertEqual((adapter.__name__.rsplit('.', 1)[-1], importlib.import_module(adapter.__name__)),
                                 (name.replace('-', '_'), adapter))
                for method in ('analyze', 'capabilities'):
                    self.assertTrue(callable(getattr(adapter, method, None)), f'{name} has no {method}')
                # its version is read from its binary (tool.version_of), or by its own reader
                self.assertTrue(callable(getattr(adapter, 'version', None)) or getattr(adapter, 'BINARY', None),
                                f'{name} has no version reader')
                self.assertEqual(adapter.PINNED, tool.pinned(name), 'the adapter and the registry pin one version')
                if name not in UNSAMPLED:
                    self.assertEqual(sample(name)['pinned_version'], adapter.PINNED,
                                     f'{name}: captured from another version')
                for capability in adapter.capabilities(): self.assertIn(capability.kind, KINDS)


class JscpdContractTests(unittest.TestCase):
    def test_jscpd_clones_and_statistics_keep_their_shape(self):
        report = sample('jscpd')['jscpd-report.json']
        for clone in report['duplicates']:
            for side in ('firstFile', 'secondFile'):
                self.assertLessEqual({'name', 'start'}, set(clone[side]))
            self.assertIn('lines', clone)
        self.assertLessEqual({'sources', 'lines', 'percentage', 'clones'}, set(report['statistics']['total']))

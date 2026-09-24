"""A dead-code candidate whose name lives in a distribution registry is not dead.

The detector scans the snapshot for module lists (``MODULES = [a, b, c]``), dictionary
lookups that reference a name by string, ``getattr(obj, "name")``, ``__all__``
declarations, ``importlib.import_module('x')`` calls and JSON-name records under
``eaos/data/``. A candidate whose qualified name resolves through any of those
patterns is kept in the fact set (so downstream stages and the S2 measure still see
it) but is tagged ``value.referenced_by_registry = True``; the cluster pass skips the
tagged facts so a dead_code claim is never raised for them — the NS4.T2 spec:
'a candidate referenced by one of these sources stays as engine_finding and does
not become a dead_code claim'.

Findings the engine mislabels as ``dead_code`` (compatibility markers, plugin rows)
carry the right kind but do not name a function or method; they are left alone, with
no registry tag.
"""
import tempfile
import unittest
from pathlib import Path

from eaos.correlate import filter_dead_code_references, _filter_registry_referenced_dead_code
from eaos.facts.source import Source


def _write(root, rel, content=''):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _dead_fact(symbol, message=None):
    if message is None:
        message = 'Dead code candidate: function ' + symbol
    return {'id': 'FACT-' + symbol, 'kind': 'engine_finding', 'extractor': 'external',
            'extractor_version': '1', 'input_sha': 'a' * 64,
            'location': {'path': symbol.split('.')[0] + '.py', 'line': 1, 'symbol': symbol},
            'value': {'engine': 'enola', 'engine_version': '0', 'rule': 'dead-code',
                      'kind': 'dead_code', 'method': 'heuristic', 'message': message,
                      'measurements': [], 'engine_confidence': 0,
                      'subject_kind': 'symbol', 'sites': []}}


class RegistrySignatureTests(unittest.TestCase):
    """The hook returns what it claims to return."""

    def test_filter_returns_a_tuple_of_kept_list_and_dropped_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            kept, dropped = filter_dead_code_references([_dead_fact('a.b.c')], Source(Path(tmp)))
        self.assertIsInstance(kept, list)
        self.assertIsInstance(dropped, int)


class RegistryReferenceTests(unittest.TestCase):
    """A function whose module sits in a MODULES list is reachable by attribute access."""

    def test_a_module_listed_in_MODULES_is_marked(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, 'pkgs/__init__.py', 'MODULES = [jvm_web, python_web]\n')
            _write(tmp, 'pkgs/jvm_web.py', 'def detect(): return 1\n')
            src = Source(Path(tmp))
            kept, dropped = filter_dead_code_references(
                [_dead_fact('eaos/pkgs/jvm_web.detect'),
                 _dead_fact('eaos/pkgs/python_web.detect'),
                 _dead_fact('eaos/pkgs/unrelated.dead')], src)
            self.assertEqual(dropped, 2, 'two references were marked')
            self.assertEqual(len(kept), 3, 'all three facts are still on disk')
            registry_marked = [f for f in kept if (f.get('value') or {}).get('referenced_by_registry')]
            unrelated = [f for f in kept if not (f.get('value') or {}).get('referenced_by_registry')]
            self.assertEqual(len(registry_marked), 2)
            self.assertEqual(len(unrelated), 1)
            self.assertEqual(unrelated[0]['location']['symbol'], 'eaos/pkgs/unrelated.dead')

    def test_a_module_listed_in_MODULES_can_be_a_module_path(self):
        # The detector's name follows the convention ``module.detect``; the registry
        # holds the bare module name and registers the full path automatically.
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, 'pkgs/__init__.py', 'MODULES = [jvm_web, python_web]\n')
            _write(tmp, 'pkgs/jvm_web.py', 'def detect(): return 1\n')
            _write(tmp, 'pkgs/python_web.py', 'def detect(): return 2\n')
            src = Source(Path(tmp))
            kept, dropped = filter_dead_code_references(
                [_dead_fact('pkgs/jvm_web.detect'),
                 _dead_fact('pkgs/python_web.detect'),
                 _dead_fact('pkgs/jvm_web.unrelated')], src)
            self.assertEqual(dropped, 2)
            self.assertEqual(len(kept), 3)

    def test_a_compatibility_path_finding_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Source(Path(tmp))
            facts = [_dead_fact('eaos/claims.py',
                                'compatibility path has 6 markers without a clear sunset or migration boundary'),
                     _dead_fact('eaos/dossier.py',
                                'compatibility path has 3 markers without a clear sunset')]
            kept, dropped = filter_dead_code_references(facts, src)
            self.assertEqual(dropped, 0, 'compatibility paths are not function references')
            self.assertEqual(len(kept), 2)
            for f in kept:
                self.assertFalse((f.get('value') or {}).get('referenced_by_registry'))

    def test_all_names_module_patresets_a_registry_invocation(self):
        # ``__all__ = ['detect', 'compute']`` re-exports those names for ``from x import *``;
        # the detector marks a candidate whose bare name appears in any ``__all__`` list.
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, 'pkgs/__init__.py', "MODULES = [bar]\n__all__ = ['compute']\n")
            _write(tmp, 'pkgs/bar.py', 'def compute(): return 1\n')
            src = Source(Path(tmp))
            kept, dropped = filter_dead_code_references(
                [_dead_fact('pkgs/bar.compute'),
                 _dead_fact('pkgs/bar.unrelated')], src)
            self.assertEqual(dropped, 1)
            self.assertEqual(len(kept), 2)

    def test_an_importlib_call_with_a_literal_argument_is_a_registry(self):
        # importlib.import_module('foo') pulls 'foo' by name at runtime; the detector
        # marks a candidate whose bare name appears as a literal argument.
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, 'a.py', "importlib.import_module('compute')\n")
            _write(tmp, 'pkgs/__init__.py', "MODULES = [bar]\n")
            _write(tmp, 'pkgs/bar.py', 'def compute(): return 1\n')
            src = Source(Path(tmp))
            kept, dropped = filter_dead_code_references(
                [_dead_fact('pkgs/bar.compute'),
                 _dead_fact('pkgs/bar.unrelated')], src)
            self.assertEqual(dropped, 1)
            self.assertEqual(len(kept), 2)


class IntegrationTests(unittest.TestCase):
    """End-to-end: filter_dead_code_references leaves facts on disk but marks them."""

    def test_filtered_facts_still_have_kind_dead_code_for_the_s2_measure(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, 'pkgs/__init__.py', 'MODULES = [jvm_web]\n')
            _write(tmp, 'pkgs/jvm_web.py', 'def detect(): return 1\n')
            src = Source(Path(tmp))
            kept, dropped = filter_dead_code_references(
                [_dead_fact('pkgs/jvm_web.detect'),
                 _dead_fact('pkgs/jvm_web.unrelated')], src)
            self.assertEqual(dropped, 1)
            self.assertEqual(len(kept), 2)
            for f in kept:
                self.assertEqual(f['value']['kind'], 'dead_code',
                                  'the S2 measure still counts this candidate')

    def test_the_cluster_pass_skips_registry_marked_facts(self):
        from eaos.correlate import clusters
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, 'pkgs/__init__.py', 'MODULES = [bar]\n')
            _write(tmp, 'pkgs/bar.py', 'def detect(): return 1\n')
            src = Source(Path(tmp))
            facts = filter_dead_code_references(
                [_dead_fact('pkgs/bar.detect'),
                 _dead_fact('pkgs/bar.unrelated')], src)[0]
            filtered = _filter_registry_referenced_dead_code(facts, {})
            found = {f['location']['symbol'] for f in filtered
                     if not (f.get('value') or {}).get('referenced_by_registry')}
            self.assertIn('pkgs/bar.unrelated', found)
            self.assertNotIn('pkgs/bar.detect', found)

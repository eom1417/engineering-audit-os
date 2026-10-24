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

from eaos.facts.registry import filter_dead_code_references, filter_in_sets
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


def marked(files, symbols):
    with tempfile.TemporaryDirectory() as tmp:
        for rel, content in files.items():
            _write(tmp, rel, content)
        kept, dropped = filter_dead_code_references([_dead_fact(symbol) for symbol in symbols], Source(Path(tmp)))
    return kept, dropped


class RegistryReferenceTests(unittest.TestCase):
    def test_names_a_registry_reaches_are_marked_but_kept_as_dead_code_facts(self):
        cases = [({'pkgs/__init__.py': 'MODULES = [jvm_web, python_web]\n', 'pkgs/jvm_web.py': 'def detect(): return 1\n'},
                  ['eaos/pkgs/jvm_web.detect', 'eaos/pkgs/python_web.detect', 'eaos/pkgs/unrelated.dead'], 2),
                 ({'pkgs/__init__.py': 'MODULES = [jvm_web, python_web]\n', 'pkgs/jvm_web.py': 'def detect(): return 1\n',
                   'pkgs/python_web.py': 'def detect(): return 2\n'},
                  ['pkgs/jvm_web.detect', 'pkgs/python_web.detect', 'pkgs/jvm_web.unrelated'], 2),
                 ({'pkgs/__init__.py': "MODULES = [bar]\n__all__ = ['compute']\n", 'pkgs/bar.py': 'def compute(): return 1\n'},
                  ['pkgs/bar.compute', 'pkgs/bar.unrelated'], 1),
                 ({'a.py': "importlib.import_module('compute')\n", 'pkgs/__init__.py': 'MODULES = [bar]\n',
                   'pkgs/bar.py': 'def compute(): return 1\n'}, ['pkgs/bar.compute', 'pkgs/bar.unrelated'], 1)]
        for files, symbols, expected in cases:
            with self.subTest(files=files):
                kept, dropped = marked(files, symbols)
                self.assertEqual(dropped, expected)
                self.assertEqual(len(kept), len(symbols), 'every fact stays on disk')
                self.assertTrue(all(f['value']['kind'] == 'dead_code' for f in kept), 'the S2 measure still counts them')
                unmarked = [f['location']['symbol'] for f in kept if not f['value'].get('referenced_by_registry')]
                self.assertEqual(unmarked, [symbols[-1]])

    def test_a_compatibility_path_finding_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            facts = [_dead_fact('eaos/claims.py', 'compatibility path has 6 markers without a clear sunset or migration boundary'),
                     _dead_fact('eaos/dossier.py', 'compatibility path has 3 markers without a clear sunset')]
            kept, dropped = filter_dead_code_references(facts, Source(Path(tmp)))
        self.assertEqual((dropped, len(kept)), (0, 2))
        self.assertFalse(any(f['value'].get('referenced_by_registry') for f in kept))

    def test_the_cluster_pass_skips_registry_marked_facts(self):
        kept, _ = marked({'pkgs/__init__.py': 'MODULES = [bar]\n', 'pkgs/bar.py': 'def detect(): return 1\n'},
                         ['pkgs/bar.detect', 'pkgs/bar.unrelated'])
        filtered = filter_in_sets(kept, {})
        found = {f['location']['symbol'] for f in filtered if not f['value'].get('referenced_by_registry')}
        self.assertIn('pkgs/bar.unrelated', found)
        self.assertNotIn('pkgs/bar.detect', found)

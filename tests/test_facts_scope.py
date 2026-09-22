"""Exclusion contract: vendored paths are out of scope unless the project opts in."""
import json
from pathlib import Path
import tempfile
import unittest

from eaos.facts.scope import (declared_exclusions, exclusion_reasons,
                              vendored_patterns, VENDORED)
from eaos.facts.source import Source
from shared_fixture import Workspace
from eaos.facts.run import collect


class VendoredDefaultsTests(unittest.TestCase):
    def test_vendored_set_is_well_known(self):
        for name in ("testdata", "fixtures", "vendor", "node_modules",
                      "third_party", "generated", ".venv", "dist", "build"):
            self.assertIn(name, VENDORED)
            self.assertIn(name, vendored_patterns())

    def test_declared_exclusions_include_vendored(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = declared_exclusions(Path(tmp))
            for pattern in VENDORED:
                self.assertIn(pattern, result)

    def test_opt_in_returns_only_declared(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'eaos.policy.json').write_text(json.dumps({
                'schema_version': 1,
                'layers': {'all': ['**']},
                'analysis': {'include_vendored': True,
                              'exclude': ['build_only']},
            }))
            result = declared_exclusions(Path(tmp))
            self.assertNotIn('testdata', result)
            self.assertNotIn('fixtures', result)
            self.assertIn('build_only', result)


class ExclusionReasonsTests(unittest.TestCase):
    def test_reasons_carry_a_nonempty_string_for_every_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            reasons = exclusion_reasons(Path(tmp))
            for pattern in VENDORED:
                self.assertIn(pattern, reasons)
                self.assertTrue(reasons[pattern])
                self.assertIsInstance(reasons[pattern], str)


class CollectRespectsExclusionsTests(Workspace):
    def _make_repo(self):
        repo = Path(self.tmp) / 'repo'; repo.mkdir()
        (repo / 'app.py').write_text('def hello():\n    return 1\n')
        (repo / 'lib').mkdir()
        (repo / 'lib' / 'util.py').write_text('def helper():\n    return 2\n')
        (repo / 'testdata').mkdir()
        (repo / 'testdata' / 'fixture_a.py').write_text('def noise_a():\n    return 10\n')
        (repo / 'testdata' / 'fixture_b.py').write_text('def noise_b():\n    return 20\n')
        (repo / 'vendor').mkdir()
        (repo / 'vendor' / 'lib.py').write_text('def vendored():\n    return 30\n')
        return repo

    def test_vendored_files_do_not_appear_in_facts(self):
        repo = self._make_repo()
        out = Path(self.tmp) / 'out'
        result = collect(repo, out, ['syntax'])
        self.assertGreater(result['excluded_paths'], 0)
        reasons = result['exclusion_reasons']
        self.assertIn('testdata', reasons)
        self.assertIn('vendor', reasons)
        syntax = json.loads((out / 'facts/syntax.json').read_text())
        paths = {fact['location']['path'] for fact in syntax['facts']}
        self.assertNotIn('testdata/fixture_a.py', paths)
        self.assertNotIn('testdata/fixture_b.py', paths)
        self.assertNotIn('vendor/lib.py', paths)
        self.assertIn('app.py', paths)
        self.assertIn('lib/util.py', paths)

    def test_opt_in_brings_vendored_back(self):
        repo = self._make_repo()
        (repo / 'eaos.policy.json').write_text(json.dumps({
            'schema_version': 1,
            'layers': {'all': ['**']},
            'analysis': {'include_vendored': True},
        }))
        out = Path(self.tmp) / 'out'
        result = collect(repo, out, ['syntax'])
        syntax = json.loads((out / 'facts/syntax.json').read_text())
        paths = {fact['location']['path'] for fact in syntax['facts']}
        self.assertIn('testdata/fixture_a.py', paths)


class SourceExclusionTests(Workspace):
    def test_source_excludes_vendored_by_default(self):
        repo = Path(self.tmp) / 'repo'; repo.mkdir()
        (repo / 'app.py').write_text('def hi():\n    return 1\n')
        (repo / 'testdata').mkdir()
        (repo / 'testdata' / 'fixture.py').write_text('def t():\n    return 1\n')
        src = Source(repo)
        self.assertIn('testdata/fixture.py', src.excluded_files)
        self.assertNotIn('testdata/fixture.py', [item['path'] for item in src.files])

    def test_source_respects_include_vendored_flag(self):
        repo = Path(self.tmp) / 'repo'; repo.mkdir()
        (repo / 'app.py').write_text('def hi():\n    return 1\n')
        (repo / 'testdata').mkdir()
        (repo / 'testdata' / 'fixture.py').write_text('def t():\n    return 1\n')
        src = Source(repo, include_vendored=True)
        self.assertNotIn('testdata/fixture.py', src.excluded_files)

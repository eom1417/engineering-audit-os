"""Leftover detection: temp files, build outputs, archived directories, .env, committed binaries.

A file is a leftover when its name or location declares it is not part of the product AND the
import graph does not reach it. A file the resolver already imports is not a leftover, no
matter how suspicious the name.
"""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.facts.leftovers import classify, collect, run


def _write(root, rel, content=''):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _empty_resolve():
    return []


def _importing_resolve(path):
    """A resolver says ``path`` is the target of an import; that file is reachable."""
    return [{'kind': 'module_edge', 'value': {'module': path, 'to_path': path},
             'location': {'path': 'src/index.js', 'start_line': 1}}]


class _Source:
    """Minimal Source shim: provides readable() and text() like eaos.facts.source.Source."""
    def __init__(self, root, files):
        self._root = Path(root)
        self._items = [{'path': rel, 'sha256': 'a' * 64} for rel in files]

    def readable(self):
        return self._items


class ClassifyTests(unittest.TestCase):
    def test_each_pattern_returns_a_reason(self):
        self.assertEqual(classify('temp_original.tsx'), 'temp_or_backup_name')
        self.assertEqual(classify('src/backup/file.py'), 'temp_or_backup_name')
        self.assertEqual(classify('dist/bundle.js'), 'build_output')
        self.assertEqual(classify('build_output.txt'), 'build_output')
        self.assertEqual(classify('unused-archive/old.ts'), 'archived_directory')
        self.assertEqual(classify('legacy/old.ts'), 'archived_directory')
        self.assertEqual(classify('.env'), 'env_file_committed')
        self.assertEqual(classify('.env.production'), 'env_file_committed')
        self.assertEqual(classify('bin/runner.dll'), 'committed_binary')

    def test_a_normal_source_file_is_not_a_leftover(self):
        self.assertIsNone(classify('src/app.tsx'))
        self.assertIsNone(classify('eaos/policy.py'))
        self.assertIsNone(classify('README.md'))

    def test_safe_env_files_are_excluded(self):
        self.assertIsNone(classify('.env.example'))
        self.assertIsNone(classify('.env.sample'))
        self.assertIsNone(classify('.env.template'))
        self.assertIsNone(classify('.env.test'))


class CollectTests(unittest.TestCase):
    """The collector must prove a candidate is unreachable before reporting it."""

    def test_a_temp_file_with_no_imports_becomes_a_fact(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, 'src/temp_original.tsx', 'export const x = 1;')
            _write(tmp, 'src/index.tsx', 'export {};')
            source = _Source(tmp, ['src/temp_original.tsx', 'src/index.tsx'])
            results = collect(source, _empty_resolve())
            paths = [r['path'] for r in results]
            self.assertIn('src/temp_original.tsx', paths)
            for r in results:
                self.assertEqual(r['reason'], 'temp_or_backup_name')

    def test_an_imported_temp_file_is_not_a_leftover(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, 'src/temp_original.tsx', 'export const x = 1;')
            _write(tmp, 'src/index.tsx', "import './temp_original';")
            source = _Source(tmp, ['src/temp_original.tsx', 'src/index.tsx'])
            results = collect(source, _importing_resolve('src/temp_original.tsx'))
            self.assertEqual(results, [])

    def test_a_build_output_under_dist_becomes_a_fact(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, 'dist/bundle.js', 'var x = 1;')
            _write(tmp, 'src/index.js', "require('./dist/bundle');")
            source = _Source(tmp, ['dist/bundle.js', 'src/index.js'])
            results = collect(source, _empty_resolve())
            self.assertEqual([r['path'] for r in results], ['dist/bundle.js'])

    def test_archived_directory_marks_every_file_as_a_leftover(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, 'unused-archive/supabase.ts', 'export const x = 1;')
            _write(tmp, 'unused-archive/types.ts', 'export type T = string;')
            source = _Source(tmp, ['unused-archive/supabase.ts', 'unused-archive/types.ts'])
            results = collect(source, _empty_resolve())
            self.assertEqual(sorted(r['path'] for r in results),
                             sorted(['unused-archive/supabase.ts', 'unused-archive/types.ts']))
            for r in results:
                self.assertEqual(r['reason'], 'archived_directory')

    def test_env_file_committed_is_a_leftover(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, '.env', 'SECRET=topsecret')
            _write(tmp, '.env.example', 'SECRET=changeme')
            source = _Source(tmp, ['.env', '.env.example'])
            results = collect(source, _empty_resolve())
            self.assertEqual([r['path'] for r in results], ['.env'])

    def test_binary_artifact_under_commit_is_a_leftover(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, 'vendor/runner.dll', 'MZ')
            source = _Source(tmp, ['vendor/runner.dll'])
            results = collect(source, _empty_resolve())
            self.assertEqual([r['path'] for r in results], ['vendor/runner.dll'])
            self.assertEqual(results[0]['reason'], 'committed_binary')


class RunTests(unittest.TestCase):
    def test_run_produces_a_summary_with_per_reason_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, 'src/temp_x.tsx', 'export const x = 1;')
            _write(tmp, 'dist/bundle.js', 'var x = 1;')
            _write(tmp, '.env', 'SECRET=topsecret')
            source = _Source(tmp, ['src/temp_x.tsx', 'dist/bundle.js', '.env'])
            result = run(Path(tmp), source, resolve_facts=_empty_resolve())
            self.assertEqual(result['available'], True)
            reasons = {fact['value']['reason'] for fact in result['facts']}
            self.assertIn('temp_or_backup_name', reasons)
            self.assertIn('build_output', reasons)
            self.assertIn('env_file_committed', reasons)
            self.assertEqual(result['summary']['by_reason']['temp_or_backup_name'], 1)
            self.assertEqual(result['summary']['by_reason']['build_output'], 1)
            self.assertEqual(result['summary']['by_reason']['env_file_committed'], 1)

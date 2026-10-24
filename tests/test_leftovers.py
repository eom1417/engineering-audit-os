"""Leftover detection: temp files, build outputs, archived directories, .env, committed binaries.

A file is a leftover when its name or location declares it is not part of the product AND the
import graph does not reach it. A file the resolver already imports is not a leftover, no
matter how suspicious the name.
"""
import tempfile
import unittest
from pathlib import Path

from eaos.facts.leftovers import classify, run


class _Source:
    """Minimal Source shim: provides readable() like eaos.facts.source.Source."""
    def __init__(self, files):
        self._items = [{'path': rel, 'sha256': 'a' * 64} for rel in files]

    def readable(self):
        return self._items


class LeftoverTests(unittest.TestCase):
    def test_each_leftover_pattern_has_its_reason_and_source_and_safe_env_files_have_none(self):
        for path, reason in [('temp_original.tsx', 'temp_or_backup_name'), ('src/backup/file.py', 'temp_or_backup_name'),
                             ('dist/bundle.js', 'build_output'), ('build_output.txt', 'build_output'),
                             ('unused-archive/old.ts', 'archived_directory'), ('legacy/old.ts', 'archived_directory'),
                             ('.env', 'env_file_committed'), ('.env.production', 'env_file_committed'),
                             ('bin/runner.dll', 'committed_binary'), ('src/app.tsx', None), ('eaos/analysis/policy.py', None),
                             ('README.md', None), ('.env.example', None), ('.env.sample', None), ('.env.template', None),
                             ('.env.test', None)]:
            self.assertEqual(classify(path), reason, path)

    def test_only_unreachable_candidates_are_reported_with_counts_per_reason(self):
        files = ['src/temp_x.tsx', 'src/temp_used.tsx', 'src/index.tsx', 'dist/bundle.js', '.env', '.env.example',
                 'unused-archive/supabase.ts', 'unused-archive/types.ts', 'vendor/runner.dll']
        imported = [{'kind': 'module_edge', 'value': {'module': 'src/temp_used.tsx', 'to_path': 'src/temp_used.tsx'},
                     'location': {'path': 'src/index.tsx', 'start_line': 1}}]
        with tempfile.TemporaryDirectory() as tmp:
            result = run(Path(tmp), _Source(files), resolve_facts=imported)
        self.assertTrue(result['available'])
        found = {fact['location']['path']: fact['value']['reason'] for fact in result['facts']}
        self.assertEqual(found, {'src/temp_x.tsx': 'temp_or_backup_name', 'dist/bundle.js': 'build_output',
                                 '.env': 'env_file_committed', 'unused-archive/supabase.ts': 'archived_directory',
                                 'unused-archive/types.ts': 'archived_directory', 'vendor/runner.dll': 'committed_binary'},
                         'an imported temp file is not a leftover')
        self.assertEqual(result['summary']['by_reason']['archived_directory'], 2)
        self.assertEqual(result['summary']['by_reason']['build_output'], 1)

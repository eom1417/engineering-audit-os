"""Exclusion contract: vendored paths are out of scope unless the project opts in."""
import json
from pathlib import Path

from eaos.facts.scope import declared_exclusions, exclusion_reasons, VENDORED
from eaos.facts.source import Source
from shared_fixture import Workspace
from eaos.facts.run import collect


class ScopeTests(Workspace):
    def make_repo(self):
        repo = Path(self.tmp) / 'repo'
        for name, text in {'app.py': 'def hello():\n    return 1\n', 'lib/util.py': 'def helper():\n    return 2\n',
                           'testdata/fixture_a.py': 'def noise_a():\n    return 10\n',
                           'vendor/lib.py': 'def vendored():\n    return 30\n',
                           # Claude Code keeps whole copies of the code here; counting them would count every file twice.
                           '.claude/worktrees/agent-1/app.py': 'def hello():\n    return 1\n',
                           # Minified and built files are generated, in any project: a vendor .min.js, and a built
                           # bundle (the self-audit drew eaos/data/studio/assets in its C4 diagram).
                           'web/app.js': 'export const x = 1;\n', 'web/vendor.min.js': 'var a=1;\n',
                           'pkg/data/studio/assets/index-B3x9.js': 'var a=1;' * 400 + '\n'}.items():
            (repo / name).parent.mkdir(parents=True, exist_ok=True)
            (repo / name).write_text(text)
        return repo

    def syntax_paths(self, repo, out):
        result = collect(repo, out, ['syntax'])
        return result, {fact['location']['path'] for fact in json.loads((out / 'facts/syntax.json').read_text())['facts']}

    def test_vendored_paths_and_assistant_worktrees_are_excluded_with_a_reason(self):
        repo = self.make_repo()
        exclusions, reasons = declared_exclusions(repo), exclusion_reasons(repo)
        for pattern in VENDORED:
            self.assertIn(pattern, exclusions)
            self.assertTrue(reasons[pattern])
        self.assertIn('.claude/worktrees', exclusions)
        self.assertEqual(sorted(item['path'] for item in Source(repo).files), ['app.py', 'lib/util.py', 'web/app.js'])
        self.assertIn('*.min.js', reasons)
        # The self-check of 2026-10-12: the file globs reached the engines' folder excludes and Checkov, which reads a
        # skip-path as a regular expression, crashed on `*.min.js`. The engines get folder names only.
        self.assertFalse([pattern for pattern in exclusions if '*' in pattern])
        result, paths = self.syntax_paths(repo, Path(self.tmp) / 'out')
        self.assertGreater(result['excluded_paths'], 0)
        self.assertTrue({'testdata', 'vendor'} <= set(result['exclusion_reasons']))
        self.assertEqual(paths, {'app.py', 'lib/util.py', 'web/app.js'})

    def test_opting_in_brings_vendored_code_back_but_keeps_declared_exclusions(self):
        repo = self.make_repo()
        (repo / 'eaos.policy.json').write_text(json.dumps({
            'schema_version': 1, 'layers': {'all': ['**']},
            'analysis': {'include_vendored': True, 'exclude': ['lib']}}))
        exclusions = declared_exclusions(repo)
        self.assertNotIn('testdata', exclusions)
        self.assertIn('lib', exclusions)
        _, paths = self.syntax_paths(repo, Path(self.tmp) / 'out')
        self.assertIn('testdata/fixture_a.py', paths)
        self.assertNotIn('lib/util.py', paths)

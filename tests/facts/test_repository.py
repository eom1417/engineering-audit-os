"""The repository read as an engineer reads it (M7.8) and its assistants' context (M7.9): each rule finds what it names,
and a framework's own layout, an output path, an ignored file or EAOS's own block is never a finding."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from eaos.facts.repository import read
from eaos.facts.source import Source


def project(files, tracked=None):
    root = Path(tempfile.mkdtemp())
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    if tracked is not None:
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        subprocess.run(['git', '-C', str(root), 'add', *tracked], check=True)
    return root


def found(root):
    return {(f['rule'], f['path']) for f in read.findings(Source(root), [], root)}


class CraftTests(unittest.TestCase):
    def test_a_crowded_folder_a_prefix_family_a_vague_name_and_two_versions_are_found_and_a_framework_folder_is_not(self):
        files = {f'src/part{n}.py': 'x = 1\n' for n in range(26)}
        files.update({f'src/pipeline_{n}.py': '' for n in ('a', 'b', 'c', 'd')})
        files.update({f'app/page{n}.tsx': '' for n in range(30)})             # Next.js routes: the framework's layout
        files.update({'lib/utils.py': 'x = 1\n' * 301, 'lib/small/helpers.py': 'x = 1\n', 'lib/api.js': '', 'lib/api_v2.js': ''})
        rules = {rule for rule, _ in found(project(files))}
        self.assertEqual(rules, {'crowded-folder', 'prefix-family', 'vague-name', 'version-name'})
        self.assertIn(('crowded-folder', 'src'), found(project(files)))
        self.assertNotIn(('vague-name', 'lib/small/helpers.py'), found(project(files)), 'a short helpers file is fine')

    def test_a_document_naming_a_path_of_the_tree_that_is_gone_is_found_and_an_output_path_is_not(self):
        root = project({'src/app.py': '', 'README.md': 'See `src/app.py`, `src/gone.py` and the report in `technical/RUN.md`.',
                        'CHANGELOG.md': 'Moved `src/old.py`.'})
        self.assertEqual(found(root), {('stale-doc-path', 'README.md')})

    def test_source_in_a_folder_tools_skip_and_a_machine_detail_in_a_published_file_are_found(self):
        machine = 'It ran at /home/alice/work on 10 ' + 'cores.'       # built, so this published file holds none itself
        root = project({'src/target/plan.java': 'class Plan {}', 'notes.md': machine,
                        'local.md': 'see /home/alice/x', 'tools.json': '["(?<![\\\\w.-])/work' + 'space/"]'},
                       tracked=['src', 'notes.md', 'tools.json'])
        self.assertEqual(found(root), {('trap-folder', 'src/target/plan.java'), ('dev-detail', 'notes.md')},
                         'an ignored file is not published, and a line defining the pattern is not a detail')


class ContextTests(unittest.TestCase):
    def test_heavy_repeated_and_done_context_is_measured_and_eaos_own_block_is_not_counted(self):
        rule = 'Every change goes through a branch of its own and is verified first.'
        eaos = '<!-- EAOS: begin (eaos assistant install) -->\n' + 'x' * 40000 + '\n<!-- EAOS: end -->\n'
        root = project({'AGENTS.md': rule + '\n' + '- [x] done\n' * 5, 'CLAUDE.md': '@AGENTS.md\n@docs/more.md\n' + eaos,
                        'docs/more.md': rule + '\n'})
        self.assertEqual({r for r, _ in found(root)}, {'context-repeat', 'context-done'}, "EAOS's block is not the person's weight")
        heavy = project({'AGENTS.md': 'y' * 30000})
        self.assertEqual(found(heavy), {('context-heavy', 'AGENTS.md')})


class CleanTwinTests(unittest.TestCase):
    def test_the_detection_baseline_s_clean_twin_has_no_repository_finding(self):
        root = Path(__file__).resolve().parents[1] / 'fixtures/baseline-clean'
        self.assertEqual(found(root), set())


if __name__ == '__main__':
    unittest.main()

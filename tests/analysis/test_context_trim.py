"""The assistants' context trimmed safely (M8.6): lighter, and every instruction found again in exactly one file."""
from pathlib import Path

from shared_fixture import Workspace

from eaos.analysis.repair import context_trim

RULE = 'Run the whole test suite before every commit, with the coverage gate on.\n'
FILES = {
    'src/app.py': 'x = 1\n',
    'AGENTS.md': ('# Contributing\n\n' + RULE + 'Read `docs/app.py` before changing the entry point.\nI want every answer in Arabic, short.\n\n'
                  '## Plan\n- [x] Build the login page with the session cookie\n- [ ] Add the payments screen\n'),
    'CLAUDE.md': '@AGENTS.md\n\n' + RULE + 'Claude only: keep replies short.\n',
    'GEMINI.md': RULE,
}


class ContextTrimTests(Workspace):
    def project(self, files):
        root = Path(self.tmp) / 'project'
        for name, text in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text, encoding='utf-8')
        return root

    def test_done_items_are_archived_a_repeat_is_said_once_per_reader_a_stale_path_is_fixed_and_personal_lines_go_private(self):
        root = self.project(FILES)
        done = context_trim.apply(root, private_to='DEVELOPING.md')
        self.assertEqual((root / 'AGENTS.md').read_text(), '# Contributing\n\n' + RULE + 'Read `src/app.py` before changing the entry point.\n\n'
                                                            '## Plan\n- [ ] Add the payments screen\n')
        self.assertEqual((root / 'CLAUDE.md').read_text(), '@AGENTS.md\n\nClaude only: keep replies short.\n', 'Claude reads it in AGENTS.md')
        self.assertEqual((root / 'GEMINI.md').read_text(), RULE, 'Gemini reads nothing else: its copy stays')
        self.assertIn('- [x] Build the login page with the session cookie\n', (root / 'archive/CONTEXT-DONE.md').read_text())
        self.assertIn('I want every answer in Arabic, short.\n', (root / 'DEVELOPING.md').read_text())
        self.assertEqual(done['kept_twice'], [(RULE.strip(), ['AGENTS.md', 'GEMINI.md'])])
        self.assertLess(done['tokens_after'], done['tokens_before'])

    def test_without_a_private_place_a_personal_line_is_only_proposed_and_a_lost_instruction_refuses_the_trim(self):
        root = self.project(FILES)
        drawn = context_trim.plan(root)
        self.assertEqual(drawn['personal'], [('AGENTS.md', 'I want every answer in Arabic, short.', 'speaks as one person')])
        self.assertNotIn('DEVELOPING.md', drawn['edits'])
        after = {**drawn['before'], 'AGENTS.md': drawn['edits']['AGENTS.md'].replace('Read `src/app.py`', 'Skim it')}
        self.assertTrue(any(p.startswith('lost: Read `src/app.py`') for p in context_trim.verify(drawn, after)))

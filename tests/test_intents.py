"""The assistant understands plain requests (NS9.T5): the intent table, `eaos do`, the skill it installs, and the
MCP tools. X6 is read from tests/fixtures/intents.json."""
import io
import json
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from eaos import guided, intents

FIXTURE = Path(__file__).resolve().parent / 'fixtures/intents.json'
SETS = ('cases', 'held_out', 'untuned')


def accuracy():
    """{set: (right, total)} of the intent table on every set of requests in the fixture (X6)."""
    data = json.loads(FIXTURE.read_text(encoding='utf-8'))
    found = {}
    for name in SETS:
        right = 0
        for case in data[name]:
            intent, _ = intents.understand(case['say'])
            right += (intent['id'] if intent else None) == case['expect']
        found[name] = (right, len(data[name]))
    return found


class UnderstandingTests(unittest.TestCase):
    def test_requests_in_plain_words_reach_the_right_command(self):
        rows = accuracy()
        right, total = sum(r for r, _ in rows.values()), sum(t for _, t in rows.values())
        self.assertGreaterEqual(right / total, 0.9, rows)
        self.assertGreaterEqual(rows['untuned'][0] / rows['untuned'][1], 0.9, 'what the table was never tuned on')

    def test_arabic_is_read_the_way_people_type_it(self):
        self.assertEqual(intents.normalise('أصلِحْ المشاكلَ'), intents.normalise('اصلح المشاكل'))
        self.assertEqual(intents.understand('افحص جهازي')[0]['id'], 'doctor', 'the longest phrase wins over "افحص"')
        self.assertEqual(intents.understand('وش الناقص')[0]['id'], 'doctor', 'the article does not hide the word')
        self.assertEqual(intents.understand('كيف حالك'), (None, None))

    def test_every_intent_names_a_real_command_in_both_languages(self):
        for intent in intents.catalog():
            self.assertIn(intent['command'][0], guided.COMMANDS, intent['id'])
            self.assertTrue(intent['ar'] and intent['en'] and intent['keywords'], intent['id'])
            self.assertIsInstance(intent['consent'], bool)


class DoTests(unittest.TestCase):
    def run_do(self, words, **patches):
        printed = io.StringIO()
        with redirect_stdout(printed), mock.patch.dict(guided.COMMANDS, patches):
            code = guided.do(Namespace(request=words.split(), project='.', lang='en', yes=False))
        return code, printed.getvalue()

    def test_a_request_runs_the_command_it_means(self):
        called = []
        code, printed = self.run_do('where are we please', status=lambda args: called.append(args.command) or 0)
        self.assertEqual((code, called), (0, ['status']))
        self.assertIn('eaos status', printed)

    def test_a_request_it_does_not_understand_says_how_to_ask(self):
        code, printed = self.run_do('write me a poem')
        self.assertIn('eaos do "check my project"', printed)
        self.assertTrue(printed.rstrip().endswith(guided.LINE))


class AssistantInstallTests(unittest.TestCase):
    def test_both_assistants_learn_eaos_and_only_eaos_part_of_their_files_changes(self):
        from eaos import assistant_setup
        home = Path(tempfile.mkdtemp())
        (home / '.codex').mkdir()
        (home / '.codex/AGENTS.md').write_text('# my own rules\nbe kind\n')
        (home / '.codex/config.toml').write_text('model = "x"\n')
        with mock.patch.object(assistant_setup.shutil, 'which', side_effect=lambda n: f'/usr/bin/{n}'), \
                mock.patch.object(assistant_setup.subprocess, 'run', return_value=mock.Mock(returncode=0)) as run:
            self.assertEqual(assistant_setup.install(home), ['Claude Code', 'Codex'])
            assistant_setup.install(home)
        skill = (home / '.claude/skills/eaos/SKILL.md').read_text()
        self.assertTrue(skill.startswith('---\nname: eaos\ndescription: '))
        agents = (home / '.codex/AGENTS.md').read_text()
        self.assertTrue(agents.startswith('# my own rules\nbe kind\n'))
        self.assertEqual(agents.count(assistant_setup.BEGIN), 1, 'installing twice replaces, never repeats')
        self.assertIn('Say yes for them', agents)
        config = (home / '.codex/config.toml').read_text()
        self.assertEqual((config.count('[mcp_servers.eaos]'), config.startswith('model = "x"')), (1, True))
        self.assertFalse(any('mcp' in c.args[0] and 'add' in c.args[0] for c in run.call_args_list), 'already registered: not added twice')


if __name__ == '__main__':
    unittest.main()

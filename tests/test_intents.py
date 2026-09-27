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
        self.assertIn('Never add `--yes` on your own', agents)
        config = (home / '.codex/config.toml').read_text()
        self.assertEqual((config.count('[mcp_servers.eaos]'), config.startswith('model = "x"')), (1, True))
        self.assertFalse(any('mcp' in c.args[0] and 'add' in c.args[0] for c in run.call_args_list), 'already registered: not added twice')


class McpTests(unittest.TestCase):
    def talk(self, *messages):
        from eaos import mcp_server
        out = io.StringIO()
        mcp_server.main(io.StringIO(''.join(json.dumps(m) + '\n' for m in messages)), out)
        return [json.loads(line) for line in out.getvalue().splitlines()]

    def test_the_tools_are_listed_and_a_request_comes_back_as_eaos_said_it(self):
        from eaos import mcp_server
        with mock.patch.object(mcp_server, 'request', return_value='job-1 finished.\n✅ What happened: done') as request:
            replies = self.talk({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}},
                                {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
                                {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'eaos_request',
                                                                                             'arguments': {'request': 'where are we'}}})
        self.assertEqual([r['id'] for r in replies], [1, 2, 3], 'a notification gets no answer')
        self.assertEqual({t['name'] for t in replies[1]['result']['tools']}, {'eaos_request', 'eaos_job'})
        self.assertIn('Never set agreed=true on your own', replies[1]['result']['tools'][0]['description'])
        self.assertEqual(replies[2]['result']['content'][0]['text'], 'job-1 finished.\n✅ What happened: done')
        request.assert_called_once_with({'request': 'where are we'})

    def test_agreement_is_passed_only_when_the_assistant_says_the_person_agreed(self):
        from eaos import mcp_server
        seen = []
        with mock.patch.object(mcp_server.subprocess, 'Popen', side_effect=lambda argv, **k: seen.append(argv) or mock.Mock(poll=lambda: 0)):
            mcp_server.request({'request': 'continue'})
            mcp_server.request({'request': 'continue', 'agreed': True})
        self.assertNotIn('--yes', seen[0])
        self.assertEqual(seen[1][-1], '--yes')


if __name__ == '__main__':
    unittest.main()

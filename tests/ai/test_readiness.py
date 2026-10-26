"""Which assistant EAOS uses (eaos/ai), and its readiness probe (eaos/ai/assistant/readiness.py) against fake `claude`
and `codex` commands that behave like the real ones in each state: ready, signed out, the sign-in expired, a usage limit,
silent, not installed."""
import json
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from eaos.ai.assistant import readiness

CLAUDE = r'''#!/bin/sh
echo "claude $*" >> "$FAKE_LOG"
[ -n "$FAKE_ENV_OUT" ] && echo "$CLAUDE_CONFIG_DIR" > "$FAKE_ENV_OUT"
case "$1" in
  --version) [ "$FAKE_MODE" = broken ] && exit 3; echo "9.9.9 (Claude Code)"; exit 0;;
  auth) if [ "$FAKE_MODE" = signed_out ]; then echo '{"loggedIn": false}'; exit 1; fi; echo '{"loggedIn": true}'; exit 0;;
esac
case "$FAKE_MODE" in
  ready) echo '{"type":"result","is_error":false,"result":"ready"}';;
  quiet) sleep 5;;
  call_signed_out) echo '{"type":"result","is_error":true,"result":"Not logged in · Please run /login"}'; exit 1;;
  limit) echo '{"type":"result","is_error":true,"result":"Claude AI usage limit reached"}'; exit 1;;
  session_limit) echo "You've hit your session limit · resets 7:10pm (UTC)"; exit 1;;
  leaky) echo "token sk-ant-SECRET-123 rejected: something odd" >&2; exit 1;;
esac
'''

CODEX = r'''#!/bin/sh
echo "codex $*" >> "$FAKE_LOG"
case "$1" in
  --version) echo "codex-cli 0.1.0"; exit 0;;
  login) if [ "$FAKE_MODE" = signed_out ]; then echo "Not logged in"; exit 1; fi; echo "Logged in using ChatGPT"; exit 0;;
esac
out=""
while [ $# -gt 0 ]; do [ "$1" = "-o" ] && out="$2"; shift; done
cat > /dev/null
case "$FAKE_MODE" in
  ready) echo ready > "$out";;
  expired) echo "ERROR codex_login::auth::manager: Failed to refresh token: Your access token could not be refreshed because your refresh token was already used. Please log out and sign in again." >&2; exit 1;;
  quiet) sleep 5;;
esac
'''


class Probe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.bin = root / 'bin'
        self.bin.mkdir()
        self.log = root / 'calls.log'
        self.log.touch()
        for name, body in (('claude', CLAUDE), ('codex', CODEX)):
            path = self.bin / name
            path.write_text(body, encoding='utf-8')
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
        env = mock.patch.dict(os.environ, {'PATH': f'{self.bin}:/usr/bin:/bin', 'EAOS_HOME': str(root / 'home'),
                                           'FAKE_LOG': str(self.log), 'FAKE_MODE': 'ready', 'CLAUDE_CONFIG_DIR': str(root / 'cfg')})
        env.start()
        self.addCleanup(env.stop)

    def mode(self, mode):
        os.environ['FAKE_MODE'] = mode

    def calls(self):
        return [line for line in self.log.read_text(encoding='utf-8').splitlines() if line]

    def test_a_ready_assistant_answers_and_each_state_that_is_not_ready_is_named_with_what_to_do(self):
        row = readiness.probe('claude', fresh=True)
        self.assertEqual((row['ready'], row['installed'], row['version'], row['code']), (True, True, '9.9.9 (Claude Code)', 'claude_ready'))
        self.assertTrue(any('-p' in call and "--tools" in call for call in self.calls()), 'a real one-word call was made')
        self.assertTrue(readiness.probe('codex', fresh=True)['ready'])
        self.log.write_text('')
        (self.bin / 'codex').unlink()
        which = readiness.shutil.which      # a computer may have a real codex in /usr/bin, which is on this PATH
        with mock.patch.object(readiness.shutil, 'which', side_effect=lambda name: None if name == 'codex' else which(name)):
            row = readiness.probe('codex', fresh=True)
        self.assertEqual((row['installed'], row['ready'], row['code']), (False, False, 'codex_not_installed'))
        self.assertIn('github.com/openai/codex', row['reason']['en'])
        self.assertTrue(row['reason']['ar'])
        (self.bin / 'codex').write_text(CODEX, encoding='utf-8')
        (self.bin / 'codex').chmod(0o755)
        self.mode('signed_out')
        row = readiness.probe('claude', fresh=True)
        self.assertEqual(row['code'], 'claude_not_signed_in')
        self.assertIn('Run `claude` once', row['reason']['en'])
        self.assertFalse(any(' -p' in call for call in self.calls()), 'no call is made once the status says signed out')
        self.assertEqual(readiness.probe('codex', fresh=True)['code'], 'codex_not_signed_in')
        for mode, name, code in (('call_signed_out', 'claude', 'claude_not_signed_in'), ('broken', 'claude', 'claude_not_working'),
                                 ('limit', 'claude', 'claude_limit'), ('expired', 'codex', 'codex_sign_in_expired')):
            with self.subTest(mode=mode):
                self.mode(mode)
                row = readiness.probe(name, fresh=True)
                self.assertEqual((row['installed'], row['ready'], row['code']), (True, False, code))
        self.assertIn('codex login', row['reason']['en'], 'a used refresh token: not ready though its status says logged in')
        self.mode('session_limit')     # Claude Code's own words on a spent session (2026-10-18), plain text, not JSON
        row = readiness.probe('claude', fresh=True)
        self.assertEqual((row['code'], row.get('resets')), ('claude_limit', '7:10pm (UTC)'))
        self.assertIn('7:10pm (UTC)', row['reason']['ar'], 'the person reads when it comes back, not a vague error')

    def test_no_answer_in_time_and_both_are_asked_side_by_side(self):
        self.mode('quiet')
        began = time.monotonic()
        row = readiness.probe('claude', fresh=True, timeout=1)
        self.assertEqual(row['code'], 'claude_no_answer')
        self.assertLess(time.monotonic() - began, 4.5)
        began = time.monotonic()
        rows = readiness.probe_all(fresh=True, timeout=1)
        self.assertEqual([row['id'] for row in rows], ['claude', 'codex'])
        self.assertLess(time.monotonic() - began, 4.5, 'two silent assistants cost one timeout, not two')

    def test_the_answer_is_kept_a_few_minutes_a_not_ready_one_less_and_fresh_asks_again(self):
        readiness.probe('claude', fresh=True)
        made = len(self.calls())
        again = readiness.probe('claude')
        self.assertTrue(again['cached'])
        self.assertEqual(len(self.calls()), made, 'the cache answered')
        self.assertFalse(readiness.probe('claude', fresh=True)['cached'])
        self.assertGreater(len(self.calls()), made)
        os.environ['CLAUDE_CONFIG_DIR'] = str(Path(self.tmp.name) / 'other')
        import fcntl
        import threading
        with open(readiness._cache_file().with_suffix('.lock'), 'a') as held:
            fcntl.flock(held, fcntl.LOCK_EX)                    # another program (another project's check) writes now
            answers = []
            asked = threading.Thread(target=lambda: answers.append(readiness.probe('claude')))
            asked.start()
            asked.join(2)
            self.assertEqual(len(readiness._read_cache()), 1, 'it waits for the other writer instead of overwriting it')
        asked.join(10)
        self.assertFalse(answers[0]['cached'], 'another sign-in place is another assistant')
        saved = json.loads((Path(os.environ['EAOS_HOME']) / 'assistants/readiness.json').read_text(encoding='utf-8'))
        with mock.patch.object(readiness.time, 'time', return_value=time.time() + readiness.KEEP_READY + 1):
            self.assertIsNone(readiness.cached('claude'))
        self.assertEqual(len(saved), 2)
        self.mode('signed_out')
        readiness.probe('claude', fresh=True)
        with mock.patch.object(readiness.time, 'time', return_value=time.time() + readiness.KEEP_NOT_READY + 1):
            self.assertIsNone(readiness.cached('claude'))
        self.assertLess(readiness.KEEP_NOT_READY, readiness.KEEP_READY)

    def test_the_raw_output_never_leaves_the_module_and_the_environment_is_inherited_never_set(self):
        self.mode('leaky')
        row = readiness.probe('claude', fresh=True)
        self.assertEqual(row['code'], 'claude_failed')
        cache = (Path(os.environ['EAOS_HOME']) / 'assistants/readiness.json').read_text(encoding='utf-8')
        for text in (json.dumps(row), cache):
            self.assertNotIn('SECRET', text)
            self.assertNotIn('something odd', text)
        self.mode('ready')
        seen = Path(self.tmp.name) / 'env.txt'
        os.environ['FAKE_ENV_OUT'] = str(seen)
        before = dict(os.environ)
        readiness.probe('claude', fresh=True)
        self.assertEqual(seen.read_text(encoding='utf-8').strip(), os.environ['CLAUDE_CONFIG_DIR'])
        self.assertEqual(dict(os.environ), before)

    def test_every_code_has_words_in_both_languages_and_an_answer_is_classified_by_what_it_says(self):
        for name in readiness.NAMES:
            for problem in ('ready', 'not_installed', 'not_working', 'not_signed_in', 'sign_in_expired', 'limit', 'no_answer', 'failed'):
                found = readiness.words(f'{name}_{problem}')
                self.assertTrue(found and found['ar'] and found['en'], f'{name}_{problem}')
                self.assertIn(readiness.NAMES[name], found['en'])
        self.assertTrue(readiness.words('ai_declined'))
        self.assertEqual(readiness.classify('Your refresh token was already used'), 'sign_in_expired')
        self.assertEqual(readiness.classify('Not logged in · Please run /login'), 'not_signed_in')
        self.assertEqual(readiness.classify('429 Too Many Requests'), 'limit')
        self.assertEqual(readiness.classify("You've hit your weekly limit"), 'limit')
        self.assertIsNone(readiness.resets_at('segfault'))
        self.assertEqual(readiness.classify('segfault'), 'failed')
        self.assertFalse(readiness.NoAssistant('ai_declined', 'x'))
        with self.assertRaises(ValueError): readiness.probe('gemini')


class Choice(unittest.TestCase):
    def test_the_installed_assistant_is_used_and_none_means_none(self):
        import eaos.ai as assistants
        with mock.patch.object(assistants.shutil, 'which', side_effect=lambda n: '/bin/codex' if n == 'codex' else None), \
                mock.patch.dict(os.environ, {'EAOS_ASSISTANT': ''}):
            name, provider = assistants.provider()
        self.assertEqual(name, 'codex')
        self.assertIn('eaos.ai.assistant.codex_adapter', provider.config['argv'])
        with mock.patch.object(assistants.shutil, 'which', return_value=None):
            self.assertEqual(assistants.provider(), (None, None))
        with mock.patch.object(assistants.shutil, 'which', return_value='/bin/x'), mock.patch.dict(os.environ, {'EAOS_ASSISTANT': 'none'}):
            self.assertEqual(assistants.provider(), (None, None), '`none` turns every assistant off')

    def test_codex_reads_only_what_eaos_sends_changes_nothing_and_needs_no_key(self):
        from eaos.ai.assistant import codex_adapter

        def fake(argv, **kwargs):
            Path(argv[argv.index('-o') + 1]).write_text('{"action": "final"}')
            return mock.Mock(returncode=0)
        with mock.patch.object(codex_adapter.subprocess, 'run', side_effect=fake) as run:
            self.assertEqual(codex_adapter.call([{'role': 'user', 'content': 'hi'}]), {'action': 'final'})
        argv, kwargs = run.call_args.args[0], run.call_args.kwargs
        self.assertEqual(argv[argv.index('-s') + 1], 'read-only')
        for flag in ('--ephemeral', '--ignore-rules', '--ignore-user-config', '--skip-git-repo-check'):
            self.assertIn(flag, argv)
        self.assertNotIn('env', kwargs)


if __name__ == '__main__':
    unittest.main()

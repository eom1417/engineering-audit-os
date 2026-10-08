"""A stand-in for `claude -p --output-format stream-json` in tests/test_studio_actions.py.

FAKE_MODE (environment) picks what it does: `replay` prints claude-stream.jsonl (a real recorded run, shortened);
`question` asks one eaos-question and, once resumed, finishes; `slow` prints a step every 0.2 s for FAKE_SECONDS;
`fail` ends with an error result; `crash` exits 3 with nothing on stdout. `--version` and `auth status` answer as
the real CLI does. Every argv it got is appended to FAKE_ARGV when set.
"""
import json
import os
import sys
import time
from pathlib import Path

argv = sys.argv[1:]
if os.environ.get('FAKE_ARGV'):
    with open(os.environ['FAKE_ARGV'], 'a', encoding='utf-8') as out: out.write(json.dumps(argv) + '\n')
if argv[:1] == ['--version']:
    print('9.9.9 (Claude Code)'); sys.exit(0)
if argv[:2] == ['auth', 'status']:
    print(json.dumps({'loggedIn': os.environ.get('FAKE_LOGGED_IN', '1') == '1'})); sys.exit(0)


def say(event):
    print(json.dumps(event, ensure_ascii=False), flush=True)


mode = os.environ.get('FAKE_MODE', 'question')
resumed = '--resume' in argv
say({'type': 'system', 'subtype': 'init', 'session_id': 'fake-session'})
if mode == 'replay':
    for line in (Path(__file__).parent / 'claude-stream.jsonl').read_text(encoding='utf-8').splitlines()[1:]:
        print(line, flush=True)
elif mode == 'crash':
    sys.stderr.write('something broke\n'); sys.exit(3)
elif mode == 'fail':
    say({'type': 'result', 'subtype': 'error_during_execution', 'is_error': True, 'result': 'the model is not available', 'session_id': 'fake-session'})
elif mode == 'slow':
    for index in range(int(float(os.environ.get('FAKE_SECONDS', '3')) / 0.2)):
        say({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': f'working {index}'}]}})
        time.sleep(0.2)
    say({'type': 'result', 'subtype': 'success', 'is_error': False, 'result': 'finished slowly', 'session_id': 'fake-session'})
elif not resumed:
    say({'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 't1', 'name': 'mcp__eaos__fix_edit',
                                                       'input': {'card': 'TASK-001', 'edits': [{'path': 'src/a.py', 'find': 'x = 1', 'replace': 'x = 2'}]}}]}})
    say({'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 't1',
                                                  'content': [{'type': 'text', 'text': json.dumps({'result': json.dumps({'kept': True, 'card': 'TASK-001'})})}]}]}})
    text = ('One choice for you.\n```eaos-question\n' + json.dumps({'text': {'en': 'Keep going?', 'ar': 'أكمل؟'},
            'options': [{'id': 'yes', 'label': {'en': 'Yes', 'ar': 'نعم'}}, {'id': 'no', 'label': {'en': 'No', 'ar': 'لا'}}],
            'recommendation': 'yes'}, ensure_ascii=False) + '\n```')
    say({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': text}]}})
    say({'type': 'result', 'subtype': 'success', 'is_error': False, 'result': text, 'session_id': 'fake-session'})
else:
    say({'type': 'result', 'subtype': 'success', 'is_error': False, 'result': 'All done.', 'session_id': 'fake-session'})

"""A command-kind model adapter over the Claude Code CLI already signed in on this machine.

provider.json:
    {"kind": "command", "argv": ["<python>", "-m", "eaos.runtime.claude_adapter"], "timeout_seconds": 600}

The provider (eaos/runtime/provider.py) writes {"messages": [...]} to stdin and reads one JSON object from stdout.
This adapter hands the conversation to `claude -p` as a plain model: every tool is turned off (--tools ""), the
default system prompt is replaced by the conversation's own, and no session is kept. So the model reads only what
EAOS sends and edits nothing itself; every change it proposes goes back through `eaos implement`'s checks.

No key is read or written here: the CLI uses the sign-in it already has. Each call's reported cost is appended
to $EAOS_MODEL_USAGE when that names a file, so what a run spent is on record.
"""
import json
import os
import re
import subprocess
import sys

ANSWER = 'Answer with exactly one JSON object and nothing else: no prose, no code fence.'


def render(messages):
    """(system prompt, conversation) from chat messages: system turns join the system prompt."""
    system = [m['content'] for m in messages if m.get('role') == 'system']
    turns = [f"### {m.get('role', 'user').upper()}\n{m.get('content', '')}" for m in messages if m.get('role') != 'system']
    return '\n\n'.join(system + [ANSWER]), '\n\n'.join(turns)


def parse(text):
    """The one JSON object in the model's reply; a fence or a sentence around it is tolerated, nothing else."""
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
    try: value = json.loads(text)
    except ValueError:
        start, end = text.find('{'), text.rfind('}')
        if start < 0 or end <= start: raise ValueError('the model returned no JSON object')
        value = json.loads(text[start:end + 1])
    if not isinstance(value, dict): raise ValueError('the model returned JSON that is not an object')
    return value


def call(messages, timeout=600):
    system, conversation = render(messages)
    argv = ['claude', '-p', '--tools', '', '--no-session-persistence', '--output-format', 'json', '--system-prompt', system]
    if os.environ.get('EAOS_CLAUDE_MODEL'): argv += ['--model', os.environ['EAOS_CLAUDE_MODEL']]
    done = subprocess.run(argv, input=conversation, capture_output=True, text=True, timeout=timeout)
    if done.returncode != 0: raise RuntimeError(f'claude exited {done.returncode}')
    envelope = json.loads(done.stdout)
    if envelope.get('is_error'): raise RuntimeError('claude reported an error: ' + str(envelope.get('result'))[:200])
    usage = os.environ.get('EAOS_MODEL_USAGE')
    if usage:
        with open(usage, 'a', encoding='utf-8') as log:
            log.write(json.dumps({'cost_usd': envelope.get('total_cost_usd'), 'models': list(envelope.get('modelUsage') or {}),
                                  'duration_ms': envelope.get('duration_ms')}) + '\n')
    return parse(envelope.get('result') or '')


def main():
    request = json.loads(sys.stdin.read())
    try: answer = call(request['messages'])
    except Exception as problem:   # the provider sees a failed exit; the reason goes to stderr, never to stdout
        print(f'claude adapter: {problem}', file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(answer, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

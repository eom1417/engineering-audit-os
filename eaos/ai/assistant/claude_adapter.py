"""A command-kind model adapter over the Claude Code CLI already signed in on this machine.

provider.json:
    {"kind": "command", "argv": ["<python>", "-m", "eaos.ai.assistant.claude_adapter"]}

The provider (eaos/ai/assistant/command.py) writes {"messages": [...]} to stdin and reads one JSON object from stdout.
This adapter hands the conversation to `claude -p` as a plain model: every tool is turned off (--tools ""), the
default system prompt is replaced by the conversation's own, and no session is kept. So the model reads only what
EAOS sends and edits nothing itself; every change it proposes goes back through `eaos implement`'s checks. Its stream
is copied to stderr as it comes, so the provider sees the work go on, however long it takes.

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


def stream(argv, conversation, env=None):
    """Run `claude` on the conversation, copying its stream to stderr as it comes; return the stream's result event."""
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- the assistant's CLI as its adapter builds it, a list argv, no shell
    with process.stdin: process.stdin.write(conversation)
    result = {}
    for line in process.stdout:
        sys.stderr.write(line)
        event = json.loads(line) if line.startswith('{') else None
        if isinstance(event, dict) and event.get('type') == 'result': result = event
    if process.wait() != 0: raise RuntimeError(f'claude exited {process.returncode}')
    return result


def call(messages, small=False, reads=None, deep=False):
    """`small`: the work is plain (a translation): the smallest model does it as well for less, and without thinking,
    which was 77% of a translation's output (EAOS's own check, 2026-10-14) and 20 times its time. `reads`: a folder it
    reads and searches itself, nothing else (the views and the sign-in once saw only excerpts, and missed the program
    chooser); `deep`: the longest thinking."""
    system, conversation = render(messages)
    tools = ['--tools', 'Read,Grep,Glob', '--add-dir', reads, '--permission-mode', 'dontAsk'] if reads else ['--tools', '']
    argv = ['claude', '-p', *tools, '--no-session-persistence', '--output-format', 'stream-json', '--verbose',
            '--include-partial-messages', '--system-prompt', system]
    model = 'haiku' if small else os.environ.get('EAOS_CLAUDE_MODEL')
    if model: argv += ['--model', model]
    thinking = '0' if small else '31999' if deep else None
    envelope = stream(argv, conversation, {**os.environ, 'MAX_THINKING_TOKENS': thinking} if thinking else None)
    if envelope.get('is_error'): raise RuntimeError('claude reported an error: ' + str(envelope.get('result'))[:200])
    from ...core.system.usage import from_stream
    record(from_stream([json.dumps(envelope)]))
    return parse(envelope.get('result') or '')


def record(row):
    """One call's use (eaos/core/system/usage.py) appended to $EAOS_MODEL_USAGE when that names a file, under $EAOS_MODEL_STAGE."""
    usage = os.environ.get('EAOS_MODEL_USAGE')
    if usage and row:
        with open(usage, 'a', encoding='utf-8') as log: log.write(json.dumps({**row, 'stage': os.environ.get('EAOS_MODEL_STAGE')}) + '\n')


def serve(call, name):
    """An adapter's process: the request on stdin, one JSON object on stdout, or exit 1 with the reason on stderr."""
    request = json.loads(sys.stdin.read())
    try: answer = call(request['messages'], small=bool(request.get('small')), reads=request.get('reads'), deep=bool(request.get('deep')))
    except Exception as problem:   # the provider sees a failed exit; the reason goes to stderr, never to stdout
        print(f'{name} adapter: {problem}', file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(answer, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(serve(call, 'claude'))

"""A command-kind model adapter over the Codex CLI already signed in on this machine.

The same contract as eaos/runtime/claude_adapter.py: {"messages": [...]} on stdin, one JSON object on stdout.
Codex runs `exec` in a read-only sandbox, in an empty folder, without keeping the session (--ephemeral), and
without the user's own rules or config (--ignore-rules --ignore-user-config), so it reads only what EAOS sends
and changes nothing itself. No key is read or written: the CLI uses the sign-in it has. $EAOS_CODEX_MODEL
picks the model; each call is appended to $EAOS_MODEL_USAGE when that names a file.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

from .claude_adapter import ANSWER, parse, render


def call(messages, timeout=600):
    system, conversation = render(messages)
    with tempfile.TemporaryDirectory(prefix='eaos-codex-') as empty:
        answer = os.path.join(empty, 'answer.txt')
        argv = ['codex', 'exec', '--skip-git-repo-check', '--ephemeral', '--ignore-rules', '--ignore-user-config',
                '-s', 'read-only', '--color', 'never', '-C', empty, '-o', answer]
        if os.environ.get('EAOS_CODEX_MODEL'): argv += ['-m', os.environ['EAOS_CODEX_MODEL']]
        began = time.monotonic()
        done = subprocess.run(argv + ['-'], input=f'{system}\n\n{conversation}\n\n{ANSWER}', capture_output=True,
                              text=True, timeout=timeout, cwd=empty)
        if done.returncode != 0: raise RuntimeError(f'codex exited {done.returncode}')
        text = open(answer, encoding='utf-8').read() if os.path.exists(answer) else ''
    usage = os.environ.get('EAOS_MODEL_USAGE')
    if usage:
        with open(usage, 'a', encoding='utf-8') as log:
            log.write(json.dumps({'assistant': 'codex', 'duration_ms': round((time.monotonic() - began) * 1000)}) + '\n')
    return parse(text)


def main():
    request = json.loads(sys.stdin.read())
    try: answer = call(request['messages'])
    except Exception as problem:   # the provider sees a failed exit; the reason goes to stderr, never to stdout
        print(f'codex adapter: {problem}', file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(answer, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

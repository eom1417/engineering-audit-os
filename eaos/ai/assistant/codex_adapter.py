"""A command-kind model adapter over the Codex CLI already signed in on this machine.

The same contract as eaos/ai/assistant/claude_adapter.py: {"messages": [...]} on stdin, one JSON object on stdout.
Codex runs `exec` in a read-only sandbox, in an empty folder (or the one it is given to read), without keeping the session (--ephemeral), and
without the user's own rules or config (--ignore-rules --ignore-user-config), so it reads only what EAOS sends
and changes nothing itself; its progress goes to stderr, so the provider sees the work go on. No key is read or
written: the CLI uses the sign-in it has. $EAOS_CODEX_MODEL picks the model; each call is appended to
$EAOS_MODEL_USAGE when that names a file.
"""
import os
import subprocess
import sys
import tempfile
import time

from .claude_adapter import ANSWER, parse, record, render, serve


def call(messages, small=False, reads=None, deep=False):   # the model signed in with; `reads`: the folder it reads
    system, conversation = render(messages)
    with tempfile.TemporaryDirectory(prefix='eaos-codex-') as empty:
        answer = os.path.join(empty, 'answer.txt')
        argv = ['codex', 'exec', '--skip-git-repo-check', '--ephemeral', '--ignore-rules', '--ignore-user-config',
                '-s', 'read-only', '--color', 'never', '-C', reads or empty, '-o', answer]
        if os.environ.get('EAOS_CODEX_MODEL'): argv += ['-m', os.environ['EAOS_CODEX_MODEL']]
        if small or deep: argv += ['-c', f'model_reasoning_effort="{"low" if small else "high"}"']
        began = time.monotonic()
        done = subprocess.run(argv + ['-'], input=f'{system}\n\n{conversation}\n\n{ANSWER}', stdout=sys.stderr, stderr=sys.stderr,
                              text=True, cwd=reads or empty)
        if done.returncode != 0: raise RuntimeError(f'codex exited {done.returncode}')
        text = open(answer, encoding='utf-8').read() if os.path.exists(answer) else ''
    from ...core.system.usage import row
    record(row({}, duration_ms=round((time.monotonic() - began) * 1000)))     # codex exec -o leaves no token count
    return parse(text)


if __name__ == '__main__':
    raise SystemExit(serve(call, 'codex'))

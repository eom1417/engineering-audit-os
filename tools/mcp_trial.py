"""A trial of the main way in (docs/MCP.md, X9): a real assistant, Claude Code, drives EAOS alone.

    python tools/mcp_trial.py chief-ops /workspace/owner-projects/chief-ops

The person's part is played by two messages and nothing else: a plain request in Arabic, then «نعم» to the
one question EAOS has the assistant ask. Everything between is the assistant with the EAOS tools and its own
read-only tools (Read, Grep, Glob): no Bash, no Edit, no Write, so every change goes through EAOS's gates and
no file is written by hand. When the assistant stops for anything else, the trial says «كمّل» and counts it as
one more turn from the person (X9 allows two).

Writes $EAOS_MEASURE/mcp/<name>/trial.json:
  {project, person_turns, messages[], delivered, branch, kept, failed, manual_files, minutes, tool_calls{name: n},
   final_answer, session}
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEASURE = Path(os.environ.get('EAOS_MEASURE', '/workspace/eaos-measure')) / 'mcp'
REQUEST = 'افحص مشروعي بـ EAOS وأصلح مشاكله'
YES = 'نعم، موافق'
GO_ON = 'كمّل'
MAX_TURNS = 4


def claude(prompt, where, config, session=None):
    argv = ['claude', '-p', prompt, '--mcp-config', str(config), '--strict-mcp-config', '--output-format', 'stream-json',
            '--verbose', '--allowedTools', 'mcp__eaos', 'Read', 'Grep', 'Glob',
            '--disallowedTools', 'Bash', 'Edit', 'Write', 'NotebookEdit', 'WebFetch', 'WebSearch']
    if session: argv += ['--resume', session]
    done = subprocess.run(argv, cwd=where, capture_output=True, text=True, timeout=6 * 3600)
    events = [json.loads(line) for line in done.stdout.splitlines() if line.startswith('{')]
    return events, done.stderr[-2000:]


def main(name, source):
    out = MEASURE / name
    subprocess.run(['rm', '-rf', str(out)])
    home, where = out / 'home', out / 'project'
    home.mkdir(parents=True)
    subprocess.run(['git', 'clone', '--quiet', str(source), str(where)], check=True)
    config = out / 'mcp.json'
    config.write_text(json.dumps({'mcpServers': {'eaos': {
        'command': sys.executable, 'args': ['-m', 'eaos', 'mcp'],
        'env': {'EAOS_HOME': str(home), 'PYTHONPATH': str(ROOT), 'EAOS_MODEL_USAGE': str(out / 'model-usage.jsonl')}}}}))
    os.environ['EAOS_HOME'] = str(home)
    sys.path.insert(0, str(ROOT))
    from eaos import guided

    began, session, messages, calls, answer = time.monotonic(), None, [], {}, ''
    prompt = REQUEST
    while len(messages) < MAX_TURNS:
        messages.append(prompt)
        events, errors = claude(prompt, where, config, session)
        for event in events:
            session = event.get('session_id') or session
            for block in ((event.get('message') or {}).get('content') or []) if event.get('type') == 'assistant' else []:
                if block.get('type') == 'tool_use': calls[block['name']] = calls.get(block['name'], 0) + 1
            if event.get('type') == 'result': answer = event.get('result') or errors
        (out / f'turn-{len(messages)}.jsonl').write_text('\n'.join(json.dumps(e, ensure_ascii=False) for e in events) + '\n')
        state = guided.load(where) or {}
        if any(w.get('status') == 'applied' for w in state.get('waves') or []): break
        prompt = YES if not (state.get('consent') or {}).get('run_and_fix') else GO_ON
    state = guided.load(where) or {}
    wave = next((w for w in state.get('waves') or [] if w.get('status') == 'applied'), None)
    branch_there = bool(wave) and not subprocess.run(['git', '-C', str(where), 'rev-parse', '--verify', '--quiet', wave['branch']],
                                                     capture_output=True).returncode
    changed = subprocess.run(['git', '-C', str(where), 'status', '--porcelain'], capture_output=True, text=True).stdout.split('\n')
    trial = {'project': name, 'person_turns': len(messages), 'messages': messages, 'delivered': branch_there,
             'branch': wave['branch'] if wave else None, 'kept': wave['kept'] if wave else [], 'failed': wave['failed'] if wave else {},
             'manual_files': len([line for line in changed if line.strip()]),
             'minutes': round((time.monotonic() - began) / 60, 1), 'tool_calls': calls, 'final_answer': answer[-4000:], 'session': session}
    (out / 'trial.json').write_text(json.dumps(trial, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: trial[k] for k in ('project', 'person_turns', 'delivered', 'branch', 'minutes')}, ensure_ascii=False))
    return 0 if trial['delivered'] else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1], sys.argv[2]))

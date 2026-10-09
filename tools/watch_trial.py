"""A trial of the live map's way in (PLAN-v2 7.3, phase 3): a real headless Claude Code session asks EAOS to check a
project, and the MCP `audit` answer carries `watch`, the live map's address, which the started Studio serves.

    python tools/watch_trial.py RendaPerene ~/.eaos/dev/corpus/RendaPerene

The person's part is one plain request in Arabic; the assistant has the EAOS tools and Read only. After the session,
the trial reads the address the `audit` answer gave, asks that Studio for /api/progress with the address's own token,
and stops the Studio it started.

Writes $EAOS_MEASURE/live-scan-map/watch.json:
  {project, session, transcript, audit_answers, watch, progress: {status, check_state, check_run, stages, flows},
   final_answer, minutes}
"""
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import dev_paths
from mcp_trial import claude

ROOT = Path(__file__).resolve().parents[1]
OUT = dev_paths.MEASURE / 'live-scan-map'
REQUEST = 'افحص مشروعي بـ EAOS، وقل لي وين أتابع الفحص وهو شغّال'
ADDRESS = re.compile(r'^http://127\.0\.0\.1:(\d+)/#/scan\?token=([A-Za-z0-9_-]{16,128})$')


def blocks(events, kind):
    """The content blocks of the transcript's messages of one kind (`assistant`, `user`)."""
    return [block for event in events if event.get('type') == kind
            for block in (event.get('message') or {}).get('content') or [] if isinstance(block, dict)]


def audit_answers(events):
    """The JSON answers of every `audit` call in a stream-json transcript."""
    calls = {b['id'] for b in blocks(events, 'assistant') if b.get('type') == 'tool_use' and b['name'].endswith('__audit')}
    answers = []
    for block in blocks(events, 'user'):
        if block.get('tool_use_id') not in calls: continue
        content = block.get('content')
        answers.append(answer_of(content if isinstance(content, str) else ''.join(part.get('text', '') for part in content or [])))
    return answers


def answer_of(text):
    """A tool's JSON answer; Claude Code may hand it over wrapped as {"result": "<the JSON text>"}."""
    try: answer = json.loads(text)
    except ValueError: return {'unreadable': text[:500]}
    return answer_of(answer['result']) if isinstance(answer, dict) and isinstance(answer.get('result'), str) else answer


def read_progress(watch):
    """What the Studio at the `watch` address answers on /api/progress, with the address's own token."""
    found = ADDRESS.match(watch or '')
    if not found: return {'status': None}
    port, token = found.groups()
    request = urllib.request.Request(f'http://127.0.0.1:{port}/api/progress', headers={'X-EAOS-Token': token})
    with urllib.request.urlopen(request, timeout=10) as response:
        body = json.loads(response.read())
    check = body['flows']['check']
    return {'status': response.status, 'check_state': check['state'], 'check_run': check['run'],
            'stages': len(check['stages']), 'flows': sorted(body['flows'])}


def run_session(source, out):
    """A fresh clone of the project and one headless Claude Code session in it, its transcript kept: (where, events,
    errors)."""
    subprocess.run(['rm', '-rf', str(out)])
    home, where = out / 'home', out / 'project'
    home.mkdir(parents=True)
    subprocess.run(['git', 'clone', '--quiet', str(source), str(where)], check=True)
    config = out / 'mcp.json'
    config.write_text(json.dumps({'mcpServers': {'eaos': {
        'command': sys.executable, 'args': ['-m', 'eaos', 'mcp'],
        'env': {'EAOS_HOME': str(home), 'PYTHONPATH': str(ROOT), 'PYTHONSAFEPATH': '1'}}}}))
    os.environ['EAOS_HOME'] = str(home)
    events, errors = claude(REQUEST, where, config)
    (out / 'transcript.jsonl').write_text(''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in events), encoding='utf-8')
    return where, events, errors


def ending(events):
    """(session id, final answer) of a stream-json transcript."""
    session = next((e.get('session_id') for e in events if e.get('session_id')), None)
    return session, next((e.get('result') for e in reversed(events) if e.get('type') == 'result'), '')


def main(name, source):
    out, began = OUT / 'watch', time.monotonic()
    where, events, errors = run_session(source, out)
    sys.path.insert(0, str(ROOT))
    from eaos import agent_tools
    from eaos.api import launch
    answers = audit_answers(events)
    watch = next((a['watch'] for a in answers if a.get('watch')), None)
    record = launch.running(agent_tools.project_state(str(where)))
    try: progress = read_progress(watch)
    finally:
        if record: os.kill(record['pid'], signal.SIGTERM)
    session, final = ending(events)
    result = {'project': name, 'session': session, 'transcript': str(out / 'transcript.jsonl'), 'errors': errors,
              'audit_answers': [{k: a.get(k) for k in ('status', 'job', 'watch', 'what_now', 'already_checked')} for a in answers],
              'watch': watch, 'progress': progress, 'final_answer': final, 'minutes': round((time.monotonic() - began) / 60, 1)}
    text = re.sub(r'token=[A-Za-z0-9_-]+', 'token=<redacted>', json.dumps(result, ensure_ascii=False, indent=1))
    (OUT / 'watch.json').write_text(text + '\n', encoding='utf-8')
    print(json.dumps({k: json.loads(text)[k] for k in ('session', 'watch', 'progress', 'minutes')}, ensure_ascii=False))
    return 0 if watch and progress.get('status') == 200 else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], Path(sys.argv[2]).expanduser()))

"""`eaos mcp`: EAOS as MCP tools for an AI assistant (stdio, JSON-RPC 2.0, one message per line).

Two tools, because a check takes minutes and an assistant's tool call does not wait that long:
  eaos_request {request, project, agreed}  runs `eaos do "<request>"` in the project; a quick answer comes back
                                            at once, a long one as a job to follow with eaos_job.
  eaos_job {job}                            whether that job is still running, and what it said so far.
`agreed` adds --yes, and is only for an answer the person gave to the question the previous result asked:
the tool description says so to the assistant, in the words the skill uses.
"""
import itertools
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import __version__
from .assistant_setup import eaos_command

QUICK_SECONDS = 20
TOOLS = [
    {'name': 'eaos_request',
     'description': 'Check, analyse or fix the project with Engineering Audit OS, in the person\'s own words ("check my project", '
                    '"what is wrong", "fix", "where are we", "accept the fixes", "undo"). Returns what EAOS said: a box with what '
                    'happened and the next step. A box with ❓ is a question for the person: ask them, and only if they agree '
                    'call again with agreed=true. Never set agreed=true on your own.',
     'inputSchema': {'type': 'object', 'required': ['request'],
                     'properties': {'request': {'type': 'string', 'description': 'what the person asked, in their words'},
                                    'project': {'type': 'string', 'description': 'the project folder (default: the current one)'},
                                    'agreed': {'type': 'boolean', 'description': 'the person said yes to the question EAOS asked'}}}},
    {'name': 'eaos_job',
     'description': 'Follow a long EAOS job (a check or a batch of fixes takes minutes): whether it is still running, and its output so far.',
     'inputSchema': {'type': 'object', 'required': ['job'], 'properties': {'job': {'type': 'string'}}}},
]
JOBS = {}
_ids = itertools.count(1)


def request(arguments):
    argv = eaos_command() + ['do', arguments['request'], '--project', arguments.get('project') or '.']
    if arguments.get('agreed'): argv.append('--yes')
    log = Path(tempfile.mkstemp(prefix='eaos-job-', suffix='.log')[1])
    process = subprocess.Popen(argv, cwd=arguments.get('project') or '.', stdout=log.open('w'), stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL)
    job = f'job-{next(_ids)}'
    JOBS[job] = (process, log)
    began = time.monotonic()
    while process.poll() is None and time.monotonic() - began < QUICK_SECONDS: time.sleep(0.5)
    return job_state(job)


def job_state(job):
    if job not in JOBS: return f'No job named {job}.'
    process, log = JOBS[job]
    output = log.read_text(encoding='utf-8', errors='replace')[-6000:]
    if process.poll() is None:
        return f'{job} is still running (a check takes 5-30 minutes, a batch of fixes 20-60). Output so far:\n{output}\n' \
               f'Call eaos_job with job="{job}" again in a minute or two.'
    return f'{job} finished.\n{output}'


def answer(message):
    method, params, ident = message.get('method'), message.get('params') or {}, message.get('id')
    if method == 'initialize':
        result = {'protocolVersion': params.get('protocolVersion', '2025-06-18'), 'capabilities': {'tools': {}},
                  'serverInfo': {'name': 'eaos', 'version': __version__}}
    elif method == 'tools/list':
        result = {'tools': TOOLS}
    elif method == 'tools/call':
        name, arguments = params.get('name'), params.get('arguments') or {}
        try:
            text = request(arguments) if name == 'eaos_request' else job_state(arguments.get('job', '')) if name == 'eaos_job' else None
        except (OSError, KeyError, ValueError) as problem:
            return {'jsonrpc': '2.0', 'id': ident, 'result': {'content': [{'type': 'text', 'text': str(problem)}], 'isError': True}}
        if text is None:
            return {'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32602, 'message': f'unknown tool {name}'}}
        result = {'content': [{'type': 'text', 'text': text}], 'isError': False}
    elif method == 'ping':
        result = {}
    elif ident is None:
        return None                                   # a notification: nothing to answer
    else:
        return {'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32601, 'message': f'unknown method {method}'}}
    return {'jsonrpc': '2.0', 'id': ident, 'result': result}


def main(stdin=sys.stdin, stdout=sys.stdout):
    for line in stdin:
        if not line.strip(): continue
        try: message = json.loads(line)
        except ValueError: continue
        reply = answer(message)
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False) + '\n')
            stdout.flush()
    return 0

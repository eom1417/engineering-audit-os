"""A trial of building from a plan (docs/BUILD-FROM-PLAN.md, B3 and B4): Claude Code builds a new project alone.

    python tools/build_trial.py clinic tests/fixtures/plans/clinic-prd.md

The person is played by short messages only: the request with the plan file, then «خذ توصياتك» to any choice the
assistant asks (the person has no preference), «نعم، موافق» to the one agreement, and «كمّل» when it stops before the
end. Between them is Claude Code with the EAOS tools, its read-only tools, and web search for research; no Bash,
Edit or Write, so every file goes through EAOS's gates. When the build is delivered, the finished project is audited
by EAOS itself, and the trial records what the audit finds that the build should never have let in.

Writes $EAOS_MEASURE/build/<name>/trial.json:
  {project, person_turns, messages[], delivered, branch, milestones, features, features_built, minutes, tool_calls,
   final_audit: {cycles, policy_violations, copies, dead_code, broken}, final_answer}
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEASURE = Path(os.environ.get('EAOS_MEASURE', '/workspace/eaos-measure')) / 'build'
MAX_TURNS = 8


def claude(prompt, where, config, session=None):
    argv = ['claude', '-p', prompt, '--mcp-config', str(config), '--strict-mcp-config', '--output-format', 'stream-json',
            '--verbose', '--allowedTools', 'mcp__eaos', 'Read', 'Grep', 'Glob', 'WebSearch', 'WebFetch',
            '--disallowedTools', 'Bash', 'Edit', 'Write', 'NotebookEdit']
    if session: argv += ['--resume', session]
    done = subprocess.run(argv, cwd=where, capture_output=True, text=True, timeout=8 * 3600)
    return [json.loads(line) for line in done.stdout.splitlines() if line.startswith('{')], done.stderr[-2000:]


def reply(state, answer):
    """What the person says next: 'take your recommendations' to the questions before the design, 'yes' to the one
    agreement to build, and 'go on' otherwise."""
    if not (state.get('blueprint') or {}).get('designed'): return 'ما عندي تفضيل: خذ توصياتك في كل شيء'
    if not (state.get('consent') or {}).get('build'): return 'نعم، موافق'
    return 'كمّل'


def final_audit(project, branch, out):
    """The finished project, audited by EAOS: what it finds is what the build let in."""
    work = Path(tempfile.mkdtemp(prefix='eaos-built-'))
    subprocess.run(['git', 'clone', '-q', '-b', branch, str(project), str(work / 'p')], check=True)
    subprocess.run([sys.executable, '-m', 'eaos', 'audit', str(work / 'p'), '--out', str(out), '--skip', 'site'],
                   capture_output=True, text=True, cwd=ROOT)
    from eaos.facts.store import read_set
    from eaos import blueprint
    rules = json.loads((work / 'p/eaos.policy.json').read_text(encoding='utf-8'))
    problems = blueprint.build_problems(work / 'p', out, rules, closing=True)
    count = lambda gate: sum(p['gate'] == gate for p in problems)
    shutil.rmtree(work, ignore_errors=True)
    return {'cycles': count('cycle'), 'policy_violations': count('layers') + count('structure') + count('vendor'),
            'copies': count('copy'), 'dead_code': count('dead'), 'broken': count('broken'), 'problems': problems[:40]}


def main(name, plan):
    out = MEASURE / name
    subprocess.run(['rm', '-rf', str(out)])
    home, where = out / 'home', out / 'project'
    home.mkdir(parents=True); where.mkdir()
    plan_copy = out / ('plan' + Path(plan).suffix)
    shutil.copyfile(plan, plan_copy)
    config = out / 'mcp.json'
    config.write_text(json.dumps({'mcpServers': {'eaos': {'command': sys.executable, 'args': ['-m', 'eaos', 'mcp'],
                                                          'env': {'EAOS_HOME': str(home), 'PYTHONPATH': str(ROOT)}}}}))
    os.environ['EAOS_HOME'] = str(home)
    sys.path.insert(0, str(ROOT))
    from eaos import guided

    began, session, messages, calls, answer = time.monotonic(), None, [], {}, ''
    prompt = f'عندي خطة مشروع في الملف {plan_copy}. ابنه بـ EAOS بأفضل هيكلة ممكنة.'
    while len(messages) < MAX_TURNS:
        messages.append(prompt)
        events, errors = claude(prompt, where, config, session)
        for event in events:
            session = event.get('session_id') or session
            for block in ((event.get('message') or {}).get('content') or []) if event.get('type') == 'assistant' else []:
                if block.get('type') == 'tool_use': calls[block['name']] = calls.get(block['name'], 0) + 1
            if event.get('type') == 'result': answer = event.get('result') or errors
        (out / f'turn-{len(messages)}.jsonl').write_text('\n'.join(json.dumps(e, ensure_ascii=False) for e in events) + '\n')
        state = guided.load(where.resolve()) or {}
        plan_data = json.loads((guided.outputs(state) / 'blueprint/plan.json').read_text()) if state.get('outputs') and \
            (guided.outputs(state) / 'blueprint/plan.json').is_file() else None
        if plan_data and len(state.get('built') or []) == len(plan_data['milestones']) and not state.get('open_build'): break
        prompt = reply(state, answer)
    state = guided.load(where.resolve()) or {}
    built = state.get('built') or []
    plan_data = json.loads((guided.outputs(state) / 'blueprint/plan.json').read_text()) if state.get('outputs') and \
        (guided.outputs(state) / 'blueprint/plan.json').is_file() else {'tasks': [], 'milestones': []}
    features = sorted({c['feature'] for c in plan_data['tasks'] if c.get('feature')})
    kept = {card for record in built for card in record['kept']}
    features_built = sorted({c['feature'] for c in plan_data['tasks'] if c.get('feature') and c['id'] in kept})
    delivered = bool(built) and len(built) == len(plan_data['milestones'])
    trial = {'project': name, 'person_turns': len(messages), 'messages': messages, 'delivered': delivered,
             'branch': built[-1]['branch'] if built else None, 'milestones': [r['milestone'] for r in built],
             'features': features, 'features_built': features_built, 'minutes': round((time.monotonic() - began) / 60, 1),
             'tool_calls': calls, 'final_answer': answer[-4000:], 'session': session,
             'final_audit': final_audit(where, built[-1]['branch'], out / 'final-audit') if built else None}
    (out / 'trial.json').write_text(json.dumps(trial, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: trial[k] for k in ('project', 'person_turns', 'delivered', 'milestones', 'minutes')}, ensure_ascii=False))
    return 0 if delivered else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1], sys.argv[2]))

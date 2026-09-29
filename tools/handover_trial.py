"""A trial of the handover (docs/MCP.md, P1-P3): Codex starts the work, its usage limit ends it in the middle of a batch,
and Claude Code, opened fresh, goes on from there; then the person says merge.

    python tools/handover_trial.py endomap /workspace/owner-projects/endomap

The person's part: «افحص مشروعي بـ EAOS وأصلح مشاكله» and «نعم» to Codex; then, to Claude Code, only «كمّل» (its
session-start hook, as `eaos assistant install` sets it, tells it EAOS work is open here);
when it asks whether to take the branch in, «ادمجها». The cut: Codex's process is killed once the open batch has a card
the assistant fixed and a card still to do (or, when it goes faster, once a branch waits), as a usage limit would.
Both assistants have the EAOS tools and read-only tools only, so every change goes through EAOS's gates.

Writes $EAOS_MEASURE/handover/<name>/trial.json:
  {project, cut: {batch, kept, left, at}, codex_turns, claude_turns, messages, claude_first_tool, asked_again,
   redone, delivered, merged, branch_deleted, report_updated, ledger, progress_true, handover_file, minutes, tool_calls}
"""
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEASURE = Path(os.environ.get('EAOS_MEASURE', '/workspace/eaos-measure')) / 'handover'
REQUEST, YES, GO_ON, MERGE = 'افحص مشروعي بـ EAOS وأصلح مشاكله', 'نعم، موافق', 'كمّل', 'ادمجها'
LIMIT = 3 * 3600


def load(where):
    from eaos import guided
    return guided.load(where) or {}


def cut_point(state):
    """The moment to cut Codex: a batch open with a card the assistant kept and one left, or a branch waiting."""
    wave = state.get('open_wave')
    if wave:
        left = [c for c in wave['cards'] if c not in wave['kept'] and c not in wave['failed']]
        mine = [c for c, tool in (wave.get('tools') or {}).items() if tool == 'assistant' and c in wave['kept']]
        if (mine and left) or not left: return {'batch': wave['number'], 'kept': list(wave['kept']), 'left': left}
    waiting = next((w for w in state.get('waves') or [] if w.get('status') == 'applied'), None)
    if waiting: return {'batch': waiting['number'], 'kept': list(waiting['kept']), 'left': [], 'waiting': waiting['branch']}
    return None


def codex(prompt, where, env, resume, log):
    server = f'mcp_servers.eaos={{command="{sys.executable}", args=["-m", "eaos", "mcp"], startup_timeout_sec=60, tool_timeout_sec=120, ' \
             f'env={{EAOS_HOME="{env["EAOS_HOME"]}", PYTHONPATH="{ROOT}", EAOS_ASSISTANT="Codex"}}}}'
    argv = ['codex', 'exec', *(['resume', '--last'] if resume else []), '--json', '--skip-git-repo-check',
            '-c', server, '-c', 'approval_policy="never"', '-c', 'sandbox_mode="read-only"', prompt]
    return subprocess.Popen(argv, cwd=where, stdout=log, stderr=subprocess.STDOUT, text=True, start_new_session=True)


def claude(prompt, where, config, session=None, settings=None):
    argv = ['claude', '-p', prompt, '--mcp-config', str(config), '--strict-mcp-config', '--output-format', 'stream-json',
            '--verbose', '--allowedTools', 'mcp__eaos', 'Read', 'Grep', 'Glob',
            '--disallowedTools', 'Bash', 'Edit', 'Write', 'NotebookEdit', 'WebFetch', 'WebSearch']
    if settings: argv += ['--settings', str(settings)]
    if session: argv += ['--resume', session]
    done = subprocess.run(argv, cwd=where, capture_output=True, text=True, timeout=LIMIT)
    return [json.loads(line) for line in done.stdout.splitlines() if line.startswith('{')], done.stderr[-2000:]


def main(name, source):
    out = MEASURE / name
    subprocess.run(['rm', '-rf', str(out)])
    home, where = out / 'home', out / 'project'
    home.mkdir(parents=True)
    subprocess.run(['git', 'clone', '--quiet', str(source), str(where)], check=True)
    os.environ['EAOS_HOME'] = str(home)
    sys.path.insert(0, str(ROOT))
    from eaos import guided, ledger
    skills = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude') / 'skills/eaos'
    skills.mkdir(parents=True, exist_ok=True)                  # what `eaos assistant install` puts there, this version
    (skills / 'SKILL.md').write_text((ROOT / 'eaos/templates/assistants/claude-skill.md').read_text(encoding='utf-8'), encoding='utf-8')
    began, messages, cut = time.monotonic(), [], None

    # 1. Codex, until its "limit"
    prompt, codex_turns = REQUEST, 0
    log = (out / 'codex.jsonl').open('a', encoding='utf-8')
    while cut is None and codex_turns < 15 and time.monotonic() - began < LIMIT:
        messages.append({'to': 'Codex', 'text': prompt})
        process = codex(prompt, where, {'EAOS_HOME': str(home)}, codex_turns > 0, log)
        codex_turns += 1
        while process.poll() is None:
            time.sleep(10)
            cut = cut_point(load(where))
            if cut:
                os.killpg(process.pid, signal.SIGKILL)          # the usage limit, in the middle of the work
                cut['at'] = round((time.monotonic() - began) / 60, 1)
                break
        state = load(where)
        prompt = YES if not (state.get('consent') or {}).get('run_and_fix') else GO_ON
    log.close()

    # 2. Claude Code, fresh, told only to go on
    config = out / 'mcp.json'
    config.write_text(json.dumps({'mcpServers': {'eaos': {'command': sys.executable, 'args': ['-m', 'eaos', 'mcp'],
                                                          'env': {'EAOS_HOME': str(home), 'PYTHONPATH': str(ROOT), 'EAOS_ASSISTANT': 'Claude Code'}}}}))
    settings = out / 'claude-settings.json'                     # the hook `eaos assistant install` puts in ~/.claude/settings.json
    hook = f'EAOS_HOME={home} PYTHONPATH={ROOT} {sys.executable} -m eaos handover --hook'
    settings.write_text(json.dumps({'hooks': {'SessionStart': [{'hooks': [{'type': 'command', 'command': hook, 'timeout': 20}]}]}}))
    session, calls, first, edited, answer, claude_turns, asked_again = None, {}, None, [], '', 0, False
    prompt = GO_ON
    while claude_turns < 4:
        messages.append({'to': 'Claude Code', 'text': prompt})
        events, errors = claude(prompt, where, config, session, settings)
        claude_turns += 1
        for event in events:
            session = event.get('session_id') or session
            for block in ((event.get('message') or {}).get('content') or []) if event.get('type') == 'assistant' else []:
                if block.get('type') != 'tool_use': continue
                calls[block['name']] = calls.get(block['name'], 0) + 1
                if block['name'].startswith('mcp__eaos__') and first is None: first = block['name'][len('mcp__eaos__'):]
                if block['name'] == 'mcp__eaos__fix_edit': edited.append((block.get('input') or {}).get('card'))
            if event.get('type') == 'result': answer = event.get('result') or errors
        (out / f'claude-turn-{claude_turns}.jsonl').write_text('\n'.join(json.dumps(e, ensure_ascii=False) for e in events) + '\n')
        state = load(where)
        if any(w.get('status') == 'accepted' for w in state.get('waves') or []): break
        if any(w.get('status') == 'applied' for w in state.get('waves') or []): prompt = MERGE
        else:
            asked_again = asked_again or 'موافق' in answer or '?' in answer[-300:] or '؟' in answer[-300:]
            prompt = YES if asked_again else GO_ON

    # 3. What came of it
    state = load(where)
    merged = [w for w in state.get('waves') or [] if w.get('status') == 'accepted']
    branches = subprocess.run(['git', '-C', str(where), 'branch', '--list', 'eaos/*'], capture_output=True, text=True).stdout.split()
    page = guided.outputs(state) / 'REPORT.html' if state else None
    record = ledger.load(state) if state else None
    in_branch, _ = ledger.merged_keys(where)
    kept = {k for w in merged for c, k in (w.get('keys') or {}).items() if c in (w.get('kept') or [])}
    totals = (record or {}).get('totals') or {}
    plan_cards = len(json.loads((guided.report_of(state) / 'plan.json').read_text(encoding='utf-8'))['tasks']) if state else 0
    trial = {'project': name, 'cut': cut, 'codex_turns': codex_turns, 'claude_turns': claude_turns, 'messages': messages,
             'claude_first_tool': first, 'asked_again': asked_again,
             'redone': sorted({c for c in edited if cut and c in cut['kept']}),
             'delivered': bool(merged) or any(w.get('status') == 'applied' for w in state.get('waves') or []),
             'merged': bool(merged), 'branch_deleted': bool(merged) and not any(w['branch'] in branches for w in merged),
             'report_updated': bool(merged and page and page.is_file()
                                    and page.stat().st_mtime >= max(datetime.fromisoformat(w['merged_at']).timestamp() for w in merged) - 5),
             'ledger': totals, 'progress_true': bool(merged) and totals.get('done') == len(kept) == len(kept & set(in_branch))
                                                 and totals.get('total') == plan_cards,
             'handover_file': bool(state) and 'Codex' in (guided.outputs(state) / 'HANDOVER.md').read_text(encoding='utf-8'),
             'minutes': round((time.monotonic() - began) / 60, 1), 'tool_calls': calls, 'final_answer': answer[-3000:]}
    (out / 'trial.json').write_text(json.dumps(trial, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: trial[k] for k in ('project', 'cut', 'claude_first_tool', 'asked_again', 'redone', 'merged', 'branch_deleted',
                                            'report_updated', 'progress_true', 'minutes')}, ensure_ascii=False))
    return 0 if trial['merged'] and trial['progress_true'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))

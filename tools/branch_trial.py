"""A trial of the branch (docs/MCP.md, L5): the owner's case, a project checked out on main while the work goes on in a
branch far ahead of it. A real assistant, Claude Code, with the EAOS tools and read-only tools only.

    python tools/branch_trial.py chief-ops /workspace/owner-projects/chief-ops main

The person's part: «افحص مشروعي بـ EAOS وأصلح مشاكله»; when asked which branch, «الفرع اللي تنصح فيه»; «نعم» to the
one agreement; «ادمجها» when a branch waits; «كمّل» when it stops for anything else (at most eight messages).

Writes $EAOS_MEASURE/branch/<name>/trial.json:
  {project, checked_out, recommended, asked_branch, chosen, checked_on_branch, merged_into_branch, main_untouched,
   checkout_untouched, report_names_branch, messages, minutes, tool_calls, final_answer}
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from handover_trial import claude          # noqa: E402  (one way to drive Claude Code)

MEASURE = Path(os.environ.get('EAOS_MEASURE', '/workspace/eaos-measure')) / 'branch'
REQUEST, WHICH, YES, MERGE, GO_ON = ('افحص مشروعي بـ EAOS وأصلح مشاكله', 'الفرع اللي تنصح فيه', 'نعم، موافق', 'ادمجها', 'كمّل')


def git(where, *args):
    return subprocess.run(['git', '-C', str(where), *args], capture_output=True, text=True).stdout.strip()


def main(name, source, checkout):
    out = MEASURE / name
    subprocess.run(['rm', '-rf', str(out)])
    home, where = out / 'home', out / 'project'
    home.mkdir(parents=True)
    subprocess.run(['git', 'clone', '--quiet', str(source), str(where)], check=True)
    for ref in git(where, 'for-each-ref', '--format=%(refname:short)', 'refs/remotes/origin').split():
        short = ref.split('/', 1)[-1]
        if short not in ('HEAD', 'origin') and not short.startswith('dependabot/'): git(where, 'branch', '--quiet', short, ref)
    git(where, 'checkout', '--quiet', checkout)                 # the person's folder is on main
    git(where, 'remote', 'set-head', 'origin', checkout)        # and main is the default branch, as on GitHub
    os.environ['EAOS_HOME'] = str(home)
    sys.path.insert(0, str(ROOT))
    from eaos import branches, guided
    offered = branches.choice(where)
    main_before = git(where, 'rev-parse', checkout)
    skills = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude') / 'skills/eaos'
    skills.mkdir(parents=True, exist_ok=True)
    (skills / 'SKILL.md').write_text((ROOT / 'eaos/templates/assistants/claude-skill.md').read_text(encoding='utf-8'), encoding='utf-8')
    config = out / 'mcp.json'
    config.write_text(json.dumps({'mcpServers': {'eaos': {'command': sys.executable, 'args': ['-m', 'eaos', 'mcp'],
                                                          'env': {'EAOS_HOME': str(home), 'PYTHONPATH': str(ROOT), 'EAOS_ASSISTANT': 'Claude Code'}}}}))
    began, session, messages, calls, answer, asked_branch, prompt = time.monotonic(), None, [], {}, '', False, REQUEST
    order = []
    while len(messages) < 8:
        messages.append(prompt)
        events, errors = claude(prompt, where, config, session)
        for event in events:
            session = event.get('session_id') or session
            for block in ((event.get('message') or {}).get('content') or []) if event.get('type') == 'assistant' else []:
                if block.get('type') == 'tool_use':
                    calls[block['name']] = calls.get(block['name'], 0) + 1
                    order.append(block['name'].replace('mcp__eaos__', ''))
            if event.get('type') == 'result': answer = event.get('result') or errors
        (out / f'turn-{len(messages)}.jsonl').write_text('\n'.join(json.dumps(e, ensure_ascii=False) for e in events) + '\n')
        state = guided.load(where) or {}
        if any(w.get('status') == 'accepted' for w in state.get('waves') or []): break
        if len(messages) == 1: asked_branch = not state.get('branch') and bool(offered)   # it stopped to ask, choosing nothing
        if not state.get('branch'): prompt = WHICH
        elif any(w.get('status') == 'applied' for w in state.get('waves') or []): prompt = MERGE
        else: prompt = YES if not (state.get('consent') or {}).get('run_and_fix') else GO_ON
    state = guided.load(where) or {}
    chosen = state.get('branch')
    merged = [w for w in state.get('waves') or [] if w.get('status') == 'accepted']
    page = guided.branches.home(state) / 'REPORT.html' if state.get('outputs') else None
    tip = git(where, 'rev-parse', chosen) if chosen else ''
    trial = {'project': name, 'checked_out': checkout, 'recommended': (offered or {}).get('recommended'),
             'asked_branch': asked_branch and WHICH in messages, 'chosen': chosen,
             'checked_on_branch': bool(chosen) and guided.same_code(state, state.get('scanned_commit'), tip) if state.get('scanned_commit') else False,
             'merged_into_branch': bool(merged) and all(not subprocess.run(['git', '-C', str(where), 'merge-base', '--is-ancestor', w['tip'], chosen]).returncode for w in merged),
             'main_untouched': git(where, 'rev-parse', checkout) == main_before,
             'checkout_untouched': git(where, 'symbolic-ref', '--short', 'HEAD') == checkout and not git(where, 'status', '--porcelain'),
             'report_names_branch': bool(page and page.is_file() and 'data-part="branch"' in page.read_text(encoding='utf-8') and chosen in page.read_text(encoding='utf-8')),
             'messages': messages, 'minutes': round((time.monotonic() - began) / 60, 1), 'tool_calls': calls, 'final_answer': answer[-3000:]}
    (out / 'trial.json').write_text(json.dumps(trial, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: trial[k] for k in ('project', 'recommended', 'asked_branch', 'chosen', 'checked_on_branch', 'merged_into_branch',
                                            'main_untouched', 'checkout_untouched', 'report_names_branch', 'minutes')}, ensure_ascii=False))
    return 0 if trial['merged_into_branch'] and trial['main_untouched'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 'main'))

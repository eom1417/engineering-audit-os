"""The handover: where the work is, so that another assistant continues from the exact point (docs/MCP.md).

A long piece of work can outlast an assistant's usage limit: Codex stops in the middle of a batch, and the person opens
Claude Code (or the other way round) to go on. Nothing of the work lives in the assistant: the state, the open batch
and its isolated copy, the jobs and the ledger are EAOS's own. What the next assistant needs is to know it, and what the
last one was doing. So:
  - every tool call is written to journal.jsonl beside state.json (when, which assistant, which tool, on which card,
    and what came of it), by the MCP server itself: an assistant cut off mid-sentence has still left its steps;
  - `note` lets the assistant add what the steps do not say (what it found, what it was about to do);
  - HANDOVER.md, in the person's outputs folder, is rewritten after every call: the goal, where things are, what is
    open, the last steps and notes, what the person already answered, and exactly how to continue;
  - `status` returns the same as `handover`, so the next assistant reads it by calling the tool it calls first anyway.
"""
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import guided

KEEP = 2000                  # journal lines kept
READING = {'status', 'wait', 'overview', 'findings', 'finding', 'structure', 'plan', 'report_file', 'fix_read', 'build_read',
           'open_report', 'open_blueprint', 'handover'}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def assistant():
    """The assistant this EAOS runs under: EAOS_ASSISTANT, else what its environment or its parent process says."""
    if os.environ.get('EAOS_ASSISTANT'): return os.environ['EAOS_ASSISTANT']
    if os.environ.get('CLAUDECODE') or os.environ.get('CLAUDE_CODE_ENTRYPOINT'): return 'Claude Code'
    if any(name.startswith('CODEX_') for name in os.environ): return 'Codex'
    try: parent = subprocess.run(['ps', '-o', 'comm=', '-p', str(os.getppid())], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError): parent = ''
    name = Path(parent).name.lower()
    return 'Codex' if 'codex' in name else 'Claude Code' if 'claude' in name else (Path(parent).name or 'an assistant')


def journal(state):
    return Path(state['workspace']) / 'journal.jsonl'


def _append(state, entry):
    path = journal(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as out: out.write(json.dumps(entry, ensure_ascii=False) + '\n')
    lines = path.read_text(encoding='utf-8').splitlines()
    if len(lines) > KEEP * 1.25: path.write_text('\n'.join(lines[-KEEP:]) + '\n', encoding='utf-8')


def entries(state, limit=None):
    path = journal(state)
    if not path.is_file(): return []
    out = []
    for line in path.read_text(encoding='utf-8').splitlines()[-(limit or KEEP):]:
        try: out.append(json.loads(line))
        except ValueError: continue
    return out


def _outcome(result):
    """A tool's answer in a few words: what the next assistant needs of it."""
    if not isinstance(result, dict): return ''
    if result.get('error'): return 'error: ' + str(result['error'])[:200]
    parts = [str(result[k]) for k in ('status',) if result.get(k)]
    if 'kept' in result and isinstance(result['kept'], bool): parts.append('kept' if result['kept'] else 'not kept: ' + str(result.get('why') or '')[:200])
    elif result.get('kept'): parts.append('kept: ' + ', '.join(map(str, result['kept']))[:200])
    for k in ('job', 'batch', 'branch', 'milestone', 'skipped'):
        if result.get(k) not in (None, '', False): parts.append(f'{k} {result[k]}')
    if result.get('failed'): parts.append('not passed: ' + ', '.join(map(str, result['failed']))[:200])
    return '; '.join(parts)[:400]


def _arguments(arguments):
    shown = {}
    for k, v in (arguments or {}).items():
        if k in ('project', 'edits', 'spec', 'proposal', 'text') or v in (None, '', [], {}): continue
        shown[k] = v if isinstance(v, (int, float, bool)) else str(v)[:160]
    if arguments and arguments.get('edits'): shown['files'] = sorted({str(e.get('path')) for e in arguments['edits'] if isinstance(e, dict)})[:12]
    return shown


def _state(project):
    folder = Path(project or os.getcwd()).expanduser().resolve()
    return guided.load(folder) if folder.is_dir() else None


def record(tool, arguments, result):
    """One tool call in the journal, then HANDOVER.md rewritten. Never raises: the tool's answer matters more."""
    try:
        state = _state((arguments or {}).get('project'))
        if not state: return
        _append(state, {'at': _now(), 'by': assistant(), 'tool': tool, 'card': (arguments or {}).get('card'),
                        'arguments': _arguments(arguments), 'outcome': _outcome(result)})
        if tool not in READING or tool == 'wait': refresh(state)
    except Exception:                       # the handover is extra: a failure here must not cost the tool its answer
        pass


def note(text, card=None, project=None):
    state = _state(project)
    if not state: raise LookupError('this project has no EAOS work yet: call `status` first')
    text = ' '.join(str(text or '').split())
    if not text: raise ValueError('the note is empty')
    _append(state, {'at': _now(), 'by': assistant(), 'tool': 'note', 'card': card, 'note': text[:1500]})
    refresh(state)
    return {'noted': True, 'handover': str(guided.outputs(state) / 'HANDOVER.md')}


def _open_work(state):
    wave, build = state.get('open_wave'), state.get('open_build')
    if wave:
        left = [c for c in wave['cards'] if c not in wave['kept'] and c not in wave['failed']]
        return {'kind': 'fix batch', 'number': wave['number'], 'cards': wave['cards'], 'kept': list(wave['kept']),
                'not_kept': dict(wave['failed']), 'left': left,
                'resume': (f"batch {wave['number']} is open: fix_start returns its cards left ({', '.join(left) or 'none'}); "
                           "fix each with fix_edit (finding + fix_read first), then fix_finish" if left else
                           f"batch {wave['number']} has every card kept or skipped: call fix_finish")}
    if build:
        kept, skipped = list(build.get('kept') or []), dict(build.get('skipped') or {})
        left = [c for c in build.get('cards') or [] if c not in kept and c not in skipped]
        return {'kind': 'build milestone', 'milestone': build.get('milestone'), 'kept': kept, 'not_kept': skipped, 'left': left,
                'resume': (f"milestone {build.get('milestone')} is open: build_start returns its cards left; build each with "
                           "build_edit, then build_finish")}
    return None


def brief(state, steps=12, notes=8):
    """What the next assistant needs, as a dict (status returns it; HANDOVER.md is it in words)."""
    from . import jobs
    from .ledger import load
    log = entries(state, 400)
    acting = [e for e in log if e.get('tool') not in READING]
    last = log[-1] if log else None
    busy = jobs.running(state['project'])
    waiting = next((w for w in reversed(state.get('waves') or []) if w.get('status') == 'applied'), None)
    answered = [{'question': q.get('id'), 'answer': q.get('answer')} for q in state.get('questions') or [] if 'answer' in q]
    if (state.get('consent') or {}).get('run_and_fix'): answered.append({'question': 'run the app and prepare fixes', 'answer': True})
    return {'mode': 'build from a plan' if state.get('mode') == 'build' else 'check and fix',
            'last_assistant': last.get('by') if last else None, 'last_activity': last.get('at') if last else None,
            'running_job': {'id': busy['id'], 'kind': busy['kind'], 'progress': busy.get('progress')} if busy else None,
            'open_work': _open_work(state),
            'waiting_for_the_person': {'branch': waiting['branch'], 'decision': 'accept or undo'} if waiting else None,
            'progress': (load(state) or {}).get('totals'),
            'person_already_answered': answered,
            'last_steps': [{k: e.get(k) for k in ('at', 'by', 'tool', 'card', 'outcome') if e.get(k)} for e in acting[-steps:]],
            'notes': [{k: e.get(k) for k in ('at', 'by', 'card', 'note')} for e in log if e.get('tool') == 'note'][-notes:],
            'how_to_continue': ('Continue exactly where this stopped, without asking the person again what they already answered: '
                                + ('first `wait` for the running job; ' if busy else '')
                                + ('then ' + _open_work(state)['resume'] + '; ' if _open_work(state) else '')
                                + 'follow `next` from `status`. Leave a `note` after each card and before you stop.')}


def refresh(state):
    """HANDOVER.md in the outputs folder, from the state, the journal and the ledger."""
    from . import agent_tools, build_tools
    try: now = (build_tools.status if state.get('mode') == 'build' else agent_tools.status)(state['project'])
    except Exception: now = {}
    state = guided.load(state['project']) or state
    b = brief(state, steps=25, notes=15)
    ar = state.get('lang') == 'ar'
    step = now.get('next') or {}
    lines = ['# HANDOVER: ' + Path(state['project']).name, '',
             ('> هذا الملف يُكتب تلقائيًا بعد كل خطوة، ليكمل أي مساعد ذكي (Claude Code أو Codex) من حيث توقف الآخر.' if ar else
              '> Written automatically after every step, so that any AI assistant (Claude Code or Codex) continues where the other stopped.'),
             '', f"Updated: {_now()} · project: `{state['project']}` · mode: {b['mode']}", '',
             '## Continue from here', '',
             '1. Call the eaos `status` tool first: it is the live version of this page (this file is a snapshot).',
             f"2. Next tool: `{step.get('tool', 'status')}`: {step.get('why', '')}".rstrip(': '),
             '3. ' + b['how_to_continue'], '',
             '## Where things are', '']
    p = b['progress'] or {}
    if p: lines.append(f"- Progress (in the person's branch): {p.get('closed', 0)} of {p.get('total', 0)} cards closed ({p.get('percent', 0)}%); "
                       f"{p.get('on_branch', 0)} waiting on a branch, {p.get('in_batch', 0)} in the open batch, {p.get('skipped', 0)} need a decision.")
    if b['running_job']: lines.append(f"- A job is running: `{b['running_job']['id']}` ({b['running_job']['kind']}). Follow it with `wait`.")
    work = b['open_work']
    if work:
        lines.append(f"- Open {work['kind']} {work.get('number') or work.get('milestone')}: kept {', '.join(work['kept']) or 'none'}; "
                     f"not kept {', '.join(work['not_kept']) or 'none'}; left {', '.join(work['left']) or 'none'}.")
    if b['waiting_for_the_person']: lines.append(f"- Waiting for the person: take in or throw away `{b['waiting_for_the_person']['branch']}`.")
    if not (p or work or b['running_job'] or b['waiting_for_the_person']): lines.append('- Nothing is open.')
    lines += ['', '## What the person already answered (do not ask again)', '']
    lines += [f"- {a['question']}: {a['answer']}" for a in b['person_already_answered']] or ['- Nothing yet.']
    lines += ['', '## Notes from the assistants', '']
    lines += [f"- {n['at']} · {n['by']}{' · ' + n['card'] if n.get('card') else ''}: {n['note']}" for n in b['notes']] or ['- None.']
    lines += ['', '## The last steps', '', '| When | Assistant | Tool | Card | What came of it |', '| --- | --- | --- | --- | --- |']
    lines += [f"| {s.get('at', '')} | {s.get('by', '')} | {s.get('tool', '')} | {s.get('card') or ''} | {str(s.get('outcome') or '').replace('|', '/')} |"
              for s in b['last_steps']] or ['| | | | | nothing yet |']
    lines += ['', 'The full journal: `' + str(journal(state)) + '`', '']
    target = guided.outputs(state) / 'HANDOVER.md'
    target.write_text('\n'.join(lines), encoding='utf-8')
    return target

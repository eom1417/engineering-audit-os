"""The check (audit): the person's choices for its AI, kept; the assistant's readiness; the check as a job; its overview."""
from .. import check_choices, guided
from ...core import branches, plain
from ...live import sign_in as signing
from ...ai.readiness import NoAssistant
from ...pipeline import remedies
from ...ai import readiness
from ...core import project_state
from .evidence import _ready
from .project import _read, _report, _start, state_of
from .running import CONSENT
from .where import _branch, _older_check


# ---------------------------------------------------------------- diagnosis

def audit(project=None, fresh=False, use_assistant=None, without_tools=False, assistant=None, without_ai=False, again_from=None, engines=None,
          paths=None, mode=None, sign_in=None, published=None, run_app=False, go_on=False, fixed=False, person_agreed=False):
    """`use_assistant`, `assistant`: the person's choice for the check's AI, kept (one not ready stops it, with why);
    `without_ai`: the rules alone; `again_from`: the last check goes on from that stage (`engines`: only those tools);
    `paths`, `mode`, `sign_in`, `published`, `run_app` (kept: eaos/journeys/check_choices.py); `go_on`: Retry; `fixed`: the assistant
    is fixed; `person_agreed`: their yes to a remedy's question (eaos/pipeline/remedies.py): the app runs, from setup."""
    run_app, again_from = remedies.agreed(run_app, again_from, person_agreed)
    state = state_of(project)
    asking = _branch(state)
    if asking: return asking
    state = _keep_ai_choice(state, use_assistant, assistant)
    if check_choices.keep(state, mode, sign_in, run_app): guided.save(state)
    # A check on record stands until asked for anew (fresh): one started because the code moved on stopped fixes (2026-10-10).
    if guided.scan_done(state) and not any((fresh, again_from, go_on)):
        return {'status': 'done', 'already_checked': True, **overview(project), **_older_check(state)}
    without_ai = check_choices.without_ai_kept(guided.report_of(state), without_ai, again_from, use_assistant is not None or assistant)
    blocked = None if without_ai else _assistant_not_ready(state, fixed)
    if blocked: return blocked
    arguments = {k: v for k, v in dict(without_tools=without_tools, without_ai=without_ai, again_from=again_from, engines=engines, paths=paths, published=signing.published(published), go_on=go_on).items() if v}
    return _start('audit', state, arguments, watch=True)


def _keep_ai_choice(state, use_assistant, assistant):
    """The person's choice for the check's AI, kept when made now (`use_assistant` or `assistant` given)."""
    if use_assistant is None and not assistant: return state
    return guided.choose_assistant(state, True if use_assistant is None else use_assistant, assistant, via='assistant')


def _assistant_not_ready(state, fixed=False):
    """{status: assistant_not_ready, ...} when the person's assistant does not answer now, unless they said it is `fixed`."""
    if fixed or guided.answered(state, 'use_assistant') is False: return None      # on unless the person said no
    name = guided.chosen_assistant(state)
    if not name: return None
    found = readiness.probe(name, fresh=True)          # the person may have just fixed it
    if found['ready']: return None
    return {'status': 'assistant_not_ready', 'assistant': found, 'why': (found.get('reason') or {}).get('en') or found['code'],
            'what_now': f"The check did not start: {found['name']} is not ready. Tell the person, in their language and plain words, "
                        f"what is wrong and how to fix it: {(found.get('reason') or {}).get('en') or found['code']} Then ask them: fix it and "
                        'check again (call audit again), use the other assistant (audit with assistant=claude or codex), or start '
                        'without AI (audit with use_assistant=false). End your turn until they answer.'}


def assistant_check(project=None, fresh=False, assistant=None):
    """Before a check: each AI assistant's readiness on this computer (installed, version, signed in and answering a
    one-word question, else the exact reason and its fix), the person's choice for this project, and what the
    assistant may do in the check. `fresh` asks again instead of the answer of the last few minutes; `assistant`
    asks only that one."""
    state = state_of(project)
    rows = readiness.probe_all(fresh=fresh, names=[assistant] if assistant else None)
    said = guided.answered(state, 'use_assistant')
    chosen = guided.chosen_assistant(state)
    return {'assistants': rows, 'choice': {'use_assistant': said, 'assistant': chosen if said is not False else state.get('assistant'),
                                           'kept': said is not None},
            'permission': PERMISSION,
            'what_now': 'Show the person each assistant with its readiness; when the one they want is not ready, its reason says how to fix '
                        'it. Their choice goes to audit (use_assistant, assistant).'}


PERMISSION = {'en': 'In the check the assistant only reads the facts EAOS gives it and answers: it has no tool, changes no file and '
                    'runs nothing; everything it says stays a hypothesis tied to its evidence.',
              'ar': 'في الفحص المساعد يقرأ فقط الحقائق اللي يعطيه إياها EAOS ويجاوب: ما عنده أي أداة، وما يغيّر أي ملف، وما يشغّل '
                    'شيء؛ وكل ما يقوله يبقى فرضية مربوطة بدليلها.'}


def _audit_job(project, arguments, progress):
    """The check, once none of the tools it needs here is still being installed; without those that failed only when
    the person chose to start without them (`without_tools`)."""
    state = project_state.load(project)
    without = arguments.get('without_tools')
    failed = guided.tools_for_check(state, lambda done, total: progress and progress(done, total, 'tools'), install=not without)
    if failed and not without: raise guided.ToolsMissing('these tools could not be installed: ' + '; '.join(f'{n}: {r}' for n, r in sorted(failed.items())))
    options = check_choices.options(state, progress, failed, guided.check_provider(state), guided.check_runtime(state),
                                    arguments.get('paths'), arguments.get('engines'), arguments.get('published'))
    if arguments.get('without_ai'): options['provider'] = NoAssistant('ai_skipped', 'the person started this check without AI, because their assistant was not ready')
    from ..check import run
    done = run(state, options, arguments.get('again_from'), bool(arguments.get('go_on')))[0]
    return {**overview(project), **remedies.consent(done, CONSENT)}


def overview(project=None):
    from ...report.start_here import summary_counts
    state = state_of(project)
    report = _report(state)
    plan = _read(report / 'plan.json')
    tasks = plan.get('tasks') or []
    manifest = _read(report / 'run-manifest.json') if (report / 'run-manifest.json').is_file() else {}
    claims = _read(report / 'dossier.json').get('claim_counts') if (report / 'dossier.json').is_file() else None
    return {'project': state['project'], 'checked_commit': state.get('scanned_commit'), 'status': manifest.get('status'),
            'incomplete_stages': [name for name, row in (manifest.get('stages') or {}).items() if row.get('status') in ('failed', 'not_reached')],
            'counts': summary_counts(report), 'claims_by_confidence': claims, 'problem_kinds': _problem_kinds(tasks),
            'milestones': _milestones(plan, tasks),
            'report_for_people': str(branches.home(state) / 'REPORT.html') if (branches.home(state) / 'REPORT.html').is_file() else None,
            'outputs_folder': str(guided.outputs(state)), 'technical_report': str(report),
            'next': 'Use `findings` and `finding` for the evidence, `structure` for the architecture, `plan` for the order of work.'}


def _problem_kinds(tasks):
    """overview's kinds of problem, the most frequent first: each with its plain title, count and three examples."""
    groups = {}
    for task in tasks: groups.setdefault(task.get('pattern') or 'generic', []).append(task)
    kinds = []
    for pattern, rows in sorted(groups.items(), key=lambda item: -len(item[1])):
        title, why = plain.problem(pattern, 'en')
        kinds.append({'kind': pattern, 'title': title, 'why': why, 'count': len(rows),
                      'fixable_automatically': sum(_ready(t) for t in rows),
                      'examples': [t['id'] for t in sorted(rows, key=lambda t: -(t.get('priority') or 0))[:3]]})
    return kinds


def _milestones(plan, tasks):
    """overview's milestones of the plan, each with how many of its cards EAOS can fix by itself."""
    return [{'id': m['id'], 'name': m.get('name'), 'goal': m.get('goal'), 'cards': len(m['tasks']),
             'fixable_automatically': sum(_ready(t) for t in tasks if t['id'] in set(m['tasks']))}
            for m in plan.get('milestones') or []]

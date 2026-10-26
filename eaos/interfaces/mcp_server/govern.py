"""The governance tools of `eaos mcp` (docs/MCP.md "Governance"): the Studio's queue, inbox, verbs, history and branch
control for an assistant, five tools each grouped by `op`, thin callers of eaos/interfaces/govern.py like the terminal's
commands; with them, the Studio's remaining actions (mcp_server/studio_parity.py). Each tool's function is defined once, here, with the
parameters the assistant passes (its schema); `register` puts it on the server as every tool is answered, and the tests call
it directly for its dict.

What only the person decides needs their word and the preview: `waiting(op=answer)` takes `person_said`, their reply,
given ANSWER_SECONDS or more after the question was listed; `branch_change` and `act(auto_accept=true)` take
`person_agreed` and the confirm token of the preview the person saw. Inside a Studio run all of them are refused.
"""
from .. import govern
from . import studio_parity
from .server import refuse_in_studio_run

RUN_FIELDS = ('id', 'label', 'state', 'action', 'verb', 'cards', 'created', 'started', 'ended', 'position', 'question', 'outcome')
PREVIEW_FIELDS = ('verb', 'selection', 'cards', 'left_out', 'files', 'batches', 'estimate', 'risk', 'on_failure', 'auto_accept')
ASK = ('Ask the person in their language, in plain words, with what the preview says will happen; end your turn. Only '
       'after their yes, call again with person_agreed=true and confirm set to this preview\'s confirm token.')


def _run(record):
    """A run as the assistant needs it: what it is, where it is, what it asks and what it handed over."""
    return {**{k: record.get(k) for k in RUN_FIELDS}, 'branch': (record.get('result') or {}).get('branch')}


def _needs(why, what_now):
    return {'status': 'needs_the_person', 'why': why, 'what_now': what_now}


def runs(op: str = 'list', run: str | None = None, paths: list[str] | None = None, mode: str | None = None,
         assistant: str | None = None, project: str | None = None, sign_in: str | None = None, published: str | None = None) -> str:  # limits: parameters -- the MCP tool's schema: each parameter is an argument the assistant passes
    if op == 'list': return {'runs': [_run(r) for r in govern.core(project).runs({'all': '1'})['runs'][:30]]}
    if op == 'show':
        found = govern.show_run(project, run)
        return {**found, 'run': _run(found['run'])}
    inputs = govern.check_inputs(paths, assistant, mode=mode, sign_in=sign_in, published=published)
    if op == 'estimate': return govern.estimate(project, inputs)
    if op == 'check':
        return {'run': _run(govern.start_check(project, inputs)), 'what_now': 'Tell the person the check runs in the background and '
                'how long it takes (op=estimate); follow it with op=show; answer what it asks through waiting.'}
    if op in govern.CONTROLS: return {'run': _run(govern.control(project, op, run))}
    raise ValueError('op is one of list, show, estimate, check, stop, pause, resume, retry')


def waiting(op: str = 'list', id: str | None = None, option: str | None = None, text: str | None = None, person_said: str = '',
            project: str | None = None) -> str:  # limits: parameters -- the MCP tool's schema: each parameter is an argument the assistant passes
    if op == 'list':
        rows = govern.waiting(project)
        for row in rows: govern.shown(row['id'])
        return {'waiting': rows, 'what_now': 'Each one waits for the person: ask them in their language (the options, your '
                'recommendation and why) and end your turn; answer with op=answer and person_said = their reply. A branch is '
                'taken in with accept or thrown away with undo, only after their yes.' if rows else 'Nothing waits for the person.'}
    if op != 'answer': raise ValueError('op is one of list, answer')
    refuse_in_studio_run('answer')
    why = govern.heard(id, person_said)
    if why: return _needs(why, 'The person answers, not you: ask them and end your turn; then answer with person_said = their reply.')
    return govern.answer(project, id, option, text)


def act(verb: str, ids: list[str] | None = None, group: str | None = None, op: str = 'preview', confirm: str | None = None,
        auto_accept: bool = False, person_agreed: bool = False, assistant: str | None = None, project: str | None = None) -> str:  # limits: parameters -- the MCP tool's schema: each parameter is an argument the assistant passes
    if auto_accept: refuse_in_studio_run('auto_accept')
    if op == 'start' and auto_accept and not person_agreed: return _needs('accepting by itself is the person\'s decision', ASK)
    preview = govern.verb_preview(project, verb, govern.selection_of(ids, group), auto_accept, assistant)
    if op == 'preview': return _shown(preview, auto_accept)
    if op != 'start': raise ValueError('op is one of preview, start')
    return {'run': _run(govern.verb_start(project, preview, confirm, assistant)), 'what_now': 'Follow it with runs(op=show).'}


def _shown(preview, auto_accept):
    """act's answer to op=preview: what the run would do, where, and its confirmation token."""
    where = preview.get('where') or {}
    return {**{k: preview.get(k) for k in PREVIEW_FIELDS}, 'confirm': (preview['confirm'] or {}).get('token'),
            'where': {k: where.get(k) for k in ('base', 'deliver_as', 'merge_into', 'problem')} if where else None,
            'assistant': preview.get('assistant'), 'handoff': preview['handoff']['available'],
            'what_now': ASK if auto_accept else 'Tell the person what it will do, then call op=start (with confirm, for fix).'}


def history(op: str = 'list', a: str | None = None, b: str | None = None, project: str | None = None) -> str:
    if op == 'list': return govern.history(project)
    if op == 'compare': return govern.compare(project, a, b)
    if op == 'usage': return govern.usage(project)
    raise ValueError('op is one of list, compare, usage')


# What the Studio's branch control does that is no one's decision alone: refresh a remote (name), propose how to resolve
# a merge's conflict (name into target, a review run that changes nothing).
UNDECIDED = {'fetch': lambda project, name, target: govern.fetch(project, name),
             'conflict': lambda project, name, target: govern.propose_resolution(project, name, target)}


def branch_change(op: str, name: str | None = None, target: str | None = None, confirm: str | None = None,
                  confirm_unmerged: str | None = None, person_agreed: bool = False, project: str | None = None) -> str:  # limits: parameters -- the MCP tool's schema: each parameter is an argument the assistant passes
    if op in UNDECIDED: return UNDECIDED[op](project, name, target)
    if op not in (*govern.BRANCH_OPS, 'restore'): raise ValueError('op is one of merge, delete, protect, unprotect, cleanup, restore, fetch, conflict')
    refuse_in_studio_run('branches ' + {'unprotect': 'protect'}.get(op, op))
    if op == 'restore':
        return govern.restore(project, name) if person_agreed else _needs('restoring is the person\'s decision', 'Ask them; only after their yes, call again with person_agreed=true.')
    preview = govern.branch_preview(project, op, name, target)
    if not confirm:
        return {'preview': preview, 'confirm': (preview.get('confirm') or {}).get('token'), 'confirm_unmerged': (preview.get('confirm_unmerged') or {}).get('token'),
                'what_now': ASK + ' A deletion of commits in no other branch also needs confirm_unmerged.' if not preview.get('blocked') else 'It cannot be done now: tell the person why (blocked).'}
    if not person_agreed: return _needs('this change is the person\'s decision', ASK)
    return govern.branch_change(project, op, preview, confirm, confirm_unmerged)


def register(server, reading, working, answer):
    """The five governance tools on `server`, each answered as every tool is (`answer`: mcp_server._answer)."""
    doc = ' project: the project folder (default: the folder the assistant was opened in).'

    server.tool(annotations=working, description='The runs of the Studio\'s queue, without the Studio: op=list; show (one run, the '
                'active one by default: its stage, minutes left, cost so far, last events, its question); estimate (how long a check '
                'of `paths` in `mode` takes here); check (a new check in the background, the same one the Studio and `eaos check` '
                'start: paths, mode, assistant claude|codex|none, sign_in hand|test_user|none (kept), published: an https address '
                'the person named, read signed in, read only, for this check); stop, pause, resume, retry (run, the newest it '
                'applies to by default).' + doc)(answer(runs))

    server.tool(annotations=working, description='What waits for the person: op=list (the runs\' questions, the report\'s questions, '
                'a branch waiting for accept or undo, the sign-in a check waits for: the person signs in in the Studio\'s Waiting '
                'for you or with eaos sign-in, never you; option signed_out goes on without it); op=answer (id, option or text) with person_said = the person\'s own reply, '
                'never yours: only after you listed it and asked them.' + doc)(answer(waiting))

    server.tool(annotations=working, description='A verb (fix, verify, explain, plan) on cards: ids, or group as by=value (by: area, '
                'severity, component, gap, operation). op=preview first (cards, files, batches, estimate, risk, where a fix builds, '
                'its confirm token); then op=start (fix: with confirm). The run is the Studio\'s: the person\'s assistant runs it '
                'headless, or, with assistant=handoff, it waits for you in status. auto_accept=true (fix: accepted by itself when its '
                'checks pass) is the person\'s choice: person_agreed=true only after their yes.' + doc)(answer(act))

    server.tool(annotations=reading, description='The project over time: op=list (every check on record: score, open cards, closed of '
                'total); compare (a, b: two check ids of the list); usage (what the assistant used: the last check stage by stage, '
                'every run, the chat: tokens and cost at API prices).' + doc)(answer(history))

    server.tool(annotations=working, description='Change a branch, as the Studio\'s branch control does: op=merge (name into target), '
                'delete, protect, unprotect (name), cleanup (merged branches, old worktrees), restore (name: a recovery id), fetch '
                '(name: a remote, origin by default), conflict (name into target: the person\'s assistant proposes a resolution, '
                'nothing changes). Without confirm: the preview and its confirm token(s); show it, ask, and only after their yes '
                'call again with person_agreed=true and confirm (confirm_unmerged too for commits in no other branch).' + doc)(answer(branch_change))


def every(server, reading, working, answer):
    """What `eaos mcp` adds to the server: the governance tools and the Studio's remaining actions (studio_parity)."""
    register(server, reading, working, answer)
    studio_parity.register(server, reading, working, answer)


def main():
    """`eaos mcp`: the server with every tool, these included."""
    from .server import build
    build(every).run('stdio')
    return 0

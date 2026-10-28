"""The person's own rules through every door (M16): one interface the terminal (`eaos rules`), the MCP tools, the
Studio's "Your rules" and its chat, and a card's comment share, over the one registry (eaos/core/project/rules.py).

    add       a rule said, in the person's words, for the card or batch it was said for, or pinned; the same
              requirement said again is the rule said again ("you said this on <date>"), and pinning is offered
    pin / unpin / change   the person's at any time; each shows first what it touches (its guard, the tests the guard
              runs, the context files and the hook it is written into), and its history keeps what it was
    guard     the rule's machine guard, written by the person's assistant (given) or asked of it once (`write`)
    hook      with the person's consent, the project's pre-commit hook runs the pinned rules on every commit
    changed   the diff-scoped check (eaos/analysis/rules/changed.py): the rules on what a change brought, before it lands

A pinned rule is also written between EAOS's marker lines in the project's CLAUDE.md / AGENTS.md
(eaos/analysis/rules/context.py), always from the registry: those lines are never a source of their own.
"""
from pathlib import Path

from ..analysis.rules import context, guards
from ..core.project import rules as registry, state as project_state


def _state(project):
    from ..journeys.agent_tools import state_of
    return state_of(project)


def _row(rule, state):
    last = (rule.get('breaks') or [None])[-1]
    return {'id': rule['id'], 'words': rule['words'], 'scope': rule['scope'], 'state': rule['state'],
            'in_scope': registry.in_scope(rule, state), 'said_on': registry.said_on(rule), 'said_at': rule['said'][0]['at'],
            'said': len(rule['said']), 'guard_kind': (rule.get('guard') or {}).get('kind'),
            'doors': sorted({s['door'] for s in rule['said']}), 'guard': guards.said(rule.get('guard')),
            'guarded': (rule.get('guard') or {}).get('kind') not in (None, 'none'),
            'broken': rule.get('broken', 0), 'returns': registry.came_back(rule),
            'last_broken': last and {'at': last['at'], 'where': last['where'], 'places': last['places'][:10]},
            'held': rule.get('held'), 'offer_pin': _offer_pin(rule), 'history': rule['history'][-10:]}


def _offer_pin(rule):
    """Pinning is offered for a rule not pinned that the person said twice or more, or that came back after it held."""
    return rule['scope']['kind'] != 'pinned' and (len(rule['said']) > 1 or registry.came_back(rule) > 0)


def listing(project=None):
    """Every rule of the project: in scope or not, pinned, held or broken where, and its last changes; the hook."""
    state = _state(project)
    registry.settle(state['project'], state)            # a rule whose card or batch is over ends here, with why
    record = registry.load(state['project'])
    rows = [_row(rule, state) for rule in record['rules']]
    return {'rules': rows, 'pinned': sum(r['scope']['kind'] == 'pinned' and r['state'] == 'active' for r in rows),
            'hook': context.hooked(state['project']), 'context_files': context.files(state['project'])[0] and
            [str(p.relative_to(state['project'])) for p in context.files(state['project'])[0]],
            'kept_in': str(registry.path(state['project']))}


def _scope(state, card=None, pin=False):
    if pin: return {'kind': 'pinned', 'ref': None}
    if card: return {'kind': 'card', 'ref': str(card)}
    return {'kind': 'batch', 'ref': ((state.get('open_wave') or {}).get('number'))}


def _language(pinned, state):
    """The block's own line in the language the pinned rules are written in (a public English manual keeps English)."""
    said_in = [r['lang'] for r in pinned]
    return max(('ar', 'en'), key=said_in.count) if said_in else state.get('lang') or 'en'


def written(state):
    """The pinned rules written again into the project's context (from the registry, the one source)."""
    project = state['project']
    record = registry.load(project)
    pinned = [r for r in record['rules'] if r['state'] == 'active' and r['scope']['kind'] == 'pinned']
    files, made = context.write(project, pinned, record.get('context') or [], _language(pinned, state))
    registry.keep(project, context=made)
    if not pinned and (record.get('hook') or {}).get('on'): hook(project, False)
    return files


def add(project=None, words='', door='terminal', by='person', card=None, pin=False):  # limits: parameters -- a rule said: its words, the door, who, and its scope (a card, or pinned)
    state = _state(project)
    rule, before = registry.add(state['project'], words, door, by, card and f'card {card}', _scope(state, card, pin))
    files = written(state) if rule['scope']['kind'] == 'pinned' else []
    row = _row(rule, state)
    said = (f"you said this before, on {row['said_on']} ({before} times before)" if before else None)
    return {'rule': row, 'repeat': before, 'said_before': said, 'written_into': files,
            'what_now': ('pin it so it holds for every change (rule_pin)' if row['offer_pin'] else
                         'write its guard once with rule_guard (a code pattern with examples, a test, or EAOS detectors)'
                         if not row['guarded'] else 'it is guarded: every check and change runs it')}


def touches(project, ident):
    """What changing or unpinning a rule touches: its guard, the tests the guard runs, the context files and the hook it
    is written into, the cards it holds open. A test of the project's own is never removed with the rule."""
    state = _state(project)
    rule = registry.find(registry.load(state['project']), ident)
    guard = rule.get('guard') or {}
    pinned = rule['scope']['kind'] == 'pinned' and rule['state'] == 'active'
    return {'rule': rule['id'], 'words': rule['words'], 'guard': guards.said(guard),
            'tests': guard.get('tests') or ([' '.join(guard['command'])] if guard.get('kind') == 'test' else []),
            'tests_stay': guard.get('kind') == 'test',
            'context_files': [str(p.relative_to(state['project'])) for p in context.files(state['project'])[0]] if pinned else [],
            'hook': pinned and context.hooked(state['project']),
            'files': guard.get('files') or []}


def pin(project=None, ident='', by='person', door='terminal', why=None):  # limits: parameters -- the rule, who, the door and why, as every change of a rule
    state = _state(project)
    rule = registry.change(state['project'], ident, by, door, why, scope={'kind': 'pinned', 'ref': None})
    return {'rule': _row(rule, state), 'written_into': written(state), 'touches': touches(project, ident)}


def unpin(project=None, ident='', by='person', door='terminal', why=None):  # limits: parameters -- the rule, who, the door and why, as every change of a rule
    """The rule ends: its line leaves the context files and, with the last pinned rule, the hook its block; its own guard
    goes with it (kept in its history); a test of the project's it ran stays."""
    state = _state(project)
    shown = touches(project, ident)
    rule = registry.end(state['project'], ident, by, door, why)
    return {'rule': _row(rule, state), 'removed_from': shown['context_files'], 'hook_removed': shown['hook'] and not
            listing(project)['pinned'], 'tests_kept': shown['tests'], 'written_into': written(state)}


def change(project=None, ident='', words=None, by='person', door='terminal', why=None, preview=False):  # limits: parameters -- the rule's new words, who, the door, why, and the preview first
    """The rule's words changed (preview: what it touches, nothing changed); its guard is asked again, since it guarded
    the old words."""
    shown = touches(project, ident)
    if preview: return {'preview': shown, 'what_now': 'say yes to change it'}
    state = _state(project)
    rule = registry.change(state['project'], ident, by, door, why, words=words)
    return {'rule': _row(rule, state), 'touches': shown, 'written_into': written(state) if rule['scope']['kind'] == 'pinned' else [],
            'what_now': 'check its guard still says what the new words say (rule_guard)'}


def guard(project=None, ident='', written_guard=None, write=False, by='person', door='terminal'):  # limits: parameters -- the rule, the guard given or to write, who and the door
    """The rule's guard set: the one given (checked on its examples), or asked once of the person's assistant (`write`)."""
    state = _state(project)
    rule = registry.find(registry.load(state['project']), ident)
    cost = None
    if write:
        from ..ai.rule_guard import write as ask
        from ..core.project.places import workspace
        written_guard, cost = ask(rule, state['project'], workspace(state['project']) / 'rules' / rule['id'])
        by = 'assistant'
    rule = registry.guard(state['project'], ident, guards.checked(written_guard or {}), by, door)
    result = guards.run(rule['guard'], state['project'])
    if rule['scope']['kind'] == 'pinned': written(state)
    return {'rule': _row(rule, state), 'now': result, 'cost_usd': cost}


def hook(project=None, on=True, agreed=False):
    """The pinned rules on every commit, in the project's pre-commit hook (on: only with the person's yes)."""
    state = _state(project)
    if on and not agreed:
        return {'status': 'needs_agreement', 'ask_the_person': 'Check your pinned rules on every commit? EAOS adds a few lines '
                'to the project\'s git pre-commit hook; a commit that breaks one is refused with the place.'}
    import os
    from ..ai.assistant.setup import eaos_command
    record = registry.load(state['project'])
    # the hook reads the registry this EAOS keeps: an EAOS home set here goes into its line
    home = ['env', f"EAOS_HOME={os.environ['EAOS_HOME']}"] if os.environ.get('EAOS_HOME') else []
    path, made = context.hook(state['project'], home + eaos_command(), on, (record.get('hook') or {}).get('made', False))
    registry.keep(state['project'], hook={'on': on, 'made': made, 'path': str(path)})
    return {'status': 'on' if on else 'off', 'hook': str(path)}


def _holding_now(project, hook_only):
    """The rules that hold now (the pinned ones only, for the hook: a commit never makes a project's state)."""
    state = project_state.load(project) or {} if hook_only else _state(project)
    if state.get('workspace'): registry.settle(project, state)
    return [r for r in registry.holding(project, state) if r['scope']['kind'] == 'pinned' or not hook_only]


def changed(project=None, base=None, staged=False, hook_only=False, gates=True):  # limits: parameters -- the change (its base or the index), the hook's own run, and the gates
    """The diff-scoped check: the rules that hold now (only the pinned ones from the hook) on what the change brought,
    and the code laws' gates on its files (from the hook, only when a pinned rule is guarded by them: only the person's
    pinned rules refuse a commit); each break recorded on its rule."""
    from ..analysis.rules import changed as diff
    from ..analysis.rules.held import record
    project = Path(project or '.').resolve()
    rules = _holding_now(project, hook_only)
    detected = any((r.get('guard') or {}).get('kind') == 'detector' for r in rules)
    result = diff.check(project, rules, base, staged, gates and (detected or not hook_only))
    record(project, result['results'], 'hook' if hook_only else 'changed')
    return result


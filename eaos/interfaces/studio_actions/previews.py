"""What a run would be, before the person confirms it (docs/studio-actions.json `preview`): its verb or action, its
inputs checked against the contract, its assistant, the cards it takes and leaves out, where a Fix builds, its time
and risk, the request a chat assistant could take over, and whether it needs the person's confirmation."""
from datetime import datetime

from ...ai.assistant import prompts
from ...journeys import check_choices
from ...journeys.fix import selection as selecting
from . import handoff, lane_assistants as helpers
from .runs import PLANNERS
from ...core.project import state as project_state

VERBS = ('fix', 'verify', 'explain', 'plan')


def _where_of(where):
    """The part of a Fix preview's place that is confirmed and handed to fix_start: {base, base_commit, deliver_as,
    merge_into}; None without one."""
    if not where or not where.get('base'): return None
    return {'base': where['base']['branch'], 'base_commit': where['base']['commit'], 'deliver_as': where.get('deliver_as'),
            'merge_into': where.get('merge_into')}


def _group_name(selection):
    """The name of the group a Fix was chosen as (an area, a component, ...): its new branch is named after it."""
    group = (selection or {}).get('group') if isinstance(selection, dict) and selection.get('kind') == 'group' else None
    return str((group or {}).get('value') or '') or None


def _auto_accept(verb, inputs):
    """Whether the person chose, in a Fix preview, to accept the batch automatically when its checks pass."""
    return verb == 'fix' and (inputs or {}).get('auto_accept') is True


def _bound(selection, where, auto):
    """What a confirm token is bound to: the selection, a Fix's place, and the person's auto-accept choice, so a token
    of a preview without it never starts a run that accepts by itself."""
    bound = {'selection': selection, 'where': where} if where else selection
    return {'bound': bound, 'auto_accept': True} if auto else bound


def _rough(action, inputs):
    """An action's time by a rough rule for its step, in minutes; a check's with what the experience adds when chosen."""
    low, high = (5, 30) if action == 'audit' else (10, 40) if action in ('run_setup', 'run_try', 'safety_net', 'fix_finish', 'build_finish') else (0, 1)
    return {'minutes_low': low, 'minutes_high': high, 'basis': {'en': 'a rough rule for this step', 'ar': 'تقدير تقريبي لهذه الخطوة'},
            **(check_choices.adds(inputs.get('paths')) if action == 'audit' else {})}


class Previews:
    """What a run would be: the part of Actions that previews it."""
    def _kind(self, name, body):
        """(verb or None, action id) of a preview or a run: a verb when the body selects cards."""
        verb = body.get('verb') or (name if name in VERBS and name not in self.actions else None)
        if verb is None and name in VERBS and body.get('selection'): verb = name
        if verb:
            if verb not in self.verbs: raise ValueError(f'no verb named {verb}')
            return verb, verb
        if name not in self.actions: raise KeyError(name)
        return None, name

    def _inputs(self, action, inputs, verb=None, project=None):
        """The inputs of an action, or of a verb that declares any (a Fix's auto_accept), checked against the contract;
        the project is the server's own (create), never the page's."""
        from ...core.contracts.artifact_rules import validate
        inputs = {key: value for key, value in (inputs or {}).items() if key != 'project'}
        schema = self.verbs[verb].get('inputs') if verb else self.actions[action]['inputs']
        if verb and not schema: return {}
        problems = validate(inputs, schema)
        if problems: raise ValueError('; '.join(problems[:5]))
        return {**inputs, 'project': project} if project else inputs

    def _assistant(self, wanted, needed):
        if not needed: return None
        if wanted == 'handoff': return 'handoff'
        if wanted:
            if wanted not in self.adapters: raise ValueError(f'no assistant named {wanted}')
            return wanted
        return next((key for key, adapter in self.adapters.items() if adapter.available()), 'handoff')

    def _needs_confirm(self, verb, action, inputs):
        if verb: return self.verbs[verb]['changes_code']
        spec = self.actions[action]
        return spec['irreversible'] or spec['changes_code'] or (spec['needs_consent'] and bool(inputs.get('person_agreed')))

    def _past(self, verb):
        rows = []
        for row in self.store.all():
            if row.get('verb') == verb and row.get('state') == 'done' and row.get('started') and row.get('ended') and row.get('cards'):
                minutes = (datetime.fromisoformat(row['ended']) - datetime.fromisoformat(row['started'])).total_seconds() / 60
                rows.append((minutes, len(row['cards'])))
        return rows

    def preview(self, name, body):
        verb, action = self._kind(name, body)
        inputs = self._inputs(action, body.get('inputs'), verb)
        needed = self.verbs[verb]['needs_assistant'] if verb else self.actions[action]['needs_assistant']
        assistant = self._assistant(body.get('assistant'), needed)
        chosen = self.adapters.get(assistant).detect() if assistant and assistant != 'handoff' else None
        out = {'action': action, 'verb': verb, 'selection': body.get('selection') if verb else None,
               'cards': [], 'left_out': [], 'files': [], 'batches': [],
               'assistant': chosen, 'assistants': self.assistants() if needed else [],
               'irreversible': bool(not verb and self.actions[action]['irreversible']),
               'needs_consent': bool(not verb and self.actions[action]['needs_consent']) or verb == 'fix'}
        if verb: self._verb_preview(out, verb, body)
        else: self._action_preview(out, action, inputs)
        self._handoff(out, (verb, action, needed), inputs)
        self._confirmable(out, verb, action, inputs)
        return out

    def _confirmable(self, out, verb, action, inputs):
        """The preview's auto-accept choice, and its confirm token when the run needs the person's confirmation."""
        # a Fix confirms where it builds too: the token pins the base commit the person saw, and nothing is confirmed
        # while the preview says the place is wrong (a protected target, a branch name git refuses)
        where = out.get('where')
        out['auto_accept'] = _auto_accept(verb, inputs)
        bound = _bound(out['selection'], _where_of(where), out['auto_accept'])
        out['confirm'] = (self.locks.confirm(action, bound, self.project)
                          if self._needs_confirm(verb, action, inputs) and not (where and where.get('problem')) else None)

    def _verb_preview(self, out, verb, body):
        """The cards a verb would take and leave out, and where a Fix would build."""
        cards, left = selecting.resolve(body.get('selection'), self._studio())
        out.update(selecting.preview_of(verb, cards, left, self._past(verb)))
        if verb == 'fix' and self._has_commits(): out.update(where=self.branches.fix_where(body.get('where'), _group_name(body.get('selection'))), speed=helpers.speed(self.project, cards))

    def _action_preview(self, out, action, inputs):
        """An action's time (a check's from this project's last one, eaos/journeys/check_choices.py), risk and what happens when it
        fails; where Accept would merge."""
        spec = self.actions[action]
        measured = self._measured(action, inputs)
        if action == 'audit':
            out['check'] = check_choices.offered(project_state.load(str(self.project)), self._studio() and self._studio().parent)
        out.update(estimate=measured or _rough(action, inputs),
                   risk={'level': 'high' if spec['irreversible'] else 'medium' if spec['changes_code'] else 'low',
                         'why': spec['description'] if spec['description']['en'] else spec['label']},
                   on_failure=selecting.ON_FAILURE['fix' if spec['changes_code'] else 'read'])
        if action == 'accept' and self._has_commits(): out['merge'] = self.branches.accept_where()

    def _measured(self, action, inputs):
        """A check's time as this project's last check measured it (eaos/journeys/check_choices.py); falsy for any other."""
        return action == 'audit' and self._studio() and check_choices.estimate(self._studio().parent, inputs.get('paths'), inputs.get('mode'), inputs.get('again_from'))

    def _handoff(self, out, kind, inputs):
        """The request a chat assistant could take over; `kind`: (verb, action, needs an assistant)."""
        verb, action, needed = kind
        prompt = prompts.build(verb, out['cards'], self.project, self.lang, action=action, inputs={} if verb else inputs,
                               labels={k: v['label'] for k, v in self.actions.items()}, where=_where_of(out.get('where')))
        # The planner asks the assistant itself: there is no request a chat assistant could take over.
        handed = bool(needed) and action not in PLANNERS
        out['handoff'] = {'available': handed, 'request': handoff.request_text(prompt, '<run>') if handed else None}

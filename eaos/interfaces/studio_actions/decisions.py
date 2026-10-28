"""What the person decides in the Studio: the report's questions (each answer kept, then reviewed by a run of their
assistant), and accept or undo of the branch a run handed over."""
import fcntl
from pathlib import Path

from ...journeys.build_from_plan import steps as build_tools
from ...journeys.fix import selection as selecting
from ...core.project.runs import _write_json
from .lane_assistants import Refused
from ...core.system.files import read_json
from ...core.system.clock import now


def _chosen_answer(question, option, text):
    """The option the owner chose, or None for a custom answer; refused when the answer is neither, or both."""
    chosen = next((o for o in question.get('options', []) if o['id'] == option), None)
    if option is not None and text is not None:
        raise ValueError('send either an option or a custom answer, not both')
    if text is not None and not _usable(text): raise ValueError('text must contain 1 to 4000 characters')
    if not chosen and not (option is None and text):
        raise ValueError('choose an authoritative option or a custom answer')
    return chosen


def _usable(text):
    """Whether a custom answer is text of 1 to 4000 characters."""
    return isinstance(text, str) and text.strip() and len(text) <= 4000


def _owner_response(saved, row, answer, path):
    """The owner's saved answer to a report question, saved now when it is the first; `answer`: (decision, option,
    text, the chosen option). A different answer to a question already answered is refused."""
    decision, option, text, chosen = answer
    response = saved.get(row['scope'])
    if response and (response['option'] != option or response.get('text') != text):
        raise LookupError('this question already has an owner answer')
    if response: return response
    response = {'decision': decision, 'scope': row['scope'], 'option': option, 'text': text,
                'label': chosen['label'] if chosen else text, 'at': now('milliseconds'), 'provenance': 'owner:studio',
                'status': 'saved', 'run': 'd' + row['scope'][:40],
                'history': [{'at': now('milliseconds'), 'event': 'saved', 'by': 'owner:studio'}]}
    saved[row['scope']] = response
    _write_json(path, saved)
    return response


def _decision_words(operation, branch, ok, result):
    """What happened to the waiting branch, in both languages."""
    if ok:
        return {'en': f"{'Taken in' if operation == 'accept' else 'Thrown away'}: {branch}",
                'ar': f"{'اعتُمد' if operation == 'accept' else 'رُمي'}: {branch}"}
    return {'en': f"{operation} did not happen: {result.get('status') or result.get('error')}",
            'ar': f"ما تم: {result.get('status') or result.get('error')}"}


class Decisions:
    """What the person decides: the part of Actions that keeps it."""
    def report_decisions(self):
        folder = self._studio()
        rows = (selecting._load(folder, 'decisions') or {}).get('decisions', []) if folder else []
        saved = read_json(self.store.folder / 'decisions.json', {}) or {}
        result = []
        for question in rows:
            scope = selecting.decision_scope(folder, question)
            response = saved.get(scope)
            run = None
            if response and response.get('run'):
                try: run = self.public(self.store.load(response['run']))
                except KeyError: pass
            result.append({'id': question['id'], 'scope': scope, 'question': question,
                           'response': response, 'execution': run})
        return result

    def answer_decision(self, decision, body):
        with (self.store.folder / 'decisions.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            row = next((r for r in self.report_decisions() if r['id'] == decision), None)
            if not row: raise KeyError(decision)
            if body.get('scope') != row['scope']: raise LookupError('the report question changed; reload before answering')
            question = row['question']
            option, text = body.get('option'), body.get('text')
            chosen = _chosen_answer(question, option, text)
            path = self.store.folder / 'decisions.json'
            saved = read_json(path, {}) or {}
            response = _owner_response(saved, row, (decision, option, text, chosen), path)
            if question.get('tool') == 'blueprint': return build_tools.answered(self.project, row, response)
            self._review_queued(question, response, body.get('assistant'))
            saved[row['scope']] = response
            _write_json(path, saved)
            self.store.set_queue(self.store.queue())
            return next(r for r in self.report_decisions() if r['id'] == decision)

    def _review_queued(self, question, response, wanted):
        """The owner's answer queued for review by a run of their assistant (made once), and so recorded."""
        run = response['run']
        try: self.store.load(run)
        except KeyError: self._queue_review(run, question, response, wanted)
        response['status'] = 'queued'
        if not any(e['event'] == 'queued' for e in response['history']):
            response['history'].append({'at': now('milliseconds'), 'event': 'queued', 'run': run})

    def _queue_review(self, run, question, response, wanted):
        """A run for the assistant to review the owner's answer, with the cards it blocks and their evidence."""
        assistant = self._assistant(wanted, True)
        record = {'id': run, 'action': 'report_decision', 'verb': None,
                  'label': {'en': 'Review owner answer', 'ar': 'مراجعة إجابة المالك'},
                  'inputs': {}, 'owner_decision': self._review_context(question, response), 'cards': question.get('blocks', []),
                  'assistant': None if assistant == 'handoff' else assistant,
                  'mode': 'handoff' if assistant == 'handoff' else 'assistant', 'state': 'queued',
                  'attempt': 1, 'created': now('milliseconds'), 'queued_at': now('milliseconds'), 'read': False}
        self.store.save(record, new=True)
        self.store.append(run, 'action', record['label'], {'action': 'report_decision', 'by': 'person'})

    def _review_context(self, question, response):
        """What the review reads: the question, the owner's answer, the cards it blocks and their evidence."""
        blocked = self._blocked_cards(question)
        evidence_ids = {e for c in blocked for e in c.get('evidence', []) if isinstance(e, str)}
        facts = (selecting._load(self._studio(), 'evidence') or {}).get('facts', [])
        return {'question': question, 'answer': response,
                'evidence': [f for f in facts if f.get('id') in evidence_ids][:40],
                'project': self.project.name, 'report': Path(self._studio()).parent.name,
                'blocked_cards': [{'id': c['id'], 'title': c.get('title'), 'paths': c.get('paths'), 'evidence': c.get('evidence')} for c in blocked]}

    def _blocked_cards(self, question):
        """The cards of the latest check that wait for the answer to `question`."""
        return [c for c in (selecting._load(self._studio(), 'cards') or {}).get('cards', []) if c['id'] in question.get('blocks', [])]

    def _merge_choice(self, body):
        """Where Accept merges, as the person chose in its sheet (one of their branches, never a protected one), and
        whether the branch is kept after merging."""
        chosen = {}
        target = str(body.get('merge_into') or '').strip()
        if target:
            from .branches import valid_name
            valid_name(self.project, target)
            if not self.branches.tip(f'refs/heads/{target}'): raise LookupError(f'no branch named {target} to merge into')
            reason = self.branches.blocked_target(target)
            if reason: raise Refused(409, f"{target} is protected ({reason['en']}): choose another branch to merge into", reasons=[reason])
            chosen['merge_into'] = target
        if body.get('delete_after') is False: chosen['delete_after'] = False
        return chosen

    def decide(self, run, operation, body):
        """Accept or undo the branch a run handed over: only with the confirm token of that preview."""
        if not self.locks.spend(body.get('confirm'), operation, None, self.project):
            raise Refused(403, f'{operation} needs your explicit confirmation: open its preview and confirm', needs='confirm')
        record = self.store.load(run)
        branch = (record.get('result') or {}).get('branch')
        if not branch: raise LookupError('this run handed no branch over')
        if record.get('outcome'): raise LookupError(f"this run's branch was already {record['outcome']}")
        # accept and undo act on the newest waiting branch: refuse when that is not this run's, so a decision on one
        # run never takes in or throws away another run's work
        newest = self.manager.newest_waiting()
        if newest != branch:
            raise LookupError(f'another branch ({newest}) waits after {branch}: decide that one first' if newest else f'{branch} is not waiting for a decision any more')
        # Accept merges where the person chose in its sheet (one of their branches, never a protected one) and deletes the
        # branch after merging unless they unticked it
        chosen = self._merge_choice(body) if operation == 'accept' else {}
        self.store.append(run, 'action', {'en': f'You chose to {operation} {branch}', 'ar': f"اخترت {'اعتماد' if operation == 'accept' else 'رمي'} {branch}"},
                          {'action': operation, 'by': 'person', 'arguments': {'branch': branch, **chosen}})
        result = self.manager.call(operation, {'person_agreed': True, **chosen})
        self._decided(run, operation, branch, result)
        return {'run': self.public(self.store.load(run)), 'result': result}

    def _decided(self, run, operation, branch, result):
        """What the accept or undo came to, in the run: its result and outcome, or why it did not happen."""
        ok = isinstance(result, dict) and not result.get('error') and result.get('status') == {'accept': 'accepted', 'undo': 'undone'}[operation]
        self.store.append(run, 'result' if ok else 'error', _decision_words(operation, branch, ok, result),
                          {'branch': branch, 'outcome': operation if ok else None, 'answer': result} if ok else
                          {'reason': str(result.get('status') or result.get('error')), 'recoverable': True,
                           'what_now': {'en': str(result.get('what_now') or ''), 'ar': str(result.get('what_now') or '')}})
        if ok: self.store.update(run, outcome={'accept': 'accepted', 'undo': 'undone'}[operation], decided=now('milliseconds'))

"""The person's answers to a run's questions (eaos/interfaces/studio/runs.py): checked, recorded, and acted on:
the step runs again, the assistant resumes with the answer, or a custom answer goes to an assistant."""
import fcntl
import threading

from ...journeys import guided
from ...ai import prompts
from ...core.store import now


class Answers:
    """The run manager's questions and their answers."""
    def _restore_question(self, run):
        record = self.store.load(run)
        pending = record.get('pending_question')
        if not pending: return False
        self.store.update(run, mode=pending['mode'], assistant=pending['assistant'],
                          pending_question=None, owner_decision=None, session=pending.get('session'))
        self._ask(run, pending['question'])
        return True

    def _ask(self, run, question):
        record = self.store.load(run)
        number = len(record.get('questions') or []) + 1
        question = {**question, 'id': f'{run}-q{number}', 'run': run, 'asked': now()}
        self.store.append(run, 'question', question['text'], question)
        self.set_state(run, 'waiting_for_person', 'a question', question=question, questions=(record.get('questions') or []) + [question['id']])

    def answer(self, question_id, option=None, text=None, via='studio'):
        with self._mutex, (self.store.folder / 'question-answer.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            run = str(question_id).rsplit('-q', 1)[0]
            record = self.store.load(run)
            previous = next((a for a in record.get('answered', []) if a['id'] == question_id), None)
            if previous:
                if previous['option'] == option and previous.get('text') == text: return record
                raise LookupError('this question already has an owner answer')
            return self._answer(question_id, option, text, via)

    def _answer(self, question_id, option=None, text=None, via='studio'):
        run, record, question = self._checked(question_id, option, text)
        option = prompts.picked(record, question, option, text)          # words act on a direct step's question too
        label = (next((o for o in question.get('options') or [] if o['id'] == option), None) or {}).get('label') or {'en': text or '', 'ar': text or ''}
        self.store.append(run, 'answer', {'en': f"You answered {prompts.WHERE[via]['en']}: {label['en']}", 'ar': f"جاوبت {prompts.WHERE[via]['ar']}: {label['ar']}"},
                          {'question': question_id, 'option': option, 'text': text, 'by': 'person', 'via': via})
        self.store.update(run, question=None, answered=(record.get('answered') or []) + [{'id': question_id, 'option': option, 'text': text, 'at': now()}])
        self.set_state(run, 'running', 'answered')
        if option is None and prompts.binding(record, question): return self._custom_answer(run, record, question, text)
        if question.get('why') == 'branch':
            # The person picked the branch in the Studio (their own press, behind the token, CSRF and Origin checks): it
            # is recorded as their choice whoever asked, then the step runs again on that branch. Recorded for direct runs
            # only, an assistant asking it got the answer as text and status kept asking for the branch.
            self._choose_branch(option, label['en'])
        if record.get('mode') == 'direct': return self._direct_answer(run, record, question, option)
        done = self._act_on(run, question, option)
        adapter = self.adapters.get(record.get('assistant'))
        if adapter is None: self._fail(run, 'the assistant of this run is not available any more')
        else: threading.Thread(target=self._launch, args=(run, adapter, prompts.answer(question, option, text, self.lang, done, via), record.get('session')), daemon=True).start()
        return self.store.load(run)

    @staticmethod
    def _well_formed(option, text):
        if option is not None and text is not None: raise ValueError('send either an option or a custom answer, not both')
        if text is not None and (not isinstance(text, str) or not text.strip() or len(text) > 4000): raise ValueError('text must contain 1 to 4000 characters')

    def _checked(self, question_id, option, text):
        """(run, record, question) of the question waiting for this answer; an error when the answer cannot be taken."""
        self._well_formed(option, text)
        run = str(question_id).rsplit('-q', 1)[0]
        question = (record := self.store.load(run)).get('question') or {}
        if record.get('state') != 'waiting_for_person' or question.get('id') != question_id: raise LookupError('this question is not waiting for an answer')
        if option is not None and (not isinstance(option, str) or option not in {o['id'] for o in question.get('options', [])}): raise ValueError('invalid option')
        if option is None and not text: raise ValueError('choose one of the options')
        return run, record, question

    def _custom_answer(self, run, record, question, text):
        """A custom answer: the run's assistant, else the first one ready, takes it on; with none, the run is handed off."""
        assistant = record.get('assistant') or next((key for key, a in self.adapters.items() if a.available()), None)
        self.store.update(run, pending_question={'question': question, 'mode': record.get('mode'), 'assistant': record.get('assistant'), 'session': record.get('session')},
                          mode='assistant' if assistant else 'handoff', assistant=assistant, owner_decision={'question': question, 'answer': {'text': text}, 'requires_explicit_consent': True})
        target, args = (self._launch, (run, self.adapters[assistant], self.prompt_of(self.store.load(run)))) if assistant else (self._handoff, (run,))
        threading.Thread(target=target, args=args, daemon=True).start()
        return self.store.load(run)

    def _direct_answer(self, run, record, question, option):
        """A direct run: the step runs again (on the chosen branch, retried, without the assistant, or agreed), else it ends."""
        why, inputs = question.get('why'), dict(record.get('inputs') or {})
        if why == 'assistant' and option in ('retry', 'without_ai'):
            # asked again on retry; without_ai is this one check with the rules alone, the person's choice kept
            inputs['without_ai' if option == 'without_ai' else 'fixed'] = True       # an answer acts: never the same question again
        elif why == 'run consent' and option == 'yes': inputs['person_agreed'] = True
        elif why != 'branch':
            self.store.append(run, 'result', {'en': 'Nothing was done: you said no.', 'ar': 'ما سوينا شي: قلت لا.'}, self._outcome(run))
            self.set_state(run, 'done')
            return self.store.load(run)
        if why != 'branch': self.store.update(run, inputs=inputs)
        threading.Thread(target=self._direct, args=(run,), daemon=True).start()
        return self.store.load(run)

    def _act_on(self, run, question, option):
        """The answer acts: an option that means closing the open batch (prompts.acts) runs fix_abandon here, before the
        assistant resumes, so "yes, close it" closes it even though the assistant's own tools may not reach it."""
        action = prompts.acts(question, option)
        if not action: return None
        try: result = self.call(action, {})
        except Exception as problem: result = {'error': f'{type(problem).__name__}: {problem}'}
        failed = isinstance(result, dict) and result.get('error')
        self.store.append(run, 'step', {'en': f"{self.labels[action]['en']}: done, as you answered" if not failed else f"{self.labels[action]['en']}: it did not happen ({str(failed)[:200]})",
                                        'ar': f"{self.labels[action]['ar']}: تم، مثل ما جاوبت" if not failed else f"{self.labels[action]['ar']}: ما تم ({str(failed)[:200]})"},
                          {'tool': action, 'by': 'person'})
        return action, result

    def _choose_branch(self, branch, said):
        from ...journeys import agent_tools
        guided.choose(agent_tools.state_of(str(self.project)), branch, said, via='studio')

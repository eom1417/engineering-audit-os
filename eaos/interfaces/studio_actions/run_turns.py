"""An assistant's turn in a run (eaos/interfaces/studio_actions/runs.py): started headless by its adapter, its stream read
into the run's events as it is written, and how the turn ends: a question, a failure, or the result."""
import os
import subprocess
import threading
import time

from ...ai.assistant import headless as adapters, prompts
from ...core.language.check import foreign, restate
from . import lane_assistants as helpers
from ...core.project.runs import now
from ...core.project import state as project_state

SAID = {'type': 'object', 'additionalProperties': False, 'required': ['text'], 'properties': {'text': {'type': 'string'}}}


def _read_from(path, offset):
    """What the file holds past `offset`, or None when it cannot be read."""
    try:
        with open(path, 'rb') as stream:
            stream.seek(offset)
            return stream.read()
    except OSError:
        return None


def _tried_card(kind, data):
    """The card an event says was tried (its gates ran, or it was skipped); None."""
    data = data or {}
    done = (kind == 'check' and data.get('name') == 'card gates') or (kind == 'step' and data.get('tool') == 'fix_skip')
    return data.get('card') if done else None


def _tried_in(wave, cards):
    """The cards of `cards` the open batch `wave` already kept or left out."""
    return {card for card in cards if card in (wave.get('kept') or {}) or card in (wave.get('failed') or {})}


def _last_answer(state, status, needed=None):
    """The last EAOS answer of the turn with `status` (and, when `needed` is named, that field filled); None."""
    return next((payload for tool, payload in reversed(state['eaos_results'])
                 if isinstance(payload, dict) and payload.get('status') == status and (needed is None or payload.get(needed))), None)


class Turns:
    """The run manager's assistant turns."""
    def _launch(self, run, adapter, prompt, session=None):
        folder = self.store.path(run)
        record = self._baseline(run)
        verb = next((v for v in self.contract['verbs'] if v['id'] == record.get('verb')), None)
        tools = [tool for tool in verb['tools'] if tool not in adapters.PERSON_ONLY] if verb else None
        if record.get('owner_decision') or record.get('review'): tools = ['status', 'overview', 'finding', 'findings', 'impact', 'structure']
        argv = adapter.argv(prompt, run, folder, session, tools=tools)
        stream = folder / 'stream.jsonl'
        offset = stream.stat().st_size if stream.is_file() else 0
        env = {**os.environ, 'EAOS_STUDIO_RUN': run, 'EAOS_STUDIO_LANG': self.lang}
        with open(stream, 'ab') as out, open(folder / 'stderr.log', 'ab') as err:
            process = subprocess.Popen(argv, cwd=self.project, stdout=out, stderr=err, stdin=subprocess.DEVNULL, env=env, start_new_session=True)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- an argument list, no shell: the adapter's own command
        self.children[run] = process
        self.store.update(run, pid=process.pid, offset=offset, turn_started=now(), turns=(record.get('turns') or 0) + 1)
        self._follow_assistant(run, adapter)

    def _follow_assistant(self, run, adapter):
        record = self.store.load(run)
        adapter = adapter or self.adapters.get(record.get('assistant'))
        if adapter is None: return self._fail(run, 'the assistant of this run is not available any more')
        self.watched.add(run)
        threading.Thread(target=self._read_stream, args=(run, adapter), daemon=True).start()

    def _ended(self, run, pid):
        """Whether the assistant's process of `run` has ended (a child of this process, or one a restart found alive)."""
        alive = helpers.alive
        return not (self.children[run].poll() is None if run in self.children else alive(pid))

    def _read_stream(self, run, adapter):
        folder = self.store.path(run)
        record = self.store.load(run)
        offset, pid = record.get('offset') or 0, record.get('pid')
        state = adapter.new_state()
        state['cards_tried'] = self._count_on(run, record)
        state['session'] = record.get('session')
        state['resumed'] = bool(record.get('session'))     # this turn resumes the assistant's session with an answer
        buffer = b''
        try:
            while True:
                finished = self._ended(run, pid)
                chunk = _read_from(folder / 'stream.jsonl', offset)
                if chunk is None: return
                offset += len(chunk)
                buffer += chunk
                *lines, buffer = buffer.split(b'\n')
                self._parse_lines(run, record, adapter, state, lines)
                if lines: self.store.update(run, offset=offset - len(buffer), session=state['session'])
                if finished and not chunk:
                    if buffer.strip():
                        self._record(run, record, adapter.parse(buffer.decode('utf-8', 'replace'), state, self.labels), state)
                    break
                if self._closed.is_set(): return
                time.sleep(0.2)
            code = self.children.pop(run).returncode if run in self.children else None
            self.store.update(run, offset=offset, session=state['session'], pid=None)
            self._end_turn(run, state, code)
        finally:
            self.watched.discard(run)

    def _parse_lines(self, run, record, adapter, state, lines):
        """Each non-empty line of the assistant's stream, parsed by its adapter, into the run."""
        for line in lines:
            text = line.decode('utf-8', 'replace').strip()
            if not text: continue
            self._record(run, record, adapter.parse(text, state, self.labels), state)
        helpers.after(self, run, state)

    def _record(self, run, record, parsed, state):
        """The assistant's events into the run. A Fix run's progress is its batch: the cards tried (kept, taken back or
        skipped) of the cards it was given, never a job's or the project's own count."""
        fixing = record.get('verb') == 'fix' and record.get('cards')
        for kind, words, data, detail in parsed:
            if fixing and kind == 'progress': continue
            self.store.append(run, kind, words, data, detail)
            card = _tried_card(kind, data)
            if fixing and card in record['cards'] and card not in state['cards_tried']:
                state['cards_tried'].add(card)
                self._cards_progress(run, state['cards_tried'], record['cards'])

    def _count_on(self, run, record):
        """A Fix run's cards its open batch already tried (kept or left out), whichever turn or assistant tried them:
        a retry, or another assistant, counts on from there."""
        wave = (project_state.load(self.project) or {}).get('open_wave') or {}
        cards = record.get('cards') or [] if record.get('verb') == 'fix' else []
        tried = _tried_in(wave, cards)
        if tried: self._cards_progress(run, tried, cards)
        return tried

    def _cards_progress(self, run, tried, cards):
        self.store.append(run, 'progress', {'en': f'{len(tried)} of {len(cards)} cards tried', 'ar': f'جُرّبت {len(tried)} من {len(cards)} بطاقات'},
                          {'batch': None, 'done': len(tried), 'total': len(cards), 'stage': 'cards'})

    def _end_turn(self, run, state, code):
        record = self.store.load(run)
        if record.get('state') in ('stopped',): return
        words = state.get('final') or '\n'.join(state.get('texts') or [])
        if record.get('pending_question') and not state.get('failed') and code in (0, None):
            self.store.append(run, 'result', {'en': 'Clarification finished; your explicit answer is still needed', 'ar': 'انتهى التوضيح؛ ما زالت إجابتك الصريحة مطلوبة'}, {'answer': words})
            return self._restore_question(run)
        question = self._question_for(record, state, words)
        if question: return self._ask(run, question)
        if (why := self._why_stopped(run, state, code, words)): return self._fail(run, why, resumable=True)
        return self._finish_turn(run, record, words)

    def _why_stopped(self, run, state, code, words):
        """Why the turn failed (the assistant said it, or stopped with an error and no words, then its last stderr);
        None when it did not."""
        if not (state.get('failed') or (code not in (0, None) and not words)): return None
        reason = state.get('failed') or f'the assistant stopped with code {code}'
        try: tail = (self.store.path(run) / 'stderr.log').read_text(encoding='utf-8', errors='replace')[-600:]
        except OSError: tail = ''
        return self.store.scrub(str(reason))[:500] + (f' ({self.store.scrub(tail.strip())[-300:]})' if tail.strip() and not state.get('failed') else '')

    def _finish_turn(self, run, record, words):
        payload = self._outcome(run, answer=self._readable(run, words))
        if record.get('verb') == 'fix' and not payload.get('branch') and not payload.get('cards_closed') and not record.get('lane'):
            # a Fix run that handed nothing over did not succeed, whatever the assistant said; nor did it break anything:
            # it ends unchanged, and the person reads why and what to do
            self.store.append(run, 'result', {'en': "Nothing changed: no fix was kept, so no branch waits for you. Read the assistant's words for why, then try again or pick other cards.",
                                              'ar': 'ما تغيّر شي: ما انقبل أي إصلاح، فما فيه فرع ينتظرك. اقرأ كلام المساعد لتعرف السبب، ثم أعد المحاولة أو اختر بطاقات ثانية.'}, {**payload, 'nothing_changed': True})
            return self.set_state(run, 'unchanged', 'nothing changed', result={**payload, 'nothing_changed': True})
        self.store.append(run, 'result', {'en': 'Done' + (f": the branch {payload['branch']} waits for you" if payload.get('branch') else
                                                          f": the fixes are on {payload['landed_on']} itself" if payload.get('landed_on') else ''),
                                          'ar': 'تم' + (f": الفرع {payload['branch']} ينتظرك" if payload.get('branch') else
                                                        f": الإصلاحات صارت في {payload['landed_on']} نفسه" if payload.get('landed_on') else '')}, payload)
        self.set_state(run, 'done', result=payload)
        self._auto_accept(run, payload)

    def _question_for(self, record, state, words):
        """The question a turn ends on: the assistant's own; else the branch, the person's to choose (choose_branch is
        person-only), asked by the Studio so the answer is recorded first; else the agreement to run the app."""
        question = prompts.question_in(words)
        branch = question is None and _last_answer(state, 'needs_branch', 'branches')
        if question is not None or branch: return question if question is not None else prompts.branch_question(branch)
        asked = _last_answer(state, 'needs_agreement')
        if asked and not self._waiting_branches() - set(record.get('branches_before') or []): return prompts.consent_question(asked)

    def _readable(self, run, words):
        """The assistant's last words in the person's language: asked of it again once when they are not (eaos/core/language/check.py)."""
        adapter = self.adapters.get(self.store.load(run).get('assistant'))
        if not foreign(words, self.lang) or adapter is None: return words
        try: said = adapters.ask(adapter, restate({'text': words}, [words], self.lang), SAID, self.store.path(run) / 'language')
        except Exception: return words
        return str((said['answer'] or {}).get('text') or words)

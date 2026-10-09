"""The run manager: the queue, the one run at a time, the assistant's process, its questions, and the way back after a restart.

A run is `direct` (EAOS's own tool, called here, its job followed for progress), `assistant` (the person's assistant
started headless by its adapter, its output read into events), or `handoff` (no assistant here: the request waits for
the next `status` call). One run per project is running, paused or waiting for the person at a time; the rest wait in
the queue in the person's order. Only the server that holds the project's `dispatch.lock` starts runs, so two Studio
servers never start the same one. Everything a run is lives on disk (eaos/studio/actions/store.py): a restarted server
goes on reading an assistant that is still alive, follows a job that is still running, and says plainly which run
stopped with the server.
"""
import fcntl
import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

from . import adapters, handoff, prompts
from .store import ACTIVE, TERMINAL, now

STUDIO = 'EAOS Studio'                      # eaos/mcp_server.py STUDIO

STOP_GRACE = 5
# Studio actions that are not an MCP tool: the planner of the ideal, which asks the person's assistant itself
# (eaos/studio/ideal.py, docs/STUDIO.md D10).
PLANNERS = ('replan_ideal', 'run_nodes')


def alive(pid):
    if not pid: return False
    try: os.kill(int(pid), 0)
    except ProcessLookupError: return False
    except PermissionError: return True
    try:
        done, _ = os.waitpid(int(pid), os.WNOHANG)
        return done == 0
    except ChildProcessError:
        return True


def _signal(pid, number):
    try: os.killpg(os.getpgid(int(pid)), number)
    except (ProcessLookupError, PermissionError, OSError):
        try: os.kill(int(pid), number)
        except (ProcessLookupError, PermissionError, OSError): pass


TEXT = {
    'queued': ({'en': 'Waiting its turn', 'ar': 'ينتظر دوره'}),
    'running': ({'en': 'Running', 'ar': 'يشتغل'}),
    'paused': ({'en': 'Paused', 'ar': 'متوقف مؤقتًا'}),
    'waiting_for_person': ({'en': 'Waiting for you', 'ar': 'ينتظرك'}),
    'done': ({'en': 'Done', 'ar': 'انتهى'}),
    'failed': ({'en': 'Did not finish', 'ar': 'ما اكتمل'}),
    'stopped': ({'en': 'Stopped', 'ar': 'أوقفته'}),
}


class Manager:
    def __init__(self, project, store, adapters, contract, tools, lang='ar'):
        self.project = Path(project).resolve()
        self.store = store
        self.adapters = adapters
        self.contract = contract
        self.actions = {action['id']: action for action in contract['actions']}
        self.labels = {action['id']: action['label'] for action in contract['actions']}
        self.tools = tools                              # name -> callable returning the MCP tool's JSON text
        self.lang = lang
        self.children = {}                              # run -> Popen started by this process
        self.watched = set()                            # runs a thread of this process follows
        self.cancels = {}                               # run -> threading.Event of a planner run
        self._lockfile = None
        self._closed = threading.Event()
        self._mutex = threading.RLock()
        self.thread = threading.Thread(target=self._loop, name=f'eaos-runs-{self.project.name}', daemon=True)
        self.thread.start()

    # lifecycle helpers
    def set_state(self, run, to, why='', **fields):
        with self._mutex:
            record = self.store.load(run)
            before = record.get('state')
            record.update(fields, state=to)
            if to == 'running' and not record.get('started'): record['started'] = now()
            if to in TERMINAL: record['ended'] = now()
            self.store.save(record)
        if before != to:
            self.store.append(run, 'state', {'en': TEXT[to]['en'] + (f': {why}' if why else ''), 'ar': TEXT[to]['ar'] + (f': {why}' if why else '')},
                              {'from': before, 'to': to, 'why': why})
        return record

    def close(self):
        self._closed.set()
        if self._lockfile:
            try: fcntl.flock(self._lockfile, fcntl.LOCK_UN); self._lockfile.close()
            except OSError: pass
            self._lockfile = None

    # the dispatcher
    def _hold(self):
        if self._lockfile: return True
        try:
            handle = open(self.store.folder / 'dispatch.lock', 'r+')     # made by the Store; a deleted folder stays deleted
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            try: handle.close()
            except NameError: pass
            return False
        self._lockfile = handle
        self.recover()
        return True

    def _loop(self):
        while not self._closed.is_set():
            if not self.store.folder.is_dir(): return
            try:
                if self._hold(): self.dispatch()
            except Exception:                           # a broken run must not stop the queue; it is marked on its own
                pass
            self.store.wait_change(0.5)

    def dispatch(self):
        with self._mutex:
            rows = self.store.all()
            if any(row.get('state') in ACTIVE for row in rows if not row.get('read')): return
            queue = self.store.queue()
            if not queue: return
            run = queue[0]
            self.set_state(run, 'running', attempt=self.store.load(run).get('attempt') or 1)
        threading.Thread(target=self._start, args=(run,), daemon=True).start()

    def recover(self):
        """At the start of the dispatcher: runs this server cannot follow any more are said to have stopped, the rest followed."""
        for record in self.store.all():
            run, state = record['id'], record.get('state')
            if state not in ('running', 'paused') or run in self.watched: continue
            if record.get('mode') == 'assistant' and alive(record.get('pid')):
                self._follow_assistant(run, None)
            elif record.get('mode') == 'direct' and record.get('job') and self._job_running(record['job']):
                threading.Thread(target=self._follow_job, args=(run, record['job']), daemon=True).start()
            elif record.get('mode') == 'handoff':
                threading.Thread(target=self._watch_handoff, args=(run,), daemon=True).start()
            else:
                self.store.append(run, 'error', {'en': 'The Studio server stopped while this ran, and the work did not finish. Try it again.',
                                                 'ar': 'خادم الاستوديو توقف أثناء التشغيل، وما اكتمل الشغل. أعد المحاولة.'},
                                  {'reason': 'server restarted', 'recoverable': True,
                                   'what_now': {'en': 'Press Retry.', 'ar': 'اضغط «أعد».'}})
                self.set_state(run, 'failed', 'the server restarted')
        for record in self.store.all():
            if record.get('state') == 'waiting_for_person' and record.get('mode') == 'handoff' and record['id'] not in self.watched:
                threading.Thread(target=self._watch_handoff, args=(record['id'],), daemon=True).start()

    # starting
    def _start(self, run):
        record = self.store.load(run)
        try:
            if record.get('action') == 'run_nodes': return self._run_nodes(run)
            if record.get('action') in PLANNERS: return self._plan_ideal(run)
            if record['mode'] == 'direct': return self._direct(run)
            if record['mode'] == 'handoff': return self._handoff(run)
            adapter = self.adapters.get(record.get('assistant'))
            if adapter is None or not adapter.available():
                self.store.append(run, 'step', {'en': 'No assistant can be started here: the request goes to your assistant\'s next session.',
                                                'ar': 'ما فيه مساعد يقدر يشتغل هنا: الطلب يروح لمساعدك في جلسته الجاية.'}, {'tool': None})
                self.store.update(run, mode='handoff')
                return self._handoff(run)
            self._launch(run, adapter, self.prompt_of(record))
        except Exception as problem:
            self._fail(run, f'{type(problem).__name__}: {problem}')

    def prompt_of(self, record):
        return prompts.build(record.get('verb'), record.get('cards_detail') or [], self.project, self.lang,
                             action=record.get('action'), inputs=record.get('inputs'), labels=self.labels)

    def _fail(self, run, reason, what_now=None):
        self.store.append(run, 'error', {'en': f'It could not go on: {reason}', 'ar': f'ما قدر يكمل: {reason}'},
                          {'reason': reason, 'recoverable': True, 'what_now': what_now or {'en': 'Press Retry, or look at the detail.', 'ar': 'اضغط «أعد»، أو شوف التفاصيل.'}})
        if self.store.load(run).get('state') not in TERMINAL: self.set_state(run, 'failed', reason[:200])

    # the planned ideal
    def _plan_ideal(self, run):
        """Re-plan the ideal of the latest check with the run's assistant (or the first one available): its steps are the
        run's events, stop kills it, and a failure leaves the rules' target in place. The Studio's data is published again
        from the ledger, so every page shows the new ideal."""
        from ... import guided
        from .. import ideal
        from .selection import studio_folder
        studio = studio_folder(self.project)
        report = studio.parent if studio else None
        if report is None or not (report / 'target-architecture.json').is_file():
            return self._fail(run, 'there is no check to plan from yet', {'en': 'Run the check first, then re-plan the ideal.',
                                                                          'ar': 'شغّل الفحص أولًا، ثم أعد تخطيط المثالي.'})
        wanted = self.store.load(run).get('assistant')
        adapters = {wanted: self.adapters[wanted]} if wanted in self.adapters else self.adapters
        cancel = self.cancels[run] = threading.Event()
        say = lambda en, ar: self.store.append(run, 'step', {'en': en, 'ar': ar}, {'tool': 'replan_ideal'})
        try:
            result = ideal.plan(report, project=self.project, lang=self.lang, adapters=adapters, cancel=cancel,
                                started=lambda pid: self.store.update(run, pid=pid), say=say)
        finally:
            self.cancels.pop(run, None)
            self.store.update(run, pid=None)
        if self.store.load(run).get('state') in TERMINAL: return
        words = result['message']
        if result['state'] != 'planned':
            return self._fail(run, words['ar' if self.lang == 'ar' else 'en'],
                              {'en': 'The rules\' target stays in place. Press Retry, or log in to Claude Code or Codex first.',
                               'ar': 'يبقى هدف القواعد مكانه. اضغط «أعد»، أو سجّل الدخول في Claude Code أو Codex أولًا.'})
        try: guided.publish(guided.load(self.project), self.lang)
        except Exception as problem:
            say(f'The Studio data could not be refreshed: {type(problem).__name__}', f'ما قدرت أحدّث بيانات الاستوديو: {type(problem).__name__}')
        payload = {**self._outcome(run, answer=words['ar' if self.lang == 'ar' else 'en']),
                   'ideal': {'elements': result['elements'], 'dropped': len(result['dropped']), 'share': result['share'],
                             'departures': len(result['departures']), 'questions': len(result['open_questions']),
                             'assistant': result['assistant'], 'model': result['model']}}
        self.store.append(run, 'result', {'en': f"The ideal is planned: {result['elements']} elements, each with its evidence",
                                          'ar': f"تم تخطيط المثالي: {result['elements']} عنصرًا، كل واحد بدليله"}, payload)
        self.set_state(run, 'done', result=payload)

    # the AI nodes
    def _run_nodes(self, run):
        """Run the AI nodes on the latest check (docs/STUDIO.md D11) with the run's assistant: each node's steps are the
        run's events, the last batch of fixes is the fix reviewer's input, and the Studio's data is published again so the
        pipeline map, the cards and the inbox show the decisions. Without an assistant every node decides by the rules."""
        from ... import guided
        from .. import nodes
        from .selection import studio_folder
        studio = studio_folder(self.project)
        report = studio.parent if studio else None
        if report is None or not (report / 'plan.json').is_file():
            return self._fail(run, 'there is no check for the AI nodes to read yet', {'en': 'Run the check first, then the AI nodes.',
                                                                                      'ar': 'شغّل الفحص أولًا، ثم عُقد الذكاء.'})
        record = self.store.load(run)
        inputs = record.get('inputs') or {}
        names = inputs.get('nodes') or [n.name for n in nodes.NODES if n.name != 'ideal_planner']
        wanted = record.get('assistant')
        adapters = {wanted: self.adapters[wanted]} if wanted in self.adapters else self.adapters
        wave = None
        try:
            state = guided.load(self.project)
            if state.get('waves'): wave = guided.runtime_of(state) / 'waves' / f"wave-{len(state['waves'])}"
        except Exception:
            wave = None
        cancel = self.cancels[run] = threading.Event()
        say = lambda en, ar: self.store.append(run, 'step', {'en': en, 'ar': ar}, {'tool': 'run_nodes'})
        try:
            records = nodes.run(report, names=names, adapters=adapters, project=self.project, lang=self.lang, fresh=bool(inputs.get('fresh')),
                                say=say, cancel=cancel, started=lambda pid: self.store.update(run, pid=pid), wave=wave)
        finally:
            self.cancels.pop(run, None)
            self.store.update(run, pid=None)
        if self.store.load(run).get('state') in TERMINAL: return
        try: guided.publish(guided.load(self.project), self.lang)
        except Exception as problem:
            say(f'The Studio data could not be refreshed: {type(problem).__name__}', f'ما قدرت أحدّث بيانات الاستوديو: {type(problem).__name__}')
        summary = {name: {'state': r['state'], 'method': r['method'], 'model': r['model'], 'cached': r['cached'],
                          'routes': {x['decision']: len(x['subjects']) for x in r['routes']}, 'dropped': len(r['dropped'])}
                   for name, r in records.items()}
        by_model = sum(r['method'] == 'model' for r in records.values())
        payload = {**self._outcome(run, answer=None), 'nodes': summary}
        self.store.append(run, 'result', {'en': f'{len(records)} AI nodes decided ({by_model} by your assistant, the rest by the rules only)',
                                          'ar': f'قرّرت {len(records)} عُقد ذكاء ({by_model} بمساعدك، والباقي بالقواعد فقط)'}, payload)
        self.set_state(run, 'done', result=payload)

    # direct calls
    def call(self, action, inputs):
        """An EAOS tool, as the MCP server runs it (its answer, its journal line, its handover): the parsed answer."""
        arguments = dict(inputs or {})
        if 'project' in (self.actions[action]['inputs'].get('properties') or {}): arguments['project'] = str(self.project)
        os.environ.setdefault('EAOS_ASSISTANT', STUDIO)
        text = self.tools()[action](**arguments)
        try: return json.loads(text)
        except (TypeError, ValueError): return {'answer': text}

    def _job_running(self, job):
        from ... import jobs
        try: return jobs.read(job)['status'] == 'running'
        except Exception: return False

    def _direct(self, run, follow=True):
        record = self.store.load(run)
        action = record['action']
        self.store.append(run, 'step', {'en': self.labels[action]['en'], 'ar': self.labels[action]['ar']}, {'tool': action})
        result = self.call(action, record.get('inputs'))
        if follow and isinstance(result, dict) and result.get('job') and result.get('status') in ('running', 'started', None):
            self.store.update(run, job=result['job'])
            return self._follow_job(run, result['job'])
        self._finish_direct(run, result)

    def _finish_direct(self, run, result):
        if self.store.load(run).get('state') in TERMINAL: return
        if isinstance(result, dict) and result.get('error'):
            return self._fail(run, str(result['error'])[:500], {'en': str(result.get('what_now') or 'Look at the detail.'), 'ar': str(result.get('what_now') or 'شوف التفاصيل.')})
        if isinstance(result, dict) and result.get('status') == 'needs_agreement':
            question = prompts.consent_question(result)
            return self._ask(run, question)
        payload = self._outcome(run, answer=result)
        self.store.append(run, 'result', {'en': 'Done', 'ar': 'تم'}, payload)
        self.set_state(run, 'done', result=payload)

    def _follow_job(self, run, job):
        from ... import jobs
        self.watched.add(run)
        try:
            seen = None
            while not self._closed.is_set():
                if self.store.load(run).get('state') in TERMINAL: return
                try: record = jobs.read(job)
                except ValueError as problem: return self._fail(run, str(problem))
                progress = record.get('progress') or {}
                if progress and progress != seen:
                    seen = progress
                    self.store.append(run, 'progress', {'en': f"{progress.get('stage') or record['kind']}: {progress.get('done')} of {progress.get('total')}",
                                                        'ar': f"{progress.get('stage') or record['kind']}: {progress.get('done')} من {progress.get('total')}"},
                                      {'batch': None, 'done': progress.get('done'), 'total': progress.get('total'), 'stage': progress.get('stage')})
                if record['status'] == 'done': return self._finish_direct(run, record.get('result') or {})
                if record['status'] == 'failed': return self._fail(run, str(record.get('error') or 'the job failed')[:500])
                time.sleep(1)
        finally:
            self.watched.discard(run)

    # the assistant
    def _launch(self, run, adapter, prompt, session=None):
        folder = self.store.path(run)
        record = self.store.load(run)
        if not record.get('branches_before'):
            self.store.update(run, branches_before=sorted(self._waiting_branches()))
        verb = next((v for v in self.contract['verbs'] if v['id'] == record.get('verb')), None)
        tools = [tool for tool in verb['tools'] if tool not in adapters.PERSON_ONLY] if verb else None
        argv = adapter.argv(prompt, run, folder, session, tools=tools)
        stream = folder / 'stream.jsonl'
        offset = stream.stat().st_size if stream.is_file() else 0
        env = {**os.environ, 'EAOS_STUDIO_RUN': run}
        with open(stream, 'ab') as out, open(folder / 'stderr.log', 'ab') as err:
            process = subprocess.Popen(argv, cwd=self.project, stdout=out, stderr=err, stdin=subprocess.DEVNULL, env=env, start_new_session=True)
        self.children[run] = process
        self.store.update(run, pid=process.pid, offset=offset, turn_started=now(), turns=(record.get('turns') or 0) + 1)
        self._follow_assistant(run, adapter)

    def _follow_assistant(self, run, adapter):
        record = self.store.load(run)
        adapter = adapter or self.adapters.get(record.get('assistant'))
        if adapter is None: return self._fail(run, 'the assistant of this run is not available any more')
        self.watched.add(run)
        threading.Thread(target=self._read_stream, args=(run, adapter), daemon=True).start()

    def _read_stream(self, run, adapter):
        folder = self.store.path(run)
        record = self.store.load(run)
        offset, pid = record.get('offset') or 0, record.get('pid')
        state = adapter.new_state()
        state['session'] = record.get('session')
        state['resumed'] = bool(record.get('session'))     # this turn resumes the assistant's session with an answer
        buffer = b''
        try:
            while True:
                finished = not (self.children[run].poll() is None if run in self.children else alive(pid))
                try:
                    with open(folder / 'stream.jsonl', 'rb') as stream:
                        stream.seek(offset)
                        chunk = stream.read()
                except OSError:
                    return
                offset += len(chunk)
                buffer += chunk
                *lines, buffer = buffer.split(b'\n')
                for line in lines:
                    text = line.decode('utf-8', 'replace').strip()
                    if not text: continue
                    for kind, words, data, detail in adapter.parse(text, state, self.labels):
                        self.store.append(run, kind, words, data, detail)
                if lines: self.store.update(run, offset=offset - len(buffer), session=state['session'])
                if finished and not chunk:
                    if buffer.strip():
                        for kind, words, data, detail in adapter.parse(buffer.decode('utf-8', 'replace'), state, self.labels):
                            self.store.append(run, kind, words, data, detail)
                    break
                if self._closed.is_set(): return
                time.sleep(0.2)
            code = self.children.pop(run).returncode if run in self.children else None
            self.store.update(run, offset=offset, session=state['session'], pid=None)
            self._end_turn(run, state, code)
        finally:
            self.watched.discard(run)

    def _end_turn(self, run, state, code):
        record = self.store.load(run)
        if record.get('state') in ('stopped',): return
        words = state.get('final') or '\n'.join(state.get('texts') or [])
        question = prompts.question_in(words)
        if question is None:
            asked = next((payload for tool, payload in reversed(state['eaos_results'])
                          if isinstance(payload, dict) and payload.get('status') == 'needs_agreement'), None)
            if asked and not self._waiting_branches() - set(record.get('branches_before') or []):
                question = prompts.consent_question(asked)
        if question: return self._ask(run, question)
        if state.get('failed') or (code not in (0, None) and not words):
            reason = state.get('failed') or f'the assistant stopped with code {code}'
            tail = ''
            try: tail = (self.store.path(run) / 'stderr.log').read_text(encoding='utf-8', errors='replace')[-600:]
            except OSError: pass
            return self._fail(run, self.store.scrub(str(reason))[:500] + (f' ({self.store.scrub(tail.strip())[-300:]})' if tail.strip() and not state.get('failed') else ''))
        payload = self._outcome(run, answer=words)
        self.store.append(run, 'result', {'en': 'Done' + (f": the branch {payload['branch']} waits for you" if payload.get('branch') else ''),
                                          'ar': 'تم' + (f": الفرع {payload['branch']} ينتظرك" if payload.get('branch') else '')}, payload)
        self.set_state(run, 'done', result=payload)

    def _ask(self, run, question):
        record = self.store.load(run)
        number = len(record.get('questions') or []) + 1
        question = {**question, 'id': f'{run}-q{number}', 'run': run, 'asked': now()}
        self.store.append(run, 'question', question['text'], question)
        self.set_state(run, 'waiting_for_person', 'a question', question=question, questions=(record.get('questions') or []) + [question['id']])

    def answer(self, question_id, option=None, text=None):
        run = str(question_id).rsplit('-q', 1)[0]
        record = self.store.load(run)
        question = record.get('question') or {}
        if record.get('state') != 'waiting_for_person' or question.get('id') != question_id:
            raise LookupError('this question is not waiting for an answer')
        if question.get('options') and option not in {o['id'] for o in question['options']} and not text:
            raise ValueError('choose one of the options')
        chosen = next((o for o in question.get('options') or [] if o['id'] == option), None)
        label = (chosen or {}).get('label') or {'en': text or '', 'ar': text or ''}
        self.store.append(run, 'answer', {'en': f"You answered: {label['en']}", 'ar': f"جاوبت: {label['ar']}"},
                          {'question': question_id, 'option': option, 'text': text, 'by': 'person'})
        self.store.update(run, question=None, answered=(record.get('answered') or []) + [{'id': question_id, 'option': option, 'text': text, 'at': now()}])
        self.set_state(run, 'running', 'answered')
        if record.get('mode') == 'direct':
            if question.get('why') == 'run consent' and option == 'yes':
                inputs = {**(record.get('inputs') or {}), 'person_agreed': True}
                self.store.update(run, inputs=inputs)
                threading.Thread(target=self._direct, args=(run,), daemon=True).start()
            else:
                self.store.append(run, 'result', {'en': 'Nothing was done: you said no.', 'ar': 'ما سوينا شي: قلت لا.'}, self._outcome(run))
                self.set_state(run, 'done')
            return self.store.load(run)
        adapter = self.adapters.get(record.get('assistant'))
        if adapter is None: self._fail(run, 'the assistant of this run is not available any more')
        else: threading.Thread(target=self._launch, args=(run, adapter, prompts.answer(question, option, text, self.lang), record.get('session')), daemon=True).start()
        return self.store.load(run)

    # the handoff
    def _handoff(self, run):
        record = self.store.load(run)
        prompt = self.prompt_of(record)
        handoff.add(self.project, run, prompt, record.get('label') or {})
        request = handoff.request_text(prompt, run)
        self.store.append(run, 'step', {'en': 'Waiting for your assistant: copy the request to it, or open it in this project; its next status call takes it.',
                                        'ar': 'ينتظر مساعدك: انسخ الطلب له، أو افتحه في هذا المشروع؛ أول ما يطلب status يستلمه.'},
                          {'tool': None, 'handoff': True, 'request': request})
        self.set_state(run, 'waiting_for_person', 'the assistant handoff', handoff=request)
        self._watch_handoff(run)

    def _watch_handoff(self, run):
        from ... import guided
        from ...handover import entries
        self.watched.add(run)
        seen = None
        try:
            while not self._closed.is_set():
                record = self.store.load(run)
                if record.get('state') in TERMINAL: return handoff.drop(self.project, run)
                row = handoff.get(self.project, run)
                if row is None:
                    if handoff.exists(self.project): self._fail(run, 'the request was removed')
                    return                                  # the project's EAOS workspace is gone with it
                if row['state'] in ('taken', 'done') and record.get('state') == 'waiting_for_person':
                    self.store.append(run, 'step', {'en': f"{row['taken_by']} took the request", 'ar': f"{row['taken_by']} استلم الطلب"}, {'tool': 'status', 'by': row['taken_by']})
                    self.set_state(run, 'running', 'taken')
                    seen = row['taken_at']
                if seen:
                    state = guided.load(self.project)
                    for entry in entries(state) if state else []:
                        if (entry.get('at') or '') > seen:
                            seen = entry['at']
                            tool = entry.get('tool')
                            label = self.labels.get(tool) or {'en': tool or 'note', 'ar': tool or 'ملاحظة'}
                            self.store.append(run, 'step', {'en': f"{entry.get('by')}: {label['en']}" + (f" {entry.get('card')}" if entry.get('card') else ''),
                                                            'ar': f"{entry.get('by')}: {label['ar']}" + (f" {entry.get('card')}" if entry.get('card') else '')},
                                              {'tool': tool, 'card': entry.get('card')}, entry.get('outcome') or entry.get('text'))
                if row['state'] == 'done':
                    payload = self._outcome(run, answer=row.get('done'))
                    self.store.append(run, 'result', {'en': 'Your assistant finished the request', 'ar': 'مساعدك خلّص الطلب'}, payload)
                    self.set_state(run, 'done', result=payload)
                    return handoff.drop(self.project, run)
                time.sleep(1)
        finally:
            self.watched.discard(run)

    # the outcome
    def _waiting_branches(self):
        from ... import guided
        state = guided.load(self.project) or {}
        return {wave['branch'] for wave in state.get('waves') or [] if wave.get('status') == 'applied' and wave.get('branch')}

    def _outcome(self, run, answer=None):
        """The result event's data: the new branch, its diff and its checks, the cards it closes, and the assistant's words."""
        from ... import guided
        record = self.store.load(run)
        state = guided.load(self.project) or {}
        before = set(record.get('branches_before') or [])
        wave = next((w for w in reversed(state.get('waves') or []) if w.get('status') == 'applied' and w.get('branch') not in before), None)
        out = {'branch': None, 'diff_stat': None, 'tests': None, 'cards_closed': [], 'indicators': [], 'answer': answer}
        if wave:
            out['branch'] = wave['branch']
            kept, failed = list(wave.get('kept') or []), wave.get('failed') or {}
            out['cards_closed'] = kept
            out['tests'] = {'passed': bool(kept), 'summary': f'{len(kept)} change(s) passed every check; {len(failed)} left out',
                            'left_out': {str(k): str(v)[:300] for k, v in (failed.items() if isinstance(failed, dict) else [])}}
            shortstat = subprocess.run(['git', '-C', str(self.project), 'diff', '--shortstat', f"HEAD...{wave['branch']}"],
                                       capture_output=True, text=True).stdout
            numbers = [int(part.split()[0]) for part in shortstat.split(',') if part.strip()[:1].isdigit()]
            labels = [part.split()[1] for part in shortstat.split(',') if part.strip()[:1].isdigit()]
            stat = {'files': 0, 'insertions': 0, 'deletions': 0}
            for number, label in zip(numbers, labels):
                stat['files' if label.startswith('file') else 'insertions' if label.startswith('insertion') else 'deletions'] = number
            out['diff_stat'] = stat
        return out

    # the person's controls
    def pause(self, run):
        record = self.store.load(run)
        if record.get('state') != 'running': raise LookupError('only a running run can be paused')
        pid = record.get('pid') or self._job_pid(record)
        if not pid: raise LookupError('this step cannot be paused; it finishes in a moment')
        _signal(pid, signal.SIGSTOP)
        return self.set_state(run, 'paused', paused_pid=pid)

    def resume(self, run):
        record = self.store.load(run)
        if record.get('state') != 'paused': raise LookupError('only a paused run can be resumed')
        _signal(record.get('paused_pid') or record.get('pid'), signal.SIGCONT)
        return self.set_state(run, 'running', 'resumed', paused_pid=None)

    def _job_pid(self, record):
        if not record.get('job'): return None
        from ... import jobs
        try: return jobs.read(record['job']).get('pid')
        except Exception: return None

    def stop(self, run):
        record = self.store.load(run)
        if record.get('state') in TERMINAL: raise LookupError('this run has already ended')
        pid = record.get('pid') or self._job_pid(record)
        self.set_state(run, 'stopped', 'you stopped it')
        if run in self.cancels: self.cancels[run].set()
        if record.get('mode') == 'handoff': handoff.drop(self.project, run)
        if pid and record.get('state') in ('running', 'paused'):
            if record.get('state') == 'paused': _signal(pid, signal.SIGCONT)
            _signal(pid, signal.SIGTERM)
            def finish():
                time.sleep(STOP_GRACE)
                if alive(pid): _signal(pid, signal.SIGKILL)
            threading.Thread(target=finish, daemon=True).start()
        return self.store.load(run)

    def retry(self, run):
        record = self.store.load(run)
        if record.get('state') not in ('failed', 'stopped'): raise LookupError('only a run that failed or was stopped can be tried again')
        record = self.set_state(run, 'queued', 'tried again', attempt=(record.get('attempt') or 1) + 1, session=None, pid=None, job=None,
                                question=None, queued_at=now(), mode='assistant' if record.get('assistant') else record.get('mode'),
                                branches_before=None)
        self.store.set_queue(self.store.queue())
        return record

    def reorder(self, order):
        queued = self.store.queue()
        order = [str(run) for run in order or []]
        if set(order) - set(queued): raise LookupError('only queued runs can be reordered')
        self.store.set_queue(order + [run for run in queued if run not in order])
        return self.store.queue()

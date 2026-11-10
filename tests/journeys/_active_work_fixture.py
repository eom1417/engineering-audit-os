"""Shared by the active-work tests: a job record, a paused process, and the batch with a job beside it."""
import os
import threading
from unittest import mock
from eaos.core.project import jobs, state as project_state
from eaos.journeys import guided
from eaos.journeys.agent_tools import fixing
from tests.journeys.test_stale_batch_changes import Batch, EDIT
UNIQUE = 'written nowhere else\n'
SECONDS = 20


UNIQUE = 'written nowhere else\n'


SECONDS = 20


def _job(project, kind='fix_edit', status='running', pid=None, ident=None):
    jobs._write({'id': ident or f'{kind}-1', 'kind': kind, 'project': str(project), 'status': status, 'pid': os.getpid()
                 if pid is None else pid,
                 'arguments': {}, 'started': '2026-01-01T00:00:00+00:00', 'result': None, 'error': None,
                 'progress': None, 'log': 'x'})


class Paused:
    """`work` in a thread, stopped at the point `at` of a real job until released."""

    def __init__(self, work):
        self.reached, self.go, self.outcome = threading.Event(), threading.Event(), {}
        def run():
            try: self.outcome['result'] = work()
            except BaseException as problem: self.outcome['raised'] = f'{type(problem).__name__}: {problem}'
        self.thread = threading.Thread(target=run, daemon=True)

    def at(self, value=None):
        def here(*_, **__):
            self.reached.set()
            self.go.wait(SECONDS)
            return value
        return here

    def start(self):
        self.thread.start()
        return self

    def end(self):
        self.go.set()
        self.thread.join(SECONDS)
        assert not self.thread.is_alive(), 'it never ended: a deadlock'
        return self.outcome


class Work(Batch):
    def edit_job(self):
        return fixing._fix_edit_job(self.where, {'card': 'TASK-001', 'edits': EDIT, 'summary': 'a fix'},
                                    lambda *_: None)

    def assertBusy(self, answer):
        self.assertEqual(answer.get('status'), 'busy', answer)
        self.assertTrue(answer.get('error'))
        self.assertTrue(answer.get('what_now'))

    def stale(self):
        self.person_commits()
        guided.save(project_state.load(self.project))

    def wave(self):
        return project_state.load(self.project).get('open_wave')

    def closed(self):
        return [wave['status'] for wave in project_state.load(self.project).get('waves') or []]

    def helper(self):
        state = project_state.load(self.project)
        state['open_wave'].update(lanes=[['TASK-001'], ['TASK-002']], claims={}, helpers={'h1': 1}, later=[],
                                  released=[])
        guided.save(state)
        return mock.patch.dict(os.environ, {'EAOS_STUDIO_RUN': 'h1'})

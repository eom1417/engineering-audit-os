"""Shared by the run-engine tests: a card, a project with its home, and the fake assistant as Claude Code."""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/fixtures/studio/actions'
FAKE = FIXTURES / 'fake_assistant.py'
from eaos.doors import runs as actions  # noqa: E402
from tests.shared_fixture import Workspace  # noqa: E402
from eaos.features.assistant.adapters import headless as adapters
from eaos.kernel.system.errors import noted
from eaos.features.studio.journey.runs import resume


ROOT = Path(__file__).resolve().parents[2]


FIXTURES = ROOT / 'tests/fixtures/studio/actions'


FAKE = FIXTURES / 'fake_assistant.py'


def card(id, **extra):
    return {'id': id, 'key': id.lower(), 'title': f'Problem {id}', 'kind': 'duplication', 'category': 'structure',
            'severity': 'high',
            'fixable': True, 'scope': 'place', 'place': f'src/{id}.py', 'paths': [f'src/{id}.py'], 'evidence': [],
            'state': 'open',
            'milestone': 'M1', **extra}


class Base(Workspace):
    """A project, its cards data, a home of its own, and the fake assistant as Claude Code."""

    def setUp(self):
        super().setUp()
        self.base = Path(self.tmp)
        saved = {k: os.environ.get(k)
                 for k in ('EAOS_HOME', 'EAOS_OUTPUT', 'FAKE_MODE', 'FAKE_SECONDS', 'FAKE_ARGV', 'FAKE_LOGGED_IN',
                           'EAOS_ASSISTANT')}
        def restore():
            for key, value in saved.items():
                if value is None: os.environ.pop(key, None)
                else: os.environ[key] = value
        self.addCleanup(restore)
        os.environ.update(EAOS_HOME=str(self.base / 'home'), EAOS_OUTPUT=str(self.base / 'out'), FAKE_MODE='question',
                          FAKE_ARGV=str(self.base / 'argv.jsonl'), FAKE_ONCE=str(self.base / 'crashed-once'))
        waits = mock.patch.object(resume, 'WAITS', (0, 0, 0))      # a stopped assistant's run goes on at once here
        waits.start()
        self.addCleanup(waits.stop)
        self.project = self.base / 'project'
        (self.project / 'src').mkdir(parents=True)
        subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        self.studio = self.base / 'studio'
        self.studio.mkdir()
        cards = [card('TASK-001'), card('TASK-002', severity='low', category='security'),
                 card('TASK-003', state='done'),
                 card('TASK-004', milestone='M2')]
        (self.studio / 'cards.json').write_text(json.dumps({'cards': cards}), encoding='utf-8')
        self.apps = []
        self.threads = set(threading.enumerate())
        self.app = self.make()

    def tearDown(self):
        for app in self.apps:
            for run in app.store.all():
                if run.get('state') in ('running', 'paused') and run.get('pid'):
                    try: os.killpg(run['pid'], 9)
                    except OSError as error: noted('the process group is already gone', error)
            app.close()
        pids = [run['pid'] for app in self.apps for run in app.store.all() if run.get('pid')]
        until(lambda: not any(alive(pid) for pid in pids), 5)
        # a run's thread ends (its last event written) before the folder is removed, or it fails with a KeyError
        started = [thread for thread in threading.enumerate() if thread not in self.threads]
        until(lambda: not any(thread.is_alive() for thread in started), 10)
        super().tearDown()

    def make(self, adapters_=None, **options):
        app = actions.Actions(self.project, port=8765, studio=self.studio,
                              adapters={'claude': adapters.ClaudeCode(command=[sys.executable, str(FAKE)])}
                              if adapters_ is None else adapters_, **options)
        self.apps.append(app)
        return app

    def headers(self, app=None, **extra):
        app = app or self.app
        return {'X-EAOS-Token': app.token, 'X-EAOS-CSRF': app.csrf, 'Origin': 'http://127.0.0.1:8765',
                'Host': '127.0.0.1:8765', **extra}

    def post(self, path, body=None, app=None):
        return (app or self.app).handle('POST', path, self.headers(app), body or {})

    def get(self, path, app=None):
        return (app or self.app).handle('GET', path, self.headers(app), None)

    def start(self, verb='explain', cards=('TASK-001',), app=None, **body):
        status, preview = self.post(f'/api/actions/{verb}/preview',
                                    {'verb': verb, 'selection': {'kind': 'cards', 'cards': list(cards)}}, app)
        self.assertEqual(status, 200, preview)
        status, created = self.post('/api/runs',
                                    {'action': verb, 'verb': verb, 'selection': {'kind': 'cards', 'cards': list(cards)},
                                     'confirm': (preview.get('confirm') or {}).get('token'), **body}, app)
        self.assertEqual(status, 200, created)
        return created['run']['id']

    def kinds(self, run, app=None):
        return [event['kind'] for event in (app or self.app).store.events(run)]


def until(condition, seconds):
    """Waits for a condition instead of a fixed sleep; whether it came true is the caller's to assert."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not condition(): time.sleep(0.05)


def alive(pid):
    from eaos.features.studio.journey.runs.lane_assistants import alive
    return alive(pid)

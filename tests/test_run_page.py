"""A run's page as the Studio derives it from the run's events (console/src/data/derive.js), replayed by Node: a Fix run
stopped twice and retried showed "0 of 50 tried" and the stopped server's message while the server said 9 of 50
(run r20261024-090619-acc214, 2026-10-24)."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

DERIVE = Path(__file__).resolve().parents[1] / 'console/src/data/derive.js'


def derived(events, run):
    script = (f"import {{ deriveRun, fixCount }} from {json.dumps(DERIVE.as_uri())};"
              "const [events, run] = JSON.parse(process.argv[1]); const view = deriveRun(events, run);"
              "console.log(JSON.stringify({ count: fixCount(view, run), now: view.now, error: view.error, cards: view.cards }));")
    done = subprocess.run(['node', '--input-type=module', '-e', script, json.dumps([events, run])], capture_output=True, text=True, timeout=60)
    if done.returncode: raise AssertionError(done.stderr)
    return json.loads(done.stdout)


@unittest.skipUnless(shutil.which('node'), 'Node.js is not installed')
class RetriedFixRun(unittest.TestCase):
    def test_the_count_is_the_servers_last_progress_and_a_retry_clears_the_stopped_attempts_words(self):
        seq = iter(range(1, 100))
        event = lambda kind, text='', **data: {'seq': next(seq), 'kind': kind, 'text': {'en': text, 'ar': text}, 'data': data}
        cards = [f'TASK-{n:03}' for n in range(1, 51)]
        events = [event('state', to='running'), event('edit', 'kept', card='TASK-001', kept=True),
                  event('progress', '1 of 50 cards tried', batch=None, done=1, total=50, stage='cards'),
                  event('error', 'The Studio server stopped while the run was going', reason='server stopped'),
                  event('state', to='queued'), event('action', 'Retry'), event('state', to='running'),
                  event('progress', '8 of 50 cards tried', batch=None, done=8, total=50, stage='cards'),
                  event('edit', 'kept', card='TASK-009', kept=True),
                  event('progress', '9 of 50 cards tried', batch=None, done=9, total=50, stage='cards')]
        run = {'verb': 'fix', 'state': 'running', 'cards': cards}
        view = derived(events, run)
        self.assertEqual(view['count'], 9, 'the server counts every attempt, the page did not')
        self.assertEqual(set(view['cards']), {'TASK-001', 'TASK-009'}, 'a retry keeps the cards tried before it')
        retried = derived(events[:8], run)        # the retry running, nothing new said yet
        self.assertEqual((retried['count'], retried['now'], retried['error']), (8, None, None),
                         "the stopped attempt's words are not what happens now")
        # before any progress of its cards, the cards seen edited count
        self.assertEqual(derived(events[:2], {'verb': 'fix', 'state': 'running', 'cards': cards})['count'], 1)


if __name__ == '__main__':
    unittest.main()

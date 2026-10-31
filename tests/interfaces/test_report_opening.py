"""What the Studio's button says after asking for the report to be rebuilt: only a rebuild that ended done is said to have opened
the report as it should; a failed or stopped one, or one still waiting, opens it as it stands and says it may be outdated."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / 'console/src/places/report/rebuilt.js'
TERMINAL = ['done', 'failed', 'stopped', 'unchanged']
SCRIPT = """
const { rebuildOutcome, OPENED_WORDS } = await import(process.argv[1]);
const states = JSON.parse(process.argv[2]);
let asked = 0;
const client = { run: async () => ({ state: states[Math.min(asked++, states.length - 1)] }) };
const outcome = await rebuildOutcome(client, { id: 'r1' }, JSON.parse(process.argv[3]), async () => {});
console.log(JSON.stringify({ outcome, words: OPENED_WORDS[outcome], asked }));
"""


@unittest.skipUnless(shutil.which('node'), 'Node.js is not installed')
class TheButton(unittest.TestCase):
    def said(self, *states):
        done = subprocess.run(['node', '--input-type=module', '-e', SCRIPT, MODULE.as_uri(), json.dumps(states), json.dumps(TERMINAL)],
                              capture_output=True, text=True, timeout=30, check=True)
        return json.loads(done.stdout)

    def test_a_rebuild_that_ended_done_says_it_opened(self):
        answer = self.said('queued', 'running', 'done')
        self.assertEqual((answer['outcome'], answer['words'], answer['asked']), ('done', 'un.files.opened', 3))

    def test_a_rebuild_that_failed_or_stopped_or_changed_nothing_never_says_it_succeeded(self):
        for state in ('failed', 'stopped', 'unchanged'):
            with self.subTest(state):
                answer = self.said('running', state)
                self.assertEqual((answer['outcome'], answer['words']), ('not_rebuilt', 'un.files.not_rebuilt'))

    def test_a_rebuild_still_waiting_when_the_time_is_up_says_the_report_may_be_outdated(self):
        answer = self.said('queued')
        self.assertEqual((answer['outcome'], answer['words'], answer['asked']), ('waiting', 'un.files.may_be_outdated', 60))

    def test_what_it_says_exists_in_both_languages_and_promises_no_update(self):
        words = (ROOT / 'console/src/words/report.js').read_text(encoding='utf-8')
        for key in ('un.files.not_rebuilt', 'un.files.may_be_outdated'):
            line = next(row for row in words.splitlines() if f"'{key}'" in row)
            self.assertIn('outdated', line)
            self.assertNotRegex(line, 'once that ends|will be rebuilt|بعد ما يخلص')


if __name__ == '__main__':
    unittest.main()

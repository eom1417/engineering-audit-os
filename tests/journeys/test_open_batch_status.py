"""A batch whose hand-over a stopped session cut stays open: the fix step is not done, and `eaos next` says to continue
it."""
import contextlib
import io
import unittest
from unittest import mock

from eaos.journeys.guided import running


class OpenBatchStatus(unittest.TestCase):
    def setUp(self):
        self.state = {'lang': 'en', 'setup': {'commit': 'abc'}, 'waves': [],
                      'open_wave': {'number': 1, 'cards': ['TASK-001', 'TASK-002'],
                                    'kept': {'TASK-001': {}}, 'failed': {}}}

    def test_an_open_batch_is_not_done_though_no_card_is_ready(self):
        with mock.patch('eaos.journeys.fix.waves.next_batch', return_value=[]), mock.patch.object(running, 'report_of'):
            self.assertFalse(running.fix_done(self.state))
            del self.state['open_wave']
            self.assertTrue(running.fix_done(self.state))

    def test_the_fix_step_says_the_open_batch_is_to_be_continued(self):
        out = io.StringIO()
        with mock.patch('eaos.journeys.fix.waves.next_batch', side_effect=AssertionError('not asked')), \
                contextlib.redirect_stdout(out):
            self.assertEqual(running.fix(self.state, None), 0)
        self.assertIn('Batch 1 is open and not handed over yet (1 changes kept)', out.getvalue())


if __name__ == '__main__':
    unittest.main()

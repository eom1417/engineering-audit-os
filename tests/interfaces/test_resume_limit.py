"""A run whose assistant hit its limit waits until the limit comes back when it said when, and work goes to another
assistant only when it answers now (an assistant that says it is signed in but is not must not stop the batch it took).
"""
import unittest
from unittest import mock
from datetime import datetime, timezone
from eaos.ai.assistant import readiness
from eaos.interfaces.studio_actions import resume

SAID = "You've hit your session limit · resets 7:40am (UTC)"


class ResumeLimitTests(unittest.TestCase):
    def test_the_stated_reset_time_is_waited_for(self):
        at = datetime(2026, 11, 4, 4, 54, tzinfo=timezone.utc)
        self.assertEqual(resume.seconds_until(readiness.resets_at(SAID), at), (2 * 3600 + 46 * 60) + 60)
        self.assertEqual(resume.seconds_until('7:40am (UTC)', datetime(2026, 11, 4, 8, 0, tzinfo=timezone.utc)), None)  # 23h40: too far
        self.assertEqual(resume.seconds_until('2 hours', at), 7260)
        self.assertEqual(resume.seconds_until('5 PM (Asia/Riyadh)', datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)), 2 * 3600 + 60)
        self.assertIsNone(resume.seconds_until('soon', at))
        self.assertIsNone(resume.seconds_until('7am (Nowhere/City)', at))

    def test_work_goes_to_an_assistant_that_answers(self):
        adapters = {'claude': 'claude', 'codex': 'codex'}
        self.assertIsNone(resume.next_assistant(adapters, 'claude', 'limit', ready=lambda name: False))
        self.assertEqual(resume.next_assistant(adapters, 'claude', 'limit', ready=lambda name: name == 'claude'), 'claude')
        self.assertEqual(readiness.classify('Your refresh token was revoked. Please log out and sign in again.'), 'sign_in_expired')

    def test_a_stopped_batch_with_nothing_kept_gives_its_cards_back(self):
        manager = mock.Mock(project='/p')
        abandon = mock.Mock(return_value={'status': 'abandoned', 'batch': 1, 'cards': ['TASK-1', 'TASK-2']})
        with mock.patch('eaos.core.project.state.load', return_value={'open_wave': {'kept': {}}}), \
                mock.patch('eaos.journeys.agent_tools.fix_abandon', abandon):
            resume.release(manager, 'r1')
        abandon.assert_called_once_with('/p')
        with mock.patch('eaos.core.project.state.load', return_value={'open_wave': {'kept': {'TASK-1': 'abc'}}}), \
                mock.patch('eaos.journeys.agent_tools.fix_abandon', abandon):
            resume.release(manager, 'r1')
        abandon.assert_called_once()        # a batch with a kept change stays, for Retry


if __name__ == '__main__':
    unittest.main()

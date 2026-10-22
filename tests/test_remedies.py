"""What EAOS does by itself about a stage that did not run (eaos/pipeline/remedies.py): the catalog's remedy applied,
the stage run again once its change is proven, a reason tried once, and the person's consent never given here."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.pipeline import remedies


def manifest(**stages):
    return {'stages': {name: {'status': status, 'reason_code': code, 'reason': code} for name, (status, code) in stages.items()}}


class RemedyTests(unittest.TestCase):
    def test_a_missing_tool_is_installed_and_its_stage_run_again_once_a_person_only_cause_is_only_said(self):
        # A real check (HungerLab): ten stages stood still and nobody tried the causes EAOS could fix by itself.
        first = manifest(engines=('unavailable', 'no_engine_installed'), setup=('unavailable', 'no_run_consent'), measure=('ok', ''))
        fixed = manifest(engines=('ok', ''), setup=('unavailable', 'no_run_consent'), measure=('ok', ''))
        calls = []
        with tempfile.TemporaryDirectory() as tmp, mock.patch('eaos.toolchain.install', return_value=[]) as install:
            done = remedies.apply(first, lambda stages: calls.append(stages) or fixed, tmp, assistant=None)
            self.assertTrue((Path(tmp) / 'run-manifest.json').is_file())
        self.assertEqual(calls, [['engines']], 'the stage runs again once, after the tool was installed')
        self.assertEqual(install.call_args.kwargs.get('names'), None)
        self.assertEqual([(r['stage'], r['outcome'], r['after']) for r in done['remedies']],
                         [('engines', 'fixed', 'ok'), ('setup', 'needs_person', 'unavailable')])
        with tempfile.TemporaryDirectory() as tmp:
            again = remedies.apply(fixed, lambda stages: self.fail('nothing to redo'), tmp)
        self.assertEqual([r['outcome'] for r in again['remedies']], ['needs_person'])

    def test_a_remedy_whose_change_is_not_proven_does_not_run_the_stage_again(self):
        broken = manifest(engines=('unavailable', 'no_engine_installed'), lock=('unavailable', 'no_features'), crawl=('unavailable', 'app_not_running'))
        with mock.patch('eaos.toolchain.install', return_value=['semgrep']), tempfile.TemporaryDirectory() as tmp:
            done = remedies.apply(broken, lambda stages: self.fail('no stage runs again'), tmp)
        self.assertEqual({r['stage']: r['outcome'] for r in done['remedies']},
                         {'engines': 'failed', 'lock': 'failed', 'crawl': 'needs_person'}, 'the crawl is not ok, so the lock is not retried')


if __name__ == '__main__':
    unittest.main()

"""The person's journey end to end, fast: check, the code changes, check again, a batch of three cards with one that
fails, accept; the counts and the progress are right at every step.

A small git project with three unreachable modules gives three ready cards. No external tool and no assistant run
(the engines stage is skipped, EAOS_ASSISTANT=none), and the live gates (the project's own checks, the behaviour lock
on the running app) are one stand-in check that fails once app/old_report.py is gone, as a project test that still
imports it would.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos import agent_tools, guided, ledger, live_setup
from eaos.pipeline import runners
from eaos.pipeline.stages import SkipStage

FILES = {
    'pyproject.toml': '[project]\nname = "shop"\nversion = "0.1.0"\n[project.scripts]\nshop = "app.main:run"\n',
    'app/__init__.py': '',
    'app/main.py': 'from app.prices import price\n\n\ndef run():\n    return price(3)\n',
    'app/prices.py': 'def price(n):\n    return n * 2\n',
    'app/old_report.py': 'def legacy_total(rows):\n    return sum(rows)\n',
    'app/old_export.py': "def legacy_export(rows):\n    return ','.join(rows)\n",
    'app/old_mail.py': 'def legacy_mail(to):\n    return to\n',
}


def git(project, *argv):
    return subprocess.run(['git', '-C', str(project), '-c', 'user.name=t', '-c', 'user.email=t@t', *argv],
                          check=True, capture_output=True, text=True).stdout.strip()


def project_checks(report, root, runtime, name, before, lock):
    """The project's own checks: one of them still needs app/old_report.py, so the batch that deletes it fails them."""
    return '' if (Path(root) / 'app/old_report.py').is_file() else "the project's own check failed: test_monthly_report"


def no_engines(context):
    raise SkipStage('the journey test runs no external tool', code='engines_not_requested')


class Journey(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for patch in (mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp.name) / 'home'), 'EAOS_ASSISTANT': 'none'}),
                      mock.patch.dict(runners.RUNNERS, engines=no_engines),
                      mock.patch.object(guided, 'tools_for_check', return_value={}),
                      mock.patch('eaos.waves.original_checks', return_value={}),
                      mock.patch('eaos.waves.gates', side_effect=project_checks)):
            patch.start()
            self.addCleanup(patch.stop)
        os.environ.pop('EAOS_DETECTOR_VERDICTS', None)      # the product's own detector verdicts, as a person gets them
        self.project = Path(self.tmp.name) / 'shop'
        for name, text in FILES.items():
            (self.project / name).parent.mkdir(parents=True, exist_ok=True)
            (self.project / name).write_text(text)
        git(self.project, 'init', '-q', '-b', 'main')
        git(self.project, 'add', '-A')
        git(self.project, 'commit', '-qm', 'first')
        self.where = str(self.project)
        agent_tools.project_state(self.where)

    def check(self):
        return agent_tools._audit_job(self.where, {}, None)

    def ready(self):
        from eaos.waves import ready_cards
        return {card['paths'][0]: card['id'] for card in ready_cards(guided.report_of(guided.load(self.project)))}

    def agree_and_record(self):
        """What run_setup and safety_net leave when the app runs and its screens are recorded."""
        state = guided.load(self.project)
        head = agent_tools._head(state)
        state['consent'] = {'run_and_fix': True}
        state['setup'] = {'commit': head, 'ok': True}
        state['safety'] = {'commit': head, 'screens': 1, 'passed': 1}
        guided.save(state)
        live_setup.authorize(guided.source(state), guided.runtime_of(state), 'tester')

    def journey(self):
        """The whole journey, asserting each step; the ledger's totals at the end."""
        first = self.check()
        cards = self.ready()
        self.assertEqual(sorted(cards), ['app/old_export.py', 'app/old_mail.py', 'app/old_report.py'], first)

        # The person changes the code: one dead module goes by hand, a new one comes. The second check sees both.
        (self.project / 'app/old_mail.py').unlink()
        (self.project / 'app/old_invoice.py').write_text('def legacy_invoice(n):\n    return n\n')
        git(self.project, 'add', '-A')
        git(self.project, 'commit', '-qm', 'the person works')
        self.check()
        cards = self.ready()
        self.assertEqual(sorted(cards), ['app/old_export.py', 'app/old_invoice.py', 'app/old_report.py'])

        # A batch of three, fixed by their codemods; the project's own check fails on one, which is found and left out.
        self.agree_and_record()
        batch = sorted(cards.values())
        opened = agent_tools._fix_start_job(self.where, {'cards': batch}, lambda *_: None)
        self.assertEqual(sorted(opened['fixed_automatically']), batch, opened)
        finished = agent_tools._fix_finish_job(self.where, {}, lambda *_: None)
        self.assertEqual(sorted(finished['kept']), sorted([cards['app/old_export.py'], cards['app/old_invoice.py']]), finished)
        self.assertIn('test_monthly_report', finished['failed'][cards['app/old_report.py']])
        self.assertEqual(finished['branch'], 'eaos/wave-1')
        self.assertTrue((self.project / 'app/old_export.py').is_file(), "the person's branch is untouched until accept")

        # Accept: the branch is merged and deleted, the two files are gone, and the progress counts the two fixes.
        accepted = agent_tools.accept(self.where, person_agreed=True)
        self.assertEqual((accepted['status'], accepted['branch_deleted']), ('accepted', True), accepted)
        self.assertFalse((self.project / 'app/old_export.py').exists())
        self.assertFalse((self.project / 'app/old_invoice.py').exists())
        self.assertTrue((self.project / 'app/old_report.py').is_file())
        return ledger.load(guided.load(self.project))['totals']

    def test_check_change_check_fix_accept(self):
        totals = self.journey()
        self.assertEqual(totals['done'], 2, totals)

    @unittest.expectedFailure      # ROADMAP 2: the module the person deleted by hand counts as closed (75%, not 2 of 3)
    def test_progress_counts_only_the_fixes_merged(self):
        totals = self.journey()
        self.assertEqual((totals['closed'], totals['total']), (2, 3), totals)


if __name__ == '__main__':
    unittest.main()

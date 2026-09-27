"""NS26: the lock and the load baseline on the original code, and the rules that make their numbers comparable."""
import json
from pathlib import Path

from shared_fixture import Workspace

from eaos.behavior_lock import spec_statuses
from eaos.live_run import load_profile
from eaos.runtime_baseline import record_after, shape
from eaos.sandbox import AuthorizationError

K6 = """export const options = {
  scenarios: { load: { executor: 'ramping-vus', startVUs: 0, stages: [
    { duration: '1m', target: 100 }, { duration: '3m', target: 100 }, { duration: '1m', target: 0 } ] } },
  thresholds: { http_req_duration: ['p(95)<800'], http_req_failed: ['rate<0.01'] },
};
"""


def report(*files):
    """A Playwright JSON report: files is [(file, [(status, message)])]."""
    return {'suites': [{'file': name, 'specs': [{'tests': [{'results': [{'status': status, 'error': {'message': message}}]}]}
                                              for status, message in outcomes]} for name, outcomes in files]}


class LockStatusTests(Workspace):
    def test_a_spec_passes_only_when_none_of_its_tests_failed_and_one_ran(self):
        statuses = spec_statuses(report(('home.spec.ts', [('passed', ''), ('skipped', '')]),
                                        ('rota.spec.ts', [('passed', ''), ('failed', 'Screenshot comparison failed')]),
                                        ('cases.spec.ts', [('skipped', '')])))
        self.assertEqual(statuses['home.spec.ts'][0], 'passed')
        self.assertEqual(statuses['rota.spec.ts'], ('failed', 'Screenshot comparison failed'))
        self.assertEqual(statuses['cases.spec.ts'][0], 'quarantined')


class BaselineTests(Workspace):
    def test_the_conditions_are_read_from_the_scenario_itself(self):
        script = Path(self.tmp) / 'qs-001.js'
        script.write_text(K6)
        self.assertEqual(shape(script), ({'p95_ms': 800.0, 'error_rate': 0.01}, 100, 300, 60))

    def test_after_needs_a_before_under_the_same_conditions(self):
        runtime = Path(self.tmp)
        (runtime / 'runtime').mkdir()
        conditions = {'build': 'npm run build', 'warmup_s': 60, 'vus': 100, 'duration_s': 300, 'machine': '4 CPU'}
        (runtime / 'runtime/performance.json').write_text(json.dumps({'schema_version': 1, 'conditions': conditions, 'scenarios': [
            {'id': 'QS-001', 'script': 'nfr/k6/qs-001.js', 'threshold': {'p95_ms': 800, 'error_rate': 0.01},
             'before': {'p95_ms': 120, 'error_rate': 0}, 'after': None},
            {'id': 'QS-002', 'script': 'nfr/k6/qs-002.js', 'threshold': {'p95_ms': 800, 'error_rate': 0.01}, 'before': None}]}))
        with self.assertRaises(ValueError): record_after(runtime, 'QS-001', {'p95_ms': 90, 'error_rate': 0}, {**conditions, 'vus': 10})
        with self.assertRaises(ValueError): record_after(runtime, 'QS-002', {'p95_ms': 90, 'error_rate': 0}, conditions)
        record = record_after(runtime, 'QS-001', {'p95_ms': 90, 'error_rate': 0}, conditions)
        self.assertEqual(record['scenarios'][0]['after'], {'p95_ms': 90, 'error_rate': 0})


class ProfileTests(Workspace):
    def test_without_a_run_profile_nothing_runs(self):
        with self.assertRaises(AuthorizationError): load_profile(self.tmp)

    def test_a_profile_breaking_its_contract_is_refused(self):
        (Path(self.tmp) / 'run.json').write_text(json.dumps({'schema_version': 1, 'install': [], 'start': []}))
        with self.assertRaises(AuthorizationError): load_profile(self.tmp)


class LiveRunTests(Workspace):
    def test_the_lock_browser_refuses_every_host_but_loopback(self):
        from eaos.behavior_lock import LOCK_CONFIG
        self.assertIn("--proxy-server=http://127.0.0.1:9", LOCK_CONFIG)
        self.assertIn("--proxy-bypass-list=127.0.0.1;localhost;[::1]", LOCK_CONFIG)
        self.assertNotIn("<-loopback>", LOCK_CONFIG)   # that token REMOVES loopback from the bypass: nothing loads
        self.assertIn('projects: (base.projects ?? []).map', LOCK_CONFIG)   # every project gets it, not only the default

    def test_the_run_environment_is_the_profile_and_the_tools_never_this_process(self):
        import os
        from unittest import mock
        from eaos.live_run import LiveRun
        run = LiveRun.__new__(LiveRun)
        run.profile = {'env': {'NODE_ENV': 'development'}}
        with mock.patch.dict(os.environ, {'OWNER_SECRET_TOKEN': 'do-not-leak'}):
            extra = run.extra()
        self.assertEqual(extra['NODE_ENV'], 'development')
        self.assertNotIn('OWNER_SECRET_TOKEN', extra)
        self.assertGreaterEqual(len(extra['AUTH_SECRET']), 48)   # generated for the run


class LockFolderTests(Workspace):
    def test_the_lock_runs_eaos_playwright_whatever_the_project_installs_or_declares(self):
        from unittest import mock
        from eaos import behavior_lock
        report, copy, tools = Path(self.tmp) / 'report', Path(self.tmp) / 'copy', Path(self.tmp) / 'tools'
        (report / 'behavior-lock/playwright').mkdir(parents=True)
        (tools / 'node/node_modules/@playwright/test').mkdir(parents=True)
        copy.mkdir()
        (copy / 'package.json').write_text('{"type": "module"}')
        live = mock.Mock()
        live.sandbox.copy = copy
        with mock.patch('eaos.toolchain.home', return_value=tools):
            lock = behavior_lock._prepare(live, report)
        self.assertTrue((lock / 'node_modules/@playwright/test').is_dir(), 'the specs import @playwright/test')
        self.assertEqual(json.loads((lock / 'package.json').read_text())['type'], 'commonjs',
                         'a project of ES modules does not change how the lock config loads')

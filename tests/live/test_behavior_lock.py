"""The behaviour lock: every feature gets a spec in its tool, describing what it does today."""
import json
from unittest import mock
import shutil
from pathlib import Path

from shared_fixture import Workspace

from eaos.core.contracts.artifact_rules import contracts, validate
from eaos.live.behavior.lock import LOCK_CONFIG, spec_statuses
from eaos.live.behavior.specs import build, import_safe, path_of, url


def playwright_report(*files):
    """A Playwright JSON report: files is [(file, [(status, message)])]."""
    return {'suites': [{'file': name, 'specs': [{'tests': [{'results': [{'status': status, 'error': {'message': message}}]}]}
                                              for status, message in outcomes]} for name, outcomes in files]}


def entry(route, surface='page', method=None, path='src/App.tsx'):
    return {'kind': 'entry_point', 'location': {'path': path}, 'value': {'route': route, 'surface': surface, 'http_method': method}}


class RouteTests(Workspace):
    def test_route_ids_become_the_urls_they_are_served_at_and_a_parameter_is_read_from_the_environment(self):
        self.assertEqual(path_of('/_authenticated/cartoes_/faturas/$invoiceId'), '/cartoes/faturas/$invoiceId')
        self.assertEqual(path_of('/(app)/settings'), '/settings')
        self.assertIsNone(path_of('/_authenticated'))
        self.assertIsNone(path_of('__root__'))
        self.assertEqual(path_of('/'), '/')
        literal, params = url('/contas/$accountId')
        self.assertEqual(params, ['accountId'])
        self.assertIn("process.env.E2E_ACCOUNTID", literal)
        # a GET /logout run with the session ended it, and every page stage after the lock saw the sign-in page
        from eaos.live.behavior.specs import playwright_spec
        spec, listed = playwright_spec({'name': 'auth'}, [('/logout', ('http', 'GET', None)), ('/login', ('http', 'GET', None))])
        self.assertNotIn("request.get(`/logout`)", spec)
        self.assertIn("request.get(`/login`)", spec)
        self.assertEqual(listed[0], '/logout (ends the session or changes data: not called)')


class BuildTests(Workspace):
    def report(self, features, entries, files=None):
        out, target = Path(self.tmp) / 'out', Path(self.tmp) / 'project'
        (out / 'facts').mkdir(parents=True)
        target.mkdir()
        (out / 'features.json').write_text(json.dumps({'features': features}))
        (out / 'facts/entrypoints.json').write_text(json.dumps({'facts': entries}))
        for name, text in (files or {}).items():
            (target / name).parent.mkdir(parents=True, exist_ok=True)
            (target / name).write_text(text)
        return out, target, build(out, target)

    def test_every_feature_has_a_spec_and_the_plan_keeps_its_contract(self):
        features = [{'name': 'Contas', 'surfaces': ['/_authenticated/contas', '/_authenticated/contas_/$accountId', '/_authenticated']},
                    {'name': 'api', 'surfaces': ['/api/health', '/api/import']}]
        entries = [entry('/_authenticated/contas'), entry('/_authenticated/contas_/$accountId'), entry('/_authenticated'),
                   entry('/api/health', 'http', 'GET'), entry('/api/import', 'http', 'POST')]
        out, _, plan = self.report(features, entries)
        self.assertEqual(validate(plan, contracts()['behavior-lock-plan']), [])
        spec = {s['feature']: s for s in plan['specs']}
        self.assertEqual(spec['Contas']['surfaces'], ['/_authenticated/contas', '/_authenticated/contas_/$accountId (needs_fixture)',
                                                      '/_authenticated (layout: no URL of its own)'])
        self.assertIn('POST /api/import (needs_fixture: writes)', spec['api']['surfaces'])
        text = (out / 'behavior-lock' / spec['Contas']['path']).read_text()
        self.assertIn("page.goto(`/contas`)", text)
        self.assertIn("toMatchSnapshot('contas.console.txt')", text)
        self.assertIn('toHaveScreenshot', text)
        self.assertIn("test.skip(!process.env.E2E_ACCOUNTID", text)
        api = (out / 'behavior-lock' / spec['api']['path']).read_text()
        self.assertIn('request.get(`/api/health`)', api)
        self.assertNotIn('request.post', api)
        auth = (out / 'behavior-lock/playwright/auth.setup.ts').read_text()
        self.assertIn('process.env.E2E_USER', auth)
        self.assertIn('process.env.E2E_PASSWORD', auth)
        self.assertNotRegex(auth, r"fill\('[^']")

    def test_a_python_feature_locks_the_interface_of_its_import_safe_modules_only(self):
        files = {'core/prices.py': 'import math\n\nRATE = 2\n\ndef total(a, b=1):\n    return a + b\n',
                 'views/page.py': 'import streamlit as st\nst.title("x")\n',
                 'run_app.py': 'def main():\n    pass\n\nif __name__ == "__main__":\n    main()\n'}
        features = [{'name': 'cli:run_app.py', 'surfaces': ['run_app.py'], 'files': list(files)}]
        out, target, plan = self.report(features, [entry('run_app', 'cli', path='run_app.py')], files)
        [spec] = plan['specs']
        self.assertEqual((spec['tool'], spec['surfaces']), ('approvaltests', ['core.prices', 'run_app']))
        self.assertFalse(import_safe(target / 'views/page.py'))
        text = (out / 'behavior-lock' / spec['path']).read_text()
        compile(text, spec['path'], 'exec')
        self.assertIn('verify(public_interface())', text)
        self.assertEqual((out / 'behavior-lock/approvals/requirements.txt').read_text(), 'approvaltests==19.1.1\npytest==9.1.1\n')

    def test_a_feature_with_nothing_to_lock_is_listed_without_a_spec_playwright_would_refuse(self):
        files = {'views/page.py': 'import streamlit as st\nst.title("x")\n'}
        _, _, plan = self.report([{'name': 'ui', 'surfaces': ['views/page.py'], 'files': ['views/page.py']}], [], files)
        self.assertEqual(plan['specs'][0]['path'], '')
        self.assertIn('needs_fixture', plan['specs'][0]['surfaces'][0])
        # A spec without a test made Playwright stop the whole lock with "No tests found" (the root layout of EAOS's Studio).
        shutil.rmtree(self.tmp); Path(self.tmp).mkdir()
        out, _, plan = self.report([{'name': 'home', 'surfaces': ['__root__']}], [entry('__root__')])
        self.assertEqual(plan['specs'], [{'feature': 'home', 'tool': 'playwright', 'path': '',
                                          'surfaces': ['__root__ (layout: no URL of its own)']}])
        self.assertFalse((out / 'behavior-lock/playwright').exists())
        self.assertFalse((out / 'behavior-lock/playwright.config.ts').exists())

    def test_the_lock_links_playwright_by_its_real_path_where_the_tools_home_is_a_link(self):
        import os
        from types import SimpleNamespace
        from unittest import mock
        from eaos.live.behavior.lock import _prepare
        real = Path(self.tmp) / 'disk/tools'
        (real / 'node/node_modules/@playwright/test').mkdir(parents=True)
        (Path(self.tmp) / 'home').mkdir()
        (Path(self.tmp) / 'home/tools').symlink_to(real)            # ~/.eaos/tools -> the one copy of the tools
        report = Path(self.tmp) / 'report'
        (report / 'behavior-lock').mkdir(parents=True)
        live = SimpleNamespace(sandbox=SimpleNamespace(copy=Path(self.tmp) / 'copy'))
        live.sandbox.copy.mkdir()
        with mock.patch.dict(os.environ, {'EAOS_ENGINE_TOOLS': str(Path(self.tmp) / 'home/tools')}):
            lock = _prepare(live, report)
        self.assertEqual(Path(os.readlink(lock / 'node_modules')), real.resolve() / 'node/node_modules',
                         'the runner and the specs load one Playwright: the sandbox shows the link and the real path apart')

    def test_a_program_with_no_feature_to_lock_records_nothing_and_says_so_instead_of_failing(self):
        from eaos.live.behavior.lock import run_lock
        report = Path(self.tmp) / 'report'
        report.mkdir()
        self.assertEqual(build(report, Path(self.tmp))['specs'], [])
        self.assertEqual(run_lock(report, Path(self.tmp), Path(self.tmp) / 'runtime')['results'], [], 'the safety net is empty, never a crash')

    def test_the_safety_net_crawls_the_running_app_for_its_pages_when_the_code_names_none(self):
        # A real incident (an SPA, 0.0.59): the safety net recorded 0 screens (the code names no page: an SPA of
        # /#/now routes), so no fix batch could open. The lock now crawls the app it started and locks those pages.
        from eaos.live.behavior import lock as behavior_lock
        report, runtime = Path(self.tmp) / 'report', Path(self.tmp) / 'runtime'
        report.mkdir(); runtime.mkdir()
        found = {'status': 'observed', 'routes': [{'path': '/'}, {'path': '/#/now'}, {'path': '/#/now?x=1'}]}
        with mock.patch('eaos.live.screens.crawl.crawl', return_value=found) as crawled:
            self.assertTrue(behavior_lock._pages_from_app(report, Path(self.tmp), 'http://127.0.0.1:1', runtime))
            self.assertFalse(behavior_lock._pages_from_app(report, Path(self.tmp), 'http://127.0.0.1:1', runtime), 'crawled once')
        self.assertEqual(crawled.call_count, 1)
        plan = json.loads((report / 'behavior-lock/plan.json').read_text())
        self.assertEqual([(s['feature'], s['surfaces']) for s in plan['specs']], [('page /', ['/']), ('page /#/now', ['/#/now'])])


JUNIT = """<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest">
<testcase classname="" name="approvals.test_broken"><error message="collection failure">ImportError: no module named x</error></testcase>
<testcase classname="approvals.test_same" name="test_the_public_interface_is_as_it_was" time="0.003" />
<testcase classname="approvals.test_changed" name="test_the_public_interface_is_as_it_was">
<failure message="ApprovalException: Approval Mismatch, received != approved">diff</failure></testcase>
</testsuite></testsuites>"""


class ApprovalResultTests(Workspace):
    def test_every_spec_gets_a_status_one_with_nothing_to_run_is_quarantined_and_approvals_alone_never_run_playwright(self):
        from eaos.live.behavior.lock import approval_statuses
        junit = Path(self.tmp) / 'approvals.xml'
        junit.write_text(JUNIT)
        self.assertEqual(approval_statuses(junit), {
            'approvals/test_broken.py': ('failed', 'collection failure'),
            'approvals/test_same.py': ('passed', ''),
            'approvals/test_changed.py': ('failed', 'ApprovalException: Approval Mismatch, received != approved')})
        self.assertEqual(approval_statuses(Path(self.tmp) / 'missing.xml'), {})
        statuses = spec_statuses(playwright_report(('home.spec.ts', [('passed', ''), ('skipped', '')]),
                                                   ('rota.spec.ts', [('passed', ''), ('failed', 'Screenshot comparison failed')]),
                                                   ('cases.spec.ts', [('skipped', '')])))
        self.assertEqual(statuses['home.spec.ts'][0], 'passed')
        self.assertEqual(statuses['rota.spec.ts'], ('failed', 'Screenshot comparison failed'))
        self.assertEqual(statuses['cases.spec.ts'][0], 'quarantined', 'a spec whose tests were all skipped')
        # Wave 4 on EAOS (2026-10-13): design cards changed the screens they were about, and the lock refused them all
        looks = lambda name: f'Error: \x1b[2mexpect(\x1b[22mpage).toHaveScreenshot(expected) failed\n  Snapshot: {name}.png'
        report = playwright_report(('root.spec.ts', [('failed', looks('change')), ('passed', '')]),
                                   ('other.spec.ts', [('failed', looks('problems'))]), ('broken.spec.ts', [('failed', 'pageerror: boom')]))
        self.assertEqual({k: s for k, (s, _) in spec_statuses(report, {'change', 'broken'}).items()},
                         {'root.spec.ts': 'passed', 'other.spec.ts': 'failed', 'broken.spec.ts': 'failed'},
                         'a declared screen may look different; an undeclared one, or any other failure, still counts')
        report = playwright_report(('root.spec.ts', [('failed', looks('problems'))]))
        report['suites'][0]['specs'][0]['title'] = '/#/problems renders as it does today'
        self.assertEqual(spec_statuses(report, (), {'/#/problems renders as it does today'})['root.spec.ts'][0], 'passed',
                         'a test failing on the code before the batch too says nothing of the batch')
        from eaos.live.behavior.lock import _results
        (Path(self.tmp) / 'behavior-lock').mkdir()
        (Path(self.tmp) / 'behavior-lock/plan.json').write_text(json.dumps({'specs': [
            {'feature': 'home', 'tool': 'playwright', 'path': '', 'surfaces': ['__root__ (layout: no URL of its own)']},
            {'feature': 'cli', 'tool': 'approvaltests', 'path': 'approvals/test_cli.py'}]}))
        self.assertEqual(_results(self.tmp, {'approvals/test_cli.py': ('passed', '')}), [
            {'path': '', 'status': 'quarantined', 'reason': 'nothing to run: __root__ (layout: no URL of its own)'},
            {'path': 'approvals/test_cli.py', 'status': 'passed'}])
        from unittest import mock
        from eaos.live.behavior import lock as behavior_lock
        lock = Path(self.tmp) / '.eaos-lock'
        (lock / 'approvals').mkdir(parents=True)
        found = {'approvals/test_cli.py': ('passed', '')}
        with mock.patch.object(behavior_lock, '_pass') as playwright, \
                mock.patch.object(behavior_lock, '_approvals', return_value=found) as approvals:
            statuses = behavior_lock._run_specs(mock.Mock(), lock, None, Path(self.tmp), behavior_lock.LockPass('record', update=True))
        self.assertEqual(statuses, found)
        playwright.assert_not_called()
        self.assertEqual(approvals.call_args.args[2:], (Path(self.tmp) / 'approvals-record.xml', True))

    def test_the_lock_runs_eaos_playwright_offline_whatever_the_project_installs_or_declares(self):
        from unittest import mock
        from eaos.live.behavior import lock as behavior_lock
        self.assertIn("--proxy-server=http://127.0.0.1:9", LOCK_CONFIG)
        self.assertIn("--proxy-bypass-list=127.0.0.1;localhost;[::1]", LOCK_CONFIG)
        self.assertNotIn("<-loopback>", LOCK_CONFIG)   # that token REMOVES loopback from the bypass: nothing loads
        self.assertIn('projects: (base.projects ?? []).map', LOCK_CONFIG)   # every project gets it, not only the default
        report, copy, tools = Path(self.tmp) / 'report', Path(self.tmp) / 'copy', Path(self.tmp) / 'tools'
        (report / 'behavior-lock/playwright').mkdir(parents=True)
        (tools / 'node/node_modules/@playwright/test').mkdir(parents=True)
        copy.mkdir()
        (copy / 'package.json').write_text('{"type": "module"}')
        live = mock.Mock()
        live.sandbox.copy = copy
        with mock.patch('eaos.core.toolchain.home', return_value=tools):
            lock = behavior_lock._prepare(live, report)
        self.assertTrue((lock / 'node_modules/@playwright/test').is_dir(), 'the specs import @playwright/test')
        self.assertEqual(json.loads((lock / 'package.json').read_text())['type'], 'commonjs',
                         'a project of ES modules does not change how the lock config loads')


class KindTests(Workspace):
    def test_each_kind_of_user_walks_its_own_pages_with_its_own_session_and_a_change_breaking_one_is_caught(self):
        from eaos.live.behavior import lock as behavior_lock
        from eaos.live.behavior.folder import lend_kinds
        report, lock = Path(self.tmp) / 'report', Path(self.tmp) / '.eaos-lock'
        (report / 'behavior-lock').mkdir(parents=True)
        (lock / '.auth/sessions').mkdir(parents=True)
        (report / 'behavior-lock/plan.json').write_text(json.dumps({'specs': [
            {'feature': 'home', 'tool': 'playwright', 'path': 'playwright/home.spec.ts', 'surfaces': ['/ (page)']},
            {'feature': 'admin', 'tool': 'playwright', 'path': 'playwright/admin.spec.ts', 'surfaces': ['GET /admin']}]}))     # Flask's
        (report / 'roles.json').write_text(json.dumps({'roles': [{'id': 'admin', 'pages': ['/admin']},
                                                                 {'id': 'guest', 'pages': ['/guest']}]}))
        (lock / '.auth/sessions/admin.json').write_text('{"cookies": [{"name": "admin"}]}')
        state = lock / '.auth/user.json'
        self.assertEqual(lend_kinds(report, lock, state), [('admin', ['playwright/admin.spec.ts'])],
                         'a kind with no session or no page of its own has no pass of its own')
        self.assertIn('"admin"', (lock / '.auth/@admin.json').read_text())
        (lock / 'playwright.config.ts').write_text('')
        ran = []

        def one_pass(live, lock, base, output, how):
            ran.append((output.name, how))
            failed = 'failed' if how[1] == 'admin' and 'verify' in output.name else 'passed'
            return playwright_report(*[(Path(f).name, [(failed, '')]) for f in how[2] or ['playwright/home.spec.ts', 'playwright/admin.spec.ts']])
        with mock.patch.object(behavior_lock, '_pass', side_effect=one_pass):
            recorded = behavior_lock._results(report, behavior_lock._run_specs(None, lock, None, Path(self.tmp), behavior_lock.LockPass('record', True)))
            after = behavior_lock._results(report, behavior_lock._run_specs(None, lock, None, Path(self.tmp), behavior_lock.LockPass('verify')))
        self.assertEqual([(name, how[:5]) for name, how in ran[:2]], [('playwright-record.json', (True, None, [], None, True)),
                                   ('playwright-record@admin.json', (True, 'admin', ['playwright/admin.spec.ts'], None, True))])
        with mock.patch.object(behavior_lock, '_pass', side_effect=one_pass):
            behavior_lock._run_specs(None, lock, None, Path(self.tmp), behavior_lock.LockPass('intended', True))
        self.assertFalse(ran[-1][1][-1], "a kept batch's screens recorded again never become the lock's original pictures")
        self.assertIn({'path': 'playwright/admin.spec.ts', 'kind': 'admin', 'status': 'passed'}, recorded)
        (Path(self.tmp) / 'behavior-lock').mkdir(exist_ok=True)
        (Path(self.tmp) / 'behavior-lock/results.json').write_text(json.dumps({'results': recorded}))
        verdict = behavior_lock._judged(behavior_lock._passed_before(Path(self.tmp), after), after)
        self.assertEqual((verdict['specs'], verdict['failed']), (3, 1), 'the admin page broken only for the admin is caught')


def git(project, *args):
    import subprocess
    return subprocess.run(['git', '-C', str(project), *args], check=True, capture_output=True, text=True).stdout.strip()


class ApprovalRunTests(Workspace):
    """The approval tests run for real, with EAOS's pinned pytest and ApprovalTests, in a sandbox copy."""

    report = BuildTests.report

    def setUp(self):
        super().setUp()
        from eaos.core import toolchain
        if not (toolchain.home() / 'bin/pytest').exists() or toolchain.pip_version('approvaltests') is None:
            self.skipTest('pytest is not installed: python -m eaos tools install --only pytest')
        import os
        from unittest import mock
        home = mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp) / 'eaos-home')})
        home.start()
        self.addCleanup(home.stop)

    def live(self, project):
        from datetime import date
        git(project, 'init', '-q'); git(project, 'add', '.')
        git(project, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'project')
        grant = Path(self.tmp) / 'authorization.json'
        grant.write_text(json.dumps({'schema_version': 1, 'project': 'p', 'commit': git(project, 'rev-parse', 'HEAD'),
                                     'granted_by': 'owner', 'stages': ['S05'], 'env_allow': [], 'expires': date.today().isoformat()}))
        from eaos.core.project.places import workspace
        workspace(project).mkdir(parents=True)                # this fixture's folder is the run's own report
        (workspace(project) / 'state.json').write_text(json.dumps({'outputs': self.tmp}))
        return self.another_copy(project)

    def another_copy(self, project):
        """A run in a new sandbox copy of the committed project, as verify_lock makes for each candidate."""
        import os
        from unittest import mock
        from eaos.core import toolchain
        from eaos.live.isolation.sandbox import Sandbox
        live = mock.Mock(log=[], sandbox=Sandbox(project, Path(self.tmp) / 'authorization.json', Path(self.tmp) / 'sandbox', 'S05'))
        live.run_env.return_value = {'PATH': f"{toolchain.home() / 'bin'}{os.pathsep}{os.environ['PATH']}"}
        return live

    def test_the_same_code_in_another_copy_matches_its_recording(self):
        # On EAOS itself a default naming a file of the copy, and a default function with its address, failed an
        # unchanged candidate: each run has its own copy and its own memory.
        from eaos.live.behavior import lock as behavior_lock
        files = {'pkg/__init__.py': '', 'pkg/paths.py': 'from pathlib import Path\n\n\n'
                 'def where(root=Path(__file__).parent, pick=lambda x: x):\n    return root\n'}
        features = [{'name': 'cli:pkg/paths.py', 'surfaces': ['pkg/paths.py'], 'files': ['pkg/paths.py']}]
        out, project, plan = self.report(features, [entry('pkg/paths.py', 'cli', path='pkg/paths.py')], files)
        recorded, first = Path(self.tmp) / 'runtime/behavior-lock', self.live(project)
        try:
            lock = behavior_lock._prepare(first, out)
            behavior_lock._run_specs(first, lock, None, recorded, behavior_lock.LockPass('record', update=True))
            behavior_lock._keep(lock, recorded)
        finally:
            first.sandbox.dispose()
        self.assertEqual(next((recorded / 'approved').iterdir()).read_text().strip(),
                         "pkg.paths.where(root=PosixPath('<root>/pkg'), pick=<function <lambda>>)")
        second = self.another_copy(project)
        try:
            statuses = behavior_lock._run_specs(second, behavior_lock._prepare(second, out, recorded), None, recorded, behavior_lock.LockPass('after'))
        finally:
            second.sandbox.dispose()
        self.assertEqual(statuses, {plan['specs'][0]['path']: ('passed', '')}, second.log)

    def test_the_first_pass_records_the_interfaces_the_second_matches_and_a_change_fails(self):
        import os
        from unittest import mock
        from eaos.live.behavior import lock as behavior_lock
        # The project's own pytest settings and conftest must not take part: either one would break the run.
        files = {'pkg/__init__.py': '', 'pkg/prices.py': 'def total(a, b=1):\n    return a + b\n',
                 'pkg/broken.py': 'import not_installed_anywhere\n',
                 'conftest.py': 'raise SystemExit("the project conftest was loaded")\n',
                 'pyproject.toml': '[tool.pytest.ini_options]\naddopts = "--no-such-option"\n'}
        features = [{'name': 'cli:pkg/prices.py', 'surfaces': ['pkg/prices.py'], 'files': ['pkg/prices.py']},
                    {'name': 'cli:pkg/broken.py', 'surfaces': ['pkg/broken.py'], 'files': ['pkg/broken.py']}]
        out, project, plan = self.report(features, [entry('pkg/prices.py', 'cli', path='pkg/prices.py')], files)
        spec, broken = plan['specs']
        live, recorded = self.live(project), Path(self.tmp) / 'runtime/behavior-lock'
        # EAOS's own packages on its PYTHONPATH must not reach the project's run: this one would shadow its module.
        shadow = Path(self.tmp) / 'eaos-site/pkg'
        shadow.mkdir(parents=True)
        (shadow / '__init__.py').write_text('')
        (shadow / 'prices.py').write_text('def total(x):\n    return x\n')
        try:
            lock = behavior_lock._prepare(live, out)
            with mock.patch.dict(os.environ, {'PYTHONPATH': str(shadow.parent)}):
                record = behavior_lock._run_specs(live, lock, None, recorded, behavior_lock.LockPass('record', update=True))
            # Recorded is passed, as Playwright's pass that writes the snapshots; a module that does not import is not.
            self.assertEqual(record[spec['path']], ('passed', ''), live.log)
            self.assertEqual(record[broken['path']][0], 'failed')
            self.assertIn('not_installed_anywhere', record[broken['path']][1])
            behavior_lock._keep(lock, recorded)
            self.assertEqual([p.name for p in (recorded / 'approved').iterdir()],
                             ['test_cli_pkg_prices_py.test_the_public_interface_is_as_it_was.approved.txt'])
            self.assertEqual(next((recorded / 'approved').iterdir()).read_text().strip(), 'pkg.prices.total(a, b=1)')
            verify = behavior_lock._run_specs(live, lock, None, recorded, behavior_lock.LockPass('verify'))
            self.assertEqual(verify[spec['path']], ('passed', ''), live.log)
            self.assertEqual(verify[broken['path']][0], 'failed')
            # Another size as well: the bytecode the first runs cached is checked by size and second.
            (live.sandbox.copy / 'pkg/prices.py').write_text('def total(a, b=1, c=0):\n    return a + b + c\n')
            lock = behavior_lock._prepare(live, out, recorded)
            changed = behavior_lock._run_specs(live, lock, None, recorded, behavior_lock.LockPass('after'))
            self.assertEqual(changed[spec['path']][0], 'failed', live.log)
            self.assertIn('Approval Mismatch', changed[spec['path']][1])
        finally:
            live.sandbox.dispose()

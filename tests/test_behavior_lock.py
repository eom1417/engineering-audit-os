"""The behaviour lock: every feature gets a spec in its tool, describing what it does today."""
import json
from pathlib import Path

from shared_fixture import Workspace

from eaos.artifact_contracts import contracts, validate
from eaos.behavior_lock import build, import_safe, path_of, url


def entry(route, surface='page', method=None, path='src/App.tsx'):
    return {'kind': 'entry_point', 'location': {'path': path}, 'value': {'route': route, 'surface': surface, 'http_method': method}}


class RouteTests(Workspace):
    def test_route_ids_become_the_urls_they_are_served_at(self):
        self.assertEqual(path_of('/_authenticated/cartoes_/faturas/$invoiceId'), '/cartoes/faturas/$invoiceId')
        self.assertEqual(path_of('/(app)/settings'), '/settings')
        self.assertIsNone(path_of('/_authenticated'))
        self.assertIsNone(path_of('__root__'))
        self.assertEqual(path_of('/'), '/')

    def test_a_parameter_is_read_from_the_environment_never_written(self):
        literal, params = url('/contas/$accountId')
        self.assertEqual(params, ['accountId'])
        self.assertIn("process.env.E2E_ACCOUNTID", literal)


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

    def test_a_feature_with_nothing_to_lock_is_listed_without_a_spec_not_dropped(self):
        files = {'views/page.py': 'import streamlit as st\nst.title("x")\n'}
        _, _, plan = self.report([{'name': 'ui', 'surfaces': ['views/page.py'], 'files': ['views/page.py']}], [], files)
        self.assertEqual(plan['specs'][0]['path'], '')
        self.assertIn('needs_fixture', plan['specs'][0]['surfaces'][0])

    def test_playwright_itself_loads_every_generated_spec(self):
        from eaos.emit import emit
        from eaos.engines.process import which
        if not which('playwright'): self.skipTest('playwright is not installed: python -m eaos tools install --only playwright')
        features = [{'name': 'home', 'surfaces': ['/', '/about/:id']}, {'name': 'api', 'surfaces': ['/api/ping']}]
        out, _, _ = self.report(features, [entry('/'), entry('/about/:id'), entry('/api/ping', 'http', 'GET')])
        _, rows = emit(out, only=['behavior-lock'], validate=True)
        self.assertEqual([(r['tool'], r['ok']) for r in rows], [('playwright', True)], rows)
        self.assertIn('Total: 4 tests in 3 files', rows[0]['output'])

    def test_a_feature_of_layouts_only_gets_no_spec_playwright_would_refuse(self):
        # A spec without a test made Playwright stop the whole lock with "No tests found" (the root layout of EAOS's Studio).
        out, _, plan = self.report([{'name': 'home', 'surfaces': ['__root__']}], [entry('__root__')])
        self.assertEqual(plan['specs'], [{'feature': 'home', 'tool': 'playwright', 'path': '',
                                          'surfaces': ['__root__ (layout: no URL of its own)']}])
        self.assertFalse((out / 'behavior-lock/playwright').exists())
        self.assertFalse((out / 'behavior-lock/playwright.config.ts').exists())


JUNIT = """<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest">
<testcase classname="" name="approvals.test_broken"><error message="collection failure">ImportError: no module named x</error></testcase>
<testcase classname="approvals.test_same" name="test_the_public_interface_is_as_it_was" time="0.003" />
<testcase classname="approvals.test_changed" name="test_the_public_interface_is_as_it_was">
<failure message="ApprovalException: Approval Mismatch, received != approved">diff</failure></testcase>
</testsuite></testsuites>"""


class ApprovalResultTests(Workspace):
    def test_every_approval_spec_gets_a_status_like_a_playwright_spec(self):
        from eaos.behavior_lock import approval_statuses
        junit = Path(self.tmp) / 'approvals.xml'
        junit.write_text(JUNIT)
        self.assertEqual(approval_statuses(junit), {
            'approvals/test_broken.py': ('failed', 'collection failure'),
            'approvals/test_same.py': ('passed', ''),
            'approvals/test_changed.py': ('failed', 'ApprovalException: Approval Mismatch, received != approved')})
        self.assertEqual(approval_statuses(Path(self.tmp) / 'missing.xml'), {})

    def test_a_spec_with_nothing_to_run_is_quarantined_with_why_not_an_error(self):
        from eaos.behavior_lock import _results
        (Path(self.tmp) / 'behavior-lock').mkdir()
        (Path(self.tmp) / 'behavior-lock/plan.json').write_text(json.dumps({'specs': [
            {'feature': 'home', 'tool': 'playwright', 'path': '', 'surfaces': ['__root__ (layout: no URL of its own)']},
            {'feature': 'cli', 'tool': 'approvaltests', 'path': 'approvals/test_cli.py'}]}))
        self.assertEqual(_results(self.tmp, {'approvals/test_cli.py': ('passed', '')}), [
            {'path': '', 'status': 'quarantined', 'reason': 'nothing to run: __root__ (layout: no URL of its own)'},
            {'path': 'approvals/test_cli.py', 'status': 'passed'}])

    def test_a_lock_of_approval_tests_only_never_runs_playwright(self):
        from unittest import mock
        from eaos import behavior_lock
        lock = Path(self.tmp) / '.eaos-lock'
        (lock / 'approvals').mkdir(parents=True)
        found = {'approvals/test_cli.py': ('passed', '')}
        with mock.patch.object(behavior_lock, '_pass') as playwright, \
                mock.patch.object(behavior_lock, '_approvals', return_value=found) as approvals:
            statuses = behavior_lock._run_specs(mock.Mock(), lock, None, Path(self.tmp), 'record', update=True)
        self.assertEqual(statuses, found)
        playwright.assert_not_called()
        self.assertEqual(approvals.call_args.args[2:], (Path(self.tmp) / 'approvals-record.xml', True))


def git(project, *args):
    import subprocess
    return subprocess.run(['git', '-C', str(project), *args], check=True, capture_output=True, text=True).stdout.strip()


class ApprovalRunTests(Workspace):
    """The approval tests run for real, with EAOS's pinned pytest and ApprovalTests, in a sandbox copy."""

    report = BuildTests.report

    def setUp(self):
        super().setUp()
        from eaos import toolchain
        if not (toolchain.home() / 'bin/pytest').exists() or toolchain.pip_version('approvaltests') is None:
            self.skipTest('pytest is not installed: python -m eaos tools install --only pytest')

    def live(self, project):
        from datetime import date
        git(project, 'init', '-q'); git(project, 'add', '.')
        git(project, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'project')
        grant = Path(self.tmp) / 'authorization.json'
        grant.write_text(json.dumps({'schema_version': 1, 'project': 'p', 'commit': git(project, 'rev-parse', 'HEAD'),
                                     'granted_by': 'owner', 'stages': ['S05'], 'env_allow': [], 'expires': date.today().isoformat()}))
        return self.another_copy(project)

    def another_copy(self, project):
        """A run in a new sandbox copy of the committed project, as verify_lock makes for each candidate."""
        import os
        from unittest import mock
        from eaos import toolchain
        from eaos.sandbox import Sandbox
        live = mock.Mock(log=[], sandbox=Sandbox(project, Path(self.tmp) / 'authorization.json', Path(self.tmp) / 'sandbox', 'S05'))
        live.extra.return_value = {'PATH': f"{toolchain.home() / 'bin'}{os.pathsep}{os.environ['PATH']}"}
        return live

    def test_the_same_code_in_another_copy_matches_its_recording(self):
        # On EAOS itself a default naming a file of the copy, and a default function with its address, failed an
        # unchanged candidate: each run has its own copy and its own memory.
        from eaos import behavior_lock
        files = {'pkg/__init__.py': '', 'pkg/paths.py': 'from pathlib import Path\n\n\n'
                 'def where(root=Path(__file__).parent, pick=lambda x: x):\n    return root\n'}
        features = [{'name': 'cli:pkg/paths.py', 'surfaces': ['pkg/paths.py'], 'files': ['pkg/paths.py']}]
        out, project, plan = self.report(features, [entry('pkg/paths.py', 'cli', path='pkg/paths.py')], files)
        recorded, first = Path(self.tmp) / 'runtime/behavior-lock', self.live(project)
        try:
            lock = behavior_lock._prepare(first, out)
            behavior_lock._run_specs(first, lock, None, recorded, 'record', update=True)
            behavior_lock._keep(lock, recorded)
        finally:
            first.sandbox.dispose()
        self.assertEqual(next((recorded / 'approved').iterdir()).read_text().strip(),
                         "pkg.paths.where(root=PosixPath('<root>/pkg'), pick=<function <lambda>>)")
        second = self.another_copy(project)
        try:
            statuses = behavior_lock._run_specs(second, behavior_lock._prepare(second, out, recorded), None, recorded, 'after', update=False)
        finally:
            second.sandbox.dispose()
        self.assertEqual(statuses, {plan['specs'][0]['path']: ('passed', '')}, second.log)

    def test_the_first_pass_records_the_interfaces_the_second_matches_and_a_change_fails(self):
        import os
        from unittest import mock
        from eaos import behavior_lock
        # The project's own pytest settings and conftest must not take part: either one would break the run.
        files = {'pkg/__init__.py': '', 'pkg/prices.py': 'def total(a, b=1):\n    return a + b\n',
                 'conftest.py': 'raise SystemExit("the project conftest was loaded")\n',
                 'pyproject.toml': '[tool.pytest.ini_options]\naddopts = "--no-such-option"\n'}
        features = [{'name': 'cli:pkg/prices.py', 'surfaces': ['pkg/prices.py'], 'files': ['pkg/prices.py']}]
        out, project, plan = self.report(features, [entry('pkg/prices.py', 'cli', path='pkg/prices.py')], files)
        [spec] = plan['specs']
        live, recorded = self.live(project), Path(self.tmp) / 'runtime/behavior-lock'
        # EAOS's own packages on its PYTHONPATH must not reach the project's run: this one would shadow its module.
        shadow = Path(self.tmp) / 'eaos-site/pkg'
        shadow.mkdir(parents=True)
        (shadow / '__init__.py').write_text('')
        (shadow / 'prices.py').write_text('def total(x):\n    return x\n')
        try:
            lock = behavior_lock._prepare(live, out)
            with mock.patch.dict(os.environ, {'PYTHONPATH': str(shadow.parent)}):
                behavior_lock._run_specs(live, lock, None, recorded, 'record', update=True)
            behavior_lock._keep(lock, recorded)
            self.assertEqual([p.name for p in (recorded / 'approved').iterdir()],
                             ['test_cli_pkg_prices_py.test_the_public_interface_is_as_it_was.approved.txt'])
            self.assertEqual(next((recorded / 'approved').iterdir()).read_text().strip(), 'pkg.prices.total(a, b=1)')
            verify = behavior_lock._run_specs(live, lock, None, recorded, 'verify', update=False)
            self.assertEqual(verify, {spec['path']: ('passed', '')}, live.log)
            # Another size as well: the bytecode the first runs cached is checked by size and second.
            (live.sandbox.copy / 'pkg/prices.py').write_text('def total(a, b=1, c=0):\n    return a + b + c\n')
            lock = behavior_lock._prepare(live, out, recorded)
            changed = behavior_lock._run_specs(live, lock, None, recorded, 'after', update=False)
            self.assertEqual(changed[spec['path']][0], 'failed', live.log)
            self.assertIn('Approval Mismatch', changed[spec['path']][1])
        finally:
            live.sandbox.dispose()

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

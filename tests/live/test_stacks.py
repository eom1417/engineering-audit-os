"""The common stacks start from their files alone, with no assistant (M5.1): the corpus' Python apps, its Expo apps
and its static site had never started without one."""
import json
import unittest
from pathlib import Path

from eaos.live.app import setup as live_setup
from shared_fixture import scratch


def project(files):
    root = Path(scratch())
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text if isinstance(text, str) else json.dumps(text))
    return root


class PythonStackTests(unittest.TestCase):
    def test_django_migrates_and_runs_its_own_server_with_values_of_its_own(self):
        found = live_setup.detect(project({
            'manage.py': 'import os\n', 'requirements.txt': 'Django==5.1\npsycopg2-binary\n',
            'site/settings.py': "import os\nSECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'x')\n"
                                "if 'DATABASE_URL' in os.environ: pass\nREDIS = os.getenv('REDIS_URL')\n"}))
        profile = found['profile']
        self.assertEqual(found['facts']['framework'], 'django')
        self.assertEqual(profile['install'][0][-2:], ['-r', 'requirements.txt'])
        self.assertEqual(profile['prepare'], [['python', 'manage.py', 'migrate', '--noinput']])
        self.assertEqual(profile['start'][:3], ['python', 'manage.py', 'runserver'])
        self.assertGreater(len(profile['env']['DJANGO_SECRET_KEY']), 30)
        # no web address as a database: the app keeps its own SQLite; a Redis client gets a Redis address
        self.assertNotIn('DATABASE_URL', profile['env'])
        self.assertEqual(profile['env']['REDIS_URL'], 'redis://127.0.0.1:9')

    def test_flask_is_found_by_its_declared_app_or_its_factory_and_gets_its_tables(self):
        microblog = live_setup.detect(project({
            'requirements.txt': 'Flask==3.0\nFlask-Migrate==4\n', '.flaskenv': 'FLASK_APP=microblog.py\n',
            'microblog.py': 'from app import create_app\napp = create_app()\n', 'migrations/alembic.ini': '',
            'config.py': "import os\nMAIL_SERVER = os.environ.get('MAIL_SERVER')\n"}))['profile']
        self.assertEqual(microblog['start'][:5], ['python', '-m', 'flask', '--app', 'microblog'])
        self.assertEqual(microblog['prepare'], [['python', '-m', 'flask', '--app', 'microblog', 'db', 'upgrade']])
        self.assertEqual(microblog['env']['MAIL_SERVER'], '127.0.0.1', 'a mail server is a host, not an address')
        flaskr = live_setup.detect(project({
            'pyproject.toml': '[project]\ndependencies = ["flask"]\n',
            'flaskr/__init__.py': 'from flask import Flask\ndef create_app():\n    return Flask(__name__)\n',
            'flaskr/db.py': 'import click\n@click.command("init-db")\ndef init_db_command(): pass\n'}))['profile']
        self.assertEqual(flaskr['install'][0][-2:], ['-e', '.'])
        self.assertEqual(flaskr['start'][4], 'flaskr')
        self.assertEqual(flaskr['prepare'], [['python', '-m', 'flask', '--app', 'flaskr', 'init-db']])
        tested = live_setup.detect(project({
            'pyproject.toml': '[project]\ndependencies = ["flask"]\n[project.optional-dependencies]\ntest = ["pytest", "coverage"]\n',
            'flaskr/__init__.py': 'from flask import Flask\ndef create_app():\n    return Flask(__name__)\n'}))['profile']
        # flaskr of the corpus: its pytest is its test extra; every gate said its tests passed and none had run (M9.3)
        self.assertEqual((tested['install'][0][-2:], tested['checks']), (['-e', '.[test]'], [['python', '-m', 'pytest', '-q']]))
        both = live_setup.detect(project({
            'requirements.txt': 'flask\n', 'pyproject.toml': '[project]\nname = "x"\n[project.optional-dependencies]\ntest = ["pytest"]\n',
            'flaskr/__init__.py': 'from flask import Flask\ndef create_app():\n    return Flask(__name__)\n'}))['profile']
        self.assertEqual([step[-1] for step in both['install']], ['requirements.txt', '.[test]'], 'the extra beside the requirements')

    def test_streamlit_and_fastapi_start_their_entry(self):
        streamlit = live_setup.detect(project({'requirements.txt': 'streamlit\n', 'pages/a.py': 'import streamlit as st\n',
                                               'streamlit_app.py': 'import streamlit as st\n'}))['profile']
        self.assertEqual(streamlit['start'][:5], ['python', '-m', 'streamlit', 'run', 'streamlit_app.py'])
        api = live_setup.detect(project({'backend/requirements.txt': 'fastapi\nuvicorn\n',
                                         'backend/app/main.py': 'from fastapi import FastAPI\napi = FastAPI()\n'}))['profile']
        self.assertEqual((api['app'], api['start'][:4]), ('backend', ['python', '-m', 'uvicorn', 'app.main:api']))

    def test_flask_lists_its_own_pages_with_their_blueprint_prefixes(self):
        from types import SimpleNamespace
        from eaos.live.app.detect_python import served_pages
        routes = ('Endpoint     Methods    Rule\n-----------  ---------  ----------------\n'
                  'auth.login   GET, POST  /auth/login\napi.get_user  GET        /api/users/<int:id>\n'
                  'main.edit    POST       /edit\nstatic       GET        /static/<path:filename>\n')
        live = SimpleNamespace(profile={'start': ['python', '-m', 'flask', '--app', 'microblog', 'run']}, run=lambda argv, timeout: (0, routes, ''))
        self.assertEqual(served_pages(live), ['/auth/login'])
        self.assertEqual(served_pages(SimpleNamespace(profile={'start': ['npm', 'run', 'dev']})), [])


class OtherStackTests(unittest.TestCase):
    def test_expo_serves_its_web_app_on_the_runs_port(self):
        profile = live_setup.detect(project({'package.json': {'scripts': {'start': 'expo start'},
                                                              'dependencies': {'expo': '53', 'react-native-web': '0.20'}}}))['profile']
        self.assertEqual(profile['start'][:4], ['npx', 'expo', 'start', '--web'])
        self.assertIn(str(profile['port']), profile['start'])
        self.assertNotIn('baseline', profile)

    def test_a_static_site_is_built_then_served_from_its_folder_and_a_node_server_is_not_one(self):
        site = live_setup.detect(project({
            'package.json': {'scripts': {'build': 'node scripts/build.js', 'start': 'npm run build && node scripts/start.js'},
                             'devDependencies': {'browser-sync': '3', 'pug': '3'}},
            'package-lock.json': '{}', 'dist/index.html': '<h1>blog</h1>'}))
        self.assertEqual(site['facts']['framework'], 'static')
        self.assertEqual(site['profile']['build'], [['npm', 'run', 'build']])
        self.assertEqual(site['profile']['start'][-2:], ['--directory', 'dist'])
        pages = live_setup.detect(project({'index.html': '<h1>hi</h1>'}))['profile']
        self.assertEqual(pages['start'][-2:], ['--directory', '.'])
        server = live_setup.detect(project({'package.json': {'scripts': {'start': 'node server.js'},
                                                             'dependencies': {'express': '4', 'serve': '14'}},
                                            'public/index.html': ''}))['profile']
        self.assertEqual(server['start'], ['npm', 'run', 'start'])

    def test_a_node_server_with_no_script_starts_from_its_main_file_on_the_port_its_code_writes(self):
        # The corpus's task-api (Express, no dev or start script, `const port = 3000`): the run started `true`
        written = live_setup.detect(project({'package.json': {'main': 'index.js', 'dependencies': {'express': '5'}},
                                             'package-lock.json': '{}', 'index.js': 'const port = 3000;\napp.listen(port);'}))['profile']
        self.assertEqual((written['start'], written['port'], written['env']['PORT']), (['node', 'index.js'], 3000, '3000'))
        chosen = live_setup.detect(project({'package.json': {'dependencies': {'express': '5'}}, 'package-lock.json': '{}',
                                            'index.js': 'app.listen(process.env.PORT || 3000);'}))['profile']
        self.assertEqual(chosen['start'], ['node', 'index.js'])
        self.assertNotEqual(chosen['port'], 3000, "the run's own port, read from PORT")


class PagesAloneTests(unittest.TestCase):
    def test_a_site_of_pages_alone_is_a_project_to_check(self):
        # its script inside its index.html: the check said "no source file" and never ran the app
        from eaos.pipeline.runners import by_rules as runners
        from eaos.pipeline.stage_run import Context
        site = project({'index.html': '<button onclick="location.hash=\'#/a\'">A</button>'})
        import subprocess
        for argv in (['init', '-q'], ['add', '.'], ['-c', 'user.name=t', '-c', 'user.email=t@e', 'commit', '-qm', 'site']):
            subprocess.run(['git', '-C', str(site), *argv], check=True)
        context = Context(target=str(site), out=Path(scratch()), exclude=[], max_files=1000, max_bytes=2_000_000)
        self.assertIn('facts', runners.facts(context))


if __name__ == '__main__':
    unittest.main()

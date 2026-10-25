"""The common stacks start from their files alone, with no assistant (M5.1): the corpus' Python apps, its Expo apps
and its static site had never started without one."""
import json
import unittest
from pathlib import Path

from eaos.live import setup as live_setup
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

    def test_streamlit_and_fastapi_start_their_entry(self):
        streamlit = live_setup.detect(project({'requirements.txt': 'streamlit\n', 'pages/a.py': 'import streamlit as st\n',
                                               'streamlit_app.py': 'import streamlit as st\n'}))['profile']
        self.assertEqual(streamlit['start'][:5], ['python', '-m', 'streamlit', 'run', 'streamlit_app.py'])
        api = live_setup.detect(project({'backend/requirements.txt': 'fastapi\nuvicorn\n',
                                         'backend/app/main.py': 'from fastapi import FastAPI\napi = FastAPI()\n'}))['profile']
        self.assertEqual((api['app'], api['start'][:4]), ('backend', ['python', '-m', 'uvicorn', 'app.main:api']))


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


if __name__ == '__main__':
    unittest.main()

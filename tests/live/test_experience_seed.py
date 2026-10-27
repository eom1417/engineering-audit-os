"""The history seeded into the copy's own database (eaos/live/experience/seed.py): only a database the run made, only
its own tables and columns, every value bound."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.live.experience import seed as seed_module
from eaos.live.experience.seed import seed

DATA = {'seed': [{'table': 'orders', 'rows': [{'total': 42, 'note': "it's paid'); drop table orders; --"}, {'total': 7, 'nope': 1}]},
                 {'table': 'missing', 'rows': [{'x': 1}]}]}


def _run(folder, kind='sqlite'):
    runtime = Path(folder) / 'runtime'
    (runtime / 'sandbox').mkdir(parents=True)
    (runtime / 'run.json').write_text(json.dumps({'database': {'kind': kind, 'name': 'app'}}))
    return runtime


def _db(path):
    with sqlite3.connect(path) as db: db.execute('create table orders (id integer primary key, total integer, note text)')
    return path


class Seed(unittest.TestCase):
    def test_rows_go_into_the_copy_s_sqlite_with_values_bound_and_unknown_names_left_out(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = _run(folder)
            file = _db(runtime / 'sandbox/app.db')
            done = seed(DATA, {'runtime': str(runtime), 'database': str(file)})
            with sqlite3.connect(file) as db: rows = db.execute('select total, note from orders order by id').fetchall()
        self.assertEqual(done['seeded'], 2)
        self.assertEqual(rows, [(42, "it's paid'); drop table orders; --"), (7, None)])
        self.assertEqual(done['tables'][1], {'table': 'missing', 'seeded': 0, 'error': 'the database has no such table'})

    def test_a_rerun_on_the_same_copy_does_not_seed_the_history_twice(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = _run(folder)
            file = _db(runtime / 'sandbox/app.db')
            first = seed(DATA, {'runtime': str(runtime), 'database': str(file)})
            again = seed(DATA, {'runtime': str(runtime), 'database': str(file)})
            with sqlite3.connect(file) as db: count = db.execute('select count(*) from orders').fetchone()[0]
        self.assertEqual((first['seeded'], again['seeded'], count), (2, 0, 2))
        self.assertIn('already', again['why'])

    def test_postgres_rows_go_into_the_copys_own_database_named_with_the_runs_suffix(self):
        named = []

        class Server:
            def __init__(self, runtime): pass

            def running(self): return {'bin': '/pg/bin'}

            def url(self, state, name):
                named.append(name)
                return f'postgresql://127.0.0.1/{name}'
        with tempfile.TemporaryDirectory() as folder, mock.patch('eaos.core.system.local_db.LocalPostgres', Server), \
                mock.patch.object(seed_module, 'run_command', return_value=mock.Mock(stdout='INSERT 0 1\nINSERT 0 1\n', stderr='')):
            runtime = _run(folder, kind='postgres')
            done = seed({'seed': DATA['seed'][:1]}, {'runtime': str(runtime), 'apart': 'tests'})
            seed({'seed': DATA['seed'][:1]}, {'runtime': str(runtime)})
        self.assertEqual((done['seeded'], named), (2, ['app_tests', 'app']), 'the suffix names a database of its own')

    def test_a_database_outside_the_run_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime, theirs = _run(folder), _db(Path(folder) / 'person.db')
            done = seed(DATA, {'runtime': str(runtime), 'database': str(theirs)})
            with sqlite3.connect(theirs) as db: count = db.execute('select count(*) from orders').fetchone()[0]
        self.assertEqual((done['seeded'], count), (0, 0))
        self.assertIn("run's own folder", done['why'])

    def test_an_app_on_no_database_of_the_run_s_own_is_not_seeded(self):
        with tempfile.TemporaryDirectory() as folder:
            done = seed(DATA, {'runtime': str(_run(folder, kind='mysql'))})
        self.assertEqual(done['seeded'], 0)
        self.assertIn('not covered', done['why'])


if __name__ == '__main__':
    unittest.main()

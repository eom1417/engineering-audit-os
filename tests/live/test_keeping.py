"""How the data is saved and kept, on a copy (M14): the database filled, read and restored; the saves sorted; the files
the server wrote; two edits of one record."""
import json
import sqlite3
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from eaos.live.keeping import files, lost_update, restore, stored, synthetic, volume, writes
from eaos.live.keeping.database import Sqlite
from shared_fixture import scratch

PICTURE = 'data:image/png;base64,' + 'A' * 3000


def app_db(folder):
    path = Path(folder) / 'app.db'
    with sqlite3.connect(path) as db:
        db.executescript("""create table customers (id integer primary key, email text unique, name text, city text);
            create table invoices (id integer primary key, customer text, logo text, body text);""")
        for n in range(6):
            db.execute('insert into customers (email, name, city) values (?, ?, ?)', (f'p{n}@shop.sa', f'Person {n}', 'Riyadh'))
            db.execute('insert into invoices (customer, logo, body) values (?, ?, ?)', (f'Person {n}', PICTURE, 'x' * 20000))
    return Sqlite(path)


class TheDatabase(unittest.TestCase):
    def setUp(self):
        self.folder = Path(scratch('eaos-keeping-'))
        self.db = app_db(self.folder)

    def test_the_copy_is_filled_to_a_real_size_its_unique_columns_kept_unique(self):
        grown = volume.fill(self.db)
        self.assertEqual(grown['customers'], {'before': 6, 'after': 300})        # GROWTH times, under ROWS
        self.assertEqual(len({row[0] for row in self.db.rows('select email from customers')}), 300)

    def test_a_table_the_copy_left_empty_gets_a_year_of_records_its_keys_pointing_at_their_parents(self):
        with sqlite3.connect(self.db.path) as db:
            db.executescript('create table posts (id integer primary key, author_id integer not null references customers (id), '
                             'title text not null, created datetime, published boolean);')
        made = synthetic.fill_empty(self.db)
        self.assertEqual(made['posts'], {'before': 0, 'after': synthetic.ROWS})
        orphans = self.db.rows('select count(*) from posts where author_id not in (select id from customers)')
        self.assertEqual(orphans, [['0']])
        self.assertEqual(len({row[0][:10] for row in self.db.rows('select created from posts')}), synthetic.ROWS)

    def test_whole_documents_pictures_in_rows_and_values_kept_in_two_tables_are_read(self):
        columns = {(c['table'], c['column']): c for c in stored.columns(self.db)}
        self.assertEqual(columns[('invoices', 'logo')]['images'], 6)
        self.assertGreater(columns[('invoices', 'body')]['average'], 10000)
        self.assertEqual([(s['one'], s['other']) for s in stored.shared(self.db)], [(['customers', 'name'], ['invoices', 'customer'])])

    def test_the_restore_drill_runs_the_project_s_backup_and_says_the_table_it_misses(self):
        project = self.folder / 'project'
        (project / 'scripts').mkdir(parents=True)
        (project / 'scripts/backup.sh').write_text('sqlite3 app.db ".dump customers" > backup.sql\n', encoding='utf-8')
        self.assertEqual([c['source'] for c in restore.commands(project)], ['scripts/backup.sh'])
        dump = self.folder / 'backup.sql'
        with sqlite3.connect(self.db.path) as source:
            dump.write_text('\n'.join(line for line in source.iterdump() if 'invoices' not in line), encoding='utf-8')
        rows = restore.compare(self.db, restore._restored(None, self.db, dump, self.folder))
        self.assertEqual({r['table']: r['restored'] for r in rows}, {'customers': 6, 'invoices': None})
        own = restore.compare(self.db, Sqlite(restore._own_dump(self.db, self.folder)))
        self.assertTrue(all(r['same'] for r in own))


class TheRun(unittest.TestCase):
    def test_a_save_that_sends_back_what_the_page_read_or_grows_with_the_data_is_sorted_out(self):
        read = {'path': '/api/orders', 'ids': ['id:1', 'id:2', 'id:3']}
        page = lambda size, sent: {'path': '/', 'reads': [read], 'writes': [{'method': 'POST', 'path': '/api/state', 'bytes': size, 'ids': sent}]}
        before, after = {'pages': [page(2000, ['id:1'])]}, {'pages': [page(90000, ['id:1'])]}
        self.assertEqual([r['kind'] for r in writes.sorted_out(before, after)], ['grows'])
        self.assertEqual([r['kind'] for r in writes.sorted_out({'pages': [page(500, read['ids'])]})], ['resends'])
        self.assertEqual(writes.sorted_out({'pages': [page(500, ['id:9'])]}), [])

    def test_the_files_a_server_wrote_while_it_ran_are_its_data_and_what_it_installed_is_not(self):
        copy = Path(scratch('eaos-copy-'))
        (copy / 'node_modules/x').mkdir(parents=True)
        (copy / 'old.json').write_text('{}')
        since = time.time() + 1
        time.sleep(1.1)
        (copy / 'state.json').write_text('{"orders": []}')
        (copy / 'node_modules/x/cache.json').write_text('{}')
        (copy / '.eaos-lock/shots').mkdir(parents=True); (copy / '.eaos-lock/shots/home.png').write_bytes(b'png')   # EAOS's own
        self.assertEqual([f['path'] for f in files.written(copy, since)], ['state.json'])


class Records(BaseHTTPRequestHandler):
    """A record API that takes any write whole (no version): the second, stale write undoes the first."""
    record = {'id': 1, 'title': 'first', 'note': 'n'}
    careful = False

    def _send(self, status, value):
        self.send_response(status); self.send_header('Content-Type', 'application/json'); self.end_headers()
        self.wfile.write(json.dumps(value).encode())

    def do_GET(self): self._send(200, [Records.record] if self.path == '/api/notes' else Records.record)

    def do_PUT(self):
        sent = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if Records.careful and sent.get('title') != Records.record['title'] and sent.get('note') != Records.record['note']:
            return self._send(409, {})
        Records.record = sent
        self._send(200, sent)

    def log_message(self, *args): pass


class TwoEdits(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Records)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def test_a_stale_write_taken_without_a_conflict_loses_the_first_edit_and_a_409_keeps_it(self):
        Records.record, Records.careful = {'id': 1, 'title': 'first', 'note': 'n'}, False
        self.assertTrue(lost_update.probe(self.base, [('PUT', '/api/notes/:id')], '')[0]['lost'])
        Records.record, Records.careful = {'id': 1, 'title': 'first', 'note': 'n'}, True
        self.assertFalse(lost_update.probe(self.base, [('PUT', '/api/notes/:id')], '')[0]['lost'])


if __name__ == '__main__':
    unittest.main()

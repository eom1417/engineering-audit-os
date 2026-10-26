"""Row-level security and access policies are read from SQL migrations in their net state."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.facts.domain.model import sql_access, table_key
from eaos.facts.run import collect

POLICY = 'CREATE POLICY "own rows" ON public.accounts FOR SELECT TO authenticated USING (auth.uid() = owner);'


class SqlAccessTests(unittest.TestCase):
    def test_policies_and_row_level_security_are_read_in_their_net_state(self):
        recreated = sql_access([('migrations/001.sql', POLICY),
                                ('migrations/002.sql', 'DROP POLICY IF EXISTS "own rows" ON public.accounts;\n' + POLICY)])
        self.assertEqual(list(recreated['policies']), [('public.accounts', 'own rows')])
        self.assertEqual(recreated['policies'][('public.accounts', 'own rows')]['path'], 'migrations/002.sql')
        # Migrations apply in path order, not listing order.
        self.assertEqual(sql_access([('migrations/002.sql', 'DROP POLICY "p" ON accounts;'),
                                     ('migrations/001.sql', 'CREATE POLICY "p" ON accounts USING (true);')])['policies'], {})
        access = sql_access([('schema.sql', 'ALTER TABLE public.notes ENABLE ROW LEVEL SECURITY;\n'
                                            'CREATE POLICY "anyone" ON public.notes FOR ALL USING (true) WITH CHECK (true);')])
        self.assertIn('public.notes', access['rls'])
        policy = access['policies'][('public.notes', 'anyone')]
        self.assertEqual((policy['command'], policy['open']), ('ALL', True))
        dropped = sql_access([('a.sql', 'ALTER TABLE t ENABLE ROW LEVEL SECURITY;\n'
                                        'CREATE POLICY "p" ON t FOR SELECT USING (x);\nDROP TABLE t;')])
        self.assertEqual((dropped['policies'], dropped['rls'], dropped['dropped']), ({}, set(), {'public.t'}))
        self.assertEqual({table_key('"public"."Accounts"'), table_key('accounts'), table_key('public.accounts')},
                         {'public.accounts'})

    def test_only_real_table_declarations_become_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            for name, text in {'server/db.ts': 'db.exec(`CREATE TABLE IF NOT EXISTS ${name} (id int)`);\n'
                                               'db.exec("CREATE TABLE IF NOT EXISTS sessions (id int)");\n',
                               'PLAN/notes.md': 'We will run CREATE TABLE audit_log (id int).\n',
                               'db/schema.sql': 'CREATE TABLE audit_log (id int);\n'}.items():
                (repo / name).parent.mkdir(parents=True, exist_ok=True)
                (repo / name).write_text(text)
            collect(repo, Path(tmp) / 'out', ['domain'])
            facts = json.loads((Path(tmp) / 'out/facts/domain.json').read_text())['facts']
        found = sorted((f['value']['name'], f['location']['path']) for f in facts if f['kind'] == 'data_table')
        # A table named at run time is not a table called "if"; prose quoting a schema declares nothing.
        self.assertEqual(found, [('audit_log', 'db/schema.sql'), ('sessions', 'server/db.ts')])

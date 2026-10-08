"""Row-level security and access policies are read from SQL migrations in their net state."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.facts.domain import sql_access, table_key
from eaos.facts.run import collect


class SqlAccessTests(unittest.TestCase):
    def test_a_policy_dropped_and_created_again_counts_once(self):
        files = [('migrations/001.sql', 'CREATE POLICY "own rows" ON public.accounts FOR SELECT TO authenticated USING (auth.uid() = owner);'),
                 ('migrations/002.sql', 'DROP POLICY IF EXISTS "own rows" ON public.accounts;\n'
                                        'CREATE POLICY "own rows" ON public.accounts FOR SELECT TO authenticated USING (auth.uid() = owner);')]
        access = sql_access(files)
        self.assertEqual(list(access['policies']), [('public.accounts', 'own rows')])
        self.assertEqual(access['policies'][('public.accounts', 'own rows')]['path'], 'migrations/002.sql')

    def test_migrations_apply_in_path_order(self):
        files = [('migrations/002.sql', 'DROP POLICY "p" ON accounts;'),
                 ('migrations/001.sql', 'CREATE POLICY "p" ON accounts USING (true);')]
        self.assertEqual(sql_access(files)['policies'], {})

    def test_row_level_security_and_open_policies_are_recorded(self):
        files = [('schema.sql', 'ALTER TABLE public.notes ENABLE ROW LEVEL SECURITY;\n'
                                'CREATE POLICY "anyone" ON public.notes FOR ALL USING (true) WITH CHECK (true);')]
        access = sql_access(files)
        self.assertIn('public.notes', access['rls'])
        policy = access['policies'][('public.notes', 'anyone')]
        self.assertEqual((policy['command'], policy['open']), ('ALL', True))

    def test_a_dropped_table_keeps_no_policy(self):
        files = [('a.sql', 'ALTER TABLE t ENABLE ROW LEVEL SECURITY;\nCREATE POLICY "p" ON t FOR SELECT USING (x);\nDROP TABLE t;')]
        access = sql_access(files)
        self.assertEqual((access['policies'], access['rls'], access['dropped']), ({}, set(), {'public.t'}))

    def test_one_spelling_per_table(self):
        self.assertEqual({table_key('"public"."Accounts"'), table_key('accounts'), table_key('public.accounts')},
                         {'public.accounts'})


class TableDeclarationTests(unittest.TestCase):
    def tables(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'
            for name, text in files.items():
                (repo / name).parent.mkdir(parents=True, exist_ok=True)
                (repo / name).write_text(text)
            collect(repo, Path(tmp) / 'out', ['domain'])
            facts = json.loads((Path(tmp) / 'out/facts/domain.json').read_text())['facts']
        return sorted((f['value']['name'], f['location']['path']) for f in facts if f['kind'] == 'data_table')

    def test_a_table_named_at_run_time_is_not_a_table_called_if(self):
        found = self.tables({'server/db.ts': 'db.exec(`CREATE TABLE IF NOT EXISTS ${name} (id int)`);\n'
                                             'db.exec("CREATE TABLE IF NOT EXISTS sessions (id int)");\n'})
        self.assertEqual(found, [('sessions', 'server/db.ts')])

    def test_prose_quoting_a_schema_declares_no_table(self):
        found = self.tables({'PLAN/notes.md': 'We will run CREATE TABLE audit_log (id int).\n',
                             'db/schema.sql': 'CREATE TABLE audit_log (id int);\n'})
        self.assertEqual(found, [('audit_log', 'db/schema.sql')])


if __name__ == '__main__':
    unittest.main()

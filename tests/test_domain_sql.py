"""Row-level security and access policies are read from SQL migrations in their net state."""
import unittest

from eaos.facts.domain import sql_access, table_key


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


if __name__ == '__main__':
    unittest.main()

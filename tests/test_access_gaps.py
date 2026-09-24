"""A Supabase table without row-level security, or with a write policy that checks nothing, is a confirmed risk."""
import json
from pathlib import Path
import unittest

from eaos.pipeline import execute
from shared_fixture import TemporaryWorkspace

MIGRATION = '''
CREATE TABLE public.notes (id uuid primary key, body text);
CREATE TABLE public.posts (id uuid primary key, owner uuid);
ALTER TABLE public.posts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anyone can post" ON public.posts FOR INSERT TO authenticated WITH CHECK (true);
CREATE TABLE public.accounts (id uuid primary key, owner uuid);
ALTER TABLE public.accounts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own account" ON public.accounts FOR SELECT TO authenticated USING (auth.uid() = owner);
'''


class AccessGapTests(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        root = Path(cls.workspace().name)
        target = root / 'app'
        (target / 'supabase/migrations').mkdir(parents=True)
        (target / 'supabase/migrations/20260101000000_init.sql').write_text(MIGRATION)
        (target / 'src').mkdir()
        (target / 'src/client.ts').write_text('export const ready = true;\n')
        cls.out = root / 'report'
        execute(target, cls.out, site=False)
        cls.claims = json.loads((cls.out / 'dossier.json').read_text())['claims']
        cls.gaps = [c for c in cls.claims if (c.get('render') or {}).get('key', '').startswith('access_gap_')]

    def test_the_table_without_rls_and_the_open_write_policy_are_the_only_gaps(self):
        found = sorted((c['render']['key'], c['render']['params']['table']) for c in self.gaps)
        self.assertEqual(found, [('access_gap_no_rls', 'public.notes'), ('access_gap_open_write', 'public.posts')])

    def test_each_gap_is_confirmed_by_its_probe(self):
        self.assertTrue(all(c['confidence'] == 'CONFIRMED' for c in self.gaps), [c['confidence'] for c in self.gaps])
        probes = json.loads((self.out / 'probes.json').read_text())
        rows = [p for p in probes if p['specification'].get('query') == 'access_gap_present']
        self.assertEqual(sorted(p['status'] for p in rows), ['CONFIRMED', 'CONFIRMED'])

    def test_the_security_surface_states_the_row_level_security_picture(self):
        text = (self.out / 'SECURITY-SURFACE.md').read_text(encoding='utf-8')
        self.assertIn('2/3', text)
        self.assertIn('public.notes', text)
        self.assertIn('anyone can post', text)

    def test_each_gap_gets_a_real_remediation_pattern(self):
        tasks = json.loads((self.out / 'plan.json').read_text())['tasks']
        ids = {c['id'] for c in self.gaps}
        patterns = {t.get('pattern') for t in tasks if t.get('claim_id') in ids}
        self.assertEqual(patterns, {'access_gap'})


if __name__ == '__main__':
    unittest.main()

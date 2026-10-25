"""A Supabase table without row-level security, or with a write policy that checks nothing, is a confirmed finding of
the data layer (eaos/analysis/layers/data.py), a card with the reference's fix."""
import json
from pathlib import Path

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
        execute(target, cls.out)
        claims = json.loads((cls.out / 'dossier.json').read_text())['claims']
        cls.gaps = [c for c in claims if (c.get('render') or {}).get('key') == 'layer_finding'
                    and c['render']['params']['rule'] in ('table-without-rls', 'open-write-policy')]

    def test_the_table_without_rls_and_the_open_write_policy_are_confirmed_cards_with_their_fix(self):
        self.assertEqual(sorted(c['render']['params']['rule'] for c in self.gaps), ['open-write-policy', 'table-without-rls'])
        self.assertIn('public.notes', next(c['statement'] for c in self.gaps if c['render']['params']['rule'] == 'table-without-rls'))
        self.assertIn('public.posts', next(c['statement'] for c in self.gaps if c['render']['params']['rule'] == 'open-write-policy'))
        self.assertTrue(all(c['confidence'] == 'CONFIRMED' for c in self.gaps), [c['confidence'] for c in self.gaps])
        probes = json.loads((self.out / 'probes.json').read_text())
        rows = [p for p in probes if p['specification'].get('query') == 'boundary_finding_present']
        self.assertTrue(rows and all(p['status'] == 'CONFIRMED' for p in rows), rows)
        tasks = json.loads((self.out / 'plan.json').read_text())['tasks']
        ids = {c['id'] for c in self.gaps}
        mine = [t for t in tasks if t.get('claim_id') in ids]
        self.assertEqual({t.get('pattern') for t in mine}, {'layer_boundary'})
        # the card names the boundary it breaks and the reference's fix, for the person and for the judge (M6.11)
        self.assertTrue(all(t['render']['params']['boundary'] == 'data' and 'owner' in t['render']['params']['fix_en'] for t in mine))

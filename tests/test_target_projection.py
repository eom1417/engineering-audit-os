"""The target: the same features on the reference type, every file placed, every component disposed by its numbers."""
import json
from pathlib import Path

from shared_fixture import Workspace

from eaos.reference_architecture import by_id
from eaos.target_projection import disposition, forbidden, infrastructure, moves, place, project

RULES = json.loads((Path(__file__).resolve().parents[1] / 'eaos/rules/disposition-rules.json').read_text())
REFERENCE = by_id('react-tanstack-start-supabase')


def stats(**change):
    base = {'files': 4, 'moved': 0, 'moved_share': 0.0, 'forbidden': 0, 'complexity_max': 5,
            'duplicated_lines': 0, 'unreachable': 0, 'critical': 0}
    return {**base, **change}


class PlacementTests(Workspace):
    def test_every_file_is_placed_and_every_forbidden_import_named(self):
        features = [{'name': 'Contas', 'files': ['src/components/accounts/Card.tsx', 'src/lib/format.ts']},
                    {'name': 'Metas', 'files': ['src/lib/format.ts']}]
        placed = place(['src/components/accounts/Card.tsx', 'src/lib/format.ts', 'src/components/ui/button.tsx', 'vite.config.ts'],
                       features, REFERENCE)
        self.assertEqual(placed['src/components/accounts/Card.tsx'], ('feature:contas', 'features'))
        self.assertEqual(placed['src/lib/format.ts'], ('lib', 'lib'))
        self.assertEqual(placed['src/components/ui/button.tsx'], ('ui', 'ui'))
        self.assertEqual(placed['vite.config.ts'], ('platform', 'platform'))
        # A file moves only when it is not where its component keeps files.
        self.assertTrue(moves('src/components/accounts/Card.tsx', 'feature:contas', 'features', REFERENCE))
        self.assertFalse(moves('src/features/contas/Card.tsx', 'feature:contas', 'features', REFERENCE))
        self.assertFalse(moves('src/lib/format.ts', 'lib', 'lib', REFERENCE))
        # An import the layer rules do not allow is forbidden.
        placed = {'src/lib/a.ts': ('lib', 'lib'), 'src/services/s.ts': ('data-access', 'data-access'),
                  'src/routes/r.tsx': ('routes', 'routes')}
        edges = [('src/lib/a.ts', 'src/services/s.ts'), ('src/routes/r.tsx', 'src/lib/a.ts')]
        self.assertEqual(forbidden(edges, placed, REFERENCE), [('src/lib/a.ts', 'src/services/s.ts')])


class DispositionTests(Workspace):
    def test_each_disposition_follows_the_declared_rules_in_order_and_says_why(self):
        # The self-audit sent the whole `eaos` package to rebuild for one function past complexity 40: a complex
        # function or a critical item is changed in place; only a structural reason (most files move) is a rebuild.
        cases = [(dict(unreachable=4, moved=4, moved_share=1.0), 'delete'), (dict(moved=3, moved_share=0.75), 'rebuild'),
                 (dict(complexity_max=41), 'modify'), (dict(critical=1), 'modify'), ({}, 'retain'),
                 (dict(forbidden=1), 'modify'), (dict(complexity_max=15), 'modify')]
        for change, expected in cases:
            with self.subTest(change=change):
                self.assertEqual(disposition(stats(**change), RULES)[0], expected)
        self.assertIn('complexity_max 41', disposition(stats(complexity_max=41), RULES)[1])


class InfrastructureTests(Workspace):
    def facts(self, **kinds):
        from collections import defaultdict
        facts = defaultdict(list)
        facts.update(kinds)
        return facts

    def test_every_baseline_item_is_decided_from_evidence_for_the_kind_of_program(self):
        root = Path(self.tmp)
        (root / 'supabase/migrations').mkdir(parents=True)
        facts = self.facts(ci_step=[{}], env_read=[{'location': {'path': 'src/a.ts'}}, {'location': {'path': 'src/b.ts'}}],
                           data_table=[{'value': {'rls_enabled': True}}, {'value': {'rls_enabled': False}}])
        rows = {row['area']: row for row in infrastructure(REFERENCE, facts, root, ['src/a.ts'])}
        self.assertTrue(rows['ci']['present'])
        self.assertFalse(rows['configuration']['present'])
        self.assertIn('2 file(s)', rows['configuration']['evidence'])
        self.assertFalse(rows['identity']['present'])
        self.assertTrue(rows['migrations']['present'])
        self.assertEqual(rows['dependencies']['tool'], 'Renovate')
        self.assertTrue(rows['dependencies']['alternative'].startswith('Do nothing'))
        self.assertIn('hosting', rows)
        # A desktop program is not hosted and needs no telemetry server.
        rows = {row['area']: row for row in infrastructure(by_id('python-desktop'), self.facts(), Path(self.tmp), [])}
        self.assertNotIn('hosting', rows)
        self.assertIsNone(rows['observability']['tool'])
        self.assertIn('local rotating log', rows['observability']['tool_reason'])


class ProjectTests(Workspace):
    def test_the_projection_keeps_its_contract_and_places_every_feature(self):
        from eaos.artifact_contracts import contracts, validate
        from eaos.target_architecture import build
        out, target = Path(self.tmp) / 'out', Path(self.tmp) / 'project'
        (out / 'facts').mkdir(parents=True)
        target.mkdir()
        (target / 'package.json').write_text(json.dumps({'dependencies': {'react': '1', '@tanstack/react-start': '1', '@supabase/supabase-js': '1'}}))
        nodes = [('src/components/accounts/Card.tsx', ['src/services/accounts.ts']), ('src/services/accounts.ts', ['src/lib/money.ts']),
                 ('src/lib/money.ts', [])]
        (out / 'facts/graph.json').write_text(json.dumps({'facts': [
            {'id': f'F{i}', 'kind': 'graph_node', 'location': {'path': p}, 'value': {'depends_on': d, 'fan_in': 0, 'fan_out': len(d)}}
            for i, (p, d) in enumerate(nodes)]}))
        (out / 'features.json').write_text(json.dumps({'features': [{'name': 'Contas', 'files': ['src/components/accounts/Card.tsx']}]}))
        result = build(out, target=target)
        self.assertEqual(result['reference'], 'react-tanstack-start-supabase')
        self.assertEqual(validate(result, contracts()['target-fragment']), [])
        self.assertEqual({c['name'] for c in result['target_components']}, {'feature:contas', 'data-access', 'lib'})
        feature = json.loads((out / 'features.json').read_text())['features'][0]
        self.assertEqual(feature['target_component'], 'feature:contas')
        components = {c['origin']: c for c in result['current_components']}
        # One file to move into its feature is an edit (modify), not a rebuild.
        self.assertEqual(components['src/components/accounts']['relation'], 'modify')
        self.assertTrue(all(row.get('target_component') for row in result['gap_matrix']))
        # Without a recognisable type there is no projection.
        empty = Path(self.tmp) / 'empty'
        (empty / 'facts').mkdir(parents=True)
        self.assertIsNone(project(empty, empty))

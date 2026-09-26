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
    def test_a_file_one_feature_uses_goes_to_that_feature_and_a_shared_one_to_its_layer(self):
        features = [{'name': 'Contas', 'files': ['src/components/accounts/Card.tsx', 'src/lib/format.ts']},
                    {'name': 'Metas', 'files': ['src/lib/format.ts']}]
        placed = place(['src/components/accounts/Card.tsx', 'src/lib/format.ts', 'src/components/ui/button.tsx', 'vite.config.ts'],
                       features, REFERENCE)
        self.assertEqual(placed['src/components/accounts/Card.tsx'], ('feature:contas', 'features'))
        self.assertEqual(placed['src/lib/format.ts'], ('lib', 'lib'))
        self.assertEqual(placed['src/components/ui/button.tsx'], ('ui', 'ui'))
        self.assertEqual(placed['vite.config.ts'], ('platform', 'platform'))

    def test_a_file_moves_only_when_it_is_not_where_its_component_keeps_files(self):
        self.assertTrue(moves('src/components/accounts/Card.tsx', 'feature:contas', 'features', REFERENCE))
        self.assertFalse(moves('src/features/contas/Card.tsx', 'feature:contas', 'features', REFERENCE))
        self.assertFalse(moves('src/lib/format.ts', 'lib', 'lib', REFERENCE))

    def test_an_import_the_layer_rules_do_not_allow_is_forbidden(self):
        placed = {'src/lib/a.ts': ('lib', 'lib'), 'src/services/s.ts': ('data-access', 'data-access'),
                  'src/routes/r.tsx': ('routes', 'routes')}
        edges = [('src/lib/a.ts', 'src/services/s.ts'), ('src/routes/r.tsx', 'src/lib/a.ts')]
        self.assertEqual(forbidden(edges, placed, REFERENCE), [('src/lib/a.ts', 'src/services/s.ts')])


class DispositionTests(Workspace):
    def test_each_disposition_follows_the_declared_rules_in_order(self):
        self.assertEqual(disposition(stats(unreachable=4, moved=4, moved_share=1.0), RULES)[0], 'delete')
        self.assertEqual(disposition(stats(moved=3, moved_share=0.75), RULES)[0], 'rebuild')
        self.assertEqual(disposition(stats(complexity_max=41), RULES)[0], 'rebuild')
        self.assertEqual(disposition(stats(critical=1), RULES)[0], 'rebuild')
        self.assertEqual(disposition(stats(), RULES)[0], 'retain')
        self.assertEqual(disposition(stats(forbidden=1), RULES)[0], 'modify')
        self.assertEqual(disposition(stats(complexity_max=15), RULES)[0], 'modify')

    def test_the_reason_carries_the_numbers_that_decided(self):
        relation, reason = disposition(stats(complexity_max=41), RULES)
        self.assertIn('complexity_max 41', reason)


class InfrastructureTests(Workspace):
    def facts(self, **kinds):
        from collections import defaultdict
        facts = defaultdict(list)
        facts.update(kinds)
        return facts

    def test_every_baseline_item_is_decided_from_evidence(self):
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

    def test_a_desktop_program_is_not_hosted_and_needs_no_telemetry_server(self):
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
        self.assertEqual(components['src/components/accounts']['relation'], 'rebuild')
        self.assertTrue(any('Rebuild `src/components/accounts` as `feature:contas`' in d['chosen'] for d in result['decisions']))
        self.assertTrue(all(row.get('target_component') for row in result['gap_matrix']))

    def test_without_a_recognisable_type_there_is_no_projection(self):
        (Path(self.tmp) / 'facts').mkdir()
        self.assertIsNone(project(self.tmp, self.tmp))

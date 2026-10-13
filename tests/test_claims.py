"""The claim ledger: attribution, falsifiability and an honest bridge from existing records."""
from pathlib import Path
import tempfile
import unittest
from eaos import claims
from eaos.claims import from_facts, naming
from eaos.fact_claims import engine_measurement
from eaos.compose.labels import IMPACTS, impact_of
from eaos.facts.run import collect
from eaos.facts.store import read_set
from eaos.vocabulary import schema_errors


def valid(**overrides):
    row = claims.make(1, 'Pricing rules live in two modules that must agree', 'cause', 'HYPOTHESIS',
                      ['model_inference'], ['SRC-1'], 'A single owner for the rule with the second site removed.')
    row.update(overrides)
    return row


class LedgerTests(unittest.TestCase):
    def test_the_ledger_rejects_claims_that_cannot_be_trusted(self):
        self.assertEqual(claims.errors([valid()]), [])
        self.assertEqual(claims.errors([valid(confidence='CONFIRMED', method=['test_evidence'])]), [])
        fact_backed = claims.make(1, 'Two modules define the same rule', 'business_rule', 'CONFIRMED', ['static_fact'],
                                  [], 'A single definition imported by the other site.', fact_ids=['FACT-1'])
        self.assertEqual(claims.errors([fact_backed]), [])
        bad_id = {'id': 'not-a-claim-id', 'statement': 'x' * 20, 'claim_type': 'risk', 'confidence': 'LIKELY',
                  'method': [], 'evidence_ids': ['SRC-1'], 'falsifier': 'a counter-example', 'status': 'open',
                  'created_at': '2026-09-20T00:00:00Z'}
        cases = [
            ([valid(falsifier='  ')], {}, 'a claim must state what would disprove it'),
            ([valid(confidence='CONFIRMED')], {}, 'CONFIRMED requires'),
            ([valid(evidence_ids=[])], {}, 'no evidence and no fact'),
            ([valid()], {'evidence_ids': {'SRC-other'}}, 'unknown evidence'),
            ([valid(), valid()], {}, 'duplicate claim id'),
            ([valid(claim_type='risk', disposition={'kind': 'accepted'})], {}, 'accepted risk needs an owner'),
            ([bad_id], {}, 'does not match'),
            ([bad_id], {}, 'needs at least 1 items'),
        ]
        for rows, options, expected in cases:
            with self.subTest(expected):
                self.assertIn(expected, ' '.join(claims.errors(rows, **options)))
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, 'Claim ledger rejected'):
            claims.save(Path(tmp) / 'claims.json', [valid(falsifier='')])
        self.assertTrue(any('unenforced keywords' in p for p in schema_errors('x', {'type': 'string', 'multipleOf': 2})))

    def test_deterministic_facts_become_confirmed_claims_and_legacy_records_do_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'a.py').write_text('from b import helper\n\n\ndef run():\n    return helper()\n')
            (repo / 'b.py').write_text('import a\n\n\ndef helper():\n    return a\n')
            collect(repo, Path(tmp) / 'out', ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'graph'])
            sets = {'graph': read_set(Path(tmp) / 'out', 'graph')}
        rows = from_facts(sets)
        self.assertTrue(rows)
        self.assertEqual((rows[0]['confidence'], rows[0]['method']), ('CONFIRMED', ['static_fact']))
        self.assertTrue(rows[0]['falsifier'])
        self.assertEqual(claims.errors(rows, fact_ids={f['id'] for f in sets['graph']['facts']}), [])
        finding = {'id': 'F-27-001', 'current_behavior': 'Verification can pass with an unplanned file present',
                   'why_this_matters': 'A delivery can be described as verified when it is not',
                   'claim_status': 'confirmed', 'status': 'open', 'evidence_ids': ['SRC-1'], 'affected_components': ['N-1']}
        model = {'nodes': [{'id': 'N-1', 'name': 'remediate', 'responsibility': 'runs checks', 'evidence_ids': ['SRC-1']}],
                 'contracts': [], 'business_rules': []}
        legacy = claims.from_legacy([finding], model, [], [])
        self.assertEqual((legacy[0]['confidence'], legacy[0]['method']), ('LIKELY', ['model_inference']))
        self.assertEqual(claims.errors(legacy, evidence_ids={'SRC-1'}), [])

    def test_a_large_project_never_overflows_a_statement(self):
        members = [f'package/module_{index:03d}.py' for index in range(80)]
        self.assertIn('74 more', naming(members))
        self.assertEqual(naming(['a.py', 'b.py']), 'a.py, b.py')
        sets = {'graph': {'facts': [{'id': 'FACT-1', 'kind': 'graph_cycle', 'location': {'path': members[0]},
                                     'value': {'members': members}}], 'summary': {}},
                'history': {'facts': [], 'summary': {'commits_analysed': 0}}}
        cycle = next(c for c in from_facts(sets) if c['claim_type'] == 'structure')
        self.assertLess(len(cycle['statement']), 600)
        self.assertEqual(cycle['probe_spec']['specification']['members'], members)
        definitions = [{'path': f'apps/api/test/auth/case-{n:02d}.e2e.ts', 'line': 24} for n in range(57)]
        sets = {'domain': {'facts': [{'id': 'FACT-1', 'kind': 'domain_constant', 'value': {
            'name': 'TEST_PORT', 'duplicated': True, 'definitions': definitions, 'distinct_values': 1}}]}}
        rule = next(c for c in from_facts(sets) if (c.get('render') or {}).get('key') == 'duplicated_rule')
        self.assertIn('and 51 more', rule['statement'])
        self.assertIn('57 places', rule['statement'])
        cut = claims.make(1, 'x' * 900, 'risk', 'CONFIRMED', ['static_fact'], ['E-1'], 'the fact disappears')
        self.assertEqual(len(cut['statement']), 600)
        self.assertEqual([e for e in claims.errors([cut]) if 'statement' in e], [])


def fact(kind, value, symbol='fn', id_=None):
    return {'id': id_ or 'FACT-' + kind, 'kind': 'engine_finding', 'location': {'path': 'a.py', 'symbol': symbol},
            'value': {'kind': kind, **value}}


def cluster(facts):
    return {'place': 'a.py', 'fact_ids': [f['id'] for f in facts]}


class EngineClusterImpactTests(unittest.TestCase):
    """Each corroborated kind cites the measurement that earned the finding, and says so when there is none."""

    def scenario(self, kind, facts, sets=None):
        sets = {'external': {'facts': facts}} if sets is None else sets
        key, params = engine_measurement(kind, cluster(facts), sets)
        return IMPACTS['ar'][key].format(**params)

    def test_each_kind_cites_its_measurement(self):
        cases = [
            ('complexity', fact('complexity', {'measurements': [{'name': 'cyclomatic_complexity', 'value': 27,
                                                                 'threshold': 15}]}), ['27', 'العتبة', '15']),
            ('literal_duplication', fact('literal_duplication', {'sites': [{'path': 'a.py'}, {'path': 'b.py'}]}),
             ['2', 'مواضع']),
            ('coupling', fact('coupling', {'message': 'fan-in 14, fan-out 10'}), ['14', '10']),
            ('dead_code', fact('dead_code', {'message': 'Dead code candidate: function eaos/foo.bar'},
                               symbol='eaos/foo.bar'), ['eaos/foo.bar']),
            ('complexity', fact('complexity', {}), ['لم يبلّغ']),
        ]
        for kind, row, expected in cases:
            with self.subTest(kind=kind, expected=expected):
                text = self.scenario(kind, [row])
                for piece in expected:
                    self.assertIn(piece, text)
        self.assertNotIn('العتبة', self.scenario('complexity', [fact('complexity', {})]))
        self.assertIn('لم يبلّغ', self.scenario('complexity', [], {}))

    def test_reforge_measurements_are_read_and_rendered_in_both_languages(self):
        complex_fact = fact('complexity', {'measurements': [
            {'name': 'function.complexity', 'value': 40.0, 'threshold': 15.0, 'unit': 'complexity'}]})
        plain = fact('complexity', {'measurements': [{'name': 'complexity', 'value': 9}]}, id_='FACT-plain')
        key, params = engine_measurement('complexity', cluster([plain, complex_fact]),
                                                  {'external': {'facts': [plain, complex_fact]}})
        self.assertEqual((key, params), ('engine_cluster_complexity', {'value': 40, 'threshold': 15}))
        literal = fact('literal_duplication', {
            'measurements': [{'name': 'group.size', 'value': 24.0, 'threshold': 12.0}],
            'sites': [{'path': 'a.py', 'line': None}] + [{'path': 'a.py', 'line': n} for n in range(34)]})
        self.assertEqual(engine_measurement('literal_duplication', cluster([literal]),
                                                     {'external': {'facts': [literal]}}),
                         ('engine_cluster_literal_duplication', {'sites': 24}))
        render = {'key': 'engine_cluster', 'params': {'place': 'a.py', 'kind': 'complexity', 'engines': 'x, y',
                                                      'verdict': 'corroborated', **params, 'impact_key': key}}
        for language in ('ar', 'en'):
            rendered = impact_of({'impact': {'scenario': ''}, 'render': render}, language)
            self.assertIn('40', rendered, language)
            self.assertIn('15', rendered, language)
        self.assertFalse(any('؀' <= c <= 'ۿ' for c in impact_of({'render': render}, 'en')))


def metric(path, symbol, scope, branches, lines=200):
    return {'id': f'FACT-m-{symbol}', 'kind': 'metric', 'location': {'path': path, 'symbol': symbol},
            'value': {'scope': scope, 'branches': branches, 'lines': lines}}


def measured(id_, engine, path, value, name='cyclomatic_complexity', threshold=15):
    return {'id': id_, 'kind': 'engine_finding', 'location': {'path': path, 'symbol': 'f'},
            'value': {'engine': engine, 'kind': 'complexity', 'subject_kind': 'symbol', 'message': 'complex',
                      'measurements': [{'name': name, 'value': value, 'threshold': threshold}], 'sites': []}}


class HotspotTests(unittest.TestCase):
    """Self-audit: class totals (Actions, 171 branches over 20 methods) were hotspots, each doubled by an engine card on the
    same file, and a complexity-1 file ranked third among the risks: ranking had no severity term."""

    def test_a_hotspot_is_one_function_one_card_and_the_worst_measurement_ranks_first(self):
        from eaos.ranking import rank
        node = lambda path, rank_, deps=(): {'id': 'G-' + path, 'kind': 'graph_node', 'location': {'path': path},
                                             'value': {'attention_rank': rank_, 'depends_on': list(deps)}}
        observed = {'status': 'observed', 'granularity': 'symbol'}
        sets = {'graph': {'facts': [node('a.py', 1), node('c.py', 2), node('d.py', 3), node('e.py', 4, ['a.py', 'c.py', 'd.py'])]},
                'metrics': {'facts': [metric('a.py', 'run', 'function', 90), metric('a.py', 'Actions', 'class', 171)]},
                'history': {'facts': [], 'summary': {'commits_analysed': 0}},
                'external': {'facts': [measured('F-1', 'lizard', 'a.py', 45), measured('F-2', 'reforge', 'a.py', 45, 'function.complexity'),
                                       measured('F-3', 'lizard', 'c.py', 16), measured('F-4', 'reforge', 'c.py', 16, 'function.complexity'),
                                       measured('F-5', 'lizard', 'd.py', 45), measured('F-6', 'reforge', 'd.py', 45, 'function.complexity')],
                             'summary': {'evaluated_kinds': {e: {'complexity': observed} for e in ('lizard', 'reforge')}}}}
        rows = from_facts(sets)
        hotspots = [c for c in rows if c['render']['key'] == 'hotspot']
        self.assertEqual([c['render']['params']['symbol'] for c in hotspots], ['run'])
        self.assertEqual(sorted(hotspots[0]['fact_ids']), ['F-1', 'F-2', 'FACT-m-run'])
        engine = {c['render']['params']['place']: c for c in rows if c['render']['key'] == 'engine_cluster'}
        self.assertEqual(sorted(engine), ['c.py', 'd.py'])
        ranked = rank(list(engine.values()), sets, {})
        self.assertEqual([c['render']['params']['place'] for c in ranked], ['d.py', 'c.py'])
        self.assertEqual(ranked[0]['priority_factors']['severity']['factor'], 3.0)

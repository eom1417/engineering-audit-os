"""The claim ledger: attribution, falsifiability and an honest bridge from existing records."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos import claims
from eaos.facts.run import collect
from eaos.facts.store import read_set

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


class ClaimLedgerTests(unittest.TestCase):
    def valid(self, **overrides):
        row = claims.make(1, 'Pricing rules live in two modules that must agree', 'cause', 'HYPOTHESIS',
                          ['model_inference'], ['SRC-1'], 'A single owner for the rule with the second site removed.')
        row.update(overrides)
        return row

    def test_a_well_formed_claim_passes(self):
        self.assertEqual(claims.errors([self.valid()]), [])

    def test_a_claim_without_a_falsifier_is_rejected(self):
        self.assertIn('CLM-001: a claim must state what would disprove it', claims.errors([self.valid(falsifier='  ')]))

    def test_model_inference_alone_can_never_be_confirmed(self):
        problems = claims.errors([self.valid(confidence='CONFIRMED')])
        self.assertTrue(any('CONFIRMED requires' in problem for problem in problems))
        self.assertEqual(claims.errors([self.valid(confidence='CONFIRMED', method=['test_evidence'])]), [])

    def test_a_claim_without_evidence_or_facts_is_rejected(self):
        self.assertTrue(any('no evidence and no fact' in problem for problem in claims.errors([self.valid(evidence_ids=[])])))

    def test_unknown_evidence_reference_is_caught(self):
        self.assertTrue(any('unknown evidence' in problem for problem in claims.errors([self.valid()], evidence_ids={'SRC-other'})))

    def test_duplicate_ids_are_caught(self):
        self.assertTrue(any('duplicate claim id' in problem for problem in claims.errors([self.valid(), self.valid()])))

    def test_accepted_risk_needs_an_owner_and_a_reason(self):
        risky = self.valid(claim_type='risk', disposition={'kind': 'accepted'})
        self.assertTrue(any('accepted risk needs an owner' in problem for problem in claims.errors([risky])))

    def test_saving_an_invalid_ledger_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Claim ledger rejected'):
                claims.save(Path(tmp) / 'claims.json', [self.valid(falsifier='')])

    def test_deterministic_facts_become_confirmed_claims_with_refutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'a.py').write_text('from b import helper\n\n\ndef run():\n    return helper()\n')
            (repo / 'b.py').write_text('import a\n\n\ndef helper():\n    return a\n')
            collect(repo, Path(tmp) / 'out', ['syntax', 'resolve', 'entrypoints', 'config', 'metrics', 'graph'])
            sets = {name: read_set(Path(tmp) / 'out', name) for name in ['graph']}
            rows = claims.from_facts(sets)
            self.assertTrue(rows)
            self.assertEqual(rows[0]['confidence'], 'CONFIRMED')
            self.assertEqual(rows[0]['method'], ['static_fact'])
            self.assertTrue(rows[0]['falsifier'])
            self.assertEqual(claims.errors(rows, fact_ids={f['id'] for f in sets['graph']['facts']}), [])

    def test_legacy_records_bridge_without_gaining_certainty(self):
        finding = {'id': 'F-27-001', 'current_behavior': 'Verification can pass with an unplanned file present',
                   'why_this_matters': 'A delivery can be described as verified when it is not',
                   'claim_status': 'confirmed', 'status': 'open', 'evidence_ids': ['SRC-1'], 'affected_components': ['N-1']}
        model = {'nodes': [{'id': 'N-1', 'name': 'remediate', 'responsibility': 'runs checks', 'evidence_ids': ['SRC-1']}],
                 'contracts': [], 'business_rules': []}
        rows = claims.from_legacy([finding], model, [], [])
        self.assertEqual(rows[0]['confidence'], 'LIKELY')
        self.assertEqual(rows[0]['method'], ['model_inference'])
        self.assertTrue(all(row['falsifier'] for row in rows))
        self.assertEqual(claims.errors(rows, evidence_ids={'SRC-1'}), [])


class SchemaKeywordTests(unittest.TestCase):
    """Regression: declared constraints that nobody enforced read as guarantees they were not."""

    def test_identifier_pattern_and_minimum_items_are_enforced(self):
        bad = {'id': 'not-a-claim-id', 'statement': 'x' * 20, 'claim_type': 'risk', 'confidence': 'LIKELY',
               'method': [], 'evidence_ids': ['SRC-1'], 'falsifier': 'a counter-example', 'status': 'open',
               'created_at': '2026-09-20T00:00:00Z'}
        problems = ' '.join(claims.errors([bad]))
        self.assertIn('does not match', problems)
        self.assertIn('needs at least 1 items', problems)

    def test_unenforced_schema_keywords_are_reported_not_ignored(self):
        from eaos.audit_records import schema_errors
        problems = schema_errors('x', {'type': 'string', 'multipleOf': 2})
        self.assertTrue(any('unenforced keywords' in problem for problem in problems))

    def test_a_fact_backed_claim_needs_no_evidence_id(self):
        row = claims.make(1, 'Two modules define the same rule', 'business_rule', 'CONFIRMED', ['static_fact'],
                          [], 'A single definition imported by the other site.', fact_ids=['FACT-1'])
        self.assertEqual(claims.errors([row]), [])


class LargeCycleTests(unittest.TestCase):
    """A cycle with many members must still produce a claim the ledger accepts."""

    def test_the_statement_stays_inside_the_schema_limit(self):
        from eaos.claims import naming
        members = [f'package/module_{index:03d}.py' for index in range(80)]
        statement = 'Import cycle between: ' + naming(members)
        self.assertLess(len(statement), 600)
        self.assertIn('74 more', statement)
        self.assertIn('package/module_000.py', statement)

    def test_a_small_cycle_still_names_every_member(self):
        from eaos.claims import naming
        self.assertEqual(naming(['a.py', 'b.py']), 'a.py, b.py')

    def test_the_full_member_list_stays_in_the_probe(self):
        from eaos.claims import from_facts
        members = [f'm{index}.py' for index in range(80)]
        sets = {'graph': {'facts': [{'id': 'FACT-1', 'kind': 'graph_cycle',
                                     'location': {'path': 'm0.py'}, 'value': {'members': members}}],
                          'summary': {}},
                'history': {'facts': [], 'summary': {'commits_analysed': 0}}}
        claims = from_facts(sets)
        cycle = next(claim for claim in claims if claim['claim_type'] == 'structure')
        self.assertLess(len(cycle['statement']), 600)
        self.assertEqual(cycle['probe_spec']['specification']['members'], members)


class EngineClusterImpactTests(unittest.TestCase):
    """Each corroborated kind must cite the measurement that earned the finding."""

    def _fact(self, kind, value, **extra):
        return {'id': 'FACT-' + kind, 'kind': 'engine_finding',
                'location': {'path': extra.get('path', 'a.py'), 'symbol': extra.get('symbol', 'fn')},
                'value': {'kind': kind, **value}}

    def _cluster(self, facts):
        return {'place': 'a.py', 'fact_ids': [f['id'] for f in facts]}

    def test_complexity_cites_value_and_threshold_when_present(self):
        from eaos.claims import _impact_for_engine_cluster
        fact = self._fact('complexity', {'measurements': [{'name': 'cyclomatic_complexity',
                                                          'value': 27, 'threshold': 15}]})
        scenario = _impact_for_engine_cluster('complexity', self._cluster([fact]),
                                              {'external': {'facts': [fact]}})
        self.assertIn('27', scenario)
        self.assertIn('العتبة', scenario)
        self.assertIn('15', scenario)

    def test_literal_duplication_cites_site_count(self):
        from eaos.claims import _impact_for_engine_cluster
        fact = self._fact('literal_duplication', {'sites': [{'path': 'a.py'}, {'path': 'b.py'}]})
        scenario = _impact_for_engine_cluster('literal_duplication', self._cluster([fact]),
                                              {'external': {'facts': [fact]}})
        self.assertIn('2', scenario)
        self.assertIn('مواضع', scenario)

    def test_coupling_cites_party_count(self):
        from eaos.claims import _impact_for_engine_cluster
        fact = self._fact('coupling', {'message': 'fan-in 14, fan-out 10'})
        scenario = _impact_for_engine_cluster('coupling', self._cluster([fact]),
                                              {'external': {'facts': [fact]}})
        self.assertIn('14', scenario)
        self.assertIn('10', scenario)

    def test_dead_code_names_the_symbol(self):
        from eaos.claims import _impact_for_engine_cluster
        fact = self._fact('dead_code', {'message': 'Dead code candidate: function eaos/foo.bar'},
                          symbol='eaos/foo.bar')
        scenario = _impact_for_engine_cluster('dead_code', self._cluster([fact]),
                                              {'external': {'facts': [fact]}})
        self.assertIn('eaos/foo.bar', scenario)

    def test_missing_measurement_says_so_instead_of_inventing_one(self):
        from eaos.claims import _impact_for_engine_cluster
        fact = self._fact('complexity', {})  # no measurements, no sites, no message
        scenario = _impact_for_engine_cluster('complexity', self._cluster([fact]),
                                              {'external': {'facts': [fact]}})
        self.assertIn('لم يبلّغ', scenario)
        self.assertNotIn('العتبة', scenario)

    def test_missing_fact_set_returns_generic_with_reason(self):
        from eaos.claims import _impact_for_engine_cluster
        scenario = _impact_for_engine_cluster('complexity', self._cluster([]), {})
        self.assertIn('لم يبلّغ', scenario)

    def test_the_rendered_impact_carries_the_measurement_in_both_languages(self):
        # The reader, not the producer: cards and reports render through impact_of, which used to
        # return the one shared engine_cluster sentence and never reached the measured scenario.
        from eaos.claims import _engine_cluster_measurement
        from eaos.compose.labels import impact_of
        fact = self._fact('complexity', {'measurements': [{'name': 'cyclomatic_complexity',
                                                          'value': 27, 'threshold': 15}]})
        key, params = _engine_cluster_measurement('complexity', self._cluster([fact]),
                                                  {'external': {'facts': [fact]}})
        render = {'key': 'engine_cluster', 'params': {'place': 'a.py', 'kind': 'complexity',
                                                      'engines': 'x, y', 'verdict': 'corroborated',
                                                      **params, 'impact_key': key}}
        for language in ('ar', 'en'):
            rendered = impact_of({'impact': {'scenario': ''}, 'render': render}, language)
            self.assertIn('27', rendered, language)
            self.assertIn('15', rendered, language)
        self.assertFalse(any('؀' <= c <= 'ۿ' for c in impact_of({'render': render}, 'en')))

    def test_reforge_measurement_names_are_read_as_the_engine_writes_them(self):
        # Printed from a real run: reforge writes function.complexity with a threshold and group.size
        # for repeated literals; its sites list is longer than the occurrence count.
        from eaos.claims import _engine_cluster_measurement
        complex_fact = self._fact('complexity', {'measurements': [
            {'name': 'function.complexity', 'value': 40.0, 'threshold': 15.0, 'unit': 'complexity'}]})
        plain = dict(self._fact('complexity', {'measurements': [{'name': 'complexity', 'value': 9}]}),
                     id='FACT-plain')
        sets = {'external': {'facts': [plain, complex_fact]}}
        self.assertEqual(_engine_cluster_measurement('complexity', self._cluster([plain, complex_fact]), sets),
                         ('engine_cluster_complexity', {'value': 40, 'threshold': 15}))
        literal = self._fact('literal_duplication', {
            'measurements': [{'name': 'group.size', 'value': 24.0, 'threshold': 12.0}],
            'sites': [{'path': 'a.py', 'line': None}] + [{'path': 'a.py', 'line': n} for n in range(34)]})
        self.assertEqual(_engine_cluster_measurement('literal_duplication', self._cluster([literal]),
                                                     {'external': {'facts': [literal]}}),
                         ('engine_cluster_literal_duplication', {'sites': 24}))

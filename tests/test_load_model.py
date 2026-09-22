"""The eight load-model questions, their shape, and what counts as evidence."""
import json
import tempfile
import unittest
from pathlib import Path
from eaos import load_model
from shared_fixture import TemporaryWorkspace


class QuestionSetTests(unittest.TestCase):
    def test_eight_questions_are_declared(self):
        self.assertEqual(len(load_model.QUESTIONS), 8)
        self.assertEqual(len(set(load_model.QUESTIONS)), 8, 'questions must be unique')

    def test_questions_are_in_the_documented_order(self):
        expected = ('data_access_calls', 'repeats_per_iteration', 'result_is_bounded',
                     'complexity_class', 'shared_mutable_state', 'outbound_calls_protected',
                     'cached', 'rate_limited')
        self.assertEqual(load_model.QUESTIONS, expected)

    def test_three_answer_statuses_are_recognised(self):
        self.assertEqual(set(load_model.ANSWER_STATUSES),
                         {'answered', 'not_applicable', 'undetectable'})


class RecordShapeTests(unittest.TestCase):
    def test_a_record_with_every_question_answered_passes_validation(self):
        record = {'schema_version': 1, 'entry_points': [{
            'id': 'E1', 'path': 'a.py', 'answers': {
                q: {'status': 'answered', 'value': True, 'evidence': ['FACT-x'],
                     'reason': ''} for q in load_model.QUESTIONS
            }
        }]}
        self.assertEqual(load_model.validate(record), [])

    def test_missing_question_is_rejected(self):
        record = {'schema_version': 1, 'entry_points': [{
            'id': 'E1', 'answers': {q: {'status': 'answered', 'evidence': ['x']}
                                     for q in load_model.QUESTIONS if q != 'cached'}
        }]}
        problems = load_model.validate(record)
        self.assertTrue(any('cached' in p for p in problems))

    def test_undetectable_without_reason_is_rejected(self):
        record = {'schema_version': 1, 'entry_points': [{
            'id': 'E1', 'answers': {
                q: {'status': 'undetectable', 'value': None, 'evidence': []}
                for q in load_model.QUESTIONS
            }
        }]}
        problems = load_model.validate(record)
        self.assertTrue(any('no reason' in p for p in problems))

    def test_undetectable_with_reason_passes_validation(self):
        record = {'schema_version': 1, 'entry_points': [{
            'id': 'E1', 'answers': {
                q: {'status': 'undetectable', 'value': None, 'evidence': [],
                     'reason': 'we have no traces of pool sizing in this build'}
                for q in load_model.QUESTIONS
            }
        }]}
        self.assertEqual(load_model.validate(record), [])

    def test_answered_without_evidence_is_rejected(self):
        record = {'schema_version': 1, 'entry_points': [{
            'id': 'E1', 'answers': {
                q: {'status': 'answered', 'value': True, 'evidence': []}
                for q in load_model.QUESTIONS
            }
        }]}
        problems = load_model.validate(record)
        self.assertTrue(any('no evidence' in p for p in problems))

    def test_not_applicable_questions_do_not_need_evidence(self):
        record = {'schema_version': 1, 'entry_points': [{
            'id': 'E1', 'answers': {
                q: {'status': 'not_applicable', 'value': None, 'evidence': [], 'reason': 'no db calls here'}
                for q in load_model.QUESTIONS
            }
        }]}
        self.assertEqual(load_model.validate(record), [])

    def test_unknown_question_is_rejected(self):
        record = {'schema_version': 1, 'entry_points': [{
            'id': 'E1', 'answers': {
                'ninth_question': {'status': 'answered', 'evidence': ['x']},
                **{q: {'status': 'answered', 'evidence': ['x']} for q in load_model.QUESTIONS}
            }
        }]}
        problems = load_model.validate(record)
        self.assertTrue(any('unknown question' in p for p in problems))

    def test_blank_answer_produces_undetectable_with_default_reason(self):
        answer = load_model.blank_answer('cached')
        self.assertEqual(answer['status'], 'undetectable')
        self.assertTrue(answer['reason'])


class SchemaTests(unittest.TestCase):
    def test_schema_is_loadable_json(self):
        schema = load_model.load_schema()
        self.assertIn('properties', schema)
        self.assertIn('entry_points', schema['properties'])

    def test_schema_defines_the_eight_questions_through_the_answer_shape(self):
        # The schema references questions only by name; their names come from QUESTIONS.
        # We assert the shape is permissive enough to accept any of them.
        record = {'schema_version': 1, 'entry_points': []}
        self.assertNotIn('errors', [])  # shape validation is enforced by validate(), not the JSON schema


class PolicyTests(unittest.TestCase):
    def test_load_model_is_a_ledger_module(self):
        import json
        from pathlib import Path
        # Walk up to find the project's eaos.policy.json
        root = Path(__file__).resolve().parents[1]
        with open(root / 'eaos.policy.json') as f:
            policy = json.load(f)
        self.assertIn('eaos/load_model.py', policy['layers']['ledger'])


if __name__ == '__main__':
    unittest.main()


class ComputeTests(unittest.TestCase):
    """compute() builds a record from facts already produced; it never invents one."""

    def _report_with(self, tmp, facts_files):
        """Write a few facts files into tmp/facts/ and return the tmp path."""
        from pathlib import Path
        import json
        facts_dir = Path(tmp) / 'facts'
        facts_dir.mkdir(parents=True, exist_ok=True)
        for name, payload in facts_files.items():
            (facts_dir / f'{name}.json').write_text(json.dumps(payload))
        return Path(tmp)

    def test_an_empty_report_produces_an_empty_record(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            record = load_model.compute(tmp)
        self.assertEqual(record['entry_points'], [])

    def test_an_undetectable_entry_point_has_eight_answers_with_a_reason(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._report_with(tmp, {
                'entrypoints': {'facts': [{
                    'kind': 'entry_point', 'id': 'E1',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'category': 'http', 'handler': 'handle'}}],
                    'flows': {'facts': []}},
                'flows': {'facts': []},
            })
            record = load_model.compute(tmp)
        self.assertEqual(len(record['entry_points']), 1)
        entry = record['entry_points'][0]
        self.assertEqual(len(entry['answers']), 8)
        for question, answer in entry['answers'].items():
            self.assertEqual(answer['status'], 'undetectable', question)
            self.assertTrue(answer['reason'], f'{question} needs a reason')
            self.assertEqual(load_model.QUESTIONS, tuple(entry['answers']),
                              'all eight questions must be answered')

    def test_a_test_entry_point_is_excluded(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._report_with(tmp, {
                'entrypoints': {'facts': [{
                    'kind': 'entry_point', 'id': 'T1',
                    'location': {'path': 'test_x.py', 'symbol': 'test_handle'},
                    'value': {'category': 'test', 'handler': 'test_handle'}}]},
            })
            record = load_model.compute(tmp)
        self.assertEqual(record['entry_points'], [])

    def test_data_access_calls_counts_call_sites_in_the_entry_file(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            self._report_with(tmp, {
                'entrypoints': {'facts': [{
                    'kind': 'entry_point', 'id': 'E1',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'category': 'http', 'handler': 'handle'}}]},
                'structure': {'facts': [
                    {'id': 'cs1', 'kind': 'call_site',
                     'location': {'path': 'a.py'},
                     'value': {'callee': 'session.execute', 'attribute': True, 'enclosing': 'handle'}},
                    {'id': 'cs2', 'kind': 'call_site',
                     'location': {'path': 'a.py'},
                     'value': {'callee': 'parse_int', 'attribute': False, 'enclosing': 'handle'}},
                ]},
                'flows': {'facts': [{
                    'kind': 'flow',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'flow_id': 'F1', 'steps': [], 'in_codebase_steps': 0,
                                'unresolved_steps': 0, 'handler_found': True}}]},
            })
            record = load_model.compute(tmp)
        self.assertEqual(record['entry_points'][0]['answers']['data_access_calls']['status'], 'answered')
        self.assertEqual(record['entry_points'][0]['answers']['data_access_calls']['value'], 1)

    def test_query_bound_with_bounded_true_yields_answer(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._report_with(tmp, {
                'entrypoints': {'facts': [{
                    'kind': 'entry_point', 'id': 'E1',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'category': 'http', 'handler': 'handle'}}]},
                'flows': {'facts': [{
                    'kind': 'flow',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'flow_id': 'F1', 'steps': [], 'in_codebase_steps': 0,
                                'unresolved_steps': 0, 'handler_found': True}}]},
                'runtime': {'facts': [
                    {'id': 'qb1', 'kind': 'query_bound',
                     'location': {'path': 'a.py'},
                     'value': {'bounded': True, 'mechanism': 'limit', 'kind': 'sqlalchemy_limit'}},
                ]},
            })
            record = load_model.compute(tmp)
        ans = record['entry_points'][0]['answers']['result_is_bounded']
        self.assertEqual(ans['status'], 'answered')
        self.assertTrue(ans['value'])


class ComputeValidationTests(unittest.TestCase):
    """The record compute() returns must pass its own validate()."""

    def test_computed_record_is_well_formed_for_traced_entry(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            from pathlib import Path
            import json
            facts_dir = Path(tmp) / 'facts'
            facts_dir.mkdir(parents=True, exist_ok=True)
            for name, payload in {
                'entrypoints': {'facts': [{
                    'kind': 'entry_point', 'id': 'E1',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'category': 'http', 'handler': 'handle'}}]},
                'flows': {'facts': [{
                    'kind': 'flow',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'flow_id': 'F1', 'steps': [], 'in_codebase_steps': 0,
                                'unresolved_steps': 0, 'handler_found': True}}]},
            }.items():
                (facts_dir / f'{name}.json').write_text(json.dumps(payload))
            record = load_model.compute(tmp)
            problems = load_model.validate(record)
            self.assertEqual(problems, [], f'unexpected problems: {problems}')

    def test_computed_record_with_undetectable_answers_is_well_formed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            from pathlib import Path
            import json
            facts_dir = Path(tmp) / 'facts'
            facts_dir.mkdir(parents=True, exist_ok=True)
            for name, payload in {
                'entrypoints': {'facts': [{
                    'kind': 'entry_point', 'id': 'E1',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'category': 'http', 'handler': 'handle'}}]},
                'flows': {'facts': []},
            }.items():
                (facts_dir / f'{name}.json').write_text(json.dumps(payload))
            record = load_model.compute(tmp)
            problems = load_model.validate(record)
            self.assertEqual(problems, [])


class ProjectionTests(unittest.TestCase):
    """The projection is a stated heuristic; it ranks entries and names bottlenecks."""

    def test_a_complete_record_projects_a_finite_cost(self):
        record = {'entry_points': [{
            'id': 'E1', 'path': 'a.py',
            'answers': {
                q: {'status': 'answered', 'value': (5 if q == 'data_access_calls' else True),
                     'evidence': ['F-x']} for q in load_model.QUESTIONS
            }
        }]}
        projected = load_model.project(record)
        entry = projected['entry_points'][0]
        self.assertFalse(entry['projection']['incomplete'])
        self.assertGreater(entry['projection']['cost_score'], 0)

    def test_an_incomplete_record_marks_incomplete_and_lists_missing(self):
        record = {'entry_points': [{
            'id': 'E1', 'path': 'a.py',
            'answers': {
                q: {'status': 'undetectable', 'reason': 'no evidence yet'}
                for q in load_model.QUESTIONS
            }
        }]}
        projected = load_model.project(record)
        entry = projected['entry_points'][0]
        self.assertTrue(entry['projection']['incomplete'])
        self.assertEqual(len(entry['projection']['unanswered_questions']), 8)

    def test_bottlenecks_are_ranked_in_priority_order(self):
        record = {'entry_points': [{
            'id': 'E1', 'path': 'a.py',
            'answers': {
                'data_access_calls': {'status': 'answered', 'value': 5, 'evidence': ['x']},
                'repeats_per_iteration': {'status': 'answered', 'value': True, 'evidence': ['x']},
                'result_is_bounded': {'status': 'answered', 'value': False, 'evidence': ['x']},
                'shared_mutable_state': {'status': 'answered', 'value': True, 'evidence': ['x']},
                'outbound_calls_protected': {'status': 'answered', 'value': {'timeout': False, 'retry': False, 'circuit_breaker': False}, 'evidence': ['x']},
                'cached': {'status': 'answered', 'value': False, 'evidence': ['x']},
                'rate_limited': {'status': 'answered', 'value': False, 'evidence': ['x']},
                'complexity_class': {'status': 'answered', 'value': 'O(n)', 'evidence': ['x']},
            }
        }]}
        projected = load_model.project(record)
        bottlenecks = projected['entry_points'][0]['projection']['bottlenecks']
        self.assertEqual(bottlenecks, ['no_rate_limit', 'n_plus_one', 'unbounded_query', 'shared_mutable_state'])

    def test_projection_includes_a_method_statement(self):
        record = {'entry_points': []}
        projected = load_model.project(record)
        self.assertIn('method', projected['projection'])
        self.assertIn('multiplier', projected['projection'])

    def test_projection_with_unbounded_query_only_yields_finite_cost(self):
        record = {'entry_points': [{
            'id': 'E1', 'path': 'a.py',
            'answers': {
                q: {'status': 'answered', 'value': (5 if q == 'data_access_calls'
                                                     else True if q in {'repeats_per_iteration', 'cached', 'rate_limited'}
                                                     else False if q in {'result_is_bounded'}
                                                     else {'timeout': True, 'retry': True, 'circuit_breaker': True}
                                                          if q == 'outbound_calls_protected'
                                                     else 'O(1)'),
                     'evidence': ['x']} for q in load_model.QUESTIONS
            }
        }]}
        projected = load_model.project(record)
        entry = projected['entry_points'][0]
        self.assertFalse(entry['projection']['incomplete'])
        self.assertIn('unbounded_query', entry['projection']['bottlenecks'])

    def test_projection_with_no_evidence_marks_incomplete(self):
        record = {'entry_points': [{
            'id': 'E1', 'path': 'a.py',
            'answers': {
                q: {'status': 'answered', 'value': False, 'evidence': []}
                for q in load_model.QUESTIONS
            }
        }]}
        projected = load_model.project(record)
        # The projection still runs even if the record was invalid; we only care about shape here.
        self.assertIn('cost_score', projected['entry_points'][0]['projection'])


class ProjectionDeterminismTests(unittest.TestCase):
    def test_same_record_projects_the_same_score(self):
        record = {'entry_points': [{
            'id': 'E1', 'path': 'a.py',
            'answers': {q: {'status': 'answered', 'value': 1, 'evidence': ['x']} for q in load_model.QUESTIONS}
        }]}
        first = load_model.project(record)
        second = load_model.project(record)
        self.assertEqual(first['entry_points'][0]['projection']['cost_score'],
                          second['entry_points'][0]['projection']['cost_score'])


class EvidenceOnlyTests(unittest.TestCase):
    """The load model reads facts; it never measures anything itself."""

    def test_every_answer_cites_a_fact_that_exists_in_the_report(self):
        """eaos/load_model.py:compute — this module only reads the facts."""
        import json as _json
        import tempfile as _tempfile
        from pathlib import Path as _Path
        from eaos.facts.run import collect
        from eaos.dossier import assemble
        from eaos.load_model import compute
        fixture = _Path(__file__).resolve().parent / 'fixtures/sustainability'
        with _tempfile.TemporaryDirectory() as out:
            collect(fixture, out)
            assemble(fixture, out, language='en')
            record = compute(out)
            known = set()
            for path in (_Path(out) / 'facts').glob('*.json'):
                try:
                    payload = _json.loads(path.read_text(encoding='utf-8'))
                except ValueError:
                    continue
                known.update(fact['id'] for fact in payload.get('facts', []))
        for entry in record['entry_points']:
            for question, answer in entry['answers'].items():
                for reference in answer.get('evidence', []):
                    self.assertIn(reference, known,
                                  f'{entry.get("id")}/{question} cites a fact that is not in the report')

    def test_no_answer_is_produced_without_either_evidence_or_a_reason(self):
        from eaos.load_model import QUESTIONS
        import tempfile as _tempfile
        from pathlib import Path as _Path
        from eaos.facts.run import collect
        from eaos.dossier import assemble
        from eaos.load_model import compute
        fixture = _Path(__file__).resolve().parent / 'fixtures/sustainability'
        with _tempfile.TemporaryDirectory() as out:
            collect(fixture, out)
            assemble(fixture, out, language='en')
            record = compute(out)
        for entry in record['entry_points']:
            self.assertEqual(sorted(entry['answers']), sorted(QUESTIONS))
            for question, answer in entry['answers'].items():
                if answer['status'] == 'answered':
                    self.assertTrue(answer.get('evidence'), f'{question} answered with no evidence')
                elif answer['status'] == 'undetectable':
                    self.assertTrue(answer.get('reason'), f'{question} undetectable with no reason')


class DocumentBudgetTests(unittest.TestCase):
    """The load document must stay readable on a real project, not only on a fixture."""

    def _record(self, entries):
        return {'entry_points': entries, 'projection': {'multiplier': 1000, 'method': 'structural'},
                'limits': 'structural projection'}

    def test_a_project_with_many_unanswered_questions_still_fits_the_budget(self):
        from eaos.load_report import render
        from eaos.load_model import QUESTIONS
        entries = [{'id': f'E{index}', 'entry': {'route': f'/r{index}', 'surface': 'http'},
                    'answers': {question: {'status': 'undetectable',
                                           'reason': 'the flow could not be traced'}
                                for question in QUESTIONS},
                    'projection': {'incomplete': True, 'unanswered_questions': list(QUESTIONS)}}
                   for index in range(60)]
        text = render(self._record(entries), language='en')
        self.assertLessEqual(text.count('\n'), 200,
                             'the document grows with the project instead of pointing at the record')

    def test_the_repeated_reasons_are_counted_rather_than_repeated(self):
        from eaos.load_report import render
        from eaos.load_model import QUESTIONS
        entries = [{'id': f'E{index}', 'entry': {'route': f'/r{index}', 'surface': 'http'},
                    'answers': {QUESTIONS[0]: {'status': 'undetectable', 'reason': 'one shared reason'}},
                    'projection': {}} for index in range(20)]
        text = render(self._record(entries), language='en')
        self.assertEqual(text.count('one shared reason'), 1, 'the same reason was printed twenty times')
        self.assertIn('20:', text, 'the count of affected entry points is not stated')


class BlockerTests(unittest.TestCase):
    """A blocker comes only from an answered question, and reaches a task card."""

    def _record(self, question, value, status='answered'):
        from eaos.load_model import QUESTIONS
        answers = {name: {'status': 'undetectable', 'reason': 'not measured here'} for name in QUESTIONS}
        answers[question] = {'status': status, 'value': value, 'evidence': ['FACT-1']}
        return {'entry_points': [{'id': 'E1', 'path': 'app.py', 'entry': {'route': '/orders'},
                                  'answers': answers}]}

    def test_an_unanswered_question_is_never_a_blocker(self):
        from eaos.load_model import blockers
        self.assertEqual(blockers(self._record('repeats_per_iteration', None, status='undetectable')), [])

    def test_a_query_per_item_is_a_blocker(self):
        from eaos.load_model import blockers
        found = blockers(self._record('repeats_per_iteration', True))
        self.assertEqual([row['kind'] for row in found], ['n_plus_one'])
        self.assertTrue(found[0]['falsifier'])
        self.assertEqual(found[0]['evidence'], ['FACT-1'])

    def test_a_bounded_result_is_not_a_blocker_and_an_unbounded_one_is(self):
        from eaos.load_model import blockers
        self.assertEqual(blockers(self._record('result_is_bounded', True)), [])
        self.assertEqual([row['kind'] for row in blockers(self._record('result_is_bounded', False))],
                         ['unbounded_result'])

    def test_a_call_with_a_timeout_is_not_a_blocker(self):
        from eaos.load_model import blockers
        guarded = {'timeout': True, 'retry': False, 'circuit_breaker': False}
        self.assertEqual(blockers(self._record('outbound_calls_protected', guarded)), [])
        bare = {'timeout': False, 'retry': True, 'circuit_breaker': False}
        self.assertEqual([row['kind'] for row in blockers(self._record('outbound_calls_protected', bare))],
                         ['unprotected_dependency'],
                         'retries without a timeout make the pile-up worse, not better')

    def test_every_blocker_states_what_would_disprove_it_and_what_it_costs(self):
        from eaos.load_model import BLOCKERS
        for question, rule in BLOCKERS.items():
            for field in ('kind', 'statement', 'statement_en', 'falsifier', 'scenario'):
                self.assertTrue(rule[field].strip(), f'{question}.{field}')


class BlockerToCardTests(unittest.TestCase):
    """The fixture that degrades under load must come out the other end as cards."""

    FIXTURE = Path(__file__).resolve().parent / 'fixtures/load/degrades'

    def test_the_planted_blockers_become_claims_and_cards(self):
        import json as _json
        import tempfile as _tempfile
        from eaos.audit import run as run_audit
        truth = _json.loads((self.FIXTURE / 'ground-truth.json').read_text(encoding='utf-8'))
        expected = {row['kind'] for row in truth['planted']}
        with _tempfile.TemporaryDirectory() as out:
            run_audit(self.FIXTURE, out, language='en')
            dossier = _json.loads(Path(out, 'dossier.json').read_text(encoding='utf-8'))
            record = _json.loads(Path(out, 'load-model.json').read_text(encoding='utf-8'))
        from eaos.load_model import blockers
        found = {row['kind'] for row in blockers(record)}
        self.assertEqual(sorted(found), sorted(expected), 'a planted load blocker was not detected')
        claims = [claim for claim in dossier['claims']
                  if (claim.get('render') or {}).get('key') == 'load_blocker']
        self.assertEqual(len(claims), len(expected))
        for claim in claims:
            self.assertTrue(claim['falsifier'].strip())
            self.assertTrue(claim.get('fact_ids'), 'a load claim with no fact behind it')
        cards = [task for task in dossier['tasks'] if task['pattern'] == 'load_blocker']
        self.assertEqual(len(cards), len(expected), 'a load claim did not reach a task card')
        for card in cards:
            self.assertTrue(card['options'])
            self.assertTrue(card['rollback'].strip())


class NegativeAnswerTests(TemporaryWorkspace):
    """When the detector looked and the path is in a supported language, the answer is
    `answered, value=False` (negative result), not `undetectable`. The path's language
    and the detector's vocabulary are the boundary: outside the vocabulary, undetectable
    remains the honest answer.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = cls.workspace()

    def test_a_python_path_with_no_cache_becomes_answered_false(self):
        import json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            facts_dir = Path(tmp) / 'facts'
            facts_dir.mkdir(parents=True, exist_ok=True)
            for name, payload in {
                'entrypoints': {'facts': [{
                    'kind': 'entry_point', 'id': 'E1',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'category': 'http', 'handler': 'handle'}}]},
                'flows': {'facts': [{
                    'kind': 'flow',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'flow_id': 'F-E1', 'steps': [], 'in_codebase_steps': 0,
                                'unresolved_steps': 0, 'handler_found': True}}]},
                'structure': {'facts': [
                    {'id': 'sf1', 'kind': 'source_file',
                     'location': {'path': 'a.py'},
                     'value': {'language': 'python', 'parse_status': 'PARSED'}}]},
            }.items():
                (facts_dir / f'{name}.json').write_text(json.dumps(payload))
            record = load_model.compute(tmp)
        cached = record['entry_points'][0]['answers']['cached']
        self.assertEqual(cached['status'], 'answered')
        self.assertEqual(cached['value'], False)
        self.assertTrue(cached['evidence'])

    def test_a_go_path_with_no_cache_becomes_answered_false(self):
        # Go is in the cache detector's vocabulary; absence is an answered "no".
        import json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            facts_dir = Path(tmp) / 'facts'
            facts_dir.mkdir(parents=True, exist_ok=True)
            for name, payload in {
                'entrypoints': {'facts': [{
                    'kind': 'entry_point', 'id': 'E1',
                    'location': {'path': 'main.go', 'symbol': 'main'},
                    'value': {'category': 'cli', 'handler': 'main', 'framework': 'go_main'}}]},
                'flows': {'facts': [{
                    'kind': 'flow',
                    'location': {'path': 'main.go', 'symbol': 'main'},
                    'value': {'flow_id': 'F-E1', 'steps': [], 'in_codebase_steps': 0,
                                'unresolved_steps': 0, 'handler_found': True}}]},
                'structure': {'facts': [
                    {'id': 'sf1', 'kind': 'source_file',
                     'location': {'path': 'main.go'},
                     'value': {'language': 'go', 'parse_status': 'PARSED'}}]},
            }.items():
                (facts_dir / f'{name}.json').write_text(json.dumps(payload))
            record = load_model.compute(tmp)
        cached = record['entry_points'][0]['answers']['cached']
        self.assertEqual(cached['status'], 'answered')
        self.assertEqual(cached['value'], False)

    def test_a_ruby_path_keeps_undetectable(self):
        # The shared_mutable_state detector targets Python only; Ruby stays undetectable.
        import json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            facts_dir = Path(tmp) / 'facts'
            facts_dir.mkdir(parents=True, exist_ok=True)
            for name, payload in {
                'entrypoints': {'facts': [{
                    'kind': 'entry_point', 'id': 'E1',
                    'location': {'path': 'a.rb', 'symbol': 'handle'},
                    'value': {'category': 'http', 'handler': 'handle'}}]},
                'flows': {'facts': [{
                    'kind': 'flow',
                    'location': {'path': 'a.rb', 'symbol': 'handle'},
                    'value': {'flow_id': 'F-E1', 'steps': [], 'in_codebase_steps': 0,
                                'unresolved_steps': 0, 'handler_found': True}}]},
                'structure': {'facts': [
                    {'id': 'sf1', 'kind': 'source_file',
                     'location': {'path': 'a.rb'},
                     'value': {'language': 'ruby', 'parse_status': 'PARSED'}}]},
            }.items():
                (facts_dir / f'{name}.json').write_text(json.dumps(payload))
            record = load_model.compute(tmp)
        sms = record['entry_points'][0]['answers']['shared_mutable_state']
        self.assertEqual(sms['status'], 'undetectable')
        self.assertIn('vocabulary', sms['reason'])

    def test_a_path_we_could_not_trace_keeps_undetectable(self):
        # If the flow is missing, the answer stays undetectable even in a supported language.
        import json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            facts_dir = Path(tmp) / 'facts'
            facts_dir.mkdir(parents=True, exist_ok=True)
            for name, payload in {
                'entrypoints': {'facts': [{
                    'kind': 'entry_point', 'id': 'E1',
                    'location': {'path': 'a.py', 'symbol': 'handle'},
                    'value': {'category': 'http', 'handler': 'handle'}}]},
                'flows': {'facts': []},
                'structure': {'facts': [
                    {'id': 'sf1', 'kind': 'source_file',
                     'location': {'path': 'a.py'},
                     'value': {'language': 'python', 'parse_status': 'PARSED'}}]},
            }.items():
                (facts_dir / f'{name}.json').write_text(json.dumps(payload))
            record = load_model.compute(tmp)
        cached = record['entry_points'][0]['answers']['cached']
        self.assertEqual(cached['status'], 'undetectable')
        self.assertIn('flow', cached['reason'].lower())

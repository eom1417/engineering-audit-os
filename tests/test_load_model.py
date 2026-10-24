"""The eight load-model questions, what counts as evidence, and how blockers reach the plan."""
import json
from pathlib import Path
import tempfile
import unittest
import shared_fixture  # noqa: F401  (runs without measured detector verdicts)
from eaos.analysis import load_model
from eaos.facts.domain import js_mutable_globals
from eaos.facts.frameworks.http_access import bounded
from eaos.facts.frameworks.supabase_access import extract_calls
from eaos.analysis.load_model import BLOCKERS, QUESTIONS, blockers, compute, project, validate
from eaos.pipeline import execute

FIXTURES = Path(__file__).resolve().parent / 'fixtures'


def entry(path='a.py', **value):
    return {'kind': 'entry_point', 'id': 'E1', 'location': {'path': path, 'symbol': 'handle'},
            'value': {'category': 'http', 'surface': 'http', 'handler': 'handle', **value}}


def flow(path='a.py'):
    return {'kind': 'flow', 'location': {'path': path, 'symbol': 'handle'},
            'value': {'flow_id': 'F-E1', 'steps': [], 'in_codebase_steps': 0, 'unresolved_steps': 0, 'handler_found': True}}


def source(path, language):
    return {'id': 'sf1', 'kind': 'source_file', 'location': {'path': path}, 'value': {'language': language, 'parse_status': 'PARSED'}}


def computed(sets):
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / 'facts').mkdir()
        for name, facts in sets.items():
            (Path(tmp) / 'facts' / f'{name}.json').write_text(json.dumps({'facts': facts}))
        return compute(tmp)


def record_of(answer):
    return {'schema_version': 1, 'entry_points': [{'id': 'E1', 'path': 'a.py',
                                                   'answers': {q: answer(q) for q in QUESTIONS}}]}


class RecordTests(unittest.TestCase):
    def test_every_question_is_answered_from_the_facts_with_evidence_or_a_reason(self):
        self.assertEqual(QUESTIONS, ('data_access_calls', 'repeats_per_iteration', 'result_is_bounded', 'complexity_class',
                                     'shared_mutable_state', 'outbound_calls_protected', 'cached', 'rate_limited'))
        self.assertEqual(set(load_model.ANSWER_STATUSES), {'answered', 'not_applicable', 'undetectable'})
        valid = [lambda q: {'status': 'answered', 'value': True, 'evidence': ['FACT-x'], 'reason': ''},
                 lambda q: {'status': 'undetectable', 'value': None, 'evidence': [], 'reason': 'no traces of pool sizing'},
                 lambda q: {'status': 'not_applicable', 'value': None, 'evidence': [], 'reason': 'no db calls here'}]
        for answer in valid:
            self.assertEqual(validate(record_of(answer)), [])
        missing = record_of(lambda q: {'status': 'answered', 'evidence': ['x']})
        del missing['entry_points'][0]['answers']['cached']
        unknown = record_of(lambda q: {'status': 'answered', 'evidence': ['x']})
        unknown['entry_points'][0]['answers']['ninth_question'] = {'status': 'answered', 'evidence': ['x']}
        cases = [(missing, 'cached'), (unknown, 'unknown question'),
                 (record_of(lambda q: {'status': 'undetectable', 'value': None, 'evidence': []}), 'no reason'),
                 (record_of(lambda q: {'status': 'answered', 'value': True, 'evidence': []}), 'no evidence')]
        for record, expected in cases:
            with self.subTest(expected):
                self.assertTrue(any(expected in p for p in validate(record)))
        blank = load_model.blank_answer('cached')
        self.assertEqual(blank['status'], 'undetectable')
        self.assertTrue(blank['reason'])
        # compute() reads only the facts it is given.
        self.assertEqual(computed({})['entry_points'], [])
        test_entry = dict(entry('test_x.py'), id='T1', value={'category': 'test', 'handler': 'test_handle'})
        self.assertEqual(computed({'entrypoints': [test_entry]})['entry_points'], [])
        untraced = computed({'entrypoints': [entry()], 'flows': []})
        self.assertEqual(validate(untraced), [])
        answers = untraced['entry_points'][0]['answers']
        self.assertEqual(tuple(answers), QUESTIONS)
        self.assertTrue(all(a['status'] == 'undetectable' and a['reason'] for a in answers.values()))
        traced = computed({
            'entrypoints': [entry()], 'flows': [flow()],
            'structure': [{'id': 'cs1', 'kind': 'call_site', 'location': {'path': 'a.py'},
                           'value': {'callee': 'session.execute', 'attribute': True, 'enclosing': 'handle'}},
                          {'id': 'cs2', 'kind': 'call_site', 'location': {'path': 'a.py'},
                           'value': {'callee': 'parse_int', 'attribute': False, 'enclosing': 'handle'}}],
            'runtime': [{'id': 'qb1', 'kind': 'query_bound', 'location': {'path': 'a.py'},
                         'value': {'bounded': True, 'mechanism': 'limit', 'kind': 'sqlalchemy_limit'}}]})
        self.assertEqual(validate(traced), [])
        answers = traced['entry_points'][0]['answers']
        self.assertEqual((answers['data_access_calls']['status'], answers['data_access_calls']['value']), ('answered', 1))
        self.assertEqual((answers['result_is_bounded']['status'], answers['result_is_bounded']['value']), ('answered', True))

    def test_a_negative_answer_is_given_only_inside_the_detectors_vocabulary(self):
        cases = [('a.py', 'python', True, 'cached', 'answered'), ('main.go', 'go', True, 'cached', 'answered'),
                 ('a.rb', 'ruby', True, 'shared_mutable_state', 'not_applicable'),
                 ('a.py', 'python', False, 'cached', 'undetectable')]
        for path, language, traced, question, status in cases:
            with self.subTest(path=path, traced=traced):
                answer = computed({'entrypoints': [entry(path)], 'flows': [flow(path)] if traced else [],
                                   'structure': [source(path, language)]})['entry_points'][0]['answers'][question]
                self.assertEqual(answer['status'], status)
                if status == 'answered':
                    self.assertIs(answer['value'], False)
                    self.assertTrue(answer['evidence'])
                elif status == 'not_applicable':
                    self.assertIn('vocabulary', answer['reason'])
                else:
                    self.assertIn('flow', answer['reason'].lower())


class ProjectionTests(unittest.TestCase):
    """The projection is a stated heuristic; it ranks entries and names bottlenecks."""

    def test_the_projection_is_stated_ranked_and_honest_about_gaps(self):
        complete = project(record_of(lambda q: {'status': 'answered', 'value': 5 if q == 'data_access_calls' else True,
                                                'evidence': ['F-x']}))
        self.assertFalse(complete['entry_points'][0]['projection']['incomplete'])
        self.assertGreater(complete['entry_points'][0]['projection']['cost_score'], 0)
        self.assertEqual(complete, project(record_of(lambda q: {'status': 'answered', 'value': 5 if q == 'data_access_calls'
                                                                else True, 'evidence': ['F-x']})))
        self.assertTrue({'method', 'multiplier'} <= set(complete['projection']))
        incomplete = project(record_of(lambda q: {'status': 'undetectable', 'reason': 'no evidence yet'}))['entry_points'][0]
        self.assertTrue(incomplete['projection']['incomplete'])
        self.assertEqual(len(incomplete['projection']['unanswered_questions']), 8)
        values = {'data_access_calls': 5, 'repeats_per_iteration': True, 'result_is_bounded': False,
                  'shared_mutable_state': True, 'cached': False, 'rate_limited': False, 'complexity_class': 'O(n)',
                  'outbound_calls_protected': {'timeout': False, 'retry': False, 'circuit_breaker': False}}
        ranked = project(record_of(lambda q: {'status': 'answered', 'value': values[q], 'evidence': ['x']}))
        self.assertEqual(ranked['entry_points'][0]['projection']['bottlenecks'],
                         ['no_rate_limit', 'n_plus_one', 'unbounded_query', 'shared_mutable_state'])


class BlockerTests(unittest.TestCase):
    """A blocker comes only from an answered question, and reaches a task card."""

    def record(self, question, value, status='answered'):
        answers = {name: {'status': 'undetectable', 'reason': 'not measured here'} for name in QUESTIONS}
        answers[question] = {'status': status, 'value': value, 'evidence': ['FACT-1']}
        return {'entry_points': [{'id': 'E1', 'path': 'app.py', 'entry': {'route': '/orders'}, 'answers': answers}]}

    def test_a_blocker_comes_only_from_an_answered_question(self):
        cases = [('repeats_per_iteration', None, 'undetectable', []),
                 ('repeats_per_iteration', True, 'answered', ['n_plus_one']),
                 ('result_is_bounded', True, 'answered', []),
                 ('result_is_bounded', False, 'answered', ['unbounded_result']),
                 ('outbound_calls_protected', {'timeout': True, 'retry': False, 'circuit_breaker': False}, 'answered', []),
                 # Retries without a timeout make the pile-up worse, not better.
                 ('outbound_calls_protected', {'timeout': False, 'retry': True, 'circuit_breaker': False}, 'answered',
                  ['unprotected_dependency']),
                 # A path that calls nothing external has no call to protect.
                 ('outbound_calls_protected', True, 'answered', [])]
        for question, value, status, expected in cases:
            with self.subTest(question=question, value=value):
                found = blockers(self.record(question, value, status))
                self.assertEqual([row['kind'] for row in found], expected)
                self.assertTrue(all(row['falsifier'] and row['evidence'] == ['FACT-1'] for row in found))
        for question, rule in BLOCKERS.items():
            for field in ('kind', 'statement', 'statement_en', 'falsifier', 'scenario'):
                self.assertTrue(rule[field].strip(), f'{question}.{field}')

    def test_the_planted_blockers_become_claims_and_cards(self):
        fixture = FIXTURES / 'load/degrades'
        truth = json.loads((fixture / 'ground-truth.json').read_text(encoding='utf-8'))
        expected = {row['kind'] for row in truth['planted']}
        with tempfile.TemporaryDirectory() as out:
            execute(fixture, out, skip=('engines',), language='en')
            dossier = json.loads(Path(out, 'dossier.json').read_text(encoding='utf-8'))
            record = json.loads(Path(out, 'load-model.json').read_text(encoding='utf-8'))
            tasks = json.loads(Path(out, 'plan.json').read_text(encoding='utf-8'))['tasks']
            known = set()
            for path in (Path(out) / 'facts').glob('*.json'):
                try:
                    known.update(fact['id'] for fact in json.loads(path.read_text(encoding='utf-8')).get('facts', []))
                except (ValueError, AttributeError, TypeError):
                    continue
        # Every answer cites a fact of the report, or says why it could not.
        self.assertTrue(record['entry_points'])
        for row in record['entry_points']:
            self.assertEqual(sorted(row['answers']), sorted(QUESTIONS))
            for question, answer in row['answers'].items():
                with self.subTest(question=question):
                    self.assertTrue(set(answer.get('evidence', [])) <= known)
                    self.assertTrue(answer.get('evidence') if answer['status'] == 'answered' else answer.get('reason'))
        self.assertEqual(sorted({row['kind'] for row in blockers(record)}), sorted(expected))
        claims = [c for c in dossier['claims'] if (c.get('render') or {}).get('key') == 'load_blocker']
        self.assertEqual(len(claims), len(expected))
        self.assertTrue(all(c['falsifier'].strip() and c.get('fact_ids') for c in claims))
        cards = [task for task in tasks if task['pattern'] == 'load_blocker']
        self.assertEqual(len(cards), len(expected), 'a load claim did not reach a task card')
        self.assertTrue(all(card['options'] and card['rollback'].strip() for card in cards))


class BoundedReadAndSharedStateTests(unittest.TestCase):
    def test_reads_say_whether_they_are_bounded_and_module_state_is_found(self):
        text = ('const a = await supabase.from("items").select("*");\n'
                'const b = await supabase.from("items").select("*").range(0, 49);\n'
                'const c = await supabase\n  .from("items")\n  .select("*")\n  .eq("id", id)\n  .single();\n'
                'await supabase.from("items").insert(row);\n')
        self.assertEqual([r['bounded'] for _, _, r in extract_calls(text)], [False, True, True, None])
        self.assertEqual([bounded('get', '/operators/${id}'), bounded('get', '/operators?page=2'),
                          bounded('get', '/operators'), bounded('post', '/operators')], [True, True, None, None])
        text = ('let token = null;\nconst cache = new Map();\nconst ROUTES = ["/a"];\nlet stable = 1;\n'
                'export function login(t) { token = t; cache.set(t, 1); }\n'
                'export const read = () => stable + ROUTES.length;\n')
        self.assertEqual(sorted(name for name, *_ in js_mutable_globals(text)), ['cache', 'token'])

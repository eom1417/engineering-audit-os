"""The pipeline map (NS46.T12): eaos/facts/pipeline.py finds pipelines from what code declares or does, and
eaos/studio/pipeline.py draws them as the Studio's pipeline section, current, ideal and gap."""
import json
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

from eaos import artifact_contracts
from eaos.facts import pipeline
from eaos.facts import run as facts_run
from eaos.studio import pipeline as section

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import pipeline_truth  # noqa: E402

HEAD = {'schema_version': 1, 'contract': 1, 'revision': 2}


def project(files):
    folder = tempfile.TemporaryDirectory()
    for name, text in files.items():
        path = Path(folder.name) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip(), encoding='utf-8')
    return folder


class Base(unittest.TestCase):
    def scan(self, files):
        folder = project(files)
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        return pipeline.scan(self.folder)

    def one(self, record, kind):
        found = [p for p in record['pipelines'] if p['kind'] == kind]
        self.assertEqual(len(found), 1, [p['id'] for p in record['pipelines']])
        return found[0]

    def labels(self, p):
        return [s['label'] for s in p['stages'] if s['kind'] not in pipeline_truth.STRUCTURAL]

    def links(self, p):
        label = {s['id']: s['label'] for s in p['stages']}
        return {(label[e['from']], label[e['to']]) for e in p['edges']}


STAGES = '''
from dataclasses import dataclass

@dataclass
class Stage:
    name: str
    produces: tuple = ()
    requires: tuple = ()

STAGES = (
    Stage('read', produces=('facts.json',)),
    Stage('judge', produces=('claims.json',), requires=('read',)),
    Stage('plan', produces=('plan.json',), requires=('judge',)),
    Stage('report', produces=('report.md',), requires=('plan', 'judge')),
)
'''
RUNNERS = '''
def read(context):
    context['cache'] = 1
    context['note'] = 'unused'
    return {}

def judge(context):
    return {'seen': context['cache']}

def plan(context):
    return {}

def report(context):
    return {}

RUNNERS = {'read': read, 'judge': judge, 'plan': plan, 'report': report, 'old': read}
'''
RUN = '''
from .stages import STAGES
from .runners import RUNNERS

OK, FAILED, SKIPPED = 'ok', 'failed', 'skipped'

class Skip(Exception):
    pass

def execute(context, only=()):
    results = {}
    for stage in STAGES:
        if only and stage.name not in only:
            results[stage.name] = SKIPPED
            continue
        results[stage.name] = one(stage, context)
    return results

def one(stage, context):
    runner = RUNNERS.get(stage.name)
    if runner is None:
        return FAILED
    try:
        runner(context)
    except Skip:
        return SKIPPED
    except Exception:
        return FAILED
    return OK
'''


class DeclaredDag(Base):
    def setUp(self):
        self.record = self.scan({'app/__init__.py': '', 'app/stages.py': STAGES, 'app/runners.py': RUNNERS, 'app/run.py': RUN})
        self.p = self.one(self.record, 'declared_dag')

    def test_stages_and_edges_come_from_the_declaration(self):
        self.assertTrue(self.record['detected'])
        self.assertEqual(self.labels(self.p), ['read', 'judge', 'plan', 'report'])
        self.assertEqual(self.links(self.p), {('read', 'judge'), ('judge', 'plan'), ('plan', 'report'), ('judge', 'report')})
        stage = next(s for s in self.p['stages'] if s['label'] == 'judge')
        self.assertEqual((stage['entry']['path'], stage['symbol']), ('app/runners.py', 'app.runners.judge'))
        self.assertEqual(stage['outputs'], [{'name': 'claims.json', 'kind': 'artifact', 'shape': None}])

    def test_the_registry_is_a_total_router_and_its_extra_entry_a_dead_stage(self):
        router = self.p['routers'][0]
        self.assertEqual((router['kind'], router['table'], router['total']), ('registry', 'RUNNERS', True))
        self.assertEqual({b['condition'] for b in router['branches']}, {'read', 'judge', 'plan', 'report', 'old'})
        self.assertEqual([h['name'] for h in self.p['hidden'] if h['kind'] == 'dead_stage'], ['old'])

    def test_a_context_key_one_stage_writes_and_another_reads_is_a_side_channel(self):
        kinds = {h['name']: h['kind'] for h in self.p['hidden']}
        self.assertEqual(kinds["context['cache']"], 'side_channel')
        self.assertEqual(kinds["context['note']"], 'unread_output')

    def test_failures_have_their_lanes(self):
        lanes = {(lane['to'], lane['kind']) for lane in self.p['error_lanes']}
        self.assertIn(('failed', 'catch'), lanes)
        self.assertIn(('skipped', 'skip'), lanes)
        self.assertIn(('failed', 'fail'), lanes)


REGISTRY_LOOP = '''
from . import load, clean, count, extra

STEPS = {'load': load, 'clean': clean, 'count': count, 'extra': extra}
ORDER = ['load', 'clean', 'count']

def collect(names):
    produced = {}
    for name in names:
        module = STEPS[name]
        if name == 'clean':
            result = module.run(rows=produced.get('load'))
        elif name in {'count'}:
            result = module.run(rows=produced.get('clean'), outside=produced.get('ghost'))
        else:
            result = module.run()
        produced[name] = result
    return produced
'''


class RegistryLoop(Base):
    def setUp(self):
        files = {'steps/__init__.py': REGISTRY_LOOP}
        for name in ('load', 'clean', 'count', 'extra'): files[f'steps/{name}.py'] = 'def run(**_):\n    return []\n'
        self.p = self.one(self.scan(files), 'registry_loop')

    def test_the_accumulator_gives_the_edges_and_the_if_chain_the_branches(self):
        self.assertEqual(self.labels(self.p), ['load', 'clean', 'count'])
        self.assertEqual(self.links(self.p), {('load', 'clean'), ('clean', 'count')})
        chain = next(r for r in self.p['routers'] if r['kind'] == 'if_chain')
        self.assertEqual([b['condition'] for b in chain['branches']], ['clean', 'count', 'else'])
        table = next(r for r in self.p['routers'] if r['kind'] == 'dict_dispatch')
        self.assertTrue(table['total'])

    def test_a_dispatch_eaos_cannot_follow_is_an_unresolved_step_never_an_edge(self):
        self.assertEqual([u['call'] for u in self.p['unresolved']], ["produced['ghost']"])
        self.assertFalse(any('ghost' in name for e in self.p['edges'] for name in e['data']['names']))
        self.assertEqual([h['name'] for h in self.p['hidden'] if h['kind'] == 'dead_stage'], ['extra'])


class Orchestrators(Base):
    def test_announced_phases_are_stages_in_order(self):
        p = self.one(self.scan({'audit.py': '''
            def run(job):
                def phase(name): print(name)
                phase('read the code')
                facts = job.read()
                phase('judge')
                job.judge(facts)
                phase('write the report: ' + job.name)
            '''}), 'orchestrator')
        self.assertEqual(self.labels(p), ['read the code', 'judge', 'write the report'])
        self.assertEqual(self.links(p), {('read the code', 'judge'), ('judge', 'write the report')})

    def test_values_passed_from_stage_to_stage_make_the_edges(self):
        p = self.one(self.scan({'etl/steps.py': '''
            def extract(source): return [source]
            def transform(rows): return rows
            def load(rows, target): return target
            ''', 'etl/flow.py': '''
            from etl.steps import extract, transform, load
            import pandas as pd

            def sales_pipeline(source, target):
                rows = extract(source)
                frame = pd.DataFrame(rows)
                clean = transform(frame)
                return load(clean, target)
            '''}), 'orchestrator')
        self.assertEqual(self.labels(p), ['extract', 'transform', 'load'])
        self.assertEqual(self.links(p), {('extract', 'transform'), ('transform', 'load')})
        self.assertEqual(next(e for e in p['edges'] if e['to'].endswith('/transform'))['data']['names'], ['frame'])

    def test_a_chain_of_calls_without_a_pipeline_signal_is_not_a_pipeline(self):
        record = self.scan({'billing.py': '''
            def price(order): return order
            def tax(amount): return amount
            def total(amount): return amount

            def checkout(order):
                amount = price(order)
                taxed = tax(amount)
                return total(taxed)
            '''})
        self.assertFalse(record['detected'])
        self.assertEqual(record['pipelines'], [])


AIRFLOW = '''
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator

def pick():
    if True:
        return 'small'
    return 'large'

def report(ti):
    return ti.xcom_pull(task_ids='extract')

dag = DAG(dag_id='nightly', schedule='@daily')
extract = PythonOperator(task_id='extract', python_callable=report, retries=2, dag=dag)
branch = BranchPythonOperator(task_id='branch', python_callable=pick, dag=dag)
small = PythonOperator(task_id='small', python_callable=report, dag=dag)
large = PythonOperator(task_id='large', python_callable=report, dag=dag)
publish = PythonOperator(task_id='publish', python_callable=report, dag=dag)
extract >> branch >> [small, large]
small >> publish
large >> publish
'''


class Airflow(Base):
    def test_operators_dependencies_branches_and_the_join(self):
        p = self.one(self.scan({'dags/nightly.py': AIRFLOW}), 'airflow')
        self.assertEqual(p['title'], 'nightly')
        self.assertEqual({('extract', 'branch'), ('branch', 'small'), ('branch', 'large'), ('small', 'publish'), ('large', 'publish')}
                         | {('extract', 'small'), ('extract', 'large'), ('extract', 'publish')} >= self.links(p), True)
        self.assertIn(('extract', 'branch'), self.links(p))
        router = next(r for r in p['routers'] if r['kind'] == 'branch_operator')
        self.assertEqual([b['condition'] for b in router['branches']], ["returns 'small'", "returns 'large'"])
        fan = next(f for f in p['fans'] if f['fork'].endswith('/branch'))
        self.assertTrue(fan['matched'])
        self.assertTrue(fan['join'].endswith('/publish'))
        self.assertTrue(any(c['kind'] == 'retry' for c in p['control']))


CELERY_TASKS = '''
from celery import shared_task

@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3)
def charge(self, order):
    return order

@shared_task
def record(result):
    return result

@shared_task
def notify(result):
    return 'sent'

@shared_task
def total(results):
    return sum(results)

@charge.on_failure
def charge_failed(self, exc, task_id, args, kwargs, einfo):
    self.app.send_task('shop.tasks.charge', args=args, queue='dead_letter')
'''
CELERY_CANVAS = '''
from celery import chain, group, chord
from shop.tasks import charge, record, notify, total

def pay(order):
    chain(charge.s(order), record.s()).apply_async()

def tell(results):
    group(notify.s(r) for r in results).apply_async()

def sum_all(orders):
    chord([charge.s(o) for o in orders], total.s())()
'''
CELERY_CONFIG = '''
from celery import Celery
app = Celery('shop')
app.conf.task_routes = {'shop.tasks.charge': {'queue': 'money'}, 'shop.tasks.notify': {'queue': 'mail'}}
'''


class Celery(Base):
    def setUp(self):
        self.p = self.one(self.scan({'shop/__init__.py': '', 'shop/tasks.py': CELERY_TASKS, 'shop/canvas.py': CELERY_CANVAS,
                                     'shop/celery.py': CELERY_CONFIG}), 'celery')

    def test_chain_group_and_chord(self):
        self.assertEqual(set(self.labels(self.p)), {'charge', 'record', 'notify', 'total'})
        self.assertEqual(self.links(self.p), {('charge', 'record'), ('charge', 'total')})
        fans = {f['kind']: f for f in self.p['fans']}
        self.assertFalse(fans['map']['matched'], 'a group nothing gathers is an unmatched fan-out')
        self.assertTrue(fans['chord']['matched'])

    def test_routes_retries_and_the_dead_letter_lane(self):
        router = next(r for r in self.p['routers'] if r['table'] == 'task_routes')
        self.assertEqual({b['condition'] for b in router['branches']}, {'shop.tasks.charge', 'shop.tasks.notify'})
        self.assertTrue(all(b['to'] for b in router['branches']))
        lanes = {(lane['from'].rsplit('/', 1)[-1], lane['to'], lane['kind']) for lane in self.p['error_lanes']}
        self.assertIn(('charge', 'dead_letter', 'fail'), lanes)
        self.assertIn(('charge', self.p['id'] + '/charge', 'retry'), lanes)


class Frameworks(Base):
    def test_langgraph_conditional_edges_are_a_router(self):
        p = self.one(self.scan({'graph.py': '''
            from langgraph.graph import StateGraph, START, END

            def plan(state): return state
            def act(state): return state
            def choose(state): return 'act'

            graph = StateGraph(dict)
            graph.add_node('plan', plan)
            graph.add_node('act', act)
            graph.add_edge(START, 'plan')
            graph.add_conditional_edges('plan', choose, {'go': 'act', 'stop': END})
            graph.add_edge('act', END)
            '''}), 'langgraph')
        router = p['routers'][0]
        self.assertEqual((router['kind'], [b['condition'] for b in router['branches']]), ('conditional_edges', ['go', 'stop']))
        self.assertIn(('plan', 'act'), self.links(p))

    def test_step_functions_choice_and_catch(self):
        p = self.one(self.scan({'machine.asl.json': json.dumps({'StartAt': 'Get', 'States': {
            'Get': {'Type': 'Task', 'Next': 'Check', 'Catch': [{'ErrorEquals': ['States.ALL'], 'Next': 'Fail'}]},
            'Check': {'Type': 'Choice', 'Choices': [{'Variable': '$.ok', 'BooleanEquals': True, 'Next': 'Done'}], 'Default': 'Fail'},
            'Done': {'Type': 'Succeed'}, 'Fail': {'Type': 'Fail'}}}, indent=1)}), 'step_functions')
        self.assertEqual(p['routers'][0]['total'], True)
        self.assertEqual(p['error_lanes'][0]['to'], 'Fail')

    def test_a_topic_both_produced_and_consumed_is_a_queue_edge(self):
        p = self.one(self.scan({'events.py': '''
            from kafka import KafkaProducer, KafkaConsumer

            def publish_orders(producer):
                producer.send('orders', b'1')

            def handle_orders():
                consumer = KafkaConsumer('orders')
                return consumer
            '''}), 'queue')
        self.assertEqual(self.links(p), {('publish_orders', 'handle_orders')})
        self.assertEqual(p['edges'][0]['matched_by'], 'topic')

    def test_build_and_ci_chains_are_tooling_not_a_product_pipeline(self):
        record = self.scan({
            '.github/workflows/ci.yml': 'name: ci\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: |\n          npm test\n'
                                        '  build:\n    needs: test\n    runs-on: ubuntu-latest\n  deploy:\n    needs: [build, test]\n    runs-on: ubuntu-latest\n',
            'Makefile': 'all: build test\nbuild: deps\n\techo build\ntest: build\n\techo test\ndeps:\n\techo deps\n',
            'package.json': json.dumps({'scripts': {'build': 'npm run lint && tsc && vite build', 'dev': 'vite'}}, indent=2)})
        self.assertFalse(record['detected'])
        kinds = {p['kind']: p for p in record['pipelines']}
        self.assertEqual(set(kinds), {'github_actions', 'makefile', 'npm_scripts'})
        self.assertTrue(all(p['role'] == 'tooling' for p in record['pipelines']))
        self.assertEqual(self.links(kinds['github_actions']), {('test', 'build'), ('build', 'deploy'), ('test', 'deploy')})
        self.assertEqual(self.labels(kinds['npm_scripts']), ['lint', 'tsc', 'vite build'])
        self.assertIn(('deps', 'build'), self.links(kinds['makefile']))


class NothingInvented(Base):
    def test_an_app_holds_no_pipeline(self):
        record = self.scan({'src/App.tsx': 'export function App() { return null }\n',
                            'src/api/client.ts': 'export async function load(){ const r = await fetch("/api"); return r.json() }\n',
                            'server/views.py': '''
                                def get_user(request): return request
                                def serialize(user): return user
                                def respond(data): return data

                                def user_view(request):
                                    user = get_user(request)
                                    data = serialize(user)
                                    return respond(data)
                                ''',
                            'package.json': json.dumps({'scripts': {'dev': 'vite', 'build': 'vite build'}})})
        self.assertFalse(record['detected'])
        self.assertEqual(record['pipelines'], [])
        self.assertEqual([row['found'] for row in record['looked_for']], [0] * len(pipeline.KINDS))
        body = {**HEAD, **section.section(record, lang='en')}
        self.assertEqual(artifact_contracts.validate(body, artifact_contracts.contracts()['studio-pipeline']), [])
        self.assertIn('No pipeline', body['verdict'])

    def test_never_runs_the_project(self):
        self.scan({'flow.py': '''
            import pathlib
            pathlib.Path('ran.txt').write_text('ran')
            raise SystemExit('the scan imported me')

            def load(x): return x
            def clean(x): return x
            def save(x): return x

            def daily_pipeline(x):
                return save(clean(load(x)))
            '''})
        self.assertFalse((self.folder / 'ran.txt').exists())
        self.assertFalse(Path('ran.txt').exists())


class Section(Base):
    def setUp(self):
        self.record = self.scan({'app/__init__.py': '', 'app/stages.py': STAGES, 'app/runners.py': RUNNERS, 'app/run.py': RUN,
                                 'shop/__init__.py': '', 'shop/tasks.py': CELERY_TASKS, 'shop/canvas.py': CELERY_CANVAS,
                                 'shop/celery.py': CELERY_CONFIG})
        self.body = {**HEAD, **section.section(self.record, cards=[{'id': 'TASK-1', 'paths': ['app/runners.py'], 'milestone': 'M01'}], lang='en')}

    def test_it_meets_its_contract(self):
        self.assertEqual(artifact_contracts.validate(self.body, artifact_contracts.contracts()['studio-pipeline']), [])
        self.assertEqual({row['kind'] for row in self.body['looked_for']}, {kind for kind, _ in pipeline.KINDS})

    def test_one_gap_per_broken_rule_with_its_evidence_card_and_step(self):
        rules = {g['rule'] for g in self.body['views']['gap']}
        self.assertTrue({'P2', 'P3', 'P5', 'P6', 'P8'} <= rules, rules)
        side = next(g for g in self.body['views']['gap'] if g['rule'] == 'P3')
        self.assertEqual((side['operation'], side['card'], side['step']), ('refactor', 'TASK-1', 'M01'))
        broken = {r['id']: r['broken'] for r in self.body['rules']}
        self.assertEqual(broken['P3'], sum(g['rule'] == 'P3' for g in self.body['views']['gap']))
        joins = [s for s in self.body['views']['ideal']['stages'] if s['op'] == 'new' and s['rule'] == 'P5']
        self.assertEqual(len(joins), 1)

    def test_every_stage_has_a_stable_place(self):
        again = section.section(self.record, lang='en')
        place = lambda body: {s['id']: (s['layer'], s['order']) for s in body['stages']}
        self.assertEqual(place(self.body), place(again))
        dag = {s['label']: s['layer'] for s in self.body['stages'] if s['pipeline'].endswith('STAGES') and s['kind'] == 'stage'}
        self.assertEqual(dag, {'read': 0, 'judge': 1, 'plan': 2, 'report': 3})
        self.assertEqual(self.body['views']['current']['stages'], [s['id'] for s in self.body['stages']])

    def test_the_facts_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            pipeline.write(folder, self.record)
            back = pipeline.read(folder)
        self.assertEqual([p['id'] for p in back['pipelines']], [p['id'] for p in self.record['pipelines']])
        first = back['pipelines'][0]
        self.assertTrue(first['stages'][0]['fact'].startswith('FACT-'))
        self.assertEqual(section.section(back, lang='en')['counts']['stages'], section.section(self.record, lang='en')['counts']['stages'])

    def test_the_facts_stage_runs_the_extractor(self):
        self.assertIn('pipeline', facts_run.ORDER)
        self.assertIs(facts_run.EXTRACTORS['pipeline'], pipeline)


class Scale(unittest.TestCase):
    def test_a_1000_stage_pipeline_builds_within_its_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            body = ['def stage_%d(value):\n    return value + %d\n' % (n, n) for n in range(1000)]
            calls = ['    v0 = stage_0(seed)'] + ['    v%d = stage_%d(v%d)' % (n, n, n - 1) for n in range(1, 1000)]
            (Path(folder) / 'flow.py').write_text('\n'.join(body) + '\n\ndef run_pipeline(seed):\n' + '\n'.join(calls) + '\n    return v999\n',
                                                  encoding='utf-8')
            began = time.monotonic()
            data = {**HEAD, **section.section(pipeline.scan(folder))}
            spent = time.monotonic() - began
        self.assertEqual(len(data['stages']), 1000)
        self.assertEqual(len(data['edges']), 999)
        self.assertEqual(max(s['layer'] for s in data['stages']), 999)
        self.assertEqual(artifact_contracts.validate(data, artifact_contracts.contracts()['studio-pipeline']), [])
        self.assertLess(spent, 20.0)


class Eaos(unittest.TestCase):
    """EAOS itself, against its hand-written truth file."""

    @classmethod
    def setUpClass(cls):
        cls.record = pipeline.scan(ROOT)

    def test_its_pipelines_match_the_truth(self):
        scores = pipeline_truth.compare(pipeline_truth.load('eaos'), self.record)
        for part in ('stages', 'edges', 'branches'):
            self.assertGreaterEqual(scores[part]['recall'], 0.8, scores[part])
            self.assertGreaterEqual(scores[part]['precision'], 0.9, scores[part])

    def test_every_element_names_its_evidence(self):
        self.assertEqual(pipeline_truth.verify(ROOT, self.record), [])

    def test_the_fixture_is_eaos_and_meets_the_contract(self):
        fixture = json.loads((ROOT / 'tests/fixtures/studio/v2/pipeline.json').read_text(encoding='utf-8'))
        self.assertEqual(artifact_contracts.validate(fixture, artifact_contracts.contracts()['studio-pipeline']), [])
        self.assertTrue(fixture['detected'])
        self.assertTrue({'eaos/pipeline/stages.py:STAGES', 'eaos/facts/run.py:collect'} <= {p['id'] for p in fixture['pipelines']})


if __name__ == '__main__':
    unittest.main()

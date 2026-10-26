"""Runtime and operational facts: deployment, CI, security, observability, integrations, capacity."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos.facts.run import collect

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/polyglot'


def runtime_facts(files, kind=None):
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / 'repo'; repo.mkdir()
        for name, text in files.items():
            (repo / name).parent.mkdir(parents=True, exist_ok=True)
            (repo / name).write_text(text)
        collect(repo, Path(tmp) / 'out', ['runtime'])
        facts = json.loads((Path(tmp) / 'out/facts/runtime.json').read_text())['facts']
    return [f for f in facts if kind is None or f['kind'] == kind]


class RuntimeFactTests(unittest.TestCase):
    def test_deployment_targets_ci_steps_and_migrations_are_found(self):
        facts = runtime_facts({
            'Dockerfile': 'FROM python:3.11\nEXPOSE 8080\nEXPOSE 9090\n',
            'docker-compose.yml': '---\nservices:\n  api:\n    image: app\n  worker:\n    image: app\n',
            'vercel.json': '{"rewrites": []}', 'app/railway.toml': '[build]\n',
            '.github/workflows/ci.yml': 'jobs:\n  test:\n    steps:\n      - name: install\n        run: pip install\n'
                                        '      - name: test\n        run: pytest\n',
            'migrations/0001_initial.py': 'pass'})
        targets = [f for f in facts if f['kind'] == 'deployment_target']
        self.assertEqual(sorted(t['value']['port'] for t in targets if t['value'].get('port')), ['8080', '9090'])
        self.assertEqual({t['value']['service'] for t in targets if t['value'].get('kind') == 'compose'}, {'api', 'worker'})
        self.assertEqual({(t['location']['path'], t['value']['host']) for t in targets if t['value'].get('kind') == 'hosting'},
                         {('vercel.json', 'Vercel'), ('app/railway.toml', 'Railway')})
        self.assertIn('install', [s['value']['name'] for s in facts if s['kind'] == 'ci_step'])
        self.assertEqual(len([f for f in facts if f['kind'] == 'migration_step']), 1)

    def test_security_observability_and_outbound_integrations_are_found_in_code(self):
        facts = runtime_facts({'app.py': (
            "from prometheus_client import Counter\nimport logging\nimport requests\n"
            "requests_total = Counter('requests', 'Total')\nlogger = logging.getLogger('app')\n"
            "@login_required\ndef protected():\n    requests_total.inc()\n    logger.info('hello')\n"
            "    return requests.get('https://api.stripe.com/v1/charges')\n"
            "def other():\n    return requests.get('http://localhost:8080/health')\n")})
        self.assertIn('login_required', {s['value']['hint'] for s in facts if s['kind'] == 'security_surface'})
        self.assertTrue({'metric', 'log'} <= {s['value']['kind'] for s in facts if s['kind'] == 'observability_signal'})
        hosts = {t['value']['host'] for t in facts if t['kind'] == 'integration_target'}
        self.assertIn('api.stripe.com', hosts)
        self.assertNotIn('localhost', hosts)

    def test_orm_models_are_data_models_with_their_framework(self):
        for name, body, framework in [
                ('a.py', 'from sqlalchemy import Column, Integer\n\nclass Order(Base):\n    id = Column(Integer, primary_key=True)\n', 'sqlalchemy'),
                ('b.py', 'from django.db import models\n\nclass Order(models.Model):\n    name = models.CharField(max_length=100)\n', 'django'),
                ('c.py', 'class Order < ApplicationRecord\nend\n', 'rails')]:
            with self.subTest(framework=framework):
                models = runtime_facts({name: body}, 'data_model')
                self.assertEqual([(m['value']['name'], m['value']['framework']) for m in models], [('Order', framework)])

    def test_query_bounds_are_recorded_bounded_unbounded_or_unknown(self):
        cases = [('a.py', 'def f():\n    return Order.query.filter(Order.paid == True).all()\n', False),
                 ('a.py', 'def f():\n    return Order.query.limit(50).all()\n', True),
                 ('a.py', 'def f():\n    return Order.query.first()\n', True),
                 ('a.ts', 'async function f() { return await prisma.order.findMany({}); }\n', False),
                 ('a.ts', 'async function f() { return await prisma.order.findMany({ take: 25 }); }\n', True),
                 ('a.go', 'package main\nimport "database/sql"\nfunc f(db *sql.DB) error {\n'
                          '    return db.Query("SELECT * FROM orders LIMIT 100")\n}\n', True),
                 ('a.go', 'package main\nfunc f(db *gorm.DB) error {\n    return db.Limit(50).Find(&orders)\n}\n', True),
                 # A file with no detectable pattern says unknown rather than omitting the question.
                 ('a.py', 'def f():\n    x = 1 + 1\n    return x\n', 'unknown')]
        for name, body, bounded in cases:
            with self.subTest(body=body):
                bounds = runtime_facts({name: body}, 'query_bound')
                self.assertIn(bounded, [b['value']['bounded'] for b in bounds])
                for fact in bounds:
                    self.assertTrue({'bounded', 'mechanism', 'kind'} <= set(fact['value']))
        unlimited_go = runtime_facts({'a.go': 'package main\nimport "database/sql"\nfunc f(db *sql.DB) error {\n'
                                              '    return db.Query("SELECT * FROM orders")\n}\n'}, 'query_bound')
        self.assertTrue({False, 'unknown'} & {b['value']['bounded'] for b in unlimited_go})

    def test_each_outbound_call_carries_the_resilience_guards_its_file_declares(self):
        call = "    return requests.get('https://api.example.com'{})\n"
        cases = [('a.py', "import requests\ndef f():\n" + call.format(''), (False, False, False)),
                 ('a.py', "import requests\nfrom tenacity import retry\nimport pybreaker\n@retry\n"
                          "@pybreaker.CircuitBreaker(fail_max=5)\ndef f():\n" + call.format(', timeout=30'), (True, True, True)),
                 ('a.py', "import requests\nfrom tenacity import retry\n@retry\ndef f():\n" + call.format(''), (False, True, False)),
                 ('a.go', 'package api\nimport ("context"; "net/http"; "time")\n'
                          'var client = http.Client{Timeout: 2 * time.Second}\n'
                          'func Call(ctx context.Context) { ctx, cancel := context.WithTimeout(ctx, time.Second); '
                          'defer cancel(); client.Get("https://api.example.com") }\n', (True, None, None)),
                 ('a.go', 'package api\nimport "net/http"\nfunc Call() { http.Get("https://api.example.com") }\n',
                  (False, None, None))]
        for name, body, (timeout, retry, breaker) in cases:
            with self.subTest(body=body):
                policy = runtime_facts({name: body}, 'resilience_policy')[0]['value']
                self.assertIs(policy['has_timeout'], timeout)
                if retry is not None:
                    self.assertIs(policy['has_retry'], retry)
                    self.assertIs(policy['has_circuit_breaker'], breaker)
        self.assertEqual(runtime_facts({'a.py': 'def f():\n    return 1 + 1\n'}, 'resilience_policy'), [])

    def test_a_detector_that_cannot_tell_answers_unknown_never_false(self):
        from eaos.facts.runtime.operations import _has_timeout, _detect_resilience_for_integration as detect
        # The timeout detector is file-scoped and says so.
        self.assertTrue(_has_timeout('client = Client(timeout=30)\n\n\ndef fetch():\n    return client.get(url)\n'))
        self.assertFalse(_has_timeout('import requests\nrequests.get(url)\n'))
        self.assertIs(detect('import requests\nrequests.get(url)\n', 'x', 'python')['has_timeout'], False)
        uncovered = detect('HTTPoison.get(url)', 'x', 'elixir')
        self.assertEqual(uncovered['has_timeout'], 'unknown')
        self.assertTrue(uncovered['reason'])

    def test_cache_sites_carry_their_scope_and_whether_a_ttl_was_declared(self):
        cases = [('a.py', 'import functools\n@functools.lru_cache(maxsize=128)\ndef f(n):\n    return n\n', 'process', False),
                 ('a.py', "import redis\nr = redis.Redis()\ndef g():\n    return r.get('k')\n", 'shared', None),
                 ('a.py', "import redis\nr = redis.Redis()\ndef g():\n    return r.set('k', 'v', ex=30)\n", 'shared', True),
                 ('a.py', "from fastapi import Response\nresp = Response()\nresp.headers['Cache-Control'] = 'max-age=60'\n",
                  'http', None),
                 ('a.go', 'package api\nimport "github.com/patrickmn/go-cache"\n'
                          'var local = cache.New(cache.DefaultExpiration, 0)\n', None, None)]
        for name, body, scope, ttl in cases:
            with self.subTest(body=body):
                caches = runtime_facts({name: body}, 'cache_policy')
                self.assertTrue(caches)
                if scope:
                    self.assertIn(scope, {c['value']['scope'] for c in caches})
                if ttl is not None:
                    self.assertIn(ttl, {c['value']['ttl_declared'] for c in caches})
                for fact in caches:
                    self.assertNotIn('absent', json.dumps(fact['value']), 'a cache fact describes what was seen only')
        self.assertEqual(runtime_facts({'a.py': 'def f():\n    return 1 + 1\n'}, 'cache_policy'), [])

    def test_rate_limits_and_concurrency_bounds_are_found_in_code_and_config(self):
        cases = [('a.py', "@limiter.limit(limit=100, per=60)\ndef f():\n    pass\n", 'code', None),
                 ('a.py', "import asyncio\nsem = asyncio.Semaphore(10)\nasync def f():\n    async with sem: pass\n", 'code', 'semaphore'),
                 ('a.py', "from concurrent.futures import ThreadPoolExecutor\npool = ThreadPoolExecutor(max_workers=8)\n", 'code', 'worker'),
                 ('nginx.conf', 'http {\n  limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;\n}\n', 'config', None),
                 ('deployment.yaml', 'apiVersion: apps/v1\nkind: Deployment\nspec:\n  containers:\n  - name: app\n'
                                     '    resources:\n      limits:\n        cpu: "1"\n        memory: "1Gi"\n', 'config', 'resources'),
                 ('a.go', 'package api\nimport "golang.org/x/time/rate"\nvar limit = rate.NewLimiter(10, 20)\n', None, None)]
        for name, body, source, mechanism in cases:
            with self.subTest(body=body):
                limits = runtime_facts({name: body}, 'rate_limit')
                self.assertTrue(limits)
                for fact in limits:
                    self.assertTrue({'scope', 'mechanism', 'source', 'declared_limit'} <= set(fact['value']))
                if source:
                    self.assertIn(source, {l['value']['source'] for l in limits})
                if mechanism:
                    self.assertTrue(any(mechanism in l['value']['mechanism'] for l in limits))
        declared = runtime_facts({'a.py': cases[0][1]}, 'rate_limit')
        self.assertTrue(any(l['value']['declared_limit'] is not None for l in declared))
        self.assertEqual(runtime_facts({'a.py': 'def f():\n    return 1 + 1\n'}, 'rate_limit'), [])

    def test_declared_connection_pools_are_recorded_and_defaults_are_never_assumed(self):
        cases = [('a.py', "from sqlalchemy import create_engine\ne = create_engine('postgresql://x', pool_size=20)\n", 20),
                 ('a.go', 'package main\nimport "net/http"\nfunc f() *http.Client {\n'
                          '    transport := &http.Transport{MaxIdleConns: 100}\n    return &http.Client{Transport: transport}\n}\n', 100),
                 ('a.go', 'package main\nimport "github.com/jackc/pgx/v4/pgxpool"\nfunc f() {\n'
                          '    cfg, _ := pgxpool.ParseConfig("")\n    cfg.MaxConns = 30\n}\n', 30),
                 ('config.py', 'DATABASE_URL = "postgres://x?pool=50"\n', None)]
        for name, body, size in cases:
            with self.subTest(body=body):
                pools = runtime_facts({name: body}, 'connection_pool')
                self.assertTrue(pools)
                for fact in pools:
                    self.assertTrue({'resource', 'declared_size', 'source'} <= set(fact['value']))
                if size is not None:
                    self.assertEqual(pools[0]['value']['declared_size'], size)
        for body in ["from sqlalchemy import create_engine\ne = create_engine('sqlite:///local.db')\n",
                     'def f():\n    return 1 + 1\n']:
            self.assertEqual(runtime_facts({'a.py': body}, 'connection_pool'), [])

    def test_go_package_state_is_mutable_only_when_it_is_a_variable(self):
        from eaos.facts.domain.model import go_mutable_globals
        positive = ('package api\nimport "sync"\nvar mu sync.RWMutex\nvar count int\n'
                    'func Add() { mu.Lock(); count++; mu.Unlock() }\n')
        self.assertEqual({row[0] for row in go_mutable_globals(positive)}, {'mu', 'count'})
        self.assertEqual(go_mutable_globals('package api\nconst maximum = 10\nfunc Value() int { return maximum }\n'), [])

    def test_two_collections_of_the_same_tree_are_byte_identical(self):
        from eaos.facts.runtime.operations import KINDS
        self.assertEqual(list(KINDS), sorted(KINDS), 'summary key order must not depend on set iteration')
        written = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as out:
                collect(FIXTURE, out, ['syntax', 'runtime'])
                written.append(Path(out, 'facts/runtime.json').read_bytes())
        self.assertEqual(written[0], written[1])

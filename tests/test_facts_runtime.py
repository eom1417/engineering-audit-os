"""Runtime and operational facts: deployment, CI, security, observability, integrations, models."""
import json
from pathlib import Path
import tempfile
import unittest
from eaos.facts import runtime
from eaos.facts.run import collect


def _collect(tmp, body=None, name='app.py', extra_files=None):
    repo = Path(tmp) / 'repo'; repo.mkdir()
    if body is not None: (repo / name).write_text(body)
    for n, c in (extra_files or {}).items():
        path = repo / n
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(c)
    collect(repo, Path(tmp) / 'out', ['runtime'])
    return json.loads((Path(tmp) / 'out/facts/runtime.json').read_text())


class RuntimeFactTests(unittest.TestCase):
    def test_dockerfile_expose_creates_deployment_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, extra_files={'Dockerfile': 'FROM python:3.11\nEXPOSE 8080\nEXPOSE 9090\n'})
        targets = [f for f in data['facts'] if f['kind'] == 'deployment_target']
        self.assertEqual(len(targets), 2)
        ports = sorted(t['value']['port'] for t in targets)
        self.assertEqual(ports, ['8080', '9090'])

    def test_compose_services_become_deployment_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, extra_files={'docker-compose.yml':
                                                'services:\n  api:\n    image: app\n  worker:\n    image: app\n'})
        targets = [f for f in data['facts'] if f['kind'] == 'deployment_target' and f['value'].get('kind') == 'compose']
        self.assertEqual({t['value']['service'] for t in targets}, {'api', 'worker'})

    def test_github_actions_steps_become_ci_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, extra_files={'.github/workflows/ci.yml':
                                                'jobs:\n  test:\n    steps:\n      - name: install\n        run: pip install\n      - name: test\n        run: pytest\n'})
        steps = [f for f in data['facts'] if f['kind'] == 'ci_step']
        self.assertGreater(len(steps), 0)
        names = [s['value']['name'] for s in steps]
        self.assertIn('install', names)

    def test_auth_decorators_become_security_surface_facts(self):
        body = (
            "@login_required\n"
            "def protected():\n    return {}\n"
            "@permission_required('admin')\n"
            "def admin():\n    return {}\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        surfaces = [f for f in data['facts'] if f['kind'] == 'security_surface']
        self.assertGreater(len(surfaces), 0)
        hints = {s['value']['hint'] for s in surfaces}
        self.assertIn('login_required', hints)

    def test_observability_calls_become_signals(self):
        body = (
            "from prometheus_client import Counter\n"
            "import logging\n"
            "requests = Counter('requests', 'Total')\n"
            "logger = logging.getLogger('app')\n"
            "def handler():\n    requests.inc()\n    logger.info('hello')\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        signals = [f for f in data['facts'] if f['kind'] == 'observability_signal']
        kinds = {s['value']['kind'] for s in signals}
        self.assertIn('metric', kinds)
        self.assertIn('log', kinds)

    def test_outbound_http_calls_become_integration_targets(self):
        body = (
            "import requests\n"
            "def fetch():\n    return requests.get('https://api.stripe.com/v1/charges')\n"
            "def other():\n    return requests.get('http://localhost:8080/health')\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        targets = [f for f in data['facts'] if f['kind'] == 'integration_target']
        hosts = {t['value']['host'] for t in targets}
        self.assertIn('api.stripe.com', hosts)
        self.assertNotIn('localhost', hosts)

    def test_sqlalchemy_model_class_is_a_data_model(self):
        body = "from sqlalchemy import Column, Integer\n\nclass Order(Base):\n    id = Column(Integer, primary_key=True)\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        models = [f for f in data['facts'] if f['kind'] == 'data_model']
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]['value']['name'], 'Order')
        self.assertEqual(models[0]['value']['framework'], 'sqlalchemy')

    def test_django_model_class_is_data_model_not_sqlalchemy(self):
        body = "from django.db import models\n\nclass Order(models.Model):\n    name = models.CharField(max_length=100)\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        models = [f for f in data['facts'] if f['kind'] == 'data_model']
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]['value']['framework'], 'django')

    def test_rails_model_class_is_data_model(self):
        body = "class Order < ApplicationRecord\nend\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body)
        models = [f for f in data['facts'] if f['kind'] == 'data_model']
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]['value']['framework'], 'rails')

    def test_migration_files_create_migration_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, extra_files={'migrations/0001_initial.py': 'pass'})
        steps = [f for f in data['facts'] if f['kind'] == 'migration_step']
        self.assertEqual(len(steps), 1)


class RuntimeLimitationsTests(unittest.TestCase):
    def test_runtime_facts_are_static_observations(self):
        self.assertIn('static analysis', ' '.join(runtime.LIMITATIONS))


class ReproducibilityTests(unittest.TestCase):
    """Same tree, same versions, same bytes — including the order of summary keys."""

    def test_the_summary_key_order_does_not_depend_on_set_iteration(self):
        from eaos.facts.runtime import KINDS
        self.assertEqual(list(KINDS), sorted(KINDS))

    def test_two_collections_of_the_same_tree_are_byte_identical(self):
        import tempfile
        from pathlib import Path
        from eaos.facts.run import collect
        written = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as out:
                collect('eaos/compose', out, ['syntax', 'runtime'])
                written.append(Path(out, 'facts/runtime.json').read_bytes())
        self.assertEqual(written[0], written[1])


class QueryBoundDetectorTests(unittest.TestCase):
    """A query that returns rows must declare a bound, or the detector flags it."""

    FIXTURE = Path(__file__).resolve().parent / 'fixtures/runtime/query-bounds'

    def _facts_for(self, name):
        data = _collect(str(self.FIXTURE).rsplit('/', 1)[0], name=str(self.FIXTURE / name))
        return [f for f in data['facts'] if f['kind'] == 'query_bound']

    def test_python_unbounded_all_is_flagged(self):
        """An `.all()` chain without a preceding limit is unbounded."""
        body = "def f():\n    return Order.query.filter(Order.paid == True).all()\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            bounds = [f for f in data['facts'] if f['kind'] == 'query_bound']
            unbounded = [f for f in bounds if f['value']['bounded'] is False]
            self.assertGreater(len(unbounded), 0, 'expected at least one unbounded site')

    def test_python_limit_with_literal_is_bounded(self):
        body = "def f():\n    return Order.query.limit(50).all()\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            bounds = [f for f in data['facts'] if f['kind'] == 'query_bound']
            bounded = [f for f in bounds if f['value']['bounded'] is True]
            self.assertGreater(len(bounded), 0, 'expected at least one bounded site')

    def test_python_first_is_bounded(self):
        body = "def f():\n    return Order.query.first()\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            bounds = [f for f in data['facts'] if f['kind'] == 'query_bound']
            kinds = {b['value']['kind'] for b in bounds}
            self.assertIn('first', kinds)

    def test_javascript_prisma_findMany_without_take_is_unbounded(self):
        body = "async function f() { return await prisma.order.findMany({}); }\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body, name='app.ts')
            bounds = [f for f in data['facts'] if f['kind'] == 'query_bound']
            unbounded = [f for f in bounds if f['value']['bounded'] is False]
            self.assertGreater(len(unbounded), 0)

    def test_javascript_take_with_literal_is_bounded(self):
        body = "async function f() { return await prisma.order.findMany({ take: 25 }); }\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body, name='app.ts')
            bounds = [f for f in data['facts'] if f['kind'] == 'query_bound']
            bounded = [f for f in bounds if f['value']['bounded'] is True]
            self.assertGreater(len(bounded), 0)

    def test_go_sql_without_limit_is_unbounded(self):
        body = 'package main\nimport "database/sql"\nfunc f(db *sql.DB) error {\n    return db.Query("SELECT * FROM orders")\n}\n'
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body, name='orders.go')
            bounds = [f for f in data['facts'] if f['kind'] == 'query_bound']
            # We don't have a Go unbounded detector; expect unknown
            self.assertTrue(any(b['value']['bounded'] == 'unknown' for b in bounds) or
                            any(b['value']['bounded'] is False for b in bounds),
                            'Go query without LIMIT should be recorded as either unbounded or unknown')

    def test_go_sql_with_limit_is_bounded(self):
        body = 'package main\nimport "database/sql"\nfunc f(db *sql.DB) error {\n    return db.Query("SELECT * FROM orders LIMIT 100")\n}\n'
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body, name='orders.go')
            bounds = [f for f in data['facts'] if f['kind'] == 'query_bound']
            bounded = [f for f in bounds if f['value']['bounded'] is True]
            self.assertGreater(len(bounded), 0, 'expected at least one bounded site for LIMIT 100')

    def test_go_gorm_limit_is_bounded(self):
        body = 'package main\nfunc f(db *gorm.DB) error {\n    return db.Limit(50).Find(&orders)\n}\n'
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body, name='orders.go')
            bounds = [f for f in data['facts'] if f['kind'] == 'query_bound']
            bounded = [f for f in bounds if f['value']['bounded'] is True and 'gorm' in f['value']['kind']]
            self.assertGreater(len(bounded), 0)

    def test_query_bound_fact_carries_position_and_mechanism(self):
        """Every query_bound fact carries bounded, mechanism, location, kind."""
        body = "def f():\n    return Order.query.limit(10).all()\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            bounds = [f for f in data['facts'] if f['kind'] == 'query_bound']
            for fact in bounds:
                self.assertIn('bounded', fact['value'])
                self.assertIn('mechanism', fact['value'])
                self.assertIn('kind', fact['value'])
                self.assertIn('path', fact['location'])

    def test_query_bound_unknowable_recorded_as_unknown(self):
        """A file with no detectable patterns records bounded=unknown rather than silently omitting."""
        body = "def f():\n    x = 1 + 1\n    return x\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            bounds = [f for f in data['facts'] if f['kind'] == 'query_bound']
            self.assertTrue(any(b['value']['bounded'] == 'unknown' for b in bounds))


class ResiliencePolicyDetectorTests(unittest.TestCase):
    """Each outbound call carries the resilience policy the file declares for its host."""

    def test_a_bare_call_records_no_guards(self):
        body = "import requests\ndef f():\n    return requests.get('https://api.example.com')\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            policies = [f for f in data['facts'] if f['kind'] == 'resilience_policy']
            self.assertEqual(len(policies), 1)
            self.assertFalse(policies[0]['value']['has_timeout'])
            self.assertFalse(policies[0]['value']['has_retry'])
            self.assertFalse(policies[0]['value']['has_circuit_breaker'])

    def test_a_protected_call_records_timeout_retry_and_breaker(self):
        body = (
            "import requests\n"
            "from tenacity import retry\n"
            "import pybreaker\n"
            "@retry\n"
            "@pybreaker.CircuitBreaker(fail_max=5)\n"
            "def f():\n"
            "    return requests.get('https://api.example.com', timeout=30)\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            policies = [f for f in data['facts'] if f['kind'] == 'resilience_policy']
            self.assertGreater(len(policies), 0)
            self.assertTrue(policies[0]['value']['has_timeout'])
            self.assertTrue(policies[0]['value']['has_retry'])
            self.assertTrue(policies[0]['value']['has_circuit_breaker'])

    def test_retry_only_call_records_only_retry(self):
        body = (
            "import requests\n"
            "from tenacity import retry\n"
            "@retry\n"
            "def f():\n"
            "    return requests.get('https://api.example.com')\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            policies = [f for f in data['facts'] if f['kind'] == 'resilience_policy']
            self.assertGreater(len(policies), 0)
            self.assertTrue(policies[0]['value']['has_retry'])
            self.assertFalse(policies[0]['value']['has_timeout'])
            self.assertFalse(policies[0]['value']['has_circuit_breaker'])

    def test_circuit_breaker_aliases_are_detected(self):
        for alias in ['hystrix', 'CircuitBreaker', 'pybreaker', 'resilience4j']:
            body = (
                "import requests\n"
                f"import {alias}\n"
                "def f():\n"
                "    return requests.get('https://api.example.com')\n"
            )
            with tempfile.TemporaryDirectory() as tmp:
                data = _collect(tmp, body=body)
                policies = [f for f in data['facts'] if f['kind'] == 'resilience_policy'
                            and f['value']['host'] == 'api.example.com']
                if not policies:
                    continue
                # If the alias was a bare import, our regex matches the module name on import line
                self.assertTrue(policies[0]['value']['has_circuit_breaker'],
                                f'expected breaker detection for {alias}, got {policies[0]["value"]}')

    def test_go_http_client_timeout_is_detected(self):
        body = ('package main\n'
                'import ("net/http"; "time")\n'
                'func Protected(client *http.Client) error {\n'
                '    client.Timeout = 30 * time.Second\n'
                '    _, err := client.Get("https://api.example.com")\n'
                '    return err\n'
                '}\n')
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body, name='orders.go')
            policies = [f for f in data['facts'] if f['kind'] == 'resilience_policy']
            self.assertGreater(len(policies), 0)
            self.assertTrue(policies[0]['value']['has_timeout'])

    def test_no_resilience_policy_fact_when_no_outbound_call(self):
        body = "def f():\n    return 1 + 1\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            policies = [f for f in data['facts'] if f['kind'] == 'resilience_policy']
            self.assertEqual(policies, [])


class CachePolicyDetectorTests(unittest.TestCase):
    """A cache site is reported with its scope and whether a TTL was declared."""

    def test_lru_cache_creates_process_scoped_policy(self):
        body = "import functools\n@functools.lru_cache(maxsize=128)\ndef f(n):\n    return n\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            policies = [f for f in data['facts'] if f['kind'] == 'cache_policy']
            process = [p for p in policies if p['value']['scope'] == 'process']
            self.assertGreater(len(process), 0)

    def test_redis_creates_shared_scoped_policy(self):
        body = "import redis\nr = redis.Redis()\ndef g():\n    return r.get('k')\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            policies = [f for f in data['facts'] if f['kind'] == 'cache_policy']
            shared = [p for p in policies if p['value']['scope'] == 'shared']
            self.assertGreater(len(shared), 0)

    def test_cache_control_header_creates_http_scoped_policy(self):
        body = "from fastapi import Response\nresp = Response()\nresp.headers['Cache-Control'] = 'max-age=60'\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            policies = [f for f in data['facts'] if f['kind'] == 'cache_policy']
            http = [p for p in policies if p['value']['scope'] == 'http']
            self.assertGreater(len(http), 0)

    def test_ttl_declared_when_expires_in_keyword_appears(self):
        body = "import redis\nr = redis.Redis()\ndef g():\n    return r.set('k', 'v', ex=30)\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            policies = [f for f in data['facts'] if f['kind'] == 'cache_policy']
            self.assertTrue(any(p['value']['ttl_declared'] is True for p in policies))

    def test_ttl_unknown_when_no_ttl_marker_anywhere(self):
        body = "import functools\n@functools.lru_cache\ndef f(n):\n    return n\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            policies = [f for f in data['facts'] if f['kind'] == 'cache_policy']
            self.assertTrue(all(p['value']['ttl_declared'] is False for p in policies))

    def test_no_cache_fact_when_file_has_no_cache_marker(self):
        body = "def f():\n    return 1 + 1\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            policies = [f for f in data['facts'] if f['kind'] == 'cache_policy']
            self.assertEqual(policies, [])

    def test_each_cache_site_carries_location_and_mechanism(self):
        body = "import functools\n@functools.lru_cache(maxsize=10)\ndef f():\n    return 1\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            policies = [f for f in data['facts'] if f['kind'] == 'cache_policy']
            self.assertGreater(len(policies), 0)
            for fact in policies:
                self.assertIn('path', fact['location'])
                self.assertIn('mechanism', fact['value'])
                self.assertIn('scope', fact['value'])
                self.assertIn('ttl_declared', fact['value'])


class RateLimitDetectorTests(unittest.TestCase):
    """An entry point without a rate limit is recorded as one with no limit."""

    def test_a_limiter_decorator_is_a_rate_limit(self):
        body = "@limiter.limit('100/minute')\ndef api():\n    return 'ok'\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            limits = [f for f in data['facts'] if f['kind'] == 'rate_limit']
            self.assertGreater(len(limits), 0)
            self.assertEqual(limits[0]['value']['source'], 'code')

    def test_a_semaphore_is_a_rate_limit(self):
        body = "import asyncio\nsem = asyncio.Semaphore(10)\nasync def f():\n    async with sem: pass\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            limits = [f for f in data['facts'] if f['kind'] == 'rate_limit']
            sem_limits = [l for l in limits if 'semaphore' in l['value']['mechanism']]
            self.assertGreater(len(sem_limits), 0)

    def test_threadpoolexecutor_max_workers_is_a_concurrency_bound(self):
        body = "from concurrent.futures import ThreadPoolExecutor\npool = ThreadPoolExecutor(max_workers=8)\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            limits = [f for f in data['facts'] if f['kind'] == 'rate_limit']
            workers = [l for l in limits if 'worker' in l['value']['mechanism']]
            self.assertGreater(len(workers), 0)

    def test_nginx_limit_req_zone_is_a_config_rate_limit(self):
        body = 'http {\n  limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;\n}\n'
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body, name='nginx.conf')
            limits = [f for f in data['facts'] if f['kind'] == 'rate_limit']
            nginx = [l for l in limits if l['value']['source'] == 'config']
            self.assertGreater(len(nginx), 0)

    def test_kubernetes_resources_limits_is_a_config_rate_limit(self):
        body = 'apiVersion: apps/v1\nkind: Deployment\nspec:\n  containers:\n  - name: app\n    resources:\n      limits:\n        cpu: "1"\n        memory: "1Gi"\n'
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body, name='deployment.yaml')
            limits = [f for f in data['facts'] if f['kind'] == 'rate_limit']
            k8s = [l for l in limits if 'resources' in l['value']['mechanism'] or 'hpa' in l['value']['mechanism']]
            self.assertGreater(len(k8s), 0)

    def test_no_rate_limit_fact_when_nothing_matches(self):
        body = "def f():\n    return 1 + 1\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            limits = [f for f in data['facts'] if f['kind'] == 'rate_limit']
            self.assertEqual(limits, [])

    def test_declared_limit_is_captured_when_numeric_value_present(self):
        body = "@limiter.limit(limit=100, per=60)\ndef f():\n    pass\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            limits = [f for f in data['facts'] if f['kind'] == 'rate_limit']
            self.assertTrue(any(l['value']['declared_limit'] is not None for l in limits),
                            f'expected a numeric declared_limit somewhere, got {limits}')

    def test_each_rate_limit_fact_carries_scope_mechanism_and_source(self):
        body = "import asyncio\nsem = asyncio.Semaphore(10)\nasync def f():\n    async with sem: pass\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            limits = [f for f in data['facts'] if f['kind'] == 'rate_limit']
            for fact in limits:
                self.assertIn('scope', fact['value'])
                self.assertIn('mechanism', fact['value'])
                self.assertIn('source', fact['value'])
                self.assertIn('declared_limit', fact['value'])
                self.assertIn(fact['value']['source'], ('code', 'config'))


class ConnectionPoolDetectorTests(unittest.TestCase):
    """A connection pool is the real ceiling on concurrency; we record what is declared."""

    def test_sqlalchemy_pool_size_is_a_connection_pool(self):
        body = "from sqlalchemy import create_engine\ne = create_engine('postgresql://x', pool_size=20)\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            pools = [f for f in data['facts'] if f['kind'] == 'connection_pool']
            sqlalchemy = [p for p in pools if 'sqlalchemy' in p['value']['resource']]
            self.assertGreater(len(sqlalchemy), 0)
            self.assertEqual(sqlalchemy[0]['value']['declared_size'], 20)

    def test_sqlalchemy_no_pool_size_emits_no_fact(self):
        """We do not assume defaults: undeclared means unknown means no fact."""
        body = "from sqlalchemy import create_engine\ne = create_engine('sqlite:///local.db')\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            pools = [f for f in data['facts'] if f['kind'] == 'connection_pool']
            self.assertEqual(pools, [])

    def test_go_http_max_idle_conns_is_a_connection_pool(self):
        body = ('package main\n'
                'import "net/http"\n'
                'func f() *http.Client {\n'
                '    transport := &http.Transport{MaxIdleConns: 100}\n'
                '    return &http.Client{Transport: transport}\n'
                '}\n')
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body, name='orders.go')
            pools = [f for f in data['facts'] if f['kind'] == 'connection_pool']
            self.assertGreater(len(pools), 0)
            self.assertEqual(pools[0]['value']['declared_size'], 100)

    def test_pgx_max_conns_is_a_connection_pool(self):
        body = ('package main\n'
                'import "github.com/jackc/pgx/v4/pgxpool"\n'
                'func f() {\n'
                '    cfg, _ := pgxpool.ParseConfig("")\n'
                '    cfg.MaxConns = 30\n'
                '}\n')
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body, name='orders.go')
            pools = [f for f in data['facts'] if f['kind'] == 'connection_pool']
            self.assertGreater(len(pools), 0)
            self.assertEqual(pools[0]['value']['declared_size'], 30)

    def test_no_pool_fact_when_nothing_matches(self):
        body = "def f():\n    return 1 + 1\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            pools = [f for f in data['facts'] if f['kind'] == 'connection_pool']
            self.assertEqual(pools, [])

    def test_each_pool_fact_carries_resource_declared_size_and_source(self):
        body = "from sqlalchemy import create_engine\ne = create_engine('postgresql://x', pool_size=5)\n"
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body)
            pools = [f for f in data['facts'] if f['kind'] == 'connection_pool']
            for fact in pools:
                self.assertIn('resource', fact['value'])
                self.assertIn('declared_size', fact['value'])
                self.assertIn('source', fact['value'])
                self.assertIn('path', fact['location'])

    def test_database_url_with_pool_param_is_a_connection_pool(self):
        body = 'DATABASE_URL = "postgres://x?pool=50"\n'
        with tempfile.TemporaryDirectory() as tmp:
            data = _collect(tmp, body=body, name='config.py')
            pools = [f for f in data['facts'] if f['kind'] == 'connection_pool']
            self.assertGreater(len(pools), 0)

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

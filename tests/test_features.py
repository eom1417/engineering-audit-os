"""features.py: groups user-facing surfaces into named features with bound evidence.

This is a unit test of the ``build`` function over constructed fact sets. The integration
test (the audit pipeline writing features.json on every project and the
measurement reading it back) lives in tests/test_audit_pipeline.py and the contract suite.
"""
import unittest

from eaos import features
from eaos.features import build, _feature_name, _is_critical


def entry_point(route, surface='page', framework=None, handler=None, path=None,
                category='source', fact_id=None):
    """An entry-point fact whose surface is one the user can reach."""
    return {'id': fact_id or f'FACT-{route}-{surface}', 'kind': 'entry_point',
            'location': {'path': path or f'src/routes/{route.split("/")[-1] or "index"}.tsx',
                         'start_line': 1},
            'value': {'surface': surface,
                      'route': route,
                      'http_method': None,
                      'handler': handler or 'h',
                      'framework': framework or 'tanstack_router',
                      'language': 'typescript',
                      'category': category,
                      'note': None}}


def flow(route, path, touched_files=()):
    return {'id': f'FLOW-{route}', 'kind': 'flow',
            'value': {'flow_id': f'FLOW-{route}',
                      'entry': {'surface': 'page', 'route': route, 'path': path, 'line': 1},
                      'touched_files': list(touched_files)}}


def data_access(target, operation='select', path=None, fact_id=None):
    return {'id': fact_id or f'FACT-DA-{target}', 'kind': 'data_access',
            'location': {'path': path or f'src/services/{target}.ts', 'start_line': 1},
            'value': {'client': 'supabase', 'target': target, 'operation': operation,
                      'category': 'source'}}


class FeatureNameTests(unittest.TestCase):
    def test_a_route_collapses_to_its_feature_name_and_only_its_surface_marks_it_critical(self):
        for route, name in [('/_authenticated/cartoes', 'cartoes'), ('/_authenticated/cartoes/$invoiceId', 'cartoes'),
                            ('/', 'home'), ('', 'home'), ('/api/v1/users', 'api'),
                            ('/_authenticated/cartoes_/faturas/$id', 'cartoes')]:
            self.assertEqual(_feature_name(route), name, route)
        self.assertTrue(_is_critical(['/auth/login']))
        self.assertTrue(_is_critical(['/billing/checkout']))
        # ``_authenticated`` in a file path is not a surface marker.
        self.assertFalse(_is_critical(['src/routes/_authenticated/dashboard.tsx']))


class BuildTests(unittest.TestCase):
    """end-to-end behaviour of ``build(facts)`` over a constructed fact set."""

    def test_surfaces_group_into_features_with_their_data_and_every_surface_is_accounted_for(self):
        facts = [entry_point('/_authenticated/cartoes', handler='Cartoes', fact_id='F1'),
                 entry_point('/_authenticated/cartoes/$invoiceId', handler='CartoesOne', fact_id='F2'),
                 entry_point('/_authenticated/movements', path='src/routes/_authenticated/movements.tsx'),
                 data_access('movements', path='src/routes/_authenticated/movements.tsx'),
                 entry_point('/_authenticated/transfers', path='src/x.tsx'),
                 data_access('transfers', operation='insert', path='src/x.tsx'),
                 entry_point('/rare/route', surface='http', framework='express', fact_id='F3'),
                 entry_point(None, surface='cli', framework='python_script', handler=None, path='manage.py', fact_id='F-CLI-1')]
        result = build(facts)
        found = {f['name']: f for f in result['features']}
        self.assertEqual(set(found['cartoes']['surfaces']), {'/_authenticated/cartoes', '/_authenticated/cartoes/$invoiceId'})
        self.assertIn('movements', found['movements']['tables'])
        self.assertTrue(any(eid.startswith('FACT-DA-') for eid in found['movements']['evidence']))
        self.assertTrue(found['transfers']['critical'], 'a write marks the feature critical')
        self.assertEqual([name for name in found if name.startswith('cli:')], ['cli:manage.py'])
        accounted = {eid for f in result['features'] for eid in f['evidence']} | set(result['unassigned_surfaces'])
        self.assertTrue({'F1', 'F2', 'F3', 'F-CLI-1'} <= accounted)
        from eaos.artifact_contracts import contracts, validate
        self.assertEqual(validate(result, contracts()['features']), [])

    def test_a_cli_groups_by_subcommand_and_its_scripts_tools_and_web_root_are_not_features(self):
        # The self-audit: one feature per module with `__main__`, 53 features for tools/ scripts, and the whole
        # Studio front end as `home` in a command-line program.
        cli = lambda route, path, framework='argparse': entry_point(route, surface='cli', framework=framework, path=path,
                                                                     fact_id=f'C-{route}-{path}')
        facts = [cli('eaos', 'eaos/cli.py'), cli('check', 'eaos/cli.py'), cli('fix', 'eaos/cli.py'),
                 cli('eaos', 'pyproject.toml', 'console_script'), cli('plan', 'eaos/plan.py', 'python_script'),
                 cli('sbom', 'tools/sbom.py', 'python_script'), cli('shot', 'scripts/shot.py', 'python_script'),
                 entry_point('/', path='studio/src/App.tsx', fact_id='P1')]
        result = build(facts)
        self.assertEqual({f['name'] for f in result['features']}, {'cli:eaos', 'cli:check', 'cli:fix', 'studio'})
        self.assertEqual(set(result['unassigned_surfaces']), {'eaos/plan.py', 'tools/sbom.py', 'scripts/shot.py'})
        # A web app's `/` is its home; a program made only of scripts keeps them.
        self.assertEqual({f['name'] for f in build([entry_point('/', path='src/routes/index.tsx'),
                                                     cli(None, 'manage.py', 'python_script')])['features']},
                         {'home', 'cli:manage.py'})


class FeatureDataTests(unittest.TestCase):
    """A feature is tied to the data its own pages reach, through a router file, imports and an HTTP client."""

    def facts(self):
        edge = lambda i, path, to, names: [
            {'kind': 'import_edge', 'id': f'I{i}', 'location': {'path': path}, 'value': {'module': to, 'names': names}},
            {'kind': 'module_edge', 'id': f'M{i}', 'location': {'path': path}, 'value': {'to_path': to, 'import_fact_id': f'I{i}'}}]
        page = lambda i, route, handler: {'kind': 'entry_point', 'id': f'E{i}', 'location': {'path': 'src/App.tsx'},
                                          'value': {'surface': 'page', 'route': route, 'handler': handler, 'framework': 'react_router'}}
        access = lambda i, path, client, target, op: {'kind': 'data_access', 'id': f'D{i}', 'location': {'path': path},
                                                      'value': {'client': client, 'target': target, 'operation': op}}
        return ([page(1, '/drivers', 'DriversPage'), page(2, '/tolls', 'TollsPage'), page(3, '/login', 'Login'),
                 page(4, '/reset-password', 'Reset'), page(5, '/terms', 'Terms'), page(6, '*', 'NotFound')]
                + edge(1, 'src/App.tsx', 'src/pages/DriversPage.tsx', ['DriversPage'])
                + edge(2, 'src/App.tsx', 'src/pages/TollsPage.tsx', ['TollsPage'])
                + edge(3, 'src/App.tsx', 'src/pages/Login.tsx', ['Login'])
                + edge(4, 'src/pages/DriversPage.tsx', 'src/lib/operatorsApi.ts', ['operatorsApi'])
                + edge(5, 'src/pages/TollsPage.tsx', 'src/components/Widget.tsx', ['Widget'])
                + edge(6, 'src/components/Widget.tsx', 'src/lib/operatorsApi.ts', ['operatorsApi'])
                + edge(7, 'src/pages/DriversPage.tsx', 'src/components/auth/AuthContext.tsx', ['useAuth'])
                + edge(8, 'src/pages/TollsPage.tsx', 'src/components/auth/AuthContext.tsx', ['useAuth'])
                + edge(9, 'src/pages/Login.tsx', 'src/components/auth/AuthContext.tsx', ['useAuth'])
                + [access(1, 'src/lib/operatorsApi.ts', 'http', '/operators', 'post'),
                   access(2, 'src/components/auth/AuthContext.tsx', 'http', '/Auth/login', 'post'),
                   access(3, 'src/pages/TollsPage.tsx', 'supabase', 'tolls', 'select')])

    def test_each_feature_is_tied_to_the_data_its_own_pages_reach(self):
        found = {f['name']: f for f in features.build(self.facts())['features']}
        # Pages on the way in or about the product are one feature each.
        self.assertTrue({'auth', 'info'} <= set(found))
        self.assertFalse({'login', 'reset-password', 'terms', '*'} & set(found))
        # A route declared in the router file starts from its component file.
        self.assertIn('src/pages/DriversPage.tsx', found['drivers']['files'])
        # Data goes to the feature that reaches it most directly; a context file only to the feature its path names.
        self.assertEqual(found['drivers']['endpoints'], ['POST /operators'])
        self.assertEqual((found['tolls']['endpoints'], found['tolls']['tables']), ([], ['tolls']))
        self.assertEqual(found['auth']['endpoints'], ['POST /Auth/login'])
        # An HTTP write makes a feature critical; reads stay apart from writes.
        self.assertTrue(found['drivers']['critical'])
        self.assertEqual(found['tolls']['writes'], [])
        self.assertFalse(found['tolls']['critical'])
        self.assertEqual([features._count(n, features._NOUNS['page']) for n in (1, 2, 4, 12)],
                         ['صفحة واحدة', 'صفحتان', '4 صفحات', '12 صفحة'])

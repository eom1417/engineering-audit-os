"""features.py: groups user-facing surfaces into named features with bound evidence.

This is a unit test of the ``build`` function over constructed fact sets. The integration
test (the audit pipeline writing features.json + FEATURES.md on every project and the
measurement reading it back) lives in tests/test_audit_pipeline.py and the contract suite.
"""
import json
import sys
import unittest
from pathlib import Path

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
    """A route name collapses to its first non-layout, non-parameter segment."""

    def test_a_layout_segment_is_stripped(self):
        self.assertEqual(_feature_name('/_authenticated/cartoes'), 'cartoes')

    def test_a_parameter_segment_is_stripped(self):
        self.assertEqual(_feature_name('/_authenticated/cartoes/$invoiceId'), 'cartoes')

    def test_root_collapses_to_home(self):
        self.assertEqual(_feature_name('/'), 'home')
        self.assertEqual(_feature_name(''), 'home')

    def test_unrelated_segments_are_kept(self):
        self.assertEqual(_feature_name('/api/v1/users'), 'api')

    def test_trailing_underscore_is_dropped(self):
        self.assertEqual(_feature_name('/_authenticated/cartoes_/faturas/$id'), 'cartoes')


class CriticalDetectionTests(unittest.TestCase):
    """The keyword rule only matches the surface identifier, with a word boundary."""

    def test_auth_keyword_marks_critical(self):
        self.assertTrue(_is_critical(['/auth/login']))
        self.assertTrue(_is_critical(['/billing/checkout']))

    def test_a_file_path_with_auth_does_not_mark_critical(self):
        # ``_authenticated`` in a file path is not a surface marker; the rule
        # searches the surface identifier, not the files behind it.
        self.assertFalse(_is_critical(['src/routes/_authenticated/dashboard.tsx']))


class BuildTests(unittest.TestCase):
    """end-to-end behaviour of ``build(facts)`` over a constructed fact set."""

    def test_two_pages_with_a_shared_layout_become_one_feature(self):
        facts = [
            entry_point('/_authenticated/cartoes', handler='Cartoes'),
            entry_point('/_authenticated/cartoes/$invoiceId', handler='CartoesOne')]
        result = build(facts)
        self.assertEqual(len(result['features']), 1)
        self.assertEqual(result['features'][0]['name'], 'cartoes')
        self.assertEqual(set(result['features'][0]['surfaces']),
                         {'/_authenticated/cartoes', '/_authenticated/cartoes/$invoiceId'})

    def test_a_data_access_in_a_feature_file_appears_in_tables_and_evidence(self):
        facts = [entry_point('/_authenticated/movements', path='src/routes/_authenticated/movements.tsx'),
                 data_access('movements', path='src/routes/_authenticated/movements.tsx')]
        result = build(facts)
        feature = next(f for f in result['features'] if f['name'] == 'movements')
        self.assertIn('movements', feature['tables'])
        evidence_ids = feature['evidence']
        self.assertTrue(any(eid.startswith('FACT-DA-') for eid in evidence_ids))

    def test_a_write_marks_the_feature_critical(self):
        facts = [entry_point('/_authenticated/transfers', path='src/x.tsx'),
                 data_access('transfers', operation='insert', path='src/x.tsx')]
        result = build(facts)
        feature = next(f for f in result['features'] if f['name'] == 'transfers')
        self.assertTrue(feature['critical'])

    def test_all_surfaces_appear_in_some_feature_or_in_unassigned(self):
        facts = [entry_point('/_authenticated/dashboard', fact_id='F1'),
                 entry_point('/_authenticated/imports', fact_id='F2'),
                 entry_point('/rare/route', surface='http', framework='express', fact_id='F3')]
        result = build(facts)
        all_evidence = {eid for f in result['features'] for eid in f['evidence']}
        all_evidence.update(result['unassigned_surfaces'])
        self.assertEqual(all_evidence & {'F1', 'F2', 'F3'}, {'F1', 'F2', 'F3'})

    def test_a_cli_surface_groups_by_its_module_path(self):
        facts = [entry_point(None, surface='cli',
                             framework='python_script', handler=None,
                             path='manage.py', fact_id='F-CLI-1')]
        result = build(facts)
        cli_names = [f['name'] for f in result['features'] if f['name'].startswith('cli:')]
        self.assertEqual(cli_names, ['cli:manage.py'])

    def test_an_output_matches_the_features_contract_schema(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
        from contracts import contracts, validate
        facts = [entry_point('/_authenticated/accounts', path='src/x.tsx'),
                 data_access('accounts', path='src/x.tsx')]
        result = build(facts)
        self.assertEqual(validate(result, contracts()['features']), [])

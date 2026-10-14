"""External engines enter as evidence, never as authority, and a missing engine never fails a run."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos import correlate
from eaos.engines import ADAPTERS, analyze, health
from eaos.engines.contract import Report, UNAVAILABLE, finding, subject


def engine_fact(identifier, engine, kind, path, rule='r', sites=None, message='m', measurements=()):
    return {'id': identifier, 'kind': 'engine_finding',
            'location': {'path': path, 'line': None, 'symbol': path},
            'value': {'engine': engine, 'engine_version': '1', 'rule': rule, 'kind': kind, 'method': 'heuristic',
                      'message': message, 'measurements': list(measurements), 'engine_confidence': None, 'subject_kind': 'file',
                      'sites': sites if sites is not None else [{'path': path, 'line': None}]}}


def evaluated_at(**kinds):
    """{'cycle': ('observed', 'file')} -> the shape an adapter reports."""
    return {kind: {'status': state, 'granularity': level} for kind, (state, level) in kinds.items()}


def fact_set(facts, evaluated):
    return {'external': {'facts': facts, 'summary': {'evaluated_kinds': evaluated}}}


class ContractTests(unittest.TestCase):
    def test_a_finding_has_a_known_kind_a_content_identity_and_every_place_it_names(self):
        with self.assertRaises(ValueError):
            finding('e', '1', 'rule', 'not_a_kind', subject('file', 'a.py'), 'message')
        first = finding('e', '1', 'rule', 'cycle', subject('file', 'a.py'), 'message')
        self.assertEqual(first['id'], finding('e', '1', 'rule', 'cycle', subject('file', 'a.py'), 'message')['id'])
        self.assertNotEqual(first['id'], finding('e', '1', 'rule', 'cycle', subject('file', 'b.py'), 'message')['id'])
        row = finding('e', '1', 'rule', 'duplication', subject('file', 'a.py'), 'message',
                      sites=[{'path': 'b.py', 'line': 3}, {'path': 'a.py', 'line': None}])
        self.assertEqual([spot[0] for spot in row['sites']], ['a.py', 'b.py'])


class DegradationTests(unittest.TestCase):
    def test_a_missing_crashing_unknown_or_inapplicable_engine_never_fails_the_run_and_is_reported(self):
        report = health()
        self.assertEqual(sorted(report), sorted(ADAPTERS))
        self.assertTrue(all('version_matches_pin' in detail for detail in report.values()))
        absent = Report('absent', None, '1.0', UNAVAILABLE, reason='not installed').as_dict()
        self.assertEqual((absent['status'], absent['version_matches_pin']), (UNAVAILABLE, False))

        class Exploding:
            NAME, PINNED = 'exploding', '0'
            @staticmethod
            def analyze(*_args, **_kwargs): raise RuntimeError('engine crashed')
        class Calm:
            NAME, PINNED = 'calm', '0'
            @staticmethod
            def analyze(*_args, **_kwargs): return Report('calm', None, '0', UNAVAILABLE, reason='nothing here')
        ADAPTERS.update(exploding=Exploding, calm=Calm)
        try:
            with tempfile.TemporaryDirectory() as workdir:
                manifest = analyze('.', workdir, only=['exploding', 'calm', 'imaginary'])
                # Run again alone within the same check, the one that failed joins the others' results kept from it.
                Exploding.analyze = staticmethod(lambda *_a, **_k: Report('exploding', None, '0', UNAVAILABLE, reason='fixed'))
                again = analyze('.', workdir, only=['exploding'], keep=True)
        finally:
            del ADAPTERS['exploding'], ADAPTERS['calm']
        self.assertEqual(manifest['coverage']['exploding']['status'], 'error')
        self.assertIn('engine crashed', manifest['coverage']['exploding']['reason'])
        self.assertEqual({name: row['reason'] for name, row in again['coverage'].items()}, {'calm': 'nothing here', 'exploding': 'fixed'})
        self.assertEqual((manifest['unknown_engines'], manifest['findings']), (['imaginary'], []))
        # A tool with nothing to read is not applicable, not absent.
        from unittest import mock
        from eaos.engines import tool
        from eaos.engines.contract import NOT_APPLICABLE
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'app.py').write_text('print(1)\n')
            with mock.patch.object(tool, 'version', return_value='4.3.0'):
                self.assertEqual(tool.declined('sqlfluff', 'sqlfluff', tmp).status, NOT_APPLICABLE)
            with mock.patch.object(tool, 'version', return_value=None):
                self.assertEqual(tool.declined('sqlfluff', 'sqlfluff', tmp).status, 'unavailable')


class CorrelationTests(unittest.TestCase):
    def test_agreement_silence_and_resolution_decide_the_verdict(self):
        both = {'enola': evaluated_at(complexity=('observed', 'file')), 'reforge': evaluated_at(complexity=('observed', 'file'))}
        [cluster] = correlate.clusters(fact_set([engine_fact('F1', 'enola', 'complexity', 'a.py'),
                                                 engine_fact('F2', 'reforge', 'complexity', 'a.py', measurements=[{'name': 'function.complexity', 'value': 30, 'threshold': 15}])], both))
        self.assertEqual(cluster['corroboration']['complexity']['verdict'], correlate.CORROBORATED)
        self.assertEqual(cluster['engines'], ['enola', 'reforge'])
        # Silence about a threshold rule is not a denial.
        [cluster] = correlate.clusters(fact_set([engine_fact('F1', 'enola', 'complexity', 'a.py')], both))
        self.assertEqual(cluster['corroboration']['complexity']['verdict'], correlate.SINGLE)
        cycle = lambda other, enola_level='file': correlate.clusters(fact_set(
            [engine_fact('F1', 'enola', 'cycle', 'pkg')],
            {'enola': evaluated_at(cycle=('observed', enola_level)), **other}))[0]['corroboration']['cycle']
        # Silence about a structural property at the same resolution is a denial.
        detail = cycle({'codegraph': evaluated_at(cycle=('observed', 'file'))})
        self.assertEqual((detail['verdict'], detail['denied_by']), (correlate.CONTESTED, ['codegraph']))
        # Silence at another resolution is a gap, not a contradiction.
        detail = cycle({'codegraph': evaluated_at(cycle=('observed', 'file'))}, enola_level='package')
        self.assertEqual((detail['verdict'], detail['denied_by'], detail['silent_at_another_resolution'], detail['asserted_at']),
                         (correlate.GRANULARITY_GAP, [], ['codegraph'], ['package']))
        # A partial evaluation does not deny.
        detail = cycle({'reforge': evaluated_at(cycle=('partial', 'file'))})
        self.assertEqual((detail['verdict'], detail['evaluated_and_silent']), (correlate.SINGLE, {'reforge': 'partial'}))
        # A multi-site finding belongs to every site.
        sets = fact_set([engine_fact('F1', 'jscpd', 'literal_duplication', 'a.py',
                                     sites=[{'path': 'a.py', 'line': 1}, {'path': 'b.py', 'line': 9}])],
                        {'jscpd': evaluated_at(literal_duplication=('observed', 'file'))})
        self.assertEqual([c['place'] for c in correlate.clusters(sets)], ['a.py', 'b.py'])


class EngineClaimTests(unittest.TestCase):
    def test_engine_evidence_becomes_a_claim_only_when_corroborated_and_never_above_its_ceiling(self):
        from eaos.claims import from_engines
        from eaos.probes import _apply_ceiling
        self.assertEqual(from_engines(fact_set([engine_fact('F1', 'enola', 'complexity', 'a.py')],
                                               {'enola': evaluated_at(complexity=('observed', 'file'))})), [])
        [claim] = from_engines(fact_set([engine_fact('F1', 'enola', 'complexity', 'a.py'),
                                         engine_fact('F2', 'reforge', 'complexity', 'a.py', measurements=[{'name': 'function.complexity', 'value': 30, 'threshold': 15}])],
                                        {'enola': evaluated_at(complexity=('observed', 'file')),
                                         'reforge': evaluated_at(complexity=('observed', 'file'))}))
        self.assertEqual((claim['confidence'], claim['confidence_ceiling'], claim['method']), ('LIKELY', 'LIKELY', ['external_engine']))
        self.assertTrue(claim['falsifier'].strip())
        [contested] = from_engines(fact_set([engine_fact('F1', 'enola', 'cycle', 'pkg')],
                                            {'enola': evaluated_at(cycle=('observed', 'file')),
                                             'codegraph': evaluated_at(cycle=('observed', 'file'))}))
        self.assertEqual((contested['confidence'], contested['confidence_ceiling']), ('HYPOTHESIS', 'HYPOTHESIS'))
        # A probe cannot raise an external claim to confirmed; a claim without a ceiling is left alone.
        claim = {'confidence': 'CONFIRMED', 'confidence_ceiling': 'LIKELY', 'method': ['external_engine']}
        row = {'status': 'CONFIRMED', 'result': 'still reported'}
        _apply_ceiling(claim, row)
        self.assertEqual((claim['confidence'], row['status']), ('LIKELY', 'PARTIAL'))
        self.assertIn('capped at LIKELY', row['result'])
        claim, row = {'confidence': 'CONFIRMED', 'method': ['static_fact']}, {'status': 'CONFIRMED', 'result': 'proved'}
        _apply_ceiling(claim, row)
        self.assertEqual((claim['confidence'], row['status']), ('CONFIRMED', 'CONFIRMED'))


class ReportRenderingTests(unittest.TestCase):
    def test_the_engine_artifact_leads_with_disagreements_and_says_so_when_nothing_ran(self):
        from eaos.engines_report import document
        self.assertIn('No external engine ran', document({}, 'en').render())
        sets = fact_set([engine_fact('F1', 'enola', 'cycle', 'pkg')],
                        {'enola': evaluated_at(cycle=('observed', 'file')),
                         'codegraph': evaluated_at(cycle=('observed', 'file'))})
        sets['external']['summary'].update({'engines_observed': ['codegraph', 'enola'], 'engines_unavailable': [],
                                            'by_engine': {'enola': 1, 'codegraph': 0}})
        text = document(sets, 'en').render()
        self.assertIn('Contested', text)
        self.assertIn('pkg', text)


class InstalledEngineTests(unittest.TestCase):
    """Runs only where the pinned engines exist; skips rather than pretending elsewhere."""

    @classmethod
    def setUpClass(cls):
        from eaos.engines import enola, jscpd
        if not (enola.version() and jscpd.version()):
            raise unittest.SkipTest('the pinned engines are not installed in this environment')

    def test_a_run_only_runs_what_was_asked_leaves_the_target_untouched_and_is_reproducible(self):
        import os, shutil
        from eaos.facts.run import collect
        with tempfile.TemporaryDirectory() as workdir:
            manifest = analyze('eaos/compose', workdir, only=['jscpd'], formats=['python'])
        self.assertTrue(manifest['target_unchanged'])
        self.assertEqual((manifest['requested'], sorted(manifest['coverage'])), (['jscpd'], ['jscpd']))
        # A fact id hashing modification times changed with every clone, and with it the measurement a claim shows.
        ids = []
        with tempfile.TemporaryDirectory() as tmp:
            for name, mtime in (('a', 1_000_000), ('b', 2_000_000)):
                target = shutil.copytree('eaos/compose', Path(tmp, name, 'compose'))
                for path in target.rglob('*'): os.utime(path, (mtime, mtime))
                collect(target, Path(tmp, name, 'out'), engines=['enola', 'jscpd'])
                facts = json.loads(Path(tmp, name, 'out', 'facts/external.json').read_text())['facts']
                ids.append(sorted(fact['id'] for fact in facts))
        self.assertTrue(ids[0])
        self.assertEqual(ids[0], ids[1])

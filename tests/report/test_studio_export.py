"""studio/: every section the Studio reads, written from the one model, valid against its contract, with its coverage
row; the evidence excerpts; the small contract fixtures and the synthetic Studio at scale; the translation catalog."""
import copy
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.core.contracts import artifact_rules as artifact_contracts
from eaos.report.studio import coverage, evidence, export, inbox
from eaos.analysis.presentation import model
from eaos.report.studio.localization import publish
from tests.shared_fixture import Workspace
from tests.report.test_human_report import report

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import studio_synthetic  # noqa: E402

SECTIONS = ('meta', 'head', 'health', 'cards', 'evidence', 'story', 'docs', 'plans', 'decisions', 'media', 'system')
SECTIONS_V2 = ('history', 'paths', 'journeys', 'hidden', 'data_paths', 'infra', 'ideal', 'nodes', 'gaps', 'operations', 'library')
FIXTURES = ROOT / 'tests/fixtures/studio/v2'


class Export(Workspace):
    def setUp(self):
        super().setUp()
        self.out = report(self.tmp)
        (self.out / 'START-HERE.md').write_text('# Start here\n\nSix problems.\n', encoding='utf-8')
        self.result = export.export(self.out, 'en', 'shop')
        self.folder = self.out / 'studio'

    def load(self, name):
        return json.loads((self.folder / f'{name}.json').read_text(encoding='utf-8'))

    def test_every_section_meets_its_contract_with_its_fingerprint_once_and_coverage_last(self):
        from eaos import __version__
        self.assertEqual(self.result['errors'], [])
        self.assertEqual(self.result['written'], [*SECTIONS, *SECTIONS_V2, 'coverage'])
        contracts = artifact_contracts.contracts()
        for name in ('manifest', *self.result['written']):
            self.assertEqual(artifact_contracts.validate(self.load(name), contracts[f'studio-{name}']), [], name)
        manifest = self.load('manifest')
        self.assertEqual((manifest['contract'], manifest['revision'], manifest['sections'][-1]['name']), (1, 2, 'coverage'))
        for entry in manifest['sections']:
            blob = (self.folder / entry['file']).read_bytes()
            self.assertEqual((entry['sha256'], entry['bytes']), (hashlib.sha256(blob).hexdigest(), len(blob)), entry['name'])
        self.assertEqual(sorted(self.folder.glob('*.js')), [], 'one copy of each section: no .js twin')
        self.assertEqual((manifest['built']['version'], self.load('head')['eaos']['version']), (__version__, __version__))
        data = self.load('coverage')
        rows = {row['section']: row for row in data['sections']}
        self.assertEqual(list(rows)[:len(coverage.PLANNED)], list(coverage.PLANNED))
        for name in ('meta', 'head', 'health', 'cards', 'evidence', 'story', 'docs', 'plans', 'decisions', 'media', 'gaps', 'operations'):
            self.assertIn(rows[name]['state'], ('measured', 'empty'), name)
        for name in ('history', 'library'):
            self.assertEqual(rows[name]['state'], 'measured', name)
        for name in ('functions', 'screens'):
            self.assertEqual(rows[name]['state'], 'not_measured', name)
            self.assertTrue(rows[name]['detail'], name)
        self.assertEqual(data['not_measured']['value'], sum(r['state'] in ('not_measured', 'failed') for r in data['sections']))
        self.assertEqual([d['id'] for d in self.load('library')['documents']], ['START-HERE.md'])

    def test_a_reexport_in_arabic_keeps_every_decision_identity_and_writes_plain_arabic(self):
        before = {row['id']: row for row in self.load('decisions')['decisions']}
        self.assertTrue(before)
        export.export(self.out, 'ar', 'shop')
        after = {row['id']: row for row in self.load('decisions')['decisions']}
        self.assertEqual(before.keys(), after.keys())
        for identity, row in before.items():
            self.assertEqual(row['revision'], after[identity]['revision'])
            self.assertEqual(row.get('recommended_option'), after[identity].get('recommended_option'))
            self.assertEqual([o['id'] for o in row['options']], [o['id'] for o in after[identity]['options']])
        head = self.load('head')
        for text in (head['verdict'], head['next']['action']):
            self.assertIsNone(re.search(r'(?:^|\s)[لبكوف]ـ?\d', text), text)
        functions = next(r for r in self.load('coverage')['sections'] if r['section'] == 'functions')
        self.assertRegex(functions['detail'], '[؀-ۿ]')

    def test_the_studio_shows_the_reports_score_cards_plan_and_documents_and_nothing_outside_the_project(self):
        m = model.records(self.out)
        self.assertEqual(self.load('health')['score']['value'], m['score']['score'] / 100)
        areas = {d['id']: d['score']['value'] for d in self.load('health')['domains']}
        self.assertIsNone(areas['performance'], 'its stage failed: not measured, not zero')
        cards = {c['id']: c for c in self.load('cards')['cards']}
        self.assertEqual(len(cards), 6)
        self.assertTrue(cards['TASK-1']['fixable'] and cards['TASK-2']['needs_decision'])
        self.assertEqual({c['state'] for c in cards.values()}, {'open'})
        docs = {d['path']: d for d in self.load('docs')['docs']}
        self.assertEqual((docs['START-HERE.md']['group'], docs['START-HERE.md']['title']), ('start', 'Start here'))
        for outside in ('/etc/passwd', '../secret', '~/x'):
            self.assertIsNone(evidence.rel(outside), outside)
        self.assertEqual(evidence.rel('src/a.ts'), 'src/a.ts')
        self.assertNotIn(self.tmp, ''.join((self.folder / f'{n}.json').read_text(encoding='utf-8') for n in SECTIONS))
        ledger = {'cards': [{'id': 'TASK-1', 'key': 'k1', 'state': 'done'}, {'id': 'TASK-2', 'key': 'k2', 'state': 'open'}]}
        export.export(self.out, 'en', 'shop', progress={'ledger': ledger})
        plan = self.load('plans')['plans'][0]
        self.assertEqual(plan['state'], 'active')
        self.assertAlmostEqual(plan['progress']['value'], 1 / 6, places=3)
        self.assertEqual((plan['steps'][0]['state'], plan['steps'][0]['tasks'][0]['state']), ('active', 'done'))
        decision = self.load('decisions')['decisions'][0]
        self.assertEqual((decision['id'], set(decision['blocks'])), ('investigations', {'TASK-2', 'TASK-6'}))
        # The incident (decisions inbox, 2026-10-12): one topic asked twice, a fact asked of the person, and the target
        # approval offered as 51 ADR sentences
        ask = lambda id, question: {'id': id, 'question': question, 'options': [], 'state': 'waiting'}
        rows = inbox.tidy([ask('ideal-Q-search', 'هل خانتا البحث (في الشريط العلوي وفي القائمة الجانبية) تؤديان العمل نفسه؟'),
                                      ask('node-visual_reviewer:IMG-014:Q-014-1', 'هل خانتين البحث (فوق وفي القائمة الجانبية) لهم نفس الوظيفة؟'),
                                      ask('node-plan_orderer:plan:Q-cli-split', 'Split eaos/interfaces/cli.py after the stage contracts?'),
                                      ask('ideal-Q-cli-split', 'هل نقسّم eaos/interfaces/cli.py إلى وحدات حسب مجموعات الأوامر؟'),
                                      ask('node-card_triage:TASK-164:Q-164', 'هل في eaos/interfaces/studio_server/events.py دالة واحدة على الأقل تعقيدها فوق 15؟'),
                                      ask('ideal-Q-types', 'هل تُولَّد studio/src/data/types.ts من eaos/core/contracts/artifact_rules.py؟'),
                                      # 2026-10-14: two of the planner's questions ending in one sentence were read as one
                                      ask('ideal-Q-reach', 'هل يُفتح الاستوديو لشخص واحد؟ جواب الاستلام كان القيمة الافتراضية.'),
                                      ask('ideal-Q-personal-data', 'هل يخزن EAOS بيانات شخصية؟ جواب الاستلام كان القيمة الافتراضية.'),
                                      ask('ideal-Q-read-first', 'قسم «اقرأ أولًا» في المكتبة يكرر وثائق المجموعات. ما الذي نبقيه؟'),
                                      ask('node-visual_reviewer:PAGE-015:Q-1', 'هل تبقى «اقرأ أولًا» قائمة كاملة أم تُختصر؟')])
        self.assertEqual([(r['id'], r.get('merged')) for r in rows], [('ideal-Q-search', ['node-visual_reviewer:IMG-014:Q-014-1']),
                         ('node-plan_orderer:plan:Q-cli-split', ['ideal-Q-cli-split']), ('ideal-Q-types', None), ('ideal-Q-reach', None),
                         ('ideal-Q-personal-data', None), ('ideal-Q-read-first', ['node-visual_reviewer:PAGE-015:Q-1'])])
        target = export.decisions({**m, 'target': {'status': 'REVIEW_REQUIRED', 'decisions': [{'id': f'ADR-{i}', 'chosen': 'x'} for i in range(51)]}}, [], 'ar')[0]
        self.assertEqual(([o['id'] for o in target['options']], target['decisions_count']), (['approve', 'changes', 'review'], 51))

    def test_the_inbox_asks_only_what_the_assistant_left_to_the_person_and_each_card_says_what_it_decided(self):
        # The self-audit: 847 of 867 cards waited for the owner; the assistant decides the clear ones itself.
        plan = json.loads((self.out / 'plan.json').read_text(encoding='utf-8'))
        tasks = {t['id']: t for t in plan['tasks']}
        tasks['TASK-2']['resolution'] = {'resolution': 'owner', 'by': 'assistant', 'question': 'Show prices with tax?', 'options': ['Yes', 'No'],
                                         'recommendation': 'Yes', 'why': 'a product choice', 'words': 'decided by your assistant: a product choice'}
        tasks['TASK-6'].update(kind='remediate', resolution={'resolution': 'fix', 'by': 'assistant', 'change': 'Split the handler', 'capped': True,
                                                             'words': 'decided by your assistant: it mattered less'})
        tasks['TASK-6']['decision'] = {**tasks['TASK-6']['decision'], 'kind': 'repair', 'readiness': 'ready'}
        (self.out / 'plan.json').write_text(json.dumps(plan), encoding='utf-8')
        export.export(self.out, 'en', 'shop')
        decisions = self.load('decisions')['decisions']
        self.assertEqual([(d['id'], d['question'], d['recommended_option']) for d in decisions], [('card:TASK-2', 'Show prices with tax?', 'o1')])
        cards = {c['id']: c for c in self.load('cards')['cards']}
        self.assertEqual((cards['TASK-6']['fixable'], cards['TASK-6']['needs_decision'], cards['TASK-6']['resolution']['kind'],
                          cards['TASK-6']['resolution']['change'], cards['TASK-6']['resolution']['capped']), (True, False, 'fix', 'Split the handler', True))
        self.assertEqual((cards['TASK-2']['needs_decision'], cards['TASK-2']['resolution']['options']), (True, ['Yes', 'No']))

    def test_a_section_that_fails_or_records_that_cannot_be_read_are_named_and_never_counted_as_measured(self):
        with mock.patch.object(export.library_section, 'media', side_effect=ValueError('no folder')):
            result = export.export(self.out, 'en', 'shop')
        self.assertEqual(result['errors'], [{'section': 'media', 'error': 'ValueError: no folder'}])
        # the library carries the media's content: without the media it is not written either
        self.assertEqual(result['written'], [n for n in SECTIONS if n != 'media'] + [n for n in SECTIONS_V2 if n != 'library'] + ['coverage'])
        self.assertNotIn('media', {entry['name'] for entry in self.load('manifest')['sections']})
        rows = {row['section']: row for row in self.load('coverage')['sections']}
        self.assertEqual((rows['media']['state'], rows['media']['reason']), ('failed', 'section_error'))
        built = {'cards': [{'id': 'TASK-1'}], 'functions': {'functions': [{'id': 'f'}]}}
        rows = {row['section']: row for row in coverage.coverage(self.out, built, ['cards'], [{'section': 'media', 'error': 'broken'}], 'en')['sections']}
        self.assertEqual([rows[n]['state'] for n in ('cards', 'functions', 'media', 'evidence')], ['measured', 'not_measured', 'failed', 'not_measured'],
                         'built but not written is not measured')
        with mock.patch.object(model, 'records', side_effect=OSError('disk gone')):
            result = export.export(self.out, 'en', 'shop')
        self.assertEqual(result, {'written': [], 'errors': [{'section': 'records', 'error': 'OSError: disk gone'}]})
        self.assertFalse((self.folder / 'manifest.json').exists())
        self.assertEqual(json.loads((self.folder / 'errors.json').read_text(encoding='utf-8')), result['errors'])


class Evidence(unittest.TestCase):
    """A card says why it matters in both languages; a fact carries the code around its line, never a secret."""

    TEXT = 'import a\n\nconst KEY = "sk_live_123"\nfunction f() {\n  return 1\n}\n'

    def source(self, path):
        return {'src/a.ts': self.TEXT, 'bin.dat': 'x\0y'}.get(path)

    def test_the_code_around_a_line_is_written_with_its_numbers_and_a_secret_line_never(self):
        code = evidence.code_excerpt(self.source, 'src/a.ts', 5, 'complexity')
        self.assertEqual(code, {'start': 3, 'line': 5, 'lines': ['const KEY = "sk_live_123"', 'function f() {', '  return 1', '}'], 'hidden': []})
        self.assertEqual(evidence.code_excerpt(self.source, 'src/a.ts', 1, 'complexity')['lines'][0], 'import a')
        self.assertEqual(len(evidence.code_excerpt(lambda path: 'x' * 1000, 'min.js', 1, 'complexity')['lines'][0]), evidence.CODE_WIDTH)
        for args in (('src/a.ts', 3, 'secret'), ('src/a.ts', None, 'complexity'), ('src/a.ts', 99, 'complexity'),
                     ('gone.ts', 1, 'complexity'), ('bin.dat', 1, 'complexity')):
            self.assertIsNone(evidence.code_excerpt(self.source, *args), args)
        code = evidence.code_excerpt(self.source, 'src/a.ts', 4, 'complexity', {('src/a.ts', 3)})
        self.assertEqual(code['hidden'], [3])
        self.assertEqual(code['lines'][code['hidden'][0] - code['start']], '')
        self.assertNotIn('sk_live', ''.join(code['lines']))

    def test_the_evidence_section_hides_secret_lines_and_a_card_says_why_in_both_languages(self):
        facts = [{'id': 'F1', 'kind': 'engine_finding', 'location': {'path': 'src/a.ts', 'line': 4}, 'value': {'kind': 'complexity', 'message': 'complex'}},
                 {'id': 'F2', 'kind': 'engine_finding', 'location': {'path': 'src/a.ts'}, 'value': {'kind': 'secret', 'sites': [{'path': 'src/a.ts', 'line': 3}]}}]
        from eaos.facts.store import write_set
        with tempfile.TemporaryDirectory() as report:
            write_set(report, 'external', 'external', '1', facts, 'sha', [])
            rows = {f['id']: f for f in evidence.evidence(report, {'F1', 'F2'}, self.source)}
        self.assertEqual((rows['F1']['line'], rows['F1']['code']['hidden']), (4, [3]))
        self.assertIsNone(rows['F2']['code'])
        self.assertNotIn('sk_live', json.dumps(rows))
        body = {'schema_version': 1, 'contract': 1, 'facts': list(rows.values())}
        self.assertEqual(artifact_contracts.validate(body, artifact_contracts.contracts()['studio-evidence']), [])
        why = export.why_of({'impact': 'Code nobody runs is still read.', 'impact_render': {'key': 'dead_code', 'params': {}}})['why']
        self.assertEqual(set(why), {'ar', 'en'})
        self.assertRegex(why['ar'], '[؀-ۿ]')
        self.assertEqual(export.why_of({}), {})

    def test_files_are_read_at_the_scanned_commit_and_never_outside_the_project(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / 'p'
            (project / 'src').mkdir(parents=True)
            (Path(folder) / 'outside.txt').write_text('secret', encoding='utf-8')
            (project / 'src/a.ts').write_text('old\n', encoding='utf-8')
            git = lambda *a: subprocess.run(['git', '-C', str(project), *a], check=True, capture_output=True, text=True).stdout.strip()
            git('init', '-q'); git('add', '.'); git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'one')
            commit = git('rev-parse', 'HEAD')
            (project / 'src/a.ts').write_text('new\n', encoding='utf-8')
            self.assertEqual(evidence.sources(project, commit)('src/a.ts'), 'old\n')
            self.assertEqual(evidence.sources(project, None)('src/a.ts'), 'new\n')
            self.assertIsNone(evidence.sources(project, None)('../outside.txt'))
            self.assertIsNone(evidence.sources(None, None)('src/a.ts'))


class Contract(unittest.TestCase):
    def load(self, name):
        return json.loads((FIXTURES / f'{name}.json').read_text(encoding='utf-8'))

    def test_the_small_fixtures_meet_their_contract_and_it_refuses_what_the_studio_must_never_show(self):
        contracts = artifact_contracts.contracts()
        names = sorted(p.stem for p in FIXTURES.glob('*.json'))
        self.assertTrue(names)
        for name in names:
            self.assertEqual(artifact_contracts.validate(self.load(name), contracts[f'studio-{name}']), [], name)
        def broken(name, change):
            data = copy.deepcopy(self.load(name))
            change(data)
            return artifact_contracts.validate(data, contracts[f'studio-{name}'])
        for name, change in (('coverage', lambda d: d['sections'][0].update(state='coming_soon')),
                             ('coverage', lambda d: d['sections'][0].pop('reason')),
                             ('functions', lambda d: d['functions'][0].update(module='/home/me/app/api.ts')),
                             ('functions', lambda d: d['modules'][0].update(id='../outside.ts')),
                             ('gaps', lambda d: d['gaps'][0]['closed'].update(value=1.5)),
                             ('gaps', lambda d: d['gaps'][0].update(operation='modify')),
                             ('history', lambda d: d['scans'][0].update(score=60)),
                             ('screens', lambda d: d['screens'][0]['issues'][0]['box'].update(x=-1)),
                             ('operations', lambda d: d.update(revision=1))):
            with self.subTest(name=name):
                self.assertTrue(broken(name, change))
        rows = {row['section']: row for row in self.load('coverage')['sections']}
        self.assertIsNone(rows['screens']['count']['value'], 'not measured is null, never 0')

    def test_the_synthetic_studio_holds_the_scale_and_every_reference_resolves(self):
        s = studio_synthetic.build(cards=5000, components=1000)
        self.assertEqual((len(s['cards']['cards']), len(s['story']['current']['components']), len(s['gaps']['gaps'])), (5000, 1000, 1000))
        self.assertGreaterEqual(len(s['functions']['functions']), 1000)
        facts = {f['id'] for f in s['evidence']['facts']}
        cards = {c['id'] for c in s['cards']['cards']}
        functions = {f['id'] for f in s['functions']['functions']}
        operations = {o['id'] for o in s['operations']['operations']}
        steps = {step['id'] for plan in s['plans']['plans'] for step in plan['steps']}
        self.assertTrue(all(set(c['evidence']) <= facts for c in s['cards']['cards']))
        self.assertTrue(all(set(f['callers']) | set(f['callees']) <= functions for f in s['functions']['functions']))
        self.assertTrue(all(set(g['operations']) <= operations and set(g['cards']) <= cards for g in s['gaps']['gaps']))
        self.assertTrue(all(o['step'] in steps and set(o['after']) <= operations for o in s['operations']['operations']))
        self.assertTrue(all(set(d['blocks']) <= cards for d in s['decisions']['decisions']))
        self.assertEqual(json.dumps(studio_synthetic.build(cards=50, components=10), sort_keys=True),
                         json.dumps(studio_synthetic.build(cards=50, components=10), sort_keys=True), 'the same seed gives the same folder')

    def test_the_synthetic_studio_is_written_whole_and_meets_the_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(studio_synthetic.write(folder, studio_synthetic.build(cards=50, components=10)), [])
            manifest = json.loads((Path(folder) / 'manifest.json').read_text(encoding='utf-8'))
            for entry in manifest['sections']:
                self.assertEqual(entry['sha256'], hashlib.sha256((Path(folder) / entry['file']).read_bytes()).hexdigest())
            self.assertEqual(manifest['sections'][-1]['name'], 'coverage')


class Localization(unittest.TestCase):
    def test_a_translation_catalog_is_optional_keeps_both_languages_and_a_blank_one_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_folder = Path(tmp)
            (report_folder / 'studio').mkdir()
            self.assertIsNone(publish(report_folder, 'ar'))
            translations = {'en': {'هل تعتمد الخطة؟': 'Do you approve the plan?'}}
            (report_folder / 'studio-translations.json').write_text(json.dumps(translations))
            metadata = publish(report_folder, 'ar')
            catalog = json.loads((report_folder / 'studio/locale.json').read_text())
            self.assertEqual((catalog['source_locale'], catalog['translations']), ('ar', translations))
            self.assertEqual((metadata['en']['file'], len(metadata['en']['sha256'])), ('locale.js', 64))
        with tempfile.TemporaryDirectory() as tmp:
            report_folder = Path(tmp)
            (report_folder / 'studio').mkdir()
            (report_folder / 'studio-translations.json').write_text(json.dumps({'en': {'question': ''}}))
            with self.assertRaises(ValueError):
                publish(report_folder, 'ar')
            self.assertFalse((report_folder / 'studio/locale.js').exists())


if __name__ == '__main__':
    unittest.main()

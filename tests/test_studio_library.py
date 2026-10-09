"""The Library, History and EAOS-quality sections of the Studio's data (NS46.T4): eaos/studio/library.py, history.py,
quality.py, and the packaged quality record (tools/engine_quality.py)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from eaos import artifact_contracts
from eaos.studio import export, history, library, quality
from tests.shared_fixture import Workspace
from tests.test_human_report import report

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import engine_quality  # noqa: E402

PNG = bytes.fromhex('89504e470d0a1a0a0000000d4948445200000001000000010806000000'
                    '1f15c4890000000d49444154789c63000100000500010d0a2db40000000049454e44ae426082')


def write(folder, files):
    for name, body in files.items():
        path = Path(folder) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body) if isinstance(body, bytes) else path.write_text(body, encoding='utf-8')


class Library(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / 'report'
        write(self.out, {
            'README.md': '# Index\n\n| 1 | [START-HERE.md](START-HERE.md) |\n| 2 | [FLOWS.md](FLOWS.md) | then [adr/ADR-001.md](adr/ADR-001.md#context) |\n',
            'START-HERE.md': '# Start here\n\n## What was found\n\n```\n## not a heading\n```\n\n### Next\n',
            'FLOWS.md': f'# Flows\n\nRead from {Path.home()}/projects/shop/src/a.ts\n',
            'adr/ADR-001.md': '# ADR-001\n',
            'engines/mirror/README.md': '# A copy of the project\n',
            'engines/mirror/logo.png': PNG,
            'handover/site/index.md': '# built site\n',
            'architecture/system.mmd': 'flowchart LR\n  a --> b\n',
            'shots/home.png': PNG,
        })

    def test_documents_follow_the_reports_reading_order_and_leave_out_the_engines_copies(self):
        rows = {d['path']: d for d in library.docs(self.out)}
        self.assertEqual(sorted(rows), ['FLOWS.md', 'README.md', 'START-HERE.md', 'adr/ADR-001.md'])
        self.assertLess(rows['START-HERE.md']['order'], rows['FLOWS.md']['order'])
        self.assertLess(rows['FLOWS.md']['order'], rows['adr/ADR-001.md']['order'])
        self.assertEqual(rows['adr/ADR-001.md']['group'], 'adr')
        self.assertEqual(rows['START-HERE.md']['headings'], [{'level': 2, 'text': 'What was found'}, {'level': 3, 'text': 'Next'}],
                         'a line inside a code block is not a heading')

    def test_the_content_travels_with_the_studio_and_the_machines_folders_do_not(self):
        docs, media = library.docs(self.out), library.media(self.out, 'en')
        self.assertEqual([m['id'] for m in media], ['architecture/system.mmd', 'shots/home.png'])
        self.assertEqual(media[0]['title'], 'Map of pages and APIs')
        body = library.library(self.out, docs, media, project=None)
        text = {d['id']: d['text'] for d in body['documents']}
        self.assertIn('~/projects/shop/src/a.ts', text['FLOWS.md'])
        self.assertNotIn(str(Path.home()), text['FLOWS.md'])
        images = {i['id']: i for i in body['images']}
        self.assertEqual(images['architecture/system.mmd']['source'], 'flowchart LR\n  a --> b\n')
        self.assertTrue(images['shots/home.png']['data'].startswith('data:image/png;base64,'))

    def test_what_is_too_large_is_listed_with_the_reason(self):
        old = library.IMAGE_LIMIT
        library.IMAGE_LIMIT = 10
        self.addCleanup(setattr, library, 'IMAGE_LIMIT', old)
        body = library.library(self.out, [], library.media(self.out), project=None)
        shot = next(i for i in body['images'] if i['id'] == 'shots/home.png')
        self.assertEqual((shot['data'], shot['embedded'], shot['reason']), (None, False, 'too_large'))
        self.assertEqual(body['counts']['truncated']['value'], 1)


CARDS = [{'id': 'TASK-1', 'severity': 'high', 'state': 'open'}, {'id': 'TASK-2', 'severity': 'low', 'state': 'done'},
         {'id': 'TASK-3', 'severity': 'low', 'state': 'open'}]
SCAN = {'commit': 'c' * 40, 'branch': 'main', 'at': '2026-10-08T09:00:00+00:00'}


class History(unittest.TestCase):
    def test_without_a_ledger_there_is_one_scan_this_one(self):
        body = history.history(SCAN, 62, CARDS)
        self.assertEqual(len(body['scans']), 1)
        scan = body['scans'][0]
        self.assertEqual((scan['score'], scan['open_total'], scan['open']['high'], scan['open']['low']), (0.62, 2, 1, 1))
        self.assertEqual((body['progress'], body['events'], body['missing']), ([], [], []))

    def test_the_ledger_gives_every_check_the_progress_and_the_events(self):
        ledger = {'history': [
            {'at': '2026-10-01T09:00:00+00:00', 'event': 'baseline', 'closed': 0, 'total': 10, 'commit': 'a' * 40},
            {'at': '2026-10-03T09:00:00+00:00', 'event': 'merged', 'closed': 3, 'total': 10, 'commit': 'b' * 40},
            {'at': '2026-10-08T09:00:00+00:00', 'event': 'recheck', 'closed': 5, 'total': 12, 'commit': 'c' * 40}],
            'cards': [{'key': 'k1', 'id': 'TASK-9', 'title': 'gone', 'state': 'resolved', 'at': '2026-10-08T09:00:00+00:00', 'new': False},
                      {'key': 'k2', 'id': 'TASK-1', 'title': 'fixed', 'state': 'done', 'at': '2026-10-03T09:00:00+00:00', 'new': False, 'batch': 1},
                      {'key': 'k3', 'id': 'TASK-3', 'title': 'appeared', 'state': 'open', 'at': None, 'new': True},
                      {'key': 'k4', 'id': 'TASK-4', 'title': 'still open', 'state': 'open', 'at': None, 'new': False}]}
        waves = [{'number': 1, 'branch': 'eaos/wave-1', 'kept': ['TASK-1', 'TASK-5'], 'merged_at': '2026-10-03T08:59:00+00:00'}]
        body = history.history(SCAN, 70, CARDS, ledger, waves)
        first, last = body['scans']
        self.assertEqual((first['score'], first['open']['high'], first['open_total']), (None, None, 10), 'never guessed')
        self.assertEqual((last['score'], last['open_total'], last['resolved'], last['added']), (0.7, 7, 1, 1))
        self.assertEqual([p['percent'] for p in body['progress']], [0.0, 0.3, 0.4167])
        self.assertEqual([e['kind'] for e in body['events']], ['scan', 'batch', 'merge', 'scan'])
        self.assertEqual(sorted(c['key'] for c in body['cards']), ['k1', 'k2', 'k3'], 'closed or new only')
        self.assertEqual(body['missing'][0]['step'], 'NS31.T1')
        self.assertEqual(body['missing'][0]['count']['value'], 1)

    def test_a_score_the_ledger_recorded_for_an_older_check_is_used(self):
        ledger = {'history': [{'at': '2026-10-01T09:00:00+00:00', 'event': 'baseline', 'closed': 0, 'total': 4, 'commit': 'a' * 40,
                               'scores': {'score': 48, 'open': {'critical': 0, 'high': 2, 'medium': 1, 'low': 1, 'info': 0}}},
                              {'at': '2026-10-08T09:00:00+00:00', 'event': 'recheck', 'closed': 1, 'total': 4, 'commit': 'a' * 40}],
                  'cards': []}
        body = history.history(SCAN, 55, CARDS, ledger)
        self.assertEqual((body['scans'][0]['score'], body['scans'][0]['open']['high']), (0.48, 2))
        self.assertEqual(len({s['id'] for s in body['scans']}), 2, 'two checks at one commit keep two ids')
        self.assertEqual(body['missing'], [])


class Quality(unittest.TestCase):
    RECORD = {'bar': {'precision': 0.8, 'recall': 0.5, 'judged': 5}, 'labelled_items': 10, 'labelled_projects': ['shop-app'],
              'north_star_measured_at': '2026-10-01',
              'detectors': [{'id': 'dead_code', 'name': {'ar': 'كود ميت', 'en': 'Dead code'}, 'status': 'meets_bar', 'shown': True,
                             'why': '', 'judged': 20, 'precision': 0.95, 'recall': 0.9, 'labelled_positives': 8,
                             'projects': {'shop-app': {'tp': 5, 'fp': 1, 'unjudged': 2}}},
                            {'id': 'structural_duplicate', 'name': {'ar': 'تشابه', 'en': 'Same structure'}, 'status': 'below_bar',
                             'shown': False, 'why': 'precision 0.3 < 0.8', 'judged': 10, 'precision': 0.3, 'recall': 1.0, 'projects': {}},
                            {'id': 'trace_gap', 'name': {'ar': 'تتبع', 'en': 'Trace gap'}, 'status': 'not_measured', 'shown': False,
                             'why': 'no labelled class', 'judged': 0, 'precision': None, 'recall': None, 'projects': {}}],
              'capabilities': [{'id': 'C3', 'name': {'ar': 'الإشارة', 'en': 'Signal'},
                                'indicators': [{'id': 'S1', 'name': {'ar': 'س١', 'en': 'Not noise'}, 'value': 0.9, 'target': 0.8, 'measured': 'automated'},
                                               {'id': 'S5', 'name': {'ar': 'س٥', 'en': 'Little noise'}, 'value': None, 'target': 0.9, 'measured': 'automated'}]}]}
    DOSSIER = {'claims': [{'render': {'key': 'dead_code'}}, {'render': {'key': 'dead_code'}}],
               'withheld_claims': [{'render': {'key': 'structural_duplicate'}}]}

    def body(self, name='shop'):
        with tempfile.TemporaryDirectory() as folder:
            return quality.quality(folder, self.DOSSIER, name, 'en', record=self.RECORD)

    def test_each_detector_with_what_it_produced_here(self):
        rows = {d['id']: d for d in self.body()['detectors']}
        self.assertEqual(rows['dead_code']['here'], {'shown': 2, 'withheld': 0, 'facts': 0})
        self.assertEqual(rows['structural_duplicate']['here']['withheld'], 1)
        self.assertEqual([k for k, d in rows.items() if d['applies']], ['dead_code', 'structural_duplicate'])
        self.assertEqual(rows['dead_code']['project'], {'tp': 5, 'fp': 1, 'unjudged': 2}, 'shop matches the labelled shop-app')
        self.assertIsNone(self.body('other')['detectors'][0]['project'])

    def test_what_was_not_measured_is_null_with_its_reason(self):
        body = self.body()
        trace = next(d for d in body['detectors'] if d['id'] == 'trace_gap')
        self.assertIsNone(trace['precision']['value'])
        self.assertIn('no judged output', trace['precision']['src'])
        s5 = next(i for i in body['indicators'] if i['id'] == 'S5')
        self.assertEqual((s5['value']['value'], s5['value']['src']), (None, 'not measured yet'))
        self.assertEqual(body['capabilities'][0]['value']['value'], 0.45, 'an unmeasured indicator counts as 0, as the plan says')
        self.assertEqual((body['counts']['shown_here']['value'], body['counts']['withheld_here']['value']), (2, 1))

    def test_no_record_no_section(self):
        self.assertIsNone(quality.quality('.', {}, 'x', 'en', record={}))


class PackagedRecord(unittest.TestCase):
    def test_the_packaged_record_is_current_and_every_row_has_a_plain_name(self):
        record = engine_quality.build()
        self.assertEqual((ROOT / 'eaos/data/engine-quality.json').read_text(encoding='utf-8'), engine_quality.text(record),
                         'stale: python tools/engine_quality.py')
        self.assertEqual(engine_quality.unnamed(record), [])
        self.assertTrue(record['detectors'] and record['capabilities'])


class Exported(Workspace):
    def test_the_exporter_writes_the_three_sections_and_they_count_as_measured(self):
        out = report(self.tmp)
        (out / 'START-HERE.md').write_text('# Start\n\n## One\n', encoding='utf-8')
        result = export.export(out, 'en', 'shop')
        self.assertEqual(result['errors'], [])
        self.assertTrue({'history', 'quality', 'library'} <= set(result['written']))
        contracts = artifact_contracts.contracts()
        for name in ('history', 'quality', 'library', 'docs'):
            data = json.loads((out / f'studio/{name}.json').read_text(encoding='utf-8'))
            self.assertEqual(artifact_contracts.validate(data, contracts[f'studio-{name}']), [], name)
        lib = json.loads((out / 'studio/library.json').read_text(encoding='utf-8'))
        self.assertEqual([d['id'] for d in lib['documents']], ['START-HERE.md'])
        self.assertTrue((out / 'studio/library.js').is_file())


if __name__ == '__main__':
    unittest.main()

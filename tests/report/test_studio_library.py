"""The Library and History sections of the Studio's data: eaos/report/studio/library.py and history.py."""
import tempfile
import unittest
from pathlib import Path

from eaos.report.studio import history, library

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
            'README.md': '# Index\n\n| 1 | [START-HERE.md](START-HERE.md) |\n| 2 | [RUN.md](RUN.md) | then [adr/ADR-001.md](adr/ADR-001.md#context) |\n',
            'START-HERE.md': '# Start here\n\n## What was found\n\n```\n## not a heading\n```\n\n### Next\n',
            'RUN.md': f'# Run\n\nRead from {Path.home()}/projects/shop/src/a.ts\n',
            'adr/ADR-001.md': '# ADR-001\n',
            'engines/mirror/README.md': '# A copy of the project\n',
            'engines/mirror/logo.png': PNG,
            'architecture/system.mmd': 'flowchart LR\n  a --> b\n',
            'shots/home.png': PNG,
            # An older crawl's Unlighthouse kept 760 such thumbnails in EAOS's own report; the Studio exported them all
            'live/crawl/unlighthouse/reports/__screenshot-thumbnails__/0.jpg': PNG,
        })

    def test_documents_follow_the_reading_order_and_travel_with_the_studio_and_the_machines_folders_and_oversized_images_do_not(self):
        rows = {d['path']: d for d in library.docs(self.out)}
        self.assertEqual(sorted(rows), ['README.md', 'RUN.md', 'START-HERE.md', 'adr/ADR-001.md'], "the engines' copies are left out")
        self.assertLess(rows['START-HERE.md']['order'], rows['RUN.md']['order'])
        self.assertLess(rows['RUN.md']['order'], rows['adr/ADR-001.md']['order'])
        self.assertEqual(rows['adr/ADR-001.md']['group'], 'adr')
        self.assertEqual(rows['START-HERE.md']['headings'], [{'level': 2, 'text': 'What was found'}, {'level': 3, 'text': 'Next'}],
                         'a line inside a code block is not a heading')
        docs, media = library.docs(self.out), library.media(self.out, 'en')
        self.assertEqual([m['id'] for m in media], ['architecture/system.mmd', 'shots/home.png'], "a crawler's thumbnails are left out")
        self.assertEqual(media[0]['title'], 'Map of pages and APIs')
        body = library.library(self.out, docs, media, project=None)
        text = {d['id']: d['text'] for d in body['documents']}
        self.assertIn('~/projects/shop/src/a.ts', text['RUN.md'])
        self.assertNotIn(str(Path.home()), text['RUN.md'])
        images = {i['id']: i for i in body['images']}
        self.assertEqual(images['architecture/system.mmd']['source'], 'flowchart LR\n  a --> b\n')
        self.assertTrue(images['shots/home.png']['data'].startswith('data:image/png;base64,'))
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
    def test_every_check_has_its_score_progress_and_events_from_the_ledger_and_nothing_is_guessed(self):
        body = history.history(SCAN, 62, CARDS)
        self.assertEqual(len(body['scans']), 1, 'without a ledger there is one scan, this one')
        scan = body['scans'][0]
        self.assertEqual((scan['score'], scan['open_total'], scan['open']['high'], scan['open']['low']), (0.62, 2, 1, 1))
        self.assertEqual((body['progress'], body['events'], body['missing']), ([], [], []))
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
        self.assertEqual(sorted(c['key'] for c in body['cards']), ['k2', 'k3'], 'done or new only')
        self.assertEqual(body['missing'][0]['count']['value'], 1)
        ledger = {'history': [{'at': '2026-10-01T09:00:00+00:00', 'event': 'baseline', 'closed': 0, 'total': 4, 'commit': 'a' * 40,
                               'scores': {'score': 48, 'open': {'critical': 0, 'high': 2, 'medium': 1, 'low': 1, 'info': 0}}},
                              {'at': '2026-10-08T09:00:00+00:00', 'event': 'recheck', 'closed': 1, 'total': 4, 'commit': 'a' * 40}],
                  'cards': []}
        body = history.history(SCAN, 55, CARDS, ledger)
        self.assertEqual((body['scans'][0]['score'], body['scans'][0]['open']['high']), (0.48, 2), 'a score the ledger recorded is used')
        self.assertEqual(len({s['id'] for s in body['scans']}), 2, 'two checks at one commit keep two ids')
        self.assertEqual(body['missing'], [])


if __name__ == '__main__':
    unittest.main()

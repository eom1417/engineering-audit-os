"""Visual evidence in the check: the assistant may open the screen pictures and nothing else, each finding names its
picture and a region inside it and becomes a design card; the crawl goes through its pinned tool and says why when it
cannot."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from shared_fixture import TemporaryWorkspace

from eaos.pipeline.run import execute
from eaos.screens import crawl
from eaos.studio.actions import adapters
from eaos.studio.nodes import core

ROOT = Path(__file__).resolve().parents[1]
PNG = bytes.fromhex('89504e470d0a1a0a0000000d4948445200000001000000010806000000'
                    '1f15c4890000000d49444154789c6360000000000300015d0b4b1c0000000049454e44ae426082')


def region(x, y, width, height):
    return {'x': x, 'y': y, 'width': width, 'height': height}


class Reviewer:
    """Sees one crowded header on both pictures of the first page, points the second page's finding at a picture of the
    first, and finds the third page clean."""
    assistant, model, cost_usd = 'Claude Code', 'test-model', None

    def __call__(self, name, prompt, schema):
        ids = schema['properties']['decisions']['items']['properties']['subject']['enum']
        finding = lambda *shows: {'title': 'Crowded header', 'kind': 'crowding', 'severity': 'high', 'why': 'Four buttons share one line',
                                  'shows': [{'picture': picture, 'region': box} for picture, box in shows]}
        rows = [{'subject': ids[0], 'decision': 'cards', 'detail': {'findings': [finding(('IMG-001', region(0, 0, 1, 0.2)),
                                                                                         ('IMG-002', region(0, 0, 1, 0.1)))]}},
                {'subject': ids[1], 'decision': 'cards', 'detail': {'findings': [finding(('IMG-001', region(0, 0, 1, 0.2)))]}},
                {'subject': ids[2], 'decision': 'clean', 'detail': {'findings': []}}]
        return {'summary': '', 'decisions': [{'options': [], 'evidence': [row['subject']], 'confidence': 0.8, 'why': 'seen',
                                              'open_questions': [], **row} for row in rows]}


PICTURED = (('http://127.0.0.1:9/', 'phone'), ('http://127.0.0.1:9/', 'desktop'), ('http://127.0.0.1:9/#/tasks/TASK-001', 'phone'),
            ('http://127.0.0.1:9/#/problems', 'phone'))


class VisualReviewer(TemporaryWorkspace):
    @classmethod
    def setUpClass(cls):
        cls.workspace()
        base = Path(cls.tmp.name)
        target = base / 'shop'
        shutil.copytree(ROOT / 'tests/fixtures/sustainability/redundant', target)
        cls.out = base / 'out'
        shots = cls.out / 'live/screens/screenshots'
        shots.mkdir(parents=True)
        rows = []
        for n, (page, viewport) in enumerate(PICTURED):
            (shots / f'0{n}-{viewport}.png').write_bytes(PNG)
            rows.append({'url': page, 'viewport': viewport, 'variant': 'default', 'failures': [],
                         'axe': {'violations': [{'id': 'color-contrast', 'help': 'Elements must meet contrast'}]},
                         'screenshot': f'live/screens/screenshots/0{n}-{viewport}.png'})
        pages = [{'path': '/', 'template': '/', 'same_as': ['/#/']},
                 {'path': '/#/tasks/TASK-001', 'template': '/#/tasks/:id', 'same_as': ['/#/tasks/TASK-004']}]
        (cls.out / 'live/screens.json').write_text(json.dumps({'rows': rows, 'pages': pages}), encoding='utf-8')
        made = []
        def launcher(adapter, folder, cancel=None, started=None, images=()):
            made.append(list(images))
            return Reviewer()
        with mock.patch.object(core, 'pick', return_value=object()), mock.patch.object(core, 'AdapterLauncher', side_effect=launcher), \
                mock.patch('eaos.pipeline.runners._ran', side_effect=lambda context, name: name in ('screens', 'visual')):
            cls.manifest = execute(target, cls.out, language='en', provider=object(), skip=['semantic', 'triage', 'ideal', 'order', 'pipeline_gaps'])
        cls.images = made

    def test_the_assistant_may_open_exactly_the_pictures(self):
        self.assertEqual(self.manifest['stages']['visual']['status'], 'ok')
        self.assertEqual(sorted(Path(p).name for p in self.images[0]), sorted(p.name for p in (self.out / 'live/screens/screenshots').glob('*.png')))
        argv = adapters.ClaudeCode().ask_argv({}, self.out, self.images[0])
        allowed = argv[argv.index('--allowedTools') + 1:argv.index('--permission-mode')]
        self.assertEqual((argv[argv.index('--tools') + 1], allowed), ('Read', [f'Read(/{p})' for p in self.images[0]]))
        self.assertTrue(all(rule.startswith('Read(//') for rule in allowed))
        self.assertEqual(adapters.ClaudeCode().ask_argv({}, self.out)[-4:-2], ['--tools', ''])

    def test_a_problem_is_one_finding_per_page_with_every_picture_it_shows_on_and_the_gallery_pins_it_to_each(self):
        # The self-check made 1030 findings, one per picture: the same problem on a page's phone and desktop pictures twice
        record = json.loads((self.out / 'nodes/visual_reviewer/last.json').read_text(encoding='utf-8'))
        self.assertEqual([row['why'] for row in record['dropped']], ['a finding names a picture of another page'])
        findings = json.loads((self.out / 'nodes/visual_reviewer/findings.json').read_text(encoding='utf-8'))['findings']
        self.assertEqual([(f['page'], f['viewports'], [p['region'] for p in f['pictures']]) for f in findings],
                         [('http://127.0.0.1:9/', ['phone', 'desktop'], [region(0, 0, 1, 0.2), region(0, 0, 1, 0.1)])])
        plan = json.loads((self.out / 'plan.json').read_text(encoding='utf-8'))
        card = next(t for t in plan['tasks'] if t['id'] == 'TASK-V001')
        self.assertEqual((card['origin'], card['evidence']['images'][0], card['evidence']['region']),
                         ('visual_review', 'live/screens/screenshots/00-phone.png', region(0, 0, 1, 0.2)))
        self.assertEqual(json.loads((self.out / 'cards.json').read_text(encoding='utf-8'))['design'], ['TASK-V001'])
        from eaos.studio.screens import gallery
        pages = {p['path']: p for p in gallery(self.out)}
        self.assertEqual({path: p['state'] for path, p in pages.items()},
                         {'/': 'findings', '/#/tasks/TASK-001': 'not_reviewed', '/#/problems': 'clean'})
        self.assertEqual([(shot['viewport'], [f['region'] for f in shot['findings']]) for shot in pages['/']['pictures']],
                         [('phone', [region(0, 0, 1, 0.2)]), ('desktop', [region(0, 0, 1, 0.1)])])
        self.assertEqual((pages['/#/tasks/TASK-001']['template'], pages['/#/tasks/TASK-001']['same_as']), ('/#/tasks/:id', ['/#/tasks/TASK-004']))
        # The self-check's screens were "not captured" though 54 pictures were taken: they now belong to their screen.
        from eaos.studio import library, screens
        media = library.media(self.out)
        self.assertEqual({i['path']: i['route'] for i in media if i['kind'] == 'screen'}['live/screens/screenshots/00-phone.png'], '/')
        home = screens.screens({'screens': [{'id': 'S-home', 'route': '/', 'kind': 'page'}]}, media, report=self.out)['screens'][0]
        self.assertEqual((len(home['shots']), [i['state'] for i in home['issues']][:1]), (2, ['open']))


class Crawl(unittest.TestCase):
    def test_every_page_is_found_and_lighthouse_measures_the_entry_and_each_distinct_template_ten_at_most(self):
        # Lighthouse ran on all 76 crawled routes of the Studio: 28 minutes, most of them one template with other data
        found = [{'path': '/', 'depth': 0, 'status': 'observed'}, {'path': '/#/broken', 'depth': 1, 'status': 'error'}]
        found += [{'path': f'/#/tasks/TASK-{n:03d}', 'depth': 1, 'status': 'observed'} for n in range(1, 9)]
        found += [{'path': f'/#/page{chr(97 + n)}', 'depth': 1, 'status': 'observed'} for n in range(12)]
        measured = []
        def lighthouse(url, out=None, storage_state=None):
            measured.append(url)
            return {'status': 'observed', 'scores': {'performance': 90}, 'lcp_ms': 900, 'cls': 0, 'report': str(Path(out) / 'lighthouse.json')}
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(crawl, 'discover', return_value=(found, '')), \
                mock.patch.object(crawl, 'lighthouse', side_effect=lighthouse):
            result = crawl.crawl('http://127.0.0.1:9', folder)
        self.assertEqual((result['status'], len(result['routes']), result['templates'], result['measured']), ('observed', 21, 14, 10))
        self.assertEqual(measured[:3], ['http://127.0.0.1:9/', 'http://127.0.0.1:9/#/tasks/TASK-001', 'http://127.0.0.1:9/#/pagea'])
        task = next(r for r in result['routes'] if r['path'] == '/#/tasks/TASK-001')
        self.assertEqual((task['template'], task['measured'], task['report']), ('/#/tasks/:id', True, 'lighthouse/01/lighthouse.json'))
        with mock.patch.object(crawl, 'discover', return_value=(None, 'not installed: playwright')):
            self.assertEqual(crawl.crawl('http://127.0.0.1:9', '/nonexistent')['status'], 'unavailable')

if __name__ == '__main__':
    unittest.main()

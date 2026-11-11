"""The crawl of the check: it goes through its pinned tool and says why when it cannot."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock


from eaos.live.screens import crawl

class Crawl(unittest.TestCase):
    def test_every_page_is_found_and_lighthouse_measures_the_entry_and_each_distinct_template_ten_at_most(self):
        # Lighthouse runs on a sample of routes: routes sharing one template with other data are not all measured.
        found = [{'path': '/', 'depth': 0, 'status': 'observed'}, {'path': '/#/broken', 'depth': 1, 'status': 'error'}]
        found += [{'path': f'/#/tasks/TASK-{n:03d}', 'depth': 1, 'status': 'observed'} for n in range(1, 9)]
        found += [{'path': f'/#/page{chr(97 + n)}', 'depth': 1, 'status': 'observed'} for n in range(12)]
        measured = []
        def lighthouse(url, out=None, storage_state=None):
            measured.append(url)
            return {'status': 'observed', 'scores': {'performance': 90}, 'lcp_ms': 900, 'cls': 0,
                    'report': str(Path(out) / 'lighthouse.json')}
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(crawl, 'discover', return_value=(found, '')), \
                mock.patch.object(crawl, 'lighthouse', side_effect=lighthouse):
            result = crawl.crawl('http://127.0.0.1:9', folder)
        self.assertEqual((result['status'], len(result['routes']), result['templates'], result['measured']),
                         ('observed', 21, 14, 10))
        self.assertEqual(measured[:3], ['http://127.0.0.1:9/', 'http://127.0.0.1:9/#/tasks/TASK-001',
                                        'http://127.0.0.1:9/#/pagea'])
        task = next(r for r in result['routes'] if r['path'] == '/#/tasks/TASK-001')
        self.assertEqual((task['template'], task['measured'], task['report']), ('/#/tasks/:id', True,
            'lighthouse/01/lighthouse.json'))
        with mock.patch.object(crawl, 'discover', return_value=(None, 'not installed: playwright')):
            self.assertEqual(crawl.crawl('http://127.0.0.1:9', '/nonexistent')['status'], 'unavailable')

if __name__ == '__main__':
    unittest.main()

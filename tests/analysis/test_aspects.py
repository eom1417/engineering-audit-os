"""The evidence stages of the program's aspects (eaos/analysis/understanding/aspects.py): the architecture map's digest
(eaos/analysis/maps/code_map.py), the capped journeys (eaos/live/behavior/lock.py) and the suite's health."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import shared_fixture  # noqa: F401  (runs without measured detector verdicts)
from shared_fixture import Workspace


def _write(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record) if not isinstance(record, str) else record)


class Evidence(Workspace):
    def test_the_facts_are_read_into_hotspots_and_clusters(self):
        from eaos.analysis.maps.code_map import digest
        out = Path(self.tmp)
        metric = lambda path, branches, lines: {'kind': 'metric', 'location': {'path': path},
                                                'value': {'scope': 'file', 'branches': branches, 'code_lines': lines}}
        node = lambda path, fan_in, uses: {'kind': 'graph_node', 'location': {'path': path}, 'value': {'fan_in': fan_in, 'depends_on': uses}}
        churn = lambda path, commits: {'kind': 'history_churn', 'location': {'path': path}, 'value': {'commits': commits}}
        _write(out / 'facts/metrics.json', {'facts': [metric('app/main.py', 1, 10), metric('app/prices.py', 8, 40),
                                                     metric('tests/test_prices.py', 30, 90)]})
        _write(out / 'facts/history.json', {'facts': [churn('app/main.py', 1), churn('app/prices.py', 7)]})
        # two tight groups joined by one import; a test file is not part of the map
        shop, mail = ['shop/a.py', 'shop/b.py', 'shop/c.py'], ['mail/a.py', 'mail/b.py', 'mail/c.py']
        uses = {path: [other for other in group if other != path] for group in (shop, mail) for path in group}
        uses['shop/a.py'].append('mail/a.py')
        _write(out / 'facts/graph.json', {'facts': [node(path, 3 if path == 'shop/a.py' else 1, used) for path, used in uses.items()]
                                          + [node('tests/test_shop.py', 0, ['shop/a.py'])]})
        found = digest(out)
        self.assertEqual([h['path'] for h in found['hotspots']], ['app/prices.py', 'app/main.py'])
        self.assertEqual(found['hotspots'][0]['score'], 9 * 7)
        self.assertEqual([(c['files'], c['most_depended_on']) for c in found['clusters']], [(3, 'mail/a.py'), (3, 'shop/a.py')])
        self.assertEqual(sorted(sorted(c['members']) for c in found['clusters']), [sorted(mail), sorted(shop)])
        self.assertGreater(found['modularity'], 0.3)
        # the stage writes it into a report with no architecture folder yet
        from types import SimpleNamespace
        from eaos.pipeline.runners.by_rules import architecture
        self.assertEqual(architecture(SimpleNamespace(out=out)), {'hotspots': 2, 'clusters': 2})
        self.assertEqual(json.loads((out / 'architecture/map.json').read_text())['digest'], found)

    def test_journeys_stay_light_on_disk(self):
        from eaos.live.behavior import lock as behavior_lock
        folder = Path(self.tmp)
        (folder / 'rrweb').mkdir()
        (folder / 'traces').mkdir()
        (folder / 'rrweb/big.rrweb.json').write_bytes(b'x' * 50)
        for n in range(3): (folder / f'rrweb/{n}.rrweb.json').write_bytes(b'x')
        for n in range(2): (folder / f'traces/{n}.zip').write_bytes(b'x')
        with mock.patch.multiple(behavior_lock, RECORDING_BYTES=10, JOURNEYS=2, TRACE_BYTES=10, TRACES=1):
            kept = behavior_lock.cap_journeys(folder)
        self.assertEqual((kept['recordings'], kept['traces']), (['0.rrweb.json', '1.rrweb.json'], ['0.zip']))
        self.assertEqual(sorted(p.name for p in folder.glob('*/*')), ['0.rrweb.json', '0.zip', '1.rrweb.json'])
        self.assertEqual([d['why'] for d in kept['recordings_dropped']], ['more than 2 kept', 'larger than 10 bytes'])


if __name__ == '__main__':
    unittest.main()


class SuiteHealth(unittest.TestCase):
    def test_the_suites_redundant_and_slowest_tests_are_measured_by_coverage_and_the_runners_report(self):
        """The suite's redundant and slowest tests are measured: coverage contexts name a test that runs no line of its
        own, and the runner's report gives each test's time."""
        from eaos.live.testing.verify import COVERAGERC, suite_health
        with tempfile.TemporaryDirectory() as folder:
            app = Path(folder)
            (app / 'price.py').write_text('def price(n):\n    if n > 10:\n        return n * 2\n    return n\n')
            (app / 'test_price.py').write_text(
                'import unittest\nfrom price import price\n\n\nclass T(unittest.TestCase):\n'
                '    def test_small(self):\n        self.assertEqual(price(1), 1)\n\n'
                '    def test_small_again(self):\n        self.assertEqual(price(2), 2)\n\n'
                '    def test_large(self):\n        self.assertEqual(price(11), 22)\n')
            (app / '.eaos-coveragerc').write_text(COVERAGERC)
            run = lambda *argv: subprocess.run([sys.executable, '-m', 'coverage', *argv], cwd=app, capture_output=True, check=True)
            run('run', '--rcfile=.eaos-coveragerc', '-m', 'unittest', 'test_price')
            run('json', '--rcfile=.eaos-coveragerc', '--show-contexts', '-o', 'c.json')
            contexts = {}
            for name, entry in json.loads((app / 'c.json').read_text())['files'].items():
                for line, tests in (entry.get('contexts') or {}).items():
                    for test in tests:
                        if test and name == 'price.py': contexts.setdefault(test, set()).add((name, line))
            (app / '.eaos-junit.xml').write_text('<testsuite><testcase classname="test_price.T" name="test_large" time="7.5"/>'
                                                 '<testcase classname="test_price.T" name="test_small" time="0.01"/></testsuite>')
            health = suite_health(app, contexts)
        self.assertEqual([t.split('.')[-1] for t in health['redundant']], ['test_small', 'test_small_again'])
        self.assertEqual((health['slowest'][0]['test'], health['seconds']), ('test_price.T::test_large', 7.5))

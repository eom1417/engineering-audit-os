"""The report page's experience part (M10.8, console/src/places/report/experience.js) drawn by Node from the
story.json EAOS writes for a small experience run: the personas with their goals reached or stuck, the goal opened with
its steps and pictures, the difficulties ranked with their steps to reproduce and fix card, the time, the tickets and
the replays; the app's texts escaped; a report without the file says how to run it."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from eaos.report.experience.document import write

ROOT = Path(__file__).resolve().parents[2]
PART = ROOT / 'console/src/places/report/experience.js'
ESBUILD = ROOT / 'console/node_modules/esbuild/lib/main.js'
# the part bundled as the build does (a place reaches the core through self.EAOS), with a core that names each word
DRAW = """
import { build } from %(esbuild)s;
const [story, query, file] = JSON.parse(process.argv[1]);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const t = (k, v) => k + (v ? JSON.stringify(v) : '');
const asked = [];
self.EAOS = { t, tn: (k, n) => `${k}(${n})`, num: String, esc, rich: esc, code: s => `<bdi>${esc(s)}</bdi>`, icon: () => '',
  sev: s => `<sev ${s}>`, L: String, href: (p, q) => p + JSON.stringify(q || {}), prefs: { lang: 'en' }, parseHash: () => ({ query }),
  searchTyped() {}, act() {}, offline: () => false, model: {}, normalize: {}, refresh() {},
  data: { reportFile: async p => (asked.push(p), file), tokenImage: async p => (asked.push(p), null) } };
const out = await build({ entryPoints: [%(part)s], bundle: true, write: false, format: 'esm', logLevel: 'silent',
  plugins: [{ name: 'eaos', setup(b) {
    b.onResolve({ filter: /^eaos$/ }, () => ({ path: 'eaos', namespace: 'eaos' }));
    b.onLoad({ filter: /.*/, namespace: 'eaos' }, () => ({ contents: 'module.exports = self.EAOS', loader: 'js' })); } }] });
const part = await import('data:text/javascript,' + encodeURIComponent(out.outputFiles[0].text));
const first = part.experiencePart({ query });
await new Promise(r => setTimeout(r, 10));
console.log(JSON.stringify({ first, then: part.experiencePart({ query }), asked }));
"""


def draw(story, query, file=None):
    script = DRAW % {'esbuild': json.dumps(ESBUILD.as_uri()), 'part': json.dumps(str(PART))}
    done = subprocess.run(['node', '--input-type=module', '-e', 'globalThis.self = globalThis;' + script, json.dumps([story, query, file])],
                          capture_output=True, text=True, timeout=60)
    if done.returncode: raise AssertionError(done.stderr)
    return json.loads(done.stdout)


def records(folder):
    """A small experience run: one persona, a goal reached and a goal stuck, one confirmed difficulty with its card."""
    put = lambda name, body: (folder / name).parent.mkdir(parents=True, exist_ok=True) or (folder / name).write_text(json.dumps(body))
    put('scenario.json', {'personas': [{'id': 'owner', 'name': 'Sara <b>', 'role': 'shop owner', 'about': 'Runs a small shop.'}]})
    put('run.json', {'seconds': 95, 'calls': 12, 'goals': [{'name': 'owner.sign-up', 'persona': 'owner', 'status': 'reached', 'seconds': 40, 'calls': 5},
                                                         {'name': 'owner.add-product', 'persona': 'owner', 'status': 'stuck', 'seconds': 55, 'calls': 7,
                                                          'why': 'No save button'}]})
    put('journeys/owner--add-product.json', {'goal': 'owner.add-product', 'wanted': 'Add a product',
                                             'steps': [{'action': 'click', 'target': {'name': 'Products'}, 'why': 'to find them', 'landed': '/products',
                                                        'picture': 'step-1.png'},
                                                       {'action': 'fill', 'target': {'name': 'Name'}, 'value': '<script>x</script>', 'picture': 'step-2.png',
                                                        'error': 'Server error'}],
                                             'friction': [{'step': 2, 'kind': 'finish', 'note': 'nothing saves'}]})
    put('difficulties.json', {'difficulties': [
        {'id': 'D2', 'goal': 'owner.add-product', 'verdict': 'doubt', 'severity': 'low', 'title': 'Menu hard to find', 'repro': ['Open /']},
        {'id': 'D1', 'goal': 'owner.add-product', 'verdict': 'confirm', 'severity': 'high', 'title': 'A product cannot be saved',
         'fix': 'Add a save button', 'repro': ['Open /products', "Type 'x' into 'Name'"], 'card': 'C-7'},
        {'id': 'D3', 'goal': 'owner.sign-up', 'verdict': 'reject', 'note': 'not real'}]})
    put('tickets.json', {'tickets': [{'id': 'T1', 'goal': 'owner.add-product', 'asked': 'How do I save?', 'answer': 'Press Enter', 'after': 'stuck', 'escalated': True}]})
    put('replays.json', {'summary': {'green': 1, 'red': 1}, 'replays': [{'goal': 'owner.sign-up', 'status': 'red', 'error': 'button moved'}]})
    put('data.json', {})


@unittest.skipUnless(shutil.which('node') and ESBUILD.is_file(), 'Node.js or the console build tool is not installed')
class ExperiencePart(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.report = Path(self.tmp.name)
        records(self.report / 'experience')
        self.story = json.loads(write(self.report, 'en')[1].read_text(encoding='utf-8'))

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_story_is_drawn_with_the_opened_goal_its_pictures_and_the_ranked_difficulties(self):
        got = draw(self.story, {'part': 'experience', 'goal': 'owner.add-product'}, json.dumps(self.story))
        view = got['then']
        self.assertIn('rp.ex.reading', got['first'], 'experience/story.json is read once, then drawn')
        self.assertEqual(got['asked'][0], 'experience/story.json')
        self.assertIn('rp.ex.reached{&quot;n&quot;:&quot;1&quot;,&quot;all&quot;:&quot;2&quot;}', view)
        self.assertIn('Sara &lt;b&gt;', view)
        self.assertIn('rp.ex.status.reached', view)
        self.assertIn('rp.ex.status.stuck', view)
        self.assertIn('&lt;script&gt;x&lt;/script&gt;', view)
        self.assertNotIn('<script>', view)
        self.assertIn('/api/report-image?path=' + 'experience%2Fjourneys%2Fowner--add-product%2Fstep-2.png', got['asked'])
        self.assertIn('Server error', view)
        self.assertIn('nothing saves', view)
        self.assertLess(view.index('A product cannot be saved'), view.index('Menu hard to find'), 'confirmed before doubted')
        self.assertNotIn('not real', view, 'a rejected difficulty is not among the ranked')
        self.assertIn('/problems/C-7', view)
        self.assertIn('Open /products', view)
        self.assertIn('How do I save?', view)
        self.assertIn('rp.ex.green.n{&quot;n&quot;:&quot;1&quot;}', view)
        self.assertIn('button moved', view)

    def test_a_closed_goal_reads_no_picture_and_a_report_without_the_file_says_how_to_run_it(self):
        got = draw(self.story, {'part': 'experience'}, json.dumps(self.story))
        self.assertFalse([p for p in got['asked'] if 'report-image' in p])
        self.assertNotIn('Server error', got['then'])
        missing = draw(None, {'part': 'experience'})   # the route answered 404: no file
        self.assertIn('rp.ex.reading', missing['first'])
        self.assertIn('eaos check --path experience', missing['then'])
        self.assertIn('<bdi>experience</bdi>', missing['then'])


if __name__ == '__main__':
    unittest.main()

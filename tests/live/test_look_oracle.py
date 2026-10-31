"""The style oracle on a real browser (M18.7): a value moved into a token changes nothing, and a 1px border, a colour off by one and a hover colour under a transition are all found."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from eaos.core import toolchain
from eaos.live.behavior.look_oracle import compare, judged

LOOK = Path(__file__).resolve().parents[2] / 'eaos' / 'templates' / 'screens' / 'look.cjs'
PAGE = """<!doctype html><style>{tokens}
.card{{background:{card};border:{border} solid #dddddd;padding:16px}}
.btn{{background:#1a73e8;color:#fff;transition:background .2s ease}}
.btn:hover{{background:{hover}}}
.card::before{{content:'';color:#333333}}
</style><div class=card><button class=btn>Save</button><p>text</p></div>"""
PLAIN = dict(tokens='', card='#f5f5f5', border='1px', hover='#1558b0')
DRIVER = """
const {{ chromium }} = require({playwright});
const {{ snapshot }} = require({look});
(async () => {{
  const browser = await chromium.launch();
  const page = await (await browser.newContext()).newPage();
  for (const [name, html] of Object.entries(JSON.parse(process.argv[2]))) {{
    await page.setContent(html);
    require('fs').writeFileSync(`${{process.argv[3]}}/${{name}}.json`, JSON.stringify(await snapshot(page)));
  }}
  await browser.close();
}})();
"""


class StyleOracle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        package = toolchain.home() / 'node' / 'node_modules' / 'playwright'
        if not package.is_dir() or not shutil.which('node'): raise unittest.SkipTest('the pinned Playwright is not installed')
        pages = {'plain': PLAIN, 'token': {**PLAIN, 'tokens': ':root{--card:#f5f5f5}', 'card': 'var(--card)'}, 'colour': {**PLAIN, 'card': '#f5f5f6'},
                 'border': {**PLAIN, 'border': '2px'}, 'hover': {**PLAIN, 'hover': '#1558b1'}}
        script = Path(cls.tmp.name) / 'driver.cjs'
        script.write_text(DRIVER.format(playwright=json.dumps(str(package)), look=json.dumps(str(LOOK))), encoding='utf-8')
        done = subprocess.run(['node', str(script), json.dumps({name: PAGE.format(**page) for name, page in pages.items()}), cls.tmp.name],
                              capture_output=True, text=True, timeout=120, env={'PATH': shutil.os.environ['PATH'], 'PLAYWRIGHT_BROWSERS_PATH': str(toolchain.browsers())})
        if done.returncode: raise unittest.SkipTest(done.stderr[-300:])

    def saved(self, name):
        return json.loads((Path(self.tmp.name) / f'{name}.json').read_text(encoding='utf-8'))

    def changes(self, name, allowed=None):
        return compare(self.saved('plain'), self.saved(name), allowed)

    def test_a_value_moved_into_a_token_changes_nothing(self):
        self.assertEqual(self.changes('token'), [])

    def test_one_colour_off_by_one_is_found(self):
        self.assertTrue(any(row['property'] == 'background-color' and row['to'] == 'rgb(245, 245, 246)' for row in self.changes('colour')))

    def test_a_1px_border_is_found(self):
        self.assertTrue(any(row['property'] == 'border-top-width' for row in self.changes('border')))

    def test_a_hover_colour_under_a_transition_is_found(self):
        self.assertEqual({(row['state'], row['property']) for row in self.changes('hover')}, {('hover', 'background-color')})

    def test_a_declared_change_passes_and_only_it(self):
        allowed = [{'property': None, 'from': 'rgb(245, 245, 245)', 'to': 'rgb(245, 245, 246)'}]
        self.assertEqual(self.changes('colour', allowed), [])
        self.assertTrue(self.changes('border', allowed))

    def test_a_page_with_no_second_reading_or_no_recording_proves_nothing(self):
        empty = Path(self.tmp.name) / 'empty'
        empty.mkdir(exist_ok=True)
        self.assertIn('nothing recorded', judged(empty, self.tmp.name))
        only = Path(self.tmp.name) / 'only'
        only.mkdir(exist_ok=True)
        shutil.copyfile(Path(self.tmp.name) / 'plain.json', only / 'plain.json')
        self.assertIn('not read again', judged(only, empty))


if __name__ == '__main__':
    unittest.main()

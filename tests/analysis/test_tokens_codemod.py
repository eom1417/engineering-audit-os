"""Raw values to tokens (M18.18): every way a value is written is named once, what must stay stays, and an agreed merge moves one value to another."""
import tempfile
import unittest
from pathlib import Path

from eaos.analysis.design import tokens_codemod as codemod

CSS = """/* the card #000000 */
.card { color: #222; background: #fff; padding: 8px 12px; border-radius: 4px; box-shadow: 0 1px 2px rgba(0,0,0,.2); margin: 0 }
a:hover { color: #222222 }
.x { border: 1px solid #ddd; width: 300px; color: var(--kept); }
@media (max-width: 600px) { .y { padding: 8px } }
"""
JSX = """export const A = () => <div style={{color: '#fff', padding: '8px', width: '300px'}} className="bg-[#123456] p-[8px] text-[14px] rounded-[4px] w-[300px]">x</div>;
const B = styled.div`color: #222; font-size: 14px;`;
"""


class TokensCodemod(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def files(self, **named):
        for name, text in named.items():
            path = self.root / name.replace('__', '/').replace('_css', '.css').replace('_tsx', '.tsx').replace('_html', '.html')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        return [str(p.relative_to(self.root)) for p in self.root.rglob('*') if p.is_file()]

    def test_a_stylesheet_is_named_and_what_is_not_a_value_of_the_look_stays(self):
        drawn = codemod.plan(self.root, self.files(src__app_css=CSS))
        text = drawn['files']['src/app.css']
        self.assertIn('/* the card #000000 */', text)
        self.assertIn('width: 300px', text)
        self.assertIn('var(--kept)', text)
        self.assertNotIn('#222', text.split('*/')[1])
        self.assertEqual(sum(value == '#222222' for value in drawn['tokens'].values()), 1, '#222 and #222222 are one value')
        self.assertIn('margin: 0', text)
        self.assertTrue(text.startswith('@import "./tokens.css";'))
        self.assertEqual(drawn['home'], 'src/tokens.css')
        self.assertIn('0 1px 2px rgba(0,0,0,.2)', drawn['tokens'].values())

    def test_inline_styles_css_in_js_and_tailwind_are_named_and_a_measure_stays(self):
        names = self.files(src__A_tsx=JSX, src__app_css='body{margin:0}')
        text = codemod.plan(self.root, names)['files']['src/A.tsx']
        self.assertRegex(text, r"color: 'var\(--color-text-\d\)'")
        self.assertIn("width: '300px'", text)
        self.assertRegex(text, r'bg-\[var\(--color-surface-\d\)\]')
        self.assertRegex(text, r'text-\[length:var\(--font-size-\d\)\]')
        self.assertIn('w-[300px]', text)
        self.assertRegex(text, r'color: var\(--color-text-\d\); font-size: var')

    def test_a_merge_the_person_agreed_to_names_both_values_one_token(self):
        drawn = codemod.plan(self.root, self.files(a_css='.a{color:#111111}.b{color:#121212}'), [{'from': '#121212', 'to': '#111111'}])
        self.assertEqual(list(drawn['tokens'].values()), ['#111111'])

    def test_a_page_with_its_own_style_block_holds_the_tokens_and_nothing_written_is_refused(self):
        drawn = codemod.plan(self.root, self.files(index_html='<style>body{color:#111}</style>'))
        self.assertEqual(drawn['home'], 'index.html')
        self.assertIn(':root {', drawn['files']['index.html'])
        (self.root / 'index.html').write_text('<p>nothing</p>')
        self.assertIn('no value', codemod.plan(self.root, ['index.html'])['refused'])

    def test_css_in_js_with_no_stylesheet_loads_its_tokens_from_the_page(self):
        names = self.files(src__index_html='<html><head><title>x</title></head><body></body></html>', src__A_tsx=JSX)
        drawn = codemod.plan(self.root, names)
        self.assertEqual(drawn['home'], 'src/index.html')
        self.assertIn('<style>:root {', drawn['files']['src/index.html'])

    def test_apply_writes_the_files_and_the_tokens_file_and_a_data_folder_is_left(self):
        names = self.files(src__app_css='.a{color:#111}', dist__x_css='.a{color:#222}', tests__fixtures__a_css='.a{color:#333}')
        written = codemod.apply(self.root, codemod.plan(self.root, names))
        self.assertEqual(sorted(written), ['src/app.css', 'src/tokens.css'])
        self.assertIn('#111111', (self.root / 'src/tokens.css').read_text())
        self.assertIn('#222', (self.root / 'dist/x.css').read_text())


if __name__ == '__main__':
    unittest.main()

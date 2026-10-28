"""One source per pattern read from the source (M15): the look written outside its tokens file, and element trees
repeated across screens, whatever writes them (JSX, a Vue template, a template string)."""
import unittest

from eaos.facts.duplication import element_trees, look

MODAL = ('<div className="fixed inset-0 bg-black/50"><div className="modal rounded-lg p-6"><h2 className="title">{t}</h2>'
         '<p className="body">{b}</p><div className="actions"><button className="btn">OK</button><button className="btn ghost">'
         'Cancel</button></div></div></div>')


def _trees(files):
    rows = []
    for path, text in files.items():
        language = 'tsx' if path.endswith('.tsx') else 'javascript' if path.endswith('.js') else 'vue'
        rows += element_trees.candidates(path, element_trees.file_trees(text, path, language))
    return element_trees.repeated(rows)


class TheLook(unittest.TestCase):
    def test_a_value_outside_the_tokens_file_is_counted_wherever_it_is_written(self):
        css = '.card { color: #1a2b3c; padding: 12px 0; margin: var(--s2); border-radius: 6px; z-index: 30; }\n' \
              '.wide { width: calc(100% - 12px); font-size: var(--fs-body); box-shadow: none }'
        self.assertEqual(look.values('src/app.css', css, None),
                         [('color', '#1a2b3c', 1), ('spacing', '12px', 1), ('radius', '6px', 1), ('z_index', '30', 1)])
        jsx = ('const A = () => <p className="text-[13px] bg-[#ff0000] p-4 z-[60]" style={{ marginTop: 8, color: "red" }}>'
               '<span style="padding:3px">x</span></p>;\nconst brand = "#2a49c8";')
        self.assertEqual(sorted((k, v) for k, v, _ in look.values('src/A.tsx', jsx, 'tsx')),
                         [('color', '#2a49c8'), ('color', '#ff0000'), ('color', 'red'), ('font_size', '13px'), ('spacing', '3px'),
                          ('spacing', '8px'), ('z_index', '60')])

    def test_the_tokens_file_is_the_home_never_counted(self):
        tokens = ':root {' + ''.join(f' --c{i}: #00000{i};' for i in range(8)) + ' }\n.x { color: #123456 }'
        self.assertTrue(look.is_tokens_file('src/styles/main.css', tokens))
        self.assertEqual(look.values('src/styles/main.css', tokens, None), [])
        self.assertEqual(look.values('tailwind.config.js', "colors: { brand: '#2a49c8' }", 'javascript'), [])


class ElementTrees(unittest.TestCase):
    def test_a_pop_up_written_in_three_screens_is_one_pattern_with_every_place(self):
        own = {'Orders': '<table><tr><td/></tr></table>', 'Users': '<ul><li/><li/></ul>', 'Billing': '<form><input/><select/></form>'}
        files = {f'src/pages/{name}.tsx': f'export const {name} = () => (<main><h1>{name}</h1>{body}{MODAL}</main>);'
                 for name, body in own.items()}
        found = _trees(files)
        self.assertEqual(len(found), 1)
        self.assertEqual(sorted(m['path'] for m in found[0]['members']), sorted(files))
        self.assertEqual((found[0]['members'][0]['tag'], found[0]['similarity'] >= 0.8), ('div', True))

    def test_the_same_tree_in_html_a_vue_template_and_a_template_string_is_found_alike(self):
        html = MODAL.replace('className', 'class').replace('{t}', 'x').replace('{b}', 'y')
        files = {'src/a.js': f'el.innerHTML = `{html}`;', 'src/B.vue': f'<template>{html}</template>', 'src/c.js': f'render(`<section>{html}</section>`)'}
        self.assertEqual(len(_trees(files)), 1)

    def test_primitives_alike_on_purpose_and_a_twice_written_tree_stay_unfound(self):
        primitives = {f'src/components/ui/{name}.tsx': f'export const {name} = () => {MODAL};' for name in ('Dialog', 'Sheet', 'Drawer')}
        self.assertEqual(_trees(primitives), [])
        twice = {f'src/pages/{name}.tsx': f'export const {name} = () => {MODAL};' for name in ('Orders', 'Users')}
        self.assertEqual(_trees(twice), [])
        # Three trees made of the project's own components are composition, not a copy.
        composed = '<Card><CardHeader><CardTitle>x</CardTitle></CardHeader><CardContent><Table/></CardContent></Card>'
        self.assertEqual(_trees({f'src/p{i}.tsx': f'export const P = () => {composed};' for i in range(3)}), [])


if __name__ == '__main__':
    unittest.main()

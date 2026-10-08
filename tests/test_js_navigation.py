"""The links a front end writes from one screen to another are navigation facts (eaos/facts/frameworks/js_navigation.py)."""
import unittest

from eaos.facts.entrypoints import Context
from eaos.facts.frameworks import js_navigation


def links(rel, text):
    return [(line, row['via'], row['target'], row['dynamic'], row['relative'])
            for _offset, line, row in js_navigation.detect(Context(rel, text, 'tsx', []))]


class NavigationTests(unittest.TestCase):
    def test_links_redirects_and_calls_are_read_with_their_line(self):
        text = ('import { Link, Navigate, useNavigate } from "react-router-dom";\n'
                'export function Page() {\n'
                '  const navigate = useNavigate();\n'
                '  if (!user) return <Navigate to="/login" replace />;\n'
                '  return <div><Link to="/app/drivers/new">New</Link>\n'
                '    <button onClick={() => navigate(`/app/drivers/${d.id}/edit`)}>Edit</button>\n'
                '    <a href="/terms">Terms</a><a href="https://example.com">out</a></div>;\n'
                '}\n')
        self.assertEqual(links('src/pages/Drivers.tsx', text),
                         [(4, 'redirect', '/login', False, False), (5, 'link', '/app/drivers/new', False, False),
                          (6, 'navigate', '/app/drivers/:param/edit', True, False), (7, 'link', '/terms', False, False)])

    def test_a_commented_out_link_is_not_a_link(self):
        # Found on FleetManageWeb: the Predictions menu entry is commented out; the screen is not in the menu.
        text = ('export const items = [\n  { title: "Drivers", url: "/app/drivers" },\n'
                '  /* { title: "Predictions", url: "/app/maintenance/predictions" }, */\n'
                '  // { title: "Old", url: "/app/old" },\n];\n')
        self.assertEqual(links('src/components/sidebar/navigationItems.ts', text), [(2, 'menu', '/app/drivers', False, False)])

    def test_object_entries_are_menu_links_only_in_navigation_files(self):
        text = 'const api = { url: "/Auth/login" };\n'
        self.assertEqual(links('src/lib/Api.ts', text), [])

    def test_a_query_is_dropped_and_a_relative_target_is_marked(self):
        text = 'navigate("/login?mode=signup");\n<Navigate to="account" replace />\nnavigate({ to: "/reports" });\n'
        self.assertEqual(links('src/App.tsx', text),
                         [(1, 'navigate', '/login', False, False), (2, 'redirect', 'account', False, True),
                          (3, 'navigate', '/reports', False, False)])

    def test_a_target_held_in_a_variable_or_another_site_is_not_guessed(self):
        text = 'navigate(next);\nnavigate(`${base}/x`);\nwindow.location.href = "mailto:a@b.c";\n<Link to="#top" />\n'
        self.assertEqual(links('src/App.tsx', text), [])


class EntryPointsTests(unittest.TestCase):
    def test_the_entrypoints_run_writes_navigation_facts_beside_the_routes(self):
        import tempfile
        from pathlib import Path
        from eaos.facts import entrypoints
        from eaos.facts.source import Source
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'src').mkdir()
            (root / 'src/App.tsx').write_text('import { Routes, Route, Link } from "react-router-dom";\n'
                                              '<Routes><Route path="/a" element={<A />} /></Routes>\n<Link to="/a">A</Link>\n')
            out = entrypoints.run(root, Source(root), symbols=[])
        kinds = sorted(f['kind'] for f in out['facts'])
        self.assertEqual(kinds, ['entry_point', 'navigation'])
        self.assertEqual((out['summary']['navigation'], out['summary']['entry_points']), (1, 1))
        [link] = [f for f in out['facts'] if f['kind'] == 'navigation']
        self.assertEqual((link['location']['path'], link['location']['start_line'], link['value']['target']), ('src/App.tsx', 3, '/a'))


if __name__ == '__main__':
    unittest.main()

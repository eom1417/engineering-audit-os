"""The links a front end writes from one screen to another are navigation facts (eaos/facts/frameworks/js_navigation.py)."""
import tempfile
import unittest
from pathlib import Path

from eaos.facts.code.entrypoints import Context
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
                '}\n'
                'navigate("/login?mode=signup");\n<Navigate to="account" replace />\nnavigate({ to: "/reports" });\n')
        self.assertEqual(links('src/pages/Drivers.tsx', text),
                         [(4, 'redirect', '/login', False, False), (5, 'link', '/app/drivers/new', False, False),
                          (6, 'navigate', '/app/drivers/:param/edit', True, False), (7, 'link', '/terms', False, False),
                          (9, 'navigate', '/login', False, False), (10, 'redirect', 'account', False, True),
                          (11, 'navigate', '/reports', False, False)])

    def test_commented_out_variable_and_non_menu_targets_are_not_guessed(self):
        # Found on FleetManageWeb: the Predictions menu entry is commented out; the screen is not in the menu.
        menu = ('export const items = [\n  { title: "Drivers", url: "/app/drivers" },\n'
                '  /* { title: "Predictions", url: "/app/maintenance/predictions" }, */\n'
                '  // { title: "Old", url: "/app/old" },\n];\n')
        self.assertEqual(links('src/components/sidebar/navigationItems.ts', menu), [(2, 'menu', '/app/drivers', False, False)])
        self.assertEqual(links('src/lib/Api.ts', 'const api = { url: "/Auth/login" };\n'), [],
                         'object entries are menu links only in navigation files')
        # EAOS's Studio: its sections and its tabs are lists of { to } drawn as links, in sections.ts and SystemViews.tsx
        self.assertEqual(links('src/shell/sections.ts', "export const SECTIONS = [\n  { id: 'history', to: '/history' },\n];\n"),
                         [(2, 'menu', '/history', False, False)], 'the router\'s own word `to` is a link in any file')
        self.assertEqual(links('src/App.tsx', 'navigate(next);\nnavigate(`${base}/x`);\n'
                                              'window.location.href = "mailto:a@b.c";\n<Link to="#top" />\n'), [])

    def test_the_entrypoints_run_writes_navigation_facts_beside_the_routes(self):
        from eaos.facts.code import entrypoints
        from eaos.facts.source import Source
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'src').mkdir()
            (root / 'src/App.tsx').write_text('import { Routes, Route, Link } from "react-router-dom";\n'
                                              '<Routes><Route path="/a" element={<A />} /></Routes>\n<Link to="/a">A</Link>\n')
            out = entrypoints.run(root, Source(root), symbols=[])
        self.assertEqual(sorted(f['kind'] for f in out['facts']), ['entry_point', 'navigation'])
        self.assertEqual((out['summary']['navigation'], out['summary']['entry_points']), (1, 1))
        [link] = [f for f in out['facts'] if f['kind'] == 'navigation']
        self.assertEqual((link['location']['path'], link['location']['start_line'], link['value']['target']), ('src/App.tsx', 3, '/a'))

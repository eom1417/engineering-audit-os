"""User-facing routes of React Router, TanStack Router and Next.js apps are entry points."""
import unittest

from eaos.facts.entrypoints import Context
from eaos.facts.frameworks import js_routes


def detect(rel, text):
    return js_routes.detect(Context(rel, text, 'tsx', []))


class ReactRouterTests(unittest.TestCase):
    def test_each_jsx_route_with_a_path_is_a_page_handled_by_its_element(self):
        text = ('import { Routes, Route } from "react-router-dom";\n'
                '<Routes>\n  <Route path="/" element={<Home />} />\n  <Route path="/vehicles/:id" element={<Vehicle />} />\n'
                '  <Route index element={<Index />} />\n</Routes>\n')
        rows = detect('src/App.tsx', text)
        self.assertEqual([(r['surface'], r['route'], r['handler']) for r in rows],
                         [('page', '/', 'Home'), ('page', '/vehicles/:id', 'Vehicle')])

    def test_object_routes_are_read_when_the_file_builds_a_router(self):
        text = ('import { createBrowserRouter } from "react-router-dom";\n'
                'const router = createBrowserRouter([{ path: "/drivers", element: <Drivers /> }]);\n')
        self.assertEqual([r['route'] for r in detect('src/router.tsx', text)], ['/drivers'])

    def test_a_route_without_react_router_is_not_invented(self):
        self.assertEqual(detect('src/App.tsx', '<Route path="/x" element={<X />} />'), [])


class NestedReactRouterTests(unittest.TestCase):
    """Found on FleetManageWeb: 37 screens under <Route path="/app/*"> were reported at /drivers, /service…, where a
    person never finds them; the links of the app all point at /app/…."""
    APP = ('import { Routes, Route, Navigate } from "react-router-dom";\n'
           '<Routes>\n'
           '  <Route path="/login" element={<Login />} />\n'
           '  <Route path="/app/*" element={\n'
           '    <Layout title="Can\'t stop">\n'
           '      <Routes>\n'
           '        <Route path="/" element={<Dashboard />} />\n'
           '        <Route path="/drivers/:id" element={<Driver />} />\n'
           '        <Route path="/settings" element={<Settings />}>\n'
           '          <Route index element={<Navigate to="account" replace />} />\n'
           '          <Route path="account" element={<Account />} />\n'
           '        </Route>\n'
           '        <Route path="*" element={<NotFound />} />\n'
           '      </Routes>\n'
           '    </Layout>\n'
           '  } />\n'
           '  <Route path="*" element={<NotFound />} />\n'
           '</Routes>\n')

    def test_a_route_of_a_descendant_routes_is_joined_to_its_parent_path(self):
        rows = detect('src/App.tsx', self.APP)
        self.assertEqual([(r['route'], r['handler']) for r in rows],
                         [('/login', 'Login'), ('/app/*', 'Layout'), ('/app', 'Dashboard'), ('/app/drivers/:id', 'Driver'),
                          ('/app/settings', 'Settings'), ('/app/settings/account', 'Account'), ('/app/*', 'NotFound'),
                          ('*', 'NotFound')])

    def test_the_path_as_written_is_kept_when_it_differs(self):
        rows = {r['handler']: r for r in detect('src/App.tsx', self.APP)}
        self.assertEqual((rows['Account'].get('declared'), rows['Login'].get('declared')), ('account', None))

    def test_an_absolute_child_already_under_its_parent_is_not_joined_twice(self):
        text = ('import { Routes, Route } from "react-router-dom";\n'
                '<Route path="/admin" element={<Admin />}>\n  <Route path="/admin/users" element={<Users />} />\n</Route>\n')
        self.assertEqual([r['route'] for r in detect('src/App.tsx', text)], ['/admin', '/admin/users'])


class TanStackTests(unittest.TestCase):
    def test_a_file_route_is_a_page_with_its_component(self):
        text = ('import { createFileRoute } from "@tanstack/react-router";\n'
                'export const Route = createFileRoute("/auth")({ component: AuthPage });\n')
        [row] = detect('src/routes/auth.tsx', text)
        self.assertEqual((row['surface'], row['route'], row['handler']), ('page', '/auth', 'AuthPage'))

    def test_server_handlers_on_a_file_route_are_http_surfaces(self):
        text = ('import { createFileRoute } from "@tanstack/react-router";\n'
                'export const Route = createFileRoute("/api/hooks/run")({ server: { handlers: { POST: run } } });\n')
        self.assertEqual([(r['surface'], r['http_method']) for r in detect('src/routes/api/hooks/run.ts', text)],
                         [('http', 'POST')])


class NextTests(unittest.TestCase):
    def test_app_router_pages_are_routes(self):
        [row] = detect('app/dashboard/page.tsx', 'export default function Dashboard() { return null }')
        self.assertEqual((row['route'], row['handler']), ('/dashboard', 'Dashboard'))

    def test_a_vite_app_pages_folder_is_not_next_routing(self):
        # Found on the corpus: 47 screens under src/pages/ of a Vite app were reported as Next.js routes.
        self.assertEqual(detect('src/pages/Vehicles.tsx', 'export default function Vehicles() { return null }'), [])

    def test_a_pages_file_that_uses_next_is_a_route(self):
        text = 'import Link from "next/link";\nexport default function About() { return null }\n'
        self.assertEqual([r['route'] for r in detect('pages/about.tsx', text)], ['/about'])


if __name__ == '__main__':
    unittest.main()

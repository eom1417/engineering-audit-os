"""User-facing routes of React Router, TanStack Router and Next.js apps are entry points."""
import unittest

from eaos.facts.entrypoints import Context
from eaos.facts.frameworks import js_routes


def detect(rel, text):
    return js_routes.detect(Context(rel, text, 'tsx', []))


class ReactRouterTests(unittest.TestCase):
    def test_jsx_and_object_routes_are_pages_only_under_react_router(self):
        text = ('import { Routes, Route } from "react-router-dom";\n'
                '<Routes>\n  <Route path="/" element={<Home />} />\n  <Route path="/vehicles/:id" element={<Vehicle />} />\n'
                '  <Route index element={<Index />} />\n</Routes>\n')
        self.assertEqual([(r['surface'], r['route'], r['handler']) for r in detect('src/App.tsx', text)],
                         [('page', '/', 'Home'), ('page', '/vehicles/:id', 'Vehicle')])
        router = ('import { createBrowserRouter } from "react-router-dom";\n'
                  'const router = createBrowserRouter([{ path: "/drivers", element: <Drivers /> }]);\n')
        self.assertEqual([r['route'] for r in detect('src/router.tsx', router)], ['/drivers'])
        self.assertEqual(detect('src/App.tsx', '<Route path="/x" element={<X />} />'), [], 'no route without react-router')

    def test_nested_routes_are_joined_to_their_parent_path(self):
        # Found on FleetManageWeb: 37 screens under <Route path="/app/*"> were reported at /drivers, /service…
        app = ('import { Routes, Route, Navigate } from "react-router-dom";\n'
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
        rows = detect('src/App.tsx', app)
        self.assertEqual([(r['route'], r['handler']) for r in rows],
                         [('/login', 'Login'), ('/app/*', 'Layout'), ('/app', 'Dashboard'), ('/app/drivers/:id', 'Driver'),
                          ('/app/settings', 'Settings'), ('/app/settings/account', 'Account'), ('/app/*', 'NotFound'),
                          ('*', 'NotFound')])
        by_handler = {r['handler']: r for r in rows}
        self.assertEqual((by_handler['Account'].get('declared'), by_handler['Login'].get('declared')), ('account', None))
        # An absolute child already under its parent is not joined twice.
        text = ('import { Routes, Route } from "react-router-dom";\n'
                '<Route path="/admin" element={<Admin />}>\n  <Route path="/admin/users" element={<Users />} />\n</Route>\n')
        self.assertEqual([r['route'] for r in detect('src/App.tsx', text)], ['/admin', '/admin/users'])


class OtherRouterTests(unittest.TestCase):
    def test_tanstack_file_routes_are_pages_and_their_server_handlers_are_http(self):
        page = ('import { createFileRoute } from "@tanstack/react-router";\n'
                'export const Route = createFileRoute("/auth")({ component: AuthPage });\n')
        [row] = detect('src/routes/auth.tsx', page)
        self.assertEqual((row['surface'], row['route'], row['handler']), ('page', '/auth', 'AuthPage'))
        server = ('import { createFileRoute } from "@tanstack/react-router";\n'
                  'export const Route = createFileRoute("/api/hooks/run")({ server: { handlers: { POST: run } } });\n')
        self.assertEqual([(r['surface'], r['http_method']) for r in detect('src/routes/api/hooks/run.ts', server)],
                         [('http', 'POST')])

    def test_next_pages_are_routes_but_a_vite_pages_folder_is_not(self):
        [row] = detect('app/dashboard/page.tsx', 'export default function Dashboard() { return null }')
        self.assertEqual((row['route'], row['handler']), ('/dashboard', 'Dashboard'))
        # Found on the corpus: 47 screens under src/pages/ of a Vite app were reported as Next.js routes.
        self.assertEqual(detect('src/pages/Vehicles.tsx', 'export default function Vehicles() { return null }'), [])
        text = 'import Link from "next/link";\nexport default function About() { return null }\n'
        self.assertEqual([r['route'] for r in detect('pages/about.tsx', text)], ['/about'])

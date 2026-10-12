"""The app's own HTTP back end, seen through the client it calls it with."""
import unittest

from eaos.facts.frameworks import http_access

API = 'import axios from "axios";\nexport const api = axios.create({ baseURL: import.meta.env.VITE_API_URL });\n'
USER = ('import { api } from "@/lib/Api";\nconst DRIVERS_ENDPOINT = "/drivers";\n'
        'export const list = () => api.get<Op[]>("/operators");\n'
        'export const one = (id) => api.put(`/operators/${id}`, {});\n'
        'export const drivers = () => api.post(DRIVERS_ENDPOINT);\n'
        'export const other = () => cache.get("/operators");\n'
        'export const vin = () => axios.get("https://vpic.nhtsa.dot.gov/api/x");\n'
        'export const ask = () => fetch(`${API_URL}/ai/ask`, { method: "POST" });\n')


class HttpAccessTests(unittest.TestCase):
    def test_calls_through_the_apps_own_client_are_endpoints_with_their_method(self):
        names = http_access.prepare({'src/lib/Api.ts': API, 'src/lib/operatorsApi.ts': USER})
        self.assertEqual(names['src/lib/operatorsApi.ts'], {'api'}, 'an axios.create client is followed into its importers')
        found = [(r['operation'], r['target']) for _, _, r in http_access.extract_calls(USER, names['src/lib/operatorsApi.ts'])]
        # Another object with a get method and a third-party host are not the app's back end.
        self.assertEqual(sorted(found), sorted([('get', '/operators'), ('put', '/operators/{}'), ('post', '/drivers'),
                                                ('post', '/ai/ask')]))

    def test_a_browser_call_through_a_client_named_api_is_not_a_server_route(self):
        from types import SimpleNamespace
        from eaos.facts.frameworks import js_web
        def routes(text):
            context = SimpleNamespace(text=text, rel='src/x.ts', line_of=lambda i: text[:i].count('\n') + 1, symbol_at=lambda line: None)
            return [(r['http_method'], r['route']) for r in js_web.detect(context)]
        self.assertEqual(routes(USER), [])
        self.assertEqual(routes('import { Hono } from "hono";\nconst api = new Hono();\napi.get("/health", health);\n'), [('GET', '/health')])
        self.assertEqual(routes('app.get("/x", handler);\n'), [('GET', '/x')])

    def test_a_write_records_the_keys_it_sends_never_the_values(self):
        found = {(r['operation'], r['target']): r for _, _, r in http_access.extract_calls(
            'const api = axios.create({});\n'
            "api.post('/documents', { name, file: f, 'vin': v, nested: { a: 1 }, ...rest });\n"
            'api.patch("/x", {\n  status: "done",\n  notes,\n});\n'
            "fetch(`${API}/ai/ask`, { method: 'POST', body: JSON.stringify({ question, history: h }) });\n"
            'api.put(`/vehicles/${id}`, payload);\napi.get("/vehicles", { params: { page } });\n')}
        self.assertEqual((found[('post', '/documents')]['keys'], found[('post', '/documents')]['keys_partial']),
                         (['file', 'name', 'nested', 'vin'], True))
        self.assertEqual(found[('patch', '/x')]['keys'], ['notes', 'status'])
        self.assertEqual(found[('post', '/ai/ask')]['keys'], ['history', 'question'])
        # A variable payload and a read have no keys rather than none.
        self.assertNotIn('keys', found[('put', '/vehicles/{}')])
        self.assertNotIn('keys', found[('get', '/vehicles')])

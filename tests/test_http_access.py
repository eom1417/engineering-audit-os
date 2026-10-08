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
    def calls(self):
        names = http_access.prepare({'src/lib/Api.ts': API, 'src/lib/operatorsApi.ts': USER})
        return [r for _, _, r in http_access.extract_calls(USER, names['src/lib/operatorsApi.ts'])]

    def test_a_client_made_by_axios_create_is_followed_into_the_files_that_import_it(self):
        self.assertEqual(http_access.prepare({'src/lib/Api.ts': API, 'src/lib/operatorsApi.ts': USER})['src/lib/operatorsApi.ts'], {'api'})

    def test_each_call_is_an_endpoint_with_its_method(self):
        found = {(r['operation'], r['target']) for r in self.calls()}
        self.assertEqual(found, {('get', '/operators'), ('put', '/operators/{}'), ('post', '/drivers'), ('post', '/ai/ask')})

    def test_another_object_with_a_get_method_and_a_third_party_host_are_not_the_app_back_end(self):
        targets = [r['target'] for r in self.calls()]
        self.assertEqual(targets.count('/operators'), 1)
        self.assertFalse(any('nhtsa' in t for t in targets))


    def test_a_browser_call_through_a_client_named_api_is_not_a_server_route(self):
        from types import SimpleNamespace
        from eaos.facts.frameworks import js_web
        def routes(text):
            context = SimpleNamespace(text=text, rel='src/x.ts', line_of=lambda i: text[:i].count('\n') + 1, symbol_at=lambda line: None)
            return [(r['http_method'], r['route']) for r in js_web.detect(context)]
        self.assertEqual(routes(USER), [])
        self.assertEqual(routes('import { Hono } from "hono";\nconst api = new Hono();\napi.get("/health", health);\n'), [('GET', '/health')])
        self.assertEqual(routes('app.get("/x", handler);\n'), [('GET', '/x')])


class PayloadKeyTests(unittest.TestCase):
    """The request keys of a write: the names of the object literal it sends, never the values."""
    def calls(self, text):
        return {(r['operation'], r['target']): r for _, _, r in http_access.extract_calls('const api = axios.create({});\n' + text)}

    def test_an_object_literal_payload_gives_its_keys_and_a_spread_marks_them_partial(self):
        found = self.calls("api.post('/documents', { name, file: f, 'vin': v, nested: { a: 1 }, ...rest });\n")
        self.assertEqual((found[('post', '/documents')]['keys'], found[('post', '/documents')]['keys_partial']),
                         (['file', 'name', 'nested', 'vin'], True))

    def test_a_payload_across_lines_and_a_fetch_body_are_read(self):
        found = self.calls('api.patch("/x", {\n  status: "done",\n  notes,\n});\n'
                           "fetch(`${API}/ai/ask`, { method: 'POST', body: JSON.stringify({ question, history: h }) });\n")
        self.assertEqual(found[('patch', '/x')]['keys'], ['notes', 'status'])
        self.assertEqual(found[('post', '/ai/ask')]['keys'], ['history', 'question'])

    def test_a_variable_payload_and_a_read_have_no_keys_rather_than_none(self):
        found = self.calls('api.put(`/vehicles/${id}`, payload);\napi.get("/vehicles", { params: { page } });\n')
        self.assertNotIn('keys', found[('put', '/vehicles/{}')])
        self.assertNotIn('keys', found[('get', '/vehicles')])


if __name__ == '__main__':
    unittest.main()

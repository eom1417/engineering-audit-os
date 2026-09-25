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


if __name__ == '__main__':
    unittest.main()

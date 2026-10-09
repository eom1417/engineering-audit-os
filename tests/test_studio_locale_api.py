"""Live report translations use the same protected API boundary as report data."""
import json
import tempfile
import unittest
from pathlib import Path
from tests.test_studio_api import client, report_with_data


class LocaleReadTests(unittest.TestCase):
    def test_catalog_requires_the_launch_token_and_keeps_its_language_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = report_with_data(tmp)
            catalog = {'schema_version': 1, 'source_locale': 'ar', 'translations': {'en': {'نعم': 'Yes'}}}
            (Path(report) / 'studio/locale.json').write_text(json.dumps(catalog))
            http, keys, _ = client(report)
            with http:
                self.assertEqual(http.get('/api/locales/en').status_code, 401)
                response = http.get('/api/locales/en', headers={'X-EAOS-Token': keys.token})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), catalog)
                self.assertEqual(http.get('/api/locales/ar', headers={'X-EAOS-Token': keys.token}).status_code, 404)

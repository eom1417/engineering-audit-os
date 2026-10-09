"""A locale catalog changes presentation, not the source report's decision identities."""
import json
import tempfile
import unittest
from pathlib import Path
from eaos.studio.localization import publish


class ReportLocaleTests(unittest.TestCase):
    def test_publish_is_optional_and_keeps_both_language_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp)
            (report / 'studio').mkdir()
            self.assertIsNone(publish(report, 'ar'))
            translations = {'en': {'هل تعتمد الخطة؟': 'Do you approve the plan?'}}
            (report / 'studio-translations.json').write_text(json.dumps(translations))
            metadata = publish(report, 'ar')
            catalog = json.loads((report / 'studio/locale.json').read_text())
            self.assertEqual(catalog['source_locale'], 'ar')
            self.assertEqual(catalog['translations'], translations)
            self.assertEqual(metadata['en']['file'], 'locale.js')
            self.assertEqual(len(metadata['en']['sha256']), 64)

    def test_empty_translation_is_refused_instead_of_publishing_blank_report_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp)
            (report / 'studio').mkdir()
            (report / 'studio-translations.json').write_text(json.dumps({'en': {'question': ''}}))
            with self.assertRaises(ValueError):
                publish(report, 'ar')
            self.assertFalse((report / 'studio/locale.js').exists())

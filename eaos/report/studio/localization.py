"""Publish the reviewed report-prose translations separately from code and evidence identities.

A producer supplies studio-translations.json: {"en": {"source text": "English text"}}.
The catalog is optional for older reports. Its manifest marker lets the Studio load it
before presenting the report in English, without changing any decision or finding ID.
"""
import hashlib
import json
import re
from pathlib import Path


def publish(report, source_locale):
    report = Path(report)
    source = report / 'studio-translations.json'
    if not source.exists():
        return None
    translations = json.loads(source.read_text(encoding='utf-8'))
    if not isinstance(translations, dict) or not isinstance(translations.get('en'), dict):
        raise ValueError('Report translations must provide an English text catalog')
    if any(not isinstance(k, str) or not isinstance(v, str) or not v.strip()
           for k, v in translations['en'].items()):
        raise ValueError('Each English translation must be a nonempty string')
    if any(re.search(r'[\u0600-\u06ff]', value) for value in translations['en'].values()):
        raise ValueError('English translations must not contain Arabic prose')
    body = {'schema_version': 1, 'source_locale': source_locale, 'translations': translations}
    text = json.dumps(body, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    folder = report / 'studio'
    for filename, content in [('locale.json', text + '\n'), ('locale.js', 'window.EAOS_LOCALE=' + text + ';\n')]:
        temporary = folder / (filename + '.tmp')
        temporary.write_text(content, encoding='utf-8')
        temporary.replace(folder / filename)
    return {'en': {'file': 'locale.js', 'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()}}

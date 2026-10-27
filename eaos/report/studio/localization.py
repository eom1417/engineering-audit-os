"""The report's own texts in the other language (studio/locale.json), so the Studio shows them in the person's language.

A check writes its texts in its language; the translation stage translated every document (eaos/core/language/
bilingual.py) and kept each translation in the report's memory. The texts the Studio shows as they were written (each
card's title) are looked up there, with no model asked: a card's title as its plan document's heading reads it, or, for
a title EAOS words itself, its words in the other language. A text the memory lacks stays as written.
"""
import hashlib
import json
import re

from ...analysis.planning.documents import title_of
from ...core.language import bilingual

ARABIC = re.compile(r'[\u0600-\u06ff]')


def catalog(report, plan, cards, source_locale):
    """{other language: {a card's title as written: its translation}}, empty when nothing is translated."""
    other = 'en' if source_locale == 'ar' else 'ar'
    memory, tasks = bilingual.memory_of(report), _tasks(plan)
    out = {}
    for card in cards:
        translated = _title(card, tasks.get(card['id']), memory, other)
        if _sound(translated, card['title'], other): out[card['title']] = translated
    return {other: out} if out else {}


def _tasks(plan):
    return {t.get('id'): t for t in plan.get('tasks') or [] if isinstance(t, dict)}


def _title(card, task, memory, lang):
    """A card's title in `lang`: EAOS's own words for it, else its plan document's heading as translated."""
    return title_of(task, lang) if task and task.get('render') else _heading(card, memory, lang)


def _heading(card, memory, lang):
    """A card's title in `lang` as its plan document's heading (`<id>: <title>`) was translated."""
    prefix = f"{card['id']}: "
    heading = bilingual.in_language(prefix + card['title'], memory, lang)
    return heading[len(prefix):] if heading and heading.startswith(prefix) else None


def _sound(text, written, lang):
    """A translation worth keeping: something other than the text as written, and in `lang` (English holds no Arabic
    prose, Arabic holds some)."""
    if not text or not text.strip() or text == written: return False
    return not ARABIC.search(text) if lang == 'en' else bool(ARABIC.search(text))


def publish(folder, source_locale, translations):
    """Write studio/locale.json (and .js) when there is anything translated; the manifest's `locales` entry, or None
    (and an earlier check's files removed)."""
    if not translations:
        for filename in ('locale.json', 'locale.js'): (folder / filename).unlink(missing_ok=True)
        return None
    body = {'schema_version': 1, 'source_locale': source_locale, 'translations': translations}
    text = json.dumps(body, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    for filename, content in [('locale.json', text + '\n'), ('locale.js', 'window.EAOS_LOCALE=' + text + ';\n')]:
        temporary = folder / (filename + '.tmp')
        temporary.write_text(content, encoding='utf-8')
        temporary.replace(folder / filename)
    return {lang: {'file': 'locale.js', 'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()} for lang in translations}

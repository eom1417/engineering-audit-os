"""Whether what an assistant wrote for the person is in the person's language.

Every prompt asks for it, and the assistants do not always keep it (EAOS on itself, 2026-10-13: two design titles and
the run messages in English in an Arabic Studio). So the texts meant for the person are checked after the answer, and
the ones in another language go back to the assistant once, to be written again in the person's language, with the
rest of the answer kept as it is. Ids, paths and code names are never texts for the person.
"""
import json
import re

ARABIC = re.compile('[؀-ۿ]')
WORD = re.compile(r'\b[A-Za-z]{2,}\b')
FOR_THE_PERSON = frozenset({'title', 'why', 'summary', 'question', 'recommendation', 'words', 'text', 'label', 'reason',
                            'change', 'plan', 'answer', 'message', 'what_now', 'statement', 'detail_text'})
NAMES = {'ar': 'Arabic (plain, Gulf-friendly)', 'en': 'English'}


def foreign(text, lang):
    """True when `text` is a sentence (four words or more) the person does not read: no Arabic letter in an Arabic
    Studio. An English Studio reads every text EAOS's assistants write."""
    return lang == 'ar' and isinstance(text, str) and not ARABIC.search(text) and len(WORD.findall(text)) >= 4


def foreign_texts(answer, lang):
    """The texts for the person in an answer (a JSON value), by their keys, that are not in the person's language."""
    found = []

    def walk(value, key=None):
        if isinstance(value, dict):
            for name, inner in value.items(): walk(inner, name)
        elif isinstance(value, list):
            for inner in value: walk(inner, key)
        elif key in FOR_THE_PERSON and foreign(value, lang) and value not in found:
            found.append(value)
    walk(answer)
    return found


def restate(answer, texts, lang):
    """The question that sends an answer back to be written again in the person's language, everything else kept."""
    return (f'Your answer below has texts for the person that are not in {NAMES[lang]}, the only language they read. '
            'Return the same JSON object, unchanged in every id, path, number, choice and decision, with these texts, and '
            f'any other text for the person, written in {NAMES[lang]} (ids, paths and code names inside them stay as they '
            'are):\n' + json.dumps(texts, ensure_ascii=False) + '\n\nYour answer:\n' + json.dumps(answer, ensure_ascii=False))

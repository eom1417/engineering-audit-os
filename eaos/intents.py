"""From what a person says to the EAOS command that does it (eaos/data/intents.json).

A request is normalised the way people actually type Arabic (hamza forms, taa marbuta, alef maqsura, diacritics
and tatweel all collapse; case and punctuation go), then matched phrase by phrase as whole words. The longest
phrase found wins, so "افحص جهازي" (check my computer) is the readiness check, not the project scan that
"افحص" alone would be. No match is an honest answer: the person is asked to say it differently.
"""
import json
import re
from pathlib import Path

INTENTS = Path(__file__).resolve().parent / 'data/intents.json'
_ARABIC = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ة': 'ه', 'ى': 'ي', 'ؤ': 'و', 'ئ': 'ي', 'ـ': ''})
_MARKS = re.compile('[ً-ٰٟ]')


def normalise(text):
    text = _MARKS.sub('', str(text)).translate(_ARABIC).lower().replace("'", '').replace('’', '')
    return ' '.join(re.sub(r'[^\w\s]', ' ', text).split())


def catalog():
    return json.loads(INTENTS.read_text(encoding='utf-8'))['intents']


PREFIXES = ('وال', 'بال', 'فال', 'كال', 'لل', 'ال', 'و', 'ف', 'ب', 'ل')
SUFFIXES = ('ها', 'هم', 'كم', 'نا', 'ه', 'ي', 'ك')
THRESHOLD = 3


def forms(word):
    """A word and what is left of it without the Arabic prefixes and suffixes people attach to it."""
    found = {word}
    for prefix in PREFIXES:
        if word.startswith(prefix) and len(word) - len(prefix) >= 3: found.add(word[len(prefix):])
    for base in list(found):
        for suffix in SUFFIXES:
            if base.endswith(suffix) and len(base) - len(suffix) >= 3: found.add(base[:-len(suffix)])
    return found


def _by_phrase(text, intents):
    """(length, intent, phrase) of the longest phrase found whole in the text (the first of equals), or None."""
    found = [(len(wanted), intent, phrase) for intent in intents for phrase in intent['ar'] + intent['en']
             if (wanted := normalise(phrase)) and f' {wanted} ' in text]
    return max(found, key=lambda row: row[0], default=None)


def _score(words, intent):
    """How strongly the words, in any of their forms, name the intent's keywords."""
    keywords = {normalise(k): v for k, v in (intent.get('keywords') or {}).items()}
    return sum(max((keywords.get(f, 0) for f in word), default=0) for word in words)


def _by_keywords(text, intents):
    """The intent the words score highest, when it reaches the threshold alone; else None."""
    words = [forms(word) for word in text.split()]
    scores = sorted(((_score(words, intent), intent) for intent in intents), key=lambda row: -row[0])
    clear = scores and scores[0][0] >= THRESHOLD and (len(scores) == 1 or scores[1][0] != scores[0][0])
    return scores[0][1] if clear else None


def understand(request):
    """(intent, how) for a request in plain words, or (None, None). A whole phrase wins, the longest first;
    otherwise the words are scored against each intent's keywords, and only a clear winner counts."""
    text = f' {normalise(request)} '
    intents = catalog()
    phrase = _by_phrase(text, intents)
    if phrase: return phrase[1], phrase[2]
    intent = _by_keywords(text, intents)
    return (intent, 'keywords') if intent else (None, None)


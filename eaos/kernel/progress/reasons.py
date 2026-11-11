"""The person's words for each `reason_code` a stage or a step ends with, in Arabic and English.

The texts live in eaos/data/errors.json -> reasons, beside the plain errors (the one catalog of what a person reads
when something did not happen). A code the catalog does not know gives None: the reader then shows the sentence EAOS
wrote itself, never an empty place.
"""
from functools import lru_cache
from ..system.files import read_json
from eaos import HOME

CATALOG = HOME / 'data/errors.json'


@lru_cache(maxsize=1)
def reasons():
    """{code: {'ar': text, 'en': text}} from the catalog; {} when it cannot be read."""
    return dict(read_json(CATALOG, {}).get('reasons') or {})


def reason_text(code, language='ar'):
    """The text of `code` in `language` (ar or en), or None for an unknown code."""
    texts = reasons().get(str(code or ''))
    if not texts: return None
    return texts.get(language) or texts.get('en')

"""EAOS's own translation memory (eaos/data/translation-memory.json): the templates every project's report shares,
translated once, reviewed and shipped, so no check spends anything on EAOS's own sentences.

    python tools/translation_seed.py todo <report> <report> ... > todo.json
    python tools/translation_seed.py merge translated.json

`todo`: the reports are of different projects, in either language; a template met in two of them is EAOS's (a project's
own words are met in one), and those the seed has no translation for are printed, {lang: [template, ...]}. Translate
them with the strongest model at hand and review them (the slots ⟦n⟧ kept, EAOS's terms in bilingual.TERMS), as
{lang: {template: translation}}; `merge` keeps the sound ones (bilingual's own test of an answer) in the seed.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eaos.core import bilingual  # noqa: E402


def _shipped():
    return json.loads(bilingual.SEED.read_text(encoding='utf-8')) if bilingual.SEED.is_file() else {}


def _met(reports):
    """How many of the reports each (language, template) is met in."""
    return Counter(pair for report in reports for pair in {
        (lang, bilingual.template(piece)[0]) for path, _ in bilingual.documents(report)
        for lang in bilingual.LANGS for piece in bilingual.pieces_to_send(path.read_text(encoding='utf-8', errors='replace'), lang)})


def todo(reports):
    met = _met(reports)
    shipped = _shipped()
    return {lang: sorted(source for (one, source), count in met.items()
                         if one == lang and count > 1 and source not in shipped.get(lang, {})) for lang in bilingual.LANGS}


def merge(translated):
    shipped = {lang: dict(entries) for lang, entries in _shipped().items()}
    for lang, entries in translated.items():
        shipped.setdefault(lang, {})
        bilingual.keep(shipped, [(lang, source) for source in entries], list(entries.values()))
        shipped[lang] = dict(sorted(shipped[lang].items()))
    bilingual.SEED.write_text(json.dumps(shipped, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return {lang: len(entries) for lang, entries in shipped.items()}


if __name__ == '__main__':
    if sys.argv[1] == 'todo': print(json.dumps(todo(sys.argv[2:]), ensure_ascii=False, indent=1))
    else: print(merge(json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))))

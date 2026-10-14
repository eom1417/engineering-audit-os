"""EAOS's own translation memory (eaos/data/translation-memory.json), from a check's: the templates every project's
report shares, translated once and shipped, so a first check spends nothing on EAOS's own sentences.

    python tools/translation_seed.py <the report folder of a check, translated>

A template is EAOS's when it has a slot (a sentence EAOS writes with numbers, paths or names in it) or is met in more
than one place of the report; one met once, without a slot, is that project's own words and stays out. What the seed
already holds is kept, a new translation of the same template wins.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eaos import bilingual  # noqa: E402


def seed(report):
    report = Path(report)
    memory = json.loads((report.parent / bilingual.MEMORY).read_text(encoding='utf-8'))
    met = Counter((lang, bilingual.template(piece)[0]) for path, _ in bilingual.documents(report)
                  for lang in bilingual.LANGS for piece in bilingual.pieces_to_send(path.read_text(encoding='utf-8'), lang))
    shipped = json.loads(bilingual.SEED.read_text(encoding='utf-8')) if bilingual.SEED.is_file() else {}
    for lang, entries in memory.items():
        kept = {source: answer for source, answer in entries.items() if bilingual.SLOT.search(source) or met[(lang, source)] > 1}
        shipped[lang] = dict(sorted({**shipped.get(lang, {}), **kept}.items()))
    bilingual.SEED.write_text(json.dumps(shipped, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return {lang: len(entries) for lang, entries in shipped.items()}


if __name__ == '__main__':
    print(seed(sys.argv[1]))

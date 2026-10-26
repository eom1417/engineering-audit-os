"""Every document of the report in both languages (report/i18n/ar/, report/i18n/en/), so the Studio shows each one
whole in the person's language and switches with it.

The documents are written by many hands (EAOS's own sentences, the engines' messages, the assistant's words) and come
out mixed. Translating what is written is small, and kept small this way (EAOS's own check, 2026-10-14: 2818 lines,
24 calls, 54 minutes, $2.19, 77% of the output the model's thinking):
- The unit is a whole piece: a heading, a list item, a paragraph with its wrapped lines joined (a line cut mid
  sentence translates badly), or one table cell. Only the pieces in the wrong language are sent; fenced code, rule
  lines, command lines, and a piece in the right language stay as written.
- Every number, path, code span, link target, id, package version and identifier (snake_case or camelCase) becomes a numbered slot (⟦1⟧) before
  sending and is put back after, so it is never altered, and two pieces that differ only by them share one template:
  the 2818 lines became 633 templates.
- A translation memory keeps every template once translated: EAOS's own (eaos/data/translation-memory.json: what the
  reports of different projects share, translated once by a strong model and reviewed, tools/translation_seed.py),
  then the report's (translation-memory.json beside it), so the next check sends only what is new.
- The rest, the project's own words, goes in batches of BATCH characters to the smallest model of the assistant the
  person already uses (no other account or key), without thinking, keyed item by item, told the
  terms EAOS uses (its labels in eaos/core/language/words.py and TERMS). An answer whose slots are not exactly the template's,
  or still in the wrong language, is asked once more, then left as written.
"""
import json
import shutil
import re
import contextvars
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .words import LABELS

LANGS = ('ar', 'en')
NAMES = {'ar': 'Arabic (Modern Standard, plain)', 'en': 'English'}
BATCH = 16000        # characters a call: fewer calls, each one's fixed start counted fewer times
WORKERS = 3          # batches asked at once: each call spends most of its time starting the assistant
ROUNDS = 2           # an answer that came back unsound is asked once more
MEMORY = 'translation-memory.json'
SEED = Path(__file__).resolve().parents[2] / 'data' / MEMORY
ARABIC = re.compile('[؀-ۿ]')
LATIN_WORD = re.compile(r'\b[A-Za-z][a-z]{2,}\b')
ARABIC_WORD = re.compile('[؀-ۿ]{2,}')
UNSENT = re.compile(r'`[^`]*`|\]\([^)]*\)|https?://\S+|\b[\w.-]+/[\w./-]+|\b\w+\.(?:py|ts|tsx|js|json|md|mjs|css)\b')
TOKEN = (UNSENT.pattern + r'|\b[\w./-]+@[\w.^~<>=*-]+|(?<!\S)/\S+|\b\w+\.(?:sh|toml|ya?ml|txt|html|cfg|ini|lock)\b|\b\w+(?:\.\w+){2,}'
         r'|\b[\w-]*\d[\w-]*%?|\b\w*_\w+\b|\b[A-Za-z][a-z]+[A-Z][A-Za-z]*\b')
KEPT = re.compile(f'(?:{TOKEN})(?:, (?:{TOKEN}))*')     # a list of them is one slot: "facts: A, B" and "facts: A, B, C" share one
COMMAND = re.compile(r'(?:\$ )?\.?(?:(?:npm|npx|pnpm|yarn|python3?|pip|git|eaos|bash|node|uv)\s|⟦\d+⟧ -)')     # a command line
PROSE = re.compile(r'[A-Za-z]{2,} [A-Za-z]{2,} [A-Za-z]{2,}')    # three words in a row: a sentence, not a list of names
SLOT = re.compile('⟦(\\d+)⟧')
LEAD = re.compile(r'\s*(?:#{1,6}\s+|[-*+]\s+(?:\[[ xX]\]\s+)?|\d+[.)]\s+|>\s*)*')
CELL = re.compile(r'(?<!\\)\|')
RULE = re.compile(r'^\s*\|?\s*:?-{3,}')
FENCE = re.compile(r'^\s*(```|~~~)')
SKIP = ('studio/', 'engines/', 'i18n/')
TERMS = {'ar': {'probe': 'مجسّ', 'claim': 'ادعاء', 'falsifier': 'دليل النقض', 'evidence': 'دليل', 'card': 'بطاقة',
                'check': 'فحص', 'audit': 'فحص', 'fix': 'إصلاح', 'batch': 'دفعة', 'gate': 'بوابة', 'layer': 'طبقة',
                'component': 'مكوّن', 'dead code': 'كود ميت', 'acceptance check': 'فحص الاستلام', 'assistant': 'المساعد',
                'Studio': 'الاستوديو', 'candidate repository': 'النسخة المعزولة', 'command': 'أمر', 'plan': 'خطة',
                'migration': 'الترحيل', 'commit': 'حفظ في git', 'retain': 'يبقى كما هو', 'live claim': 'ادعاء قائم',
                'threshold': 'الحد المسموح', 'module': 'وحدة', 'repository': 'المستودع'}}
TASK = ('Translate each item of `items` into {lang}, in plain words a non-developer reads easily. Each item is a whole '
        'heading, list item, paragraph or table cell. Keep Markdown exactly (**, links, backticks). Every slot like ⟦1⟧ '
        'stands for a number, path, code or name: copy each one unchanged, exactly once, where the sentence needs it. '
        'Keep tool and product names, and commands, as written; a lone word in a table cell is often a name in the code '
        '(a function, command, folder or table: get, measure, handover, orders): keep it as written when it reads as one. '
        'Use these terms: {terms}. Return {{"items": {{...}}}}: every key of `items` with its item translated, and '
        'nothing else.')


def wrong(text, lang):
    """Whether a text is written, beyond its code, paths and names, in the other language than `lang`."""
    if not text.strip() or RULE.match(text): return False
    prose = UNSENT.sub(' ', SLOT.sub(' ', text))
    if lang == 'en': return bool(ARABIC.search(prose))
    english, arabic = len(LATIN_WORD.findall(prose)), len(ARABIC_WORD.findall(prose))
    return english >= 1 and (arabic == 0 or english >= 3 and english > arabic)


def _segments(text):
    """The document as runs of lines: [kind, line, ...], kind 'row' for a table row, 'prose' for a heading, list item
    or paragraph with the lines that continue it, 'kept' for code, rules and blank lines."""
    out, fenced = [], False
    for line in text.split('\n'):
        if FENCE.match(line): fenced = not fenced; out.append(['kept', line])
        elif fenced or not line.strip() or RULE.match(line): out.append(['kept', line])
        elif line.lstrip().startswith('|'): out.append(['row', line])
        elif _continues(out, line): out[-1].append(line)
        else: out.append(['prose', line])
    return out


def _continues(out, line):
    """Whether a line carries on the paragraph or list item before it: no lead of its own, after prose, not a heading."""
    return out and out[-1][0] == 'prose' and not LEAD.match(line).group().strip() and not out[-1][1].lstrip().startswith('#')


def rewrite(text, change):
    """The document with each piece (a heading, list item or whole paragraph, a table cell) replaced by change(piece)
    where that is not None; the lines of an unchanged piece stay exactly as written."""
    out = []
    for kind, *lines in _segments(text):
        if kind == 'row':
            cells = CELL.split(lines[0])
            out.append('|'.join(c.replace(c.strip(), new) if c.strip() and (new := change(c.strip())) is not None else c
                                for c in cells))
        elif kind == 'prose':
            lead = LEAD.match(lines[0]).group()
            new = change(' '.join([lines[0][len(lead):].strip()] + [line.strip() for line in lines[1:]]))
            out += lines if new is None else [lead + new]
        else: out += lines
    return '\n'.join(out)


def needed(source, lang):
    """Whether a template is to be translated: in the wrong language, and not a command line."""
    return wrong(source, lang) and not COMMAND.match(source)


def pieces_to_send(text, lang):
    """The pieces of a document in the wrong language for `lang`, beyond what their slots hold."""
    found = []
    rewrite(text, lambda piece: found.append(piece) if needed(template(piece)[0], lang) else None)
    return found


def template(piece):
    """(the piece with every number, path, code, id and identifier as a numbered slot, what the slots hold)."""
    kept = []
    def slot(match): kept.append(match.group()); return f'⟦{len(kept)}⟧'
    return KEPT.sub(slot, piece), kept


def documents(report):
    report = Path(report)
    return [(path, path.relative_to(report).as_posix()) for path in sorted(report.rglob('*.md'))
            if not path.relative_to(report).as_posix().startswith(SKIP)]


def _load(path):
    try: value = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}
    return value if isinstance(value, dict) else {}


def translate(report, provider, say=lambda done, total: None):
    """Write report/i18n/<lang>/ for every document; {'pieces', 'remembered', 'calls', 'failed'}."""
    report = Path(report)
    memory_file = report.parent / MEMORY
    seed, kept = _load(SEED), _load(memory_file)
    memory = {lang: {**seed.get(lang, {}), **kept.get(lang, {})} for lang in LANGS}
    texts = [(name, path.read_text(encoding='utf-8', errors='replace')) for path, name in documents(report)]
    wanted = sorted({(lang, template(piece)[0]) for _, text in texts for lang in LANGS for piece in pieces_to_send(text, lang)})
    missing = [pair for pair in wanted if pair[1] not in memory[pair[0]]]
    counts = {'pieces': len(wanted), 'remembered': len(wanted) - len(missing), **_ask_all(provider, missing, memory, say)}
    _save_memory(memory_file, memory, wanted)
    _write_translations(report, texts, memory)
    return counts


def _save_memory(memory_file, memory, wanted):
    """Keep in the report's translation memory the templates its documents use, and only those."""
    used = {lang: {source: memory[lang][source] for one, source in wanted if one == lang and source in memory[lang]} for lang in LANGS}
    memory_file.write_text(json.dumps(used, ensure_ascii=False, indent=1), encoding='utf-8')


def _write_translations(report, texts, memory):
    """Write report/i18n/<lang>/<name> for every document, afresh."""
    shutil.rmtree(report / 'i18n', ignore_errors=True)     # the translations of documents gone (1,070 of 1,214 files)
    for name, text in texts:
        for lang in LANGS:
            target = report / 'i18n' / lang / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rewrite(text, lambda piece: _translated(piece, memory[lang], lang)), encoding='utf-8')


def _ask_all(provider, missing, memory, say):
    """Ask the model for every missing template, in ROUNDS; {'calls', 'failed'}."""
    calls = 0
    with ThreadPoolExecutor(WORKERS) as pool:
        for _ in range(ROUNDS):
            batches = list(_batches(missing))
            answers = [pool.submit(contextvars.copy_context().run, _ask, provider, batch) for batch in batches]
            for done, (batch, answer) in enumerate(zip(batches, answers)):
                say(done + 1, len(batches))
                keep(memory, batch, answer.result() or ())
            calls += len(batches)
            missing = [pair for pair in missing if pair[1] not in memory[pair[0]]]
    return {'calls': calls, 'failed': len(missing)}


def keep(memory, batch, answered):
    """Keep each sound answer: the template's slots exactly once each, and in the language asked (or, for a piece
    with no sentence in it, the template itself: names and commands, which have nothing to translate)."""
    for (lang, source), answer in zip(batch, answered):
        if not isinstance(answer, str): continue
        answer = answer.replace('\n', ' ').strip()
        if sorted(SLOT.findall(answer)) == sorted(SLOT.findall(source)) and (not wrong(answer, lang) or answer == source and not PROSE.search(source)):
            memory[lang][source] = answer


def _translated(piece, memory, lang):
    source, kept = template(piece)
    answer = memory.get(source) if needed(source, lang) else None
    return SLOT.sub(lambda match: kept[int(match.group(1)) - 1], answer) if answer else None


def _batches(pairs):
    """Templates of one language at a time, up to BATCH characters each."""
    for lang in LANGS:
        batch, size = [], 0
        for pair in (p for p in pairs if p[0] == lang):
            if batch and size + len(pair[1]) > BATCH: yield batch; batch, size = [], 0
            batch.append(pair); size += len(pair[1])
        if batch: yield batch


def _terms(lang):
    """The words EAOS uses, from the language not asked to `lang`: its labels (short ones) and TERMS."""
    pairs = {LABELS['en'][key]: value for key, value in LABELS['ar'].items()
             if key in LABELS['en'] and len(LABELS['en'][key].split()) <= 3 and '%' not in LABELS['en'][key]}
    pairs.update(TERMS['ar'])
    return '; '.join(f'{en} = {ar}' if lang == 'ar' else f'{ar} = {en}' for en, ar in pairs.items())


def _ask(provider, batch):
    """The answers of one batch in order (None where one is missing), or None when the call failed. Each item goes
    under its own key and comes back under it: in a plain list one item left out moves every answer after it."""
    lang = batch[0][0]
    items = {str(number): source for number, (_, source) in enumerate(batch, 1)}
    messages = [{'role': 'system', 'content': TASK.format(lang=NAMES[lang], terms=_terms(lang))},
                {'role': 'user', 'content': json.dumps({'items': items}, ensure_ascii=False)}]
    try: answer, _ = provider.complete(messages, small=True, stage='translate')
    except Exception: return None                          # the documents keep these pieces as written
    answers = answer.get('items') if isinstance(answer, dict) else None
    return [answers.get(number) for number in items] if isinstance(answers, dict) else None

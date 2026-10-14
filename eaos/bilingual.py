"""Every document of the report in both languages (report/i18n/ar/, report/i18n/en/), so the Studio shows each one
whole in the person's language and switches with it.

The documents are written by many hands (EAOS's own sentences, the engines' messages, the assistant's words) and came
out mixed: on EAOS itself, 153 documents, the median 42% Arabic in an Arabic report, START-HERE and the ADRs wholly
English. Rewriting each writer twice would be large; translating what is written is small, so:
- Only the lines in the wrong language are sent: a line in the right one, a fenced code block, a table's rule line,
  code spans, links' targets and paths are never sent and stay as written.
- A translation memory beside the report (translation-memory.json) keeps every line once translated: the next check
  sends only what is new, and the documents of two checks mostly repeat.
- Lines go in batches of BATCH characters, to the smallest model the assistant offers (`small`: Claude's Haiku), as
  a JSON list that must come back the same length; a batch that does not keeps its lines as written.
"""
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LANGS = ('ar', 'en')
NAMES = {'ar': 'Arabic (Modern Standard, plain)', 'en': 'English'}
BATCH = 8000
WORKERS = 3          # batches asked at once: each call spends most of its time starting the assistant
MEMORY = 'translation-memory.json'
ARABIC = re.compile('[؀-ۿ]')
LATIN_WORD = re.compile(r'\b[A-Za-z][a-z]{2,}\b')
ARABIC_WORD = re.compile('[؀-ۿ]{2,}')
UNSENT = re.compile(r'`[^`]*`|\]\([^)]*\)|https?://\S+|\b[\w.-]+/[\w./-]+|\b\w+\.(?:py|ts|tsx|js|json|md|mjs|css)\b')
RULE = re.compile(r'^\s*\|?\s*:?-{3,}')
FENCE = re.compile(r'^\s*(```|~~~)')
SKIP = ('studio/', 'engines/', 'i18n/')
TASK = ('Translate each line of `lines` into {lang}. Keep Markdown exactly (#, |, -, **, links), and keep untouched every '
        'code span in backticks, file path, identifier, number and tool name. Return {{"lines": [...]}}: the same number of '
        'lines, in the same order, each one translated line and nothing else.')


def wrong(line, lang):
    """Whether a line is written, beyond its code, paths and names, in the other language than `lang`."""
    if not line.strip() or RULE.match(line): return False
    prose = UNSENT.sub(' ', line)
    if lang == 'en': return bool(ARABIC.search(prose))
    english, arabic = len(LATIN_WORD.findall(prose)), len(ARABIC_WORD.findall(prose))
    return english >= 1 and (arabic == 0 or english >= 3 and english > arabic)


def lines_to_send(text, lang):
    """The lines of a document in the wrong language, outside fenced code."""
    out, fenced = [], False
    for line in text.split('\n'):
        if FENCE.match(line): fenced = not fenced; continue
        if not fenced and wrong(line, lang): out.append(line)
    return out


def documents(report):
    report = Path(report)
    return [(path, path.relative_to(report).as_posix()) for path in sorted(report.rglob('*.md'))
            if not path.relative_to(report).as_posix().startswith(SKIP)]


def _key(line, lang):
    return lang + ':' + hashlib.sha256(line.encode('utf-8')).hexdigest()[:24]


def translate(report, provider, say=lambda done, total: None):
    """Write report/i18n/<lang>/ for every document; {'lines', 'remembered', 'calls', 'failed'}."""
    report = Path(report)
    memory_file = report.parent / MEMORY
    try: memory = json.loads(memory_file.read_text(encoding='utf-8'))
    except (OSError, ValueError): memory = {}
    texts = [(path, name, path.read_text(encoding='utf-8', errors='replace')) for path, name in documents(report)]
    wanted = {(line, lang) for _, _, text in texts for lang in LANGS for line in lines_to_send(text, lang)}
    missing = sorted(pair for pair in wanted if _key(*pair) not in memory)
    counts = {'lines': len(wanted), 'remembered': len(wanted) - len(missing), 'failed': 0}
    batches = list(_batches(missing))
    with ThreadPoolExecutor(WORKERS) as pool:
        for done, (batch, answered) in enumerate(zip(batches, pool.map(lambda batch: _ask(provider, batch), batches))):
            say(done + 1, len(batches))
            if answered is None: counts['failed'] += len(batch); continue
            memory.update({_key(line, lang): out for (line, lang), out in zip(batch, answered)})
    counts['calls'] = len(batches)
    memory_file.write_text(json.dumps(memory, ensure_ascii=False), encoding='utf-8')
    for _, name, text in texts:
        for lang in LANGS:
            target = report / 'i18n' / lang / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_written(text, lang, memory), encoding='utf-8')
    return counts


def _written(text, lang, memory):
    out, fenced = [], False
    for line in text.split('\n'):
        if FENCE.match(line): fenced = not fenced
        out.append(memory.get(_key(line, lang), line) if not fenced and not FENCE.match(line) and wrong(line, lang) else line)
    return '\n'.join(out)


def _batches(pairs):
    """Lines of one language at a time, up to BATCH characters each."""
    for lang in LANGS:
        batch, size = [], 0
        for pair in (p for p in pairs if p[1] == lang):
            if batch and size + len(pair[0]) > BATCH: yield batch; batch, size = [], 0
            batch.append(pair); size += len(pair[0])
        if batch: yield batch


def _ask(provider, batch):
    """The translated lines of one batch, or None when the answer is not the same number of lines."""
    lang = batch[0][1]
    messages = [{'role': 'system', 'content': TASK.format(lang=NAMES[lang])},
                {'role': 'user', 'content': json.dumps({'lines': [line for line, _ in batch]}, ensure_ascii=False)}]
    try: answer, _ = provider.complete(messages, small=True, stage='translate')
    except Exception: return None                          # the documents keep these lines as written
    lines = answer.get('lines') if isinstance(answer, dict) else None
    ok = isinstance(lines, list) and len(lines) == len(batch) and all(isinstance(line, str) for line in lines)
    return [line.replace('\n', ' ') for line in lines] if ok else None

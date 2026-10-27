"""Personal values in a project's string literals, by Presidio (M12.1): run with the Python of Presidio's own environment.

    python scan.py <project> <rules json> <output jsonl> [excluded name ...]

Only string literals are read (never code tokens, which Presidio's name finder takes for people), one file's literals
joined into one text so the model is asked once per file. Presidio's own recognisers find e-mails, IBANs, card numbers,
phones and English names; the rules add Saudi mobiles, national ids (their check digit verified) and Arabic names (a
common given name and the word after it). A name or a generic phone counts only under a key that says so (`name:`,
`phone:`). Each hit is written masked, with a digest of its value so the same value can be found elsewhere; the value
itself is never written.
"""
import bisect
import hashlib
import json
import re
import sys
from pathlib import Path

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider

QUOTED = {'.sql': re.compile(r"'((?:[^'\n]|'')*)'")}
LITERAL = re.compile(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'|`([^`\\]*)`')
LATIN = re.compile(r"[A-Za-z][A-Za-z .'-]*")
KEY = re.compile(r'["\']?([\w؀-ۿ]+)["\']?\s*[:=]\s*$')


def luhn(digits):
    total = 0
    for index, digit in enumerate(int(d) for d in digits):
        doubled = digit * 2 if index % 2 == 0 else digit
        total += doubled - 9 if doubled > 9 else doubled
    return total % 10 == 0


class Checked(PatternRecognizer):
    """A pattern whose match must pass a check digit (a Saudi national id: the Luhn sum of its ten digits)."""
    def validate_result(self, pattern_text): return luhn(re.sub(r'\D', '', pattern_text))


class ArabicName(PatternRecognizer):
    """A common Arabic given name followed by another Arabic word: a person, not a phrase of the interface."""
    def __init__(self, names):
        given = '|'.join(sorted((re.escape(n) for n in names), key=len, reverse=True))
        super().__init__(supported_entity='AR_NAME', patterns=[Pattern('ar_name', rf'(?<![؀-ۿ])(?:{given})\s+(?:بن\s+)?[؀-ۿ]{{2,}}', 0.7)])


def engine(rules):
    nlp = NlpEngineProvider(nlp_configuration={'nlp_engine_name': 'spacy',
                                               'models': [{'lang_code': 'en', 'model_name': 'en_core_web_sm'}]}).create_engine()
    analyzer = AnalyzerEngine(nlp_engine=nlp, supported_languages=['en'])
    for entity, regex in rules['patterns'].items():
        kind = Checked if entity in rules['luhn'] else PatternRecognizer
        analyzer.registry.add_recognizer(kind(supported_entity=entity, patterns=[Pattern(entity.lower(), regex, 0.7)]))
    analyzer.registry.add_recognizer(ArabicName(rules['arabic_given_names']))
    return analyzer


def literals(text, suffix, bounds):
    """(start offset, line, key before it, literal) of every string literal of the file within the length bounds."""
    lines = [0] + [m.end() for m in re.finditer('\n', text)]
    for match in (QUOTED.get(suffix) or LITERAL).finditer(text):
        group = next(g for g in range(1, (match.re.groups or 0) + 1) if match.group(g) is not None)
        value = match.group(group)
        if not bounds['min'] <= len(value) <= bounds['max']: continue
        line = bisect.bisect_right(lines, match.start())
        key = KEY.search(text[max(lines[line - 1], match.start() - 80):match.start()])
        yield match.start(group), line, (key.group(1).lower() if key else ''), value


def placeholder(entity, value, rules):
    """Whether a value is one a program shows as an example (John Doe, someone@example.com, 0500000000)."""
    marks = rules['placeholders']
    if value.strip().lower() in marks['values']: return True
    if entity == 'EMAIL_ADDRESS':
        domain = value.rsplit('@', 1)[-1].lower()
        return any(domain == d or domain.endswith('.' + d) for d in marks['email_domains'])
    digits = re.sub(r'\D', '', value)
    return bool(digits) and any(re.search(pattern, digits) for pattern in marks['digits'])


def masked(entity, value):
    if entity in ('PERSON', 'AR_NAME'): return ' '.join(word[:1] + '•' * max(len(word) - 1, 1) for word in value.split())
    if '@' in value: return value[:1] + '•••@' + value.rsplit('@', 1)[-1]
    return value[:3] + '•' * max(len(value) - 6, 1) + value[-3:]


def digest(entity, value):
    normal = re.sub(r'\D', '', value) if entity not in ('PERSON', 'AR_NAME', 'EMAIL_ADDRESS') else ' '.join(value.lower().split())
    return hashlib.sha256(normal.encode('utf-8')).hexdigest()[:16]


def counted(result, where, value, rules):
    """Whether a hit is a personal value: a strong kind, or a name or phone under a key that names it. A name is a whole
    literal of two words or more (a field's value, never a word inside a sentence of the interface)."""
    if result.score < rules['min_score']: return False
    if result.entity_type in ('PERSON', 'AR_NAME') and (value != where[4].strip() or len(value.split()) < 2): return False
    if result.entity_type == 'PERSON' and not LATIN.fullmatch(value): return False
    if result.entity_type in rules['strong']: return True
    keys = rules.get(rules['keyed'].get(result.entity_type, ''), ())
    return any(word in where[3] for word in keys)


def joined(rows):
    """(one text of the literals, [(start, end, line, key, literal)])."""
    text, offsets = '', []
    for _, line, key, value in rows:
        offsets.append((len(text), len(text) + len(value), line, key, value))
        text += value + '\n'
    return text, offsets


def results(analyzer, found, rules):
    """(text, offsets, Presidio's results): the patterns over every literal, read without the language model; the
    model's names only in each literal under a name key, read alone, so a file is never read whole by it."""
    text, offsets = joined(found)
    patterns = [r for r in analyzer.registry.recognizers if r.supported_entities[0] in rules['strong'] + ['PHONE_NUMBER']]
    out = [hit for recognizer in patterns for hit in recognizer.analyze(text, recognizer.supported_entities, None) or ()]
    for start, end, line, key, value in offsets:
        if not any(word in key for word in rules['name_keys']): continue
        for hit in analyzer.analyze(text=value, language='en', entities=['PERSON']):  # one value alone, as a field holds it
            hit.start, hit.end = start + hit.start, start + hit.end
            out.append(hit)
    return text, offsets, out


def hits(analyzer, rel, text, rules):
    """The personal values of one file's literals, each with its line, key, mask, digest and whether it is a placeholder."""
    found = list(literals(text, Path(rel).suffix, rules['literal']))
    if not found: return []
    text, offsets, found = results(analyzer, found, rules)
    out, starts = [], [o[0] for o in offsets]
    for result in found:
        where = offsets[bisect.bisect_right(starts, result.start) - 1]
        where = where if where[0] <= result.start < where[1] else None
        value = text[result.start:min(result.end, where[1])].strip() if where else ''
        if where is None or not counted(result, where, value, rules): continue
        out.append({'path': rel, 'line': where[2], 'key': where[3], 'entity': result.entity_type,
                    'score': round(result.score, 2), 'masked': masked(result.entity_type, value),
                    'digest': digest(result.entity_type, value), 'placeholder': placeholder(result.entity_type, value, rules)})
    return _best(out)


def _best(rows):
    """One row per value at its place: the most certain kind when two recognisers read the same text."""
    kept = {}
    for row in sorted(rows, key=lambda r: -r['score']):
        kept.setdefault((row['line'], row['digest']), row)
    return sorted(kept.values(), key=lambda r: (r['line'], r['entity']))


def _skipped(path, rel, rules, skip):
    """Whether a file is not read: in a skipped or hidden folder, of a kind not read, minified, a link or too big."""
    folders = rel.split('/')[:-1]
    if skip & set(folders) or any(f.startswith('.') for f in folders): return True
    if path.suffix not in rules['suffixes'] or path.name in rules['skip_names'] or '.min.' in path.name: return True
    return not path.is_file() or path.is_symlink() or path.stat().st_size > rules['max_bytes']


def files(root, rules, excluded):
    skip = set(rules['skip_dirs']) | set(excluded)
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root).as_posix()
        if not _skipped(path, rel, rules, skip): yield rel, path


def main(root, rules_path, output, excluded):
    root, rules = Path(root).resolve(), json.loads(Path(rules_path).read_text(encoding='utf-8'))
    analyzer, scanned = engine(rules), 0
    with open(output, 'w', encoding='utf-8') as out:
        for rel, path in files(root, rules, excluded):
            text = path.read_text(encoding='utf-8', errors='replace')
            scanned += 1
            for row in hits(analyzer, rel, text, rules): out.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(json.dumps({'files': scanned}))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])

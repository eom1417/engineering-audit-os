"""Compare REPORT.html's annotated scalar and chart numbers with the Studio model (F7)."""
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

NUMBER = re.compile(r'<?\d+(?:\.\d+)?%?')
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}


class Numbers(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.rows, self.unowned = [], [], []

    def handle_starttag(self, tag, attrs):
        if tag in VOID: return
        self.stack.append((tag, dict(attrs), []))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] != tag: continue
            current = self.stack[index:]
            self.stack = self.stack[:index]
            for name, attrs, text in current:
                if attrs.get('data-meaning'):
                    self.rows.append((name, attrs['data-meaning'], ''.join(text)))
            break

    def handle_data(self, data):
        if any(attrs.get('data-literal') for _, attrs, _ in self.stack): return
        if NUMBER.search(data) and not any(tag in ('script', 'style', 'code', 'bdi') or attrs.get('data-meaning') for tag, attrs, _ in self.stack):
            self.unowned.append(data.strip())
        for _, _, text in self.stack: text.append(data)


def compare_numbers(page, catalog, charts=None):
    parser = Numbers(); parser.feed(page)
    mismatches = [{'value': text, 'why': 'number without a model annotation'} for text in parser.unowned]
    total = len(mismatches)
    charts = charts or {}
    for tag, meaning, value in parser.rows:
        if tag == 'span':
            total += 1
            if value not in catalog.get(meaning, []): mismatches.append({'meaning': meaning, 'value': value})
            continue
        expected = charts.get(meaning)
        if expected is None:
            total += 1
            mismatches.append({'meaning': meaning, 'value': value, 'why': 'unowned numeric annotation'})
            continue
        for literal in sorted(expected['literals'], key=len, reverse=True): value = value.replace(literal, '')
        tokens = NUMBER.findall(value)
        # A chart title may name an identifier; its annotation also carries the model's measured value.
        total += max(len(tokens), 1)
        allowed = expected['numbers']
        wrong = [token for token in tokens if token not in allowed]
        if wrong: mismatches.extend({'meaning': meaning, 'value': token} for token in wrong)
    return {'total': total, 'matched': total - len(mismatches), 'mismatches': mismatches}


def source_digest():
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted((root / 'eaos').rglob('*.py')):
        digest.update(path.relative_to(root).as_posix().encode()); digest.update(path.read_bytes())
    digest.update(Path(__file__).read_bytes())
    return digest.hexdigest()


def value(reports):
    """F7 over saved real-report comparisons; stale or partial comparisons stay unmeasured."""
    current = source_digest()
    rows = []
    for path in sorted((Path(reports) / 'report-source').glob('*/comparison.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('source_sha256') != current or not data.get('complete'): continue
        rows.append(data)
    if not rows: return None, 'no complete report/model comparison of this source under report-source'
    total = sum(row['total'] for row in rows)
    matched = sum(row['matched'] for row in rows)
    if not total: return None, 'report/model comparisons contain no measured numbers'
    return matched / total, f"REPORT.html numbers matched to the Studio model: {matched}/{total}; " + ', '.join(row['project'] for row in rows)


def measure(report, output, project=None):
    """Compare both report languages against the model built from saved audit facts."""
    from eaos import human_report
    from eaos.studio import model as M
    report, output = Path(report), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    project = project or report.name
    model = human_report.model(report)
    languages, errors = {}, []
    for lang in ('ar', 'en'):
        page, failed = human_report.render_parts(model, project, lang)
        errors.extend(failed)
        (output / f'REPORT-{lang}.html').write_text(page, encoding='utf-8')
        languages[lang] = compare_numbers(page, M.number_catalog(model), M.chart_catalog(model))
    data = {'project': project, 'report': str(report), 'source_sha256': source_digest(),
            'complete': not errors and all(row['total'] for row in languages.values()),
            'total': sum(row['total'] for row in languages.values()),
            'matched': sum(row['matched'] for row in languages.values()), 'languages': languages, 'errors': errors}
    (output / 'comparison.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return data


if __name__ == '__main__':
    import argparse
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    parser = argparse.ArgumentParser(description='Compare saved REPORT.html numeric annotations with the Studio model.')
    parser.add_argument('report', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--project')
    args = parser.parse_args()
    data = measure(args.report, args.out, args.project)
    print(f"{data['project']}: {data['matched']}/{data['total']}; complete={data['complete']}")
    raise SystemExit(0 if data['complete'] and data['matched'] == data['total'] else 1)

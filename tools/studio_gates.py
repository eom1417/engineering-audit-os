"""The screen gate every EAOS Studio screen and design mockup passes before the owner sees it.

    python tools/studio_gates.py <url [url ...] | folder | page.html> --out <dir>
        [--lang-key KEY | --lang-param NAME] [--langs ar,en]
        [--theme-key KEY | --theme-param NAME] [--themes light,dark]
        [--matrix '<json>' | --matrix matrix.json] [--viewports 390x844,768x1024,1440x900]
        [--phone-height-budget SCREENS] [--lighthouse | --lighthouse-pages a.html,b.html]
        [--lighthouse-min performance=90,accessibility=100] [--no-css]

A folder (or one HTML file) is served over loopback HTTP and every HTML page in it is audited; a URL is audited
as given (several URLs: the routes of one running app). Each page is opened at every viewport, in every language and theme the page supports: a language or
theme is set through the named localStorage key or query parameter; a theme is also set through
prefers-color-scheme, and with no key or parameter the dark theme is audited when the page declares one.

--matrix replaces the variants: {"variants": [{"name": "ar-dark", "storage": {"lang": "ar"}, "query": {},
"color_scheme": "dark"}], "viewports": [{"name": "phone", "width": 390, "height": 844}],
"height_budgets": {"index.html": 2}} (viewports and height_budgets optional; a budget is in phone screens).

Writes <out>/gates.json, <out>/screenshots/*.png and <out>/lighthouse/NN/lighthouse.json, prints a pass/fail
table and exits 1 when a row fails: a layout viewport wider than the configured width (phones are emulated as
phones, where an overflowing page silently widens it), horizontal overflow, a page that opens scrolled, an axe
violation of serious or critical impact, an interactive target under 44x44 CSS px at 390 wide, clipped text without data-truncate and a full-text path, a phone page over
its height budget, or a page that did not load; and when a page given to Lighthouse (--lighthouse: every page;
--lighthouse-pages: the named ones) scores under its mobile minimums. Exit 2: the gate could not run (a tool is
not installed; the message names the install command). The CSS design-drift counts are recorded in gates.json
for reading; they do not decide the exit code.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eaos.screens import audit  # noqa: E402


def viewports(text):
    rows = []
    for item in text.split(','):
        width, height = (int(n) for n in item.lower().split('x'))
        name = 'phone' if width <= 480 else 'tablet' if width <= 1024 else 'desktop'
        rows.append({'name': f'{name}-{width}', 'width': width, 'height': height})
    return rows


def matrix(text):
    path = Path(text)
    data = json.loads(path.read_text(encoding='utf-8') if path.is_file() else text)
    for index, row in enumerate(data.get('variants') or []):
        row.setdefault('name', f'variant-{index + 1}')
        row.setdefault('storage', {}); row.setdefault('query', {}); row.setdefault('color_scheme', 'light')
    return data


def minimums(text):
    return {name.strip(): int(value) for name, _, value in (item.partition('=') for item in text.split(',')) if name.strip()}


def table(rows, root):
    width = max([len(r['page']) for r in rows] + [4])
    lines = [f"{'page':{width}}  {'variant':12} {'viewport':14} result  why"]
    for row in rows:
        result = 'skip' if row['status'] == 'skipped' else 'FAIL' if row['failures'] else 'pass'
        why = '; '.join(row['failures']) if row['failures'] else row.get('reason', '') if result == 'skip' else ''
        lines.append(f"{row['page']:{width}}  {row['variant'] or '-':12} {row['viewport']:14} {result:6}  {why}")
    return '\n'.join(lines)


def run(targets, out, args):
    targets = [targets] if isinstance(targets, str) else list(targets)
    target = targets[0]
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    data = matrix(args.matrix) if args.matrix else {}
    page_variants = data.get('variants') or audit.variants(args.lang_key, args.lang_param, args.theme_key, args.theme_param,
                                                           args.langs.split(','), args.themes.split(','))
    sizes = data.get('viewports') or (viewports(args.viewports) if args.viewports else list(audit.VIEWPORTS))
    budgets = data.get('height_budgets') or {}
    floor = minimums(args.lighthouse_min)
    local = Path(target)
    report = {'schema_version': 1, 'target': str(target) if len(targets) == 1 else targets, 'variants': page_variants, 'viewports': sizes}

    def audit_pages(base, names):
        urls = {name: base + name if base else name for name in names}
        height = {urls[n]: budgets.get(n, args.phone_height_budget) for n in names}
        found = audit.page_audit(list(urls.values()), sizes, page_variants, out, height_budget=height)
        wanted = names if args.lighthouse else [n for n in (args.lighthouse_pages or '').split(',') if n]
        if wanted and found['status'] == 'observed':
            report['lighthouse'] = {}
            for index, name in enumerate(wanted, 1):
                scores = audit.lighthouse(urls.get(name, base + name if base else name), out / 'lighthouse' / f'{index:02d}')
                if scores['status'] == 'unavailable':
                    return {'status': 'unavailable', 'reason': scores['reason']}
                if scores.get('report'): scores['report'] = str(Path(scores['report']).relative_to(out))
                report['lighthouse'][name] = {**scores, 'minimums': floor, 'failures': audit.lighthouse_failures(scores, floor)}
        return found

    if len(targets) == 1 and local.exists():
        folder = local.resolve() if local.is_dir() else local.resolve().parent
        names = audit.pages(folder) if local.is_dir() else [local.name]
        if not names:
            print(f'no HTML page in {folder}'); return 2
        with audit.serve(folder) as base:
            result = audit_pages(base, names)
        if not args.no_css: report['css'] = audit.css_stats(folder)
        label = {base + name: name for name in names}
    else:
        result = audit_pages('', targets)
        label = {t: t for t in targets}
    report['tools'] = result.get('tools')
    report['status'] = result['status']
    if result['status'] != 'observed':
        report['reason'] = result['reason']
        (out / 'gates.json').write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(f"gate could not run: {result['reason']}")
        return 2
    rows = result['rows']
    for row in rows:
        base_url = row['url'].split('?', 1)[0]
        row['page'] = label.get(base_url, base_url)
        if row.get('screenshot'): row['screenshot'] = str(Path(row['screenshot']).relative_to(out))
    failed = [r for r in rows if r['failures']]
    slow = [name for name, scores in (report.get('lighthouse') or {}).items() if scores['failures']]
    report['rows'] = rows
    report['summary'] = {'rows': len(rows), 'passed': sum(1 for r in rows if r['status'] == 'observed' and not r['failures']),
                         'failed': len(failed), 'skipped': sum(1 for r in rows if r['status'] == 'skipped'),
                         'lighthouse_failed': len(slow)}
    report['ok'] = not failed and not slow
    (out / 'gates.json').write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(table(rows, out))
    summary = report['summary']
    print(f"\n{summary['passed']} passed, {summary['failed']} failed, {summary['skipped']} skipped; {out / 'gates.json'}")
    for name, scores in (report.get('lighthouse') or {}).items():
        verdict = 'FAIL ' + '; '.join(scores['failures']) if scores['failures'] else 'pass'
        if scores.get('status') == 'observed':
            print(f"lighthouse {name}: {verdict}; {scores['scores']} LCP {scores['lcp_ms']} ms, CLS {scores['cls']}"
                  + ''.join(f"; {category} lost on {', '.join(ids)}" for category, ids in scores['failed_audits'].items()
                            if category in scores['minimums']))
        else:
            print(f"lighthouse {name}: {verdict}")
    return 0 if report['ok'] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description='The screen gate of EAOS Studio screens and design mockups.')
    parser.add_argument('target', nargs='+', help='URLs (the routes of a running app), a folder of HTML pages, or one HTML file')
    parser.add_argument('--out', required=True, help='where gates.json and the screenshots go')
    parser.add_argument('--lang-key', help='localStorage key that sets the language')
    parser.add_argument('--lang-param', help='query parameter that sets the language')
    parser.add_argument('--langs', default='ar,en')
    parser.add_argument('--theme-key', help='localStorage key that sets the theme')
    parser.add_argument('--theme-param', help='query parameter that sets the theme')
    parser.add_argument('--themes', default='light,dark')
    parser.add_argument('--matrix', help='JSON (inline or a file) of variants and optional viewports')
    parser.add_argument('--viewports', help='comma-separated WIDTHxHEIGHT (default 390x844,768x1024,1440x900)')
    parser.add_argument('--phone-height-budget', type=float, help='the most phone screens a page may be tall at phone width')
    parser.add_argument('--lighthouse', action='store_true', help='Lighthouse mobile scores of every page, held to the minimums')
    parser.add_argument('--lighthouse-pages', help='comma-separated pages (or URLs) given to Lighthouse')
    parser.add_argument('--lighthouse-min', default=','.join(f'{k}={v}' for k, v in audit.LIGHTHOUSE_MINIMUMS.items()),
                        help='minimum mobile scores, NAME=SCORE comma-separated (default performance=90,accessibility=100)')
    parser.add_argument('--no-css', action='store_true', help='skip the CSS design-drift counts of a folder')
    args = parser.parse_args(argv)
    return run(args.target, args.out, args)


if __name__ == '__main__':
    sys.exit(main())

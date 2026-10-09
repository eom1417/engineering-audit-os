"""The screen gate every EAOS Studio screen and design mockup passes before the owner sees it.

    python tools/studio_gates.py <url [url ...] | folder | page.html> --out <dir>
        [--lang-key KEY | --lang-param NAME] [--langs ar,en]
        [--theme-key KEY | --theme-param NAME] [--themes light,dark]
        [--matrix '<json>' | --matrix matrix.json] [--viewports 390x844,768x1024,1440x900]
        [--phone-height-budget SCREENS] [--lighthouse | --lighthouse-pages a.html,b.html]
        [--lighthouse-min performance=90,accessibility=100] [--no-css]
    python tools/studio_gates.py --studio [--data <report>/studio] [--out <dir>] [--only home,problems] [--quick]

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

--studio gates the Studio this checkout ships (eaos/data/studio, built by `npm run build` in studio/): the build and
a report's data scripts (--data, default $EAOS_MEASURE/FleetManageWeb/studio) are laid out in a temporary folder as
the exporter lays them out, served over loopback, and every page of studio/gate-matrix.json is audited in its
variants and viewports (actions open the palette and a sheet; one page is opened from file://); its Lighthouse
pages are held to the mobile minimums, and the CSS drift counts of the shipped stylesheet are recorded. The result
(default $EAOS_MEASURE/studio-gates/gates.json) carries the build's source fingerprint, which F8 reads
(tools/north_star_measure.py); --only and --quick mark it incomplete.
"""
import argparse
import json
import math
import os
import re
import subprocess
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
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


def budget_failures(timing):
    failures = []
    for key, limit in (('filter_5000_ms', 100), ('home_interactive_ms', 1500)):
        value = timing.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            failures.append(f'{key}: missing or invalid timing')
        elif value > limit:
            failures.append(f'{key}: {value:.1f} ms > {limit} ms')
    return failures


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
    return finish(report, result, label, out)


def finish(report, result, label, out):
    """Write <out>/gates.json from one page_audit result, print the table, and return the exit code."""
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
        row['page'] = row.get('page') or label.get(base_url, base_url)
        if row.get('screenshot'): row['screenshot'] = str(Path(row['screenshot']).relative_to(out))
    failed = [r for r in rows if r['failures']]
    slow = [name for name, scores in (report.get('lighthouse') or {}).items() if scores['failures']]
    report['rows'] = rows
    report['summary'] = {'rows': len(rows), 'passed': sum(1 for r in rows if r['status'] == 'observed' and not r['failures']),
                         'failed': len(failed), 'skipped': sum(1 for r in rows if r['status'] == 'skipped'),
                         'lighthouse_failed': len(slow)}
    report['ok'] = not failed and not slow and not report.get('budget_failures')
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
    for failure in report.get('budget_failures', []): print(f'budget FAIL {failure}')
    return 0 if report['ok'] else 1


def studio_placeholders(data):
    """{card}: the first problem card with evidence, {fact} its first fact (with code when one has it) and {word} the longest
    word of its title; {component}: the component holding the most cards (each card's
    path counted in its deepest component), so the focused System view shows a full inspector; {path}: the code path
    the flow pages open ('none' without studio/paths.json); {task}, {screen}, {hidden_group}: the journeys and hidden pages'
    subjects; {store}: the data map's store; {stage}: the first router of the pipeline map, else its first stage ('none'
    without studio/pipeline.json or a pipeline); {ai_stage} and {ai_pipeline}: its first AI node with a router of its own
    (else its first AI stage) and that node's pipeline ('none' without one); {gap}, {op}, {plan}, {step}: Change subjects, or none; {function} and {screen_page}: explorer and gallery subjects; {doc}, {image}, {scan}, {compare}: Library and History subjects."""
    cards = json.loads((data / 'cards.json').read_text(encoding='utf-8'))['cards']
    chosen = next((c for c in cards if c.get('evidence')), cards[0] if cards else {'id': '', 'title': '', 'evidence': []})
    card = chosen['id']
    # {fact}: the card's first fact, one with code when it has one; {word}: the longest word of its title (the search)
    facts = {f['id']: f for f in (json.loads((data / 'evidence.json').read_text(encoding='utf-8'))['facts'] if (data / 'evidence.json').is_file() else [])}
    cited = [facts[i] for i in chosen.get('evidence') or [] if i in facts]
    fact = next((f for f in cited if f.get('code')), cited[0] if cited else {'id': 'none'})['id']
    word = max([w for w in re.split(r'[^\w]+', chosen.get('title') or '') if w and not w.isdigit()] or ['none'], key=len)
    story = json.loads((data / 'story.json').read_text(encoding='utf-8')) if (data / 'story.json').is_file() else {}
    names = sorted((c['name'] for c in (story.get('current') or {}).get('components') or []), key=len, reverse=True)
    held = {}
    for c in cards:
        for path in c.get('paths') or []:
            owner = next((n for n in names if path.startswith(n + '/')), None)
            if owner: held[owner] = held.get(owner, 0) + 1
    component = max(held, key=lambda n: (held[n], n)) if held else (names[-1] if names else '')
    # {path}: the code path reaching furthest through the lanes, then the longest within 60 links (studio/paths.json)
    paths = json.loads((data / 'paths.json').read_text(encoding='utf-8'))['paths'] if (data / 'paths.json').is_file() else []
    chosen = min(paths, key=lambda p: (-p['reach'], -min(len(p['steps']), 60), p['id']), default={'id': 'none'})
    # {task}, {screen}, {hidden_group}: a task with a path, a screen with a broken link (else a page) and an unseen group
    # holding items, from studio/journeys.json and hidden.json ('none' without them)
    section = lambda name: json.loads((data / f'{name}.json').read_text(encoding='utf-8')) if (data / f'{name}.json').is_file() else {}
    journeys, hidden = section('journeys'), section('hidden')
    task = next((t for t in journeys.get('tasks') or [] if len(t['path']) > 1), {'id': 'none'})
    screens = journeys.get('screens') or []
    screen = next((s for s in screens if 'broken_link' in s['flags']), None) or next((s for s in screens if s['kind'] == 'page'), {'id': 'none'})
    group = next((g for g in hidden.get('groups') or [] if g['count']['value']), {'id': 'none'})
    # {store}: the data map's first store written from more than one place, else its first (studio/data_paths.json)
    stores = section('data_paths').get('stores') or []
    store = next((s for s in stores if s.get('multi_writer')), stores[0] if stores else {'id': 'none'})
    stages = section('pipeline').get('stages') or []
    stage = next((s for s in stages if s.get('kind') == 'router'), stages[0] if stages else {'id': 'none'})
    routed = {(r.get('pipeline'), r.get('table')) for r in section('pipeline').get('routers') or []}
    ai = [s for s in stages if s.get('kind') == 'ai']
    ai = next((s for s in ai if (s.get('pipeline'), s.get('label')) in routed), ai[0] if ai else {'id': 'none', 'pipeline': 'none'})
    gaps = section('gaps').get('gaps') or []
    gap = max((g for g in gaps if g.get('operation') != 'retain'), key=lambda g: (len(g.get('cards') or []), g['id']), default={'id': 'none'})
    ops = sorted(section('operations').get('operations') or [], key=lambda o: o.get('order', 0))
    op = next((o for o in ops if o.get('after')), ops[0] if ops else {'id': 'none'})
    plans = section('plans').get('plans') or []
    plan = plans[0] if plans else {'id': 'none', 'steps': []}
    step = next((s for s in plan.get('steps') or [] if s.get('tasks')), {'id': 'none'})
    # {function}: the function with the most callers and callees, so its page draws a full call graph; {screen_page}:
    # the first screen with a shot, else the first screen (studio/functions.json, screens.json; 'none' without them)
    fns = section('functions').get('functions') or []
    function = max(fns, key=lambda f: (len(f['callers']) + len(f['callees']), f['id']), default={'id': 'none'})
    gallery = section('screens').get('screens') or []
    screen_page = next((s for s in gallery if s.get('shots')), gallery[0] if gallery else {'id': 'none'})
    # {doc}: the first document in the report's reading order with three headings or more, else the first;
    # {image}: the first diagram, else the first image; {scan} and {compare}: the last check, and the first..last
    # (one check: itself twice, which the comparison shows as "needs two checks")
    docs = sorted(section('docs').get('docs') or [], key=lambda d: (d.get('order') is None, d.get('order') or 0, d['path']))
    doc = next((d for d in docs if len(d.get('headings') or []) >= 3), docs[0] if docs else {'path': 'none'})
    images = section('media').get('images') or []
    image = next((i for i in images if i.get('kind') == 'diagram'), images[0] if images else {'id': 'none'})
    scans = section('history').get('scans') or []
    scan = scans[-1]['id'] if scans else 'none'
    return {'card': card, 'fact': fact, 'word': word, 'component': component, 'path': chosen['id'], 'task': task['id'], 'screen': screen['id'],
            'hidden_group': group['id'], 'store': store['id'], 'stage': stage['id'], 'ai_stage': ai['id'], 'ai_pipeline': ai['pipeline'], 'gap': gap['id'], 'op': op['id'], 'plan': plan['id'], 'step': step['id'], 'function': function['id'], 'screen_page': screen_page['id'], 'doc': doc['path'], 'image': image['id'], 'scan': scan, 'compare': f"{scans[0]['id'] if scans else 'none'}..{scan}"}


def studio_pages(matrix, data, base, folder, only=None):
    """The matrix's pages with their URLs: `path` under the served base, `file` as a file:// URL of the folder."""
    values = {k: quote(v, safe='') for k, v in studio_placeholders(data).items()}
    pages = []
    for page in matrix['pages']:
        if only and page['name'] not in only: continue
        entry = {k: v for k, v in page.items() if k not in ('path', 'file', 'lighthouse')}
        entry['url'] = (base + page['path'] if 'path' in page else (folder / page['file'].split('#')[0]).as_uri()
                        + ('#' + page['file'].split('#', 1)[1] if '#' in page['file'] else '')).format(**values)
        pages.append((entry, bool(page.get('lighthouse'))))
    return pages


def run_studio(args):
    """The Studio's own gate run (see --studio above)."""
    sys.path.insert(0, str(ROOT / 'tools'))
    import dev_paths
    shipped = ROOT / 'eaos/data/studio'
    data = Path(args.data or dev_paths.MEASURE / 'FleetManageWeb/studio').resolve()
    out = Path(args.out or dev_paths.MEASURE / 'studio-gates').resolve()
    if not (shipped / 'SOURCE.json').is_file():
        print(f'no shipped Studio in {shipped}: run npm run build in studio/'); return 2
    if not (data / 'manifest.json').is_file():
        print(f'no report data in {data}: export one (eaos/studio/export.py)'); return 2
    matrix = json.loads((ROOT / 'studio/gate-matrix.json').read_text(encoding='utf-8'))
    only = set(args.only.split(',')) if args.only else None
    sizes = [v for v in matrix['viewports'] if not args.quick or v['name'] in ('phone', 'desktop')]
    page_variants = [v for v in matrix['variants'] if not args.quick or v['name'].endswith('-light')]
    for row in page_variants: row.setdefault('storage', {})
    manifest = json.loads((data / 'manifest.json').read_text(encoding='utf-8'))
    source = json.loads((shipped / 'SOURCE.json').read_text(encoding='utf-8'))
    shutil.rmtree(out / 'screenshots', ignore_errors=True)
    shutil.rmtree(out / 'lighthouse', ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    floor = minimums(args.lighthouse_min)
    report = {'schema_version': 1, 'target': 'studio', 'variants': page_variants, 'viewports': sizes,
              'studio': {'source_sha256': source['source_sha256'], 'complete': not (only or args.quick or args.no_lighthouse),
                         'data': {'project': manifest['project']['name'], 'contract': manifest['contract'],
                                  'exported': manifest['built'].get('built'), 'exporter': manifest['built'].get('commit'),
                                  'folder': str(data)}}}
    with tempfile.TemporaryDirectory(prefix='eaos-studio-gate-') as folder:
        site = Path(folder)
        shutil.copytree(shipped, site, dirs_exist_ok=True)
        for script in data.glob('*.js'): shutil.copy(script, site / script.name)
        with audit.serve(site) as base:
            if args.budgets:
                (out / 'budgets.json').unlink(missing_ok=True)
                from eaos import toolchain
                cards = json.loads((data / 'cards.json').read_text(encoding='utf-8'))['cards']
                if len(cards) != 5000:
                    print('--budgets requires exactly 5000 cards; no timing written'); return 2
                absent = audit.missing('playwright')
                if absent:
                    print(absent); return 2
                config = {'base': base, 'source': source['source_sha256'], 'count': len(cards),
                          'card': cards[-1]['id'], 'other': cards[0]['id'],
                          'modules': str(toolchain.home() / 'node/node_modules')}
                trial = site / 'budget-config.json'
                trial.write_text(json.dumps(config), encoding='utf-8')
                done = subprocess.run(['node', str(ROOT / 'studio/scripts/gates.mjs'), str(trial)],
                                      capture_output=True, text=True, timeout=180,
                                      env={**os.environ, 'PLAYWRIGHT_BROWSERS_PATH': str(toolchain.browsers())})
                if done.returncode:
                    print(f'budget trial failed: {done.stderr[-1500:]}'); return 2
                timing = json.loads(done.stdout.splitlines()[-1])
                report['budgets'] = timing
                report['budget_failures'] = budget_failures(timing)
                (out / 'budgets.json').write_text(json.dumps(timing, indent=1) + '\n', encoding='utf-8')
            pages = studio_pages(matrix, data, base, site, only)
            report['pages'] = [entry['name'] for entry, _ in pages]
            entries = [{**entry, 'wait_for': entry.get('wait_for', matrix.get('wait_for'))} for entry, _ in pages]
            # the matrix grows with every Studio page: allow 5 s a screen (about twice the time one takes), at least 15 min
            shots = sum(len(e.get('viewports') or sizes) * len(e.get('variants') or page_variants) for e in entries)
            result = audit.page_audit(entries, sizes, page_variants, out, timeout=max(900, 5 * shots))
            first = page_variants[0]['query']
            if result['status'] == 'observed' and not args.quick and not args.no_lighthouse:
                report['lighthouse'] = {}
                for index, (entry, wanted) in enumerate(pages, 1):
                    if not wanted: continue
                    address, _, route = entry['url'].partition('#')
                    scores = audit.lighthouse(f"{address}?{urlencode(first)}#{route}", out / 'lighthouse' / f"{index:02d}-{entry['name']}")
                    if scores['status'] == 'unavailable':
                        result = {'status': 'unavailable', 'reason': scores['reason']}; break
                    if scores.get('report'): scores['report'] = str(Path(scores['report']).relative_to(out))
                    report['lighthouse'][entry['name']] = {**scores, 'minimums': floor, 'failures': audit.lighthouse_failures(scores, floor)}
        if not args.no_css: report['css'] = audit.css_stats(site)
    return finish(report, result, {}, out)


def main(argv=None):
    parser = argparse.ArgumentParser(description='The screen gate of EAOS Studio screens and design mockups.')
    parser.add_argument('target', nargs='*', help='URLs (the routes of a running app), a folder of HTML pages, or one HTML file')
    parser.add_argument('--out', help='where gates.json and the screenshots go (required unless --studio)')
    parser.add_argument('--studio', action='store_true', help="gate the Studio this checkout ships, on a report's data")
    parser.add_argument('--data', help="--studio: the report's studio/ folder (default $EAOS_MEASURE/FleetManageWeb/studio)")
    parser.add_argument('--only', help='--studio: comma-separated page names of studio/gate-matrix.json (an incomplete run)')
    parser.add_argument('--no-lighthouse', action='store_true', help='--studio: screens only; marks the run incomplete')
    parser.add_argument('--budgets', action='store_true', help='--studio: measure cold Home and 5000-card search on shipped assets (4x CPU, loopback network)')
    parser.add_argument('--quick', action='store_true', help='--studio: phone and desktop, light only, no Lighthouse (an incomplete run)')
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
    if args.studio: return run_studio(args)
    if not args.target or not args.out: parser.error('a target and --out are required without --studio')
    return run(args.target, args.out, args)


if __name__ == '__main__':
    sys.exit(main())

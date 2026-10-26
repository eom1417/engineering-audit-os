"""Rendered-screen checks through pinned tools that run as separate processes.

Three runners, each returning a plain dict with a `status` ('observed', 'unavailable' or 'error') and a `reason`
when it did not observe; a missing tool is reported as unavailable, it is not raised:

    page_audit(urls, viewports, variants, out)   Playwright + axe (eaos/templates/screens/audit.mjs): per page,
                                                 variant (by default the app's own theme alone) and viewport, the WCAG 2.2 A/AA violations, horizontal
                                                 overflow, the scroll position after load, interactive targets
                                                 under 44x44 CSS px at phone width, clipped text, letter-spaced
                                                 Arabic, the page's script errors, the page height and a
                                                 full-page screenshot.
    lighthouse(url, out)                         Lighthouse, mobile profile: category scores, LCP and CLS.
    css_stats(folder)                            @projectwallace/css-analyzer (eaos/templates/screens/css.mjs):
                                                 distinct colors, font sizes, spacings and selector specificity.

`failures(row)` names what fails the gate in one audited row. The browser is allowed the tested URL's origin
only (file:// pages: file:// only); every other request is aborted and listed in the row.
"""
import gzip
import io
import json
import os
import shutil
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from ...core import toolchain
from ...core.system.process import run_command

TEMPLATES = Path(__file__).resolve().parents[2] / 'templates/screens'
VIEWPORTS = ({'name': 'phone', 'width': 390, 'height': 844},
             {'name': 'tablet', 'width': 768, 'height': 1024},
             {'name': 'desktop', 'width': 1440, 'height': 900})
PHONE_WIDTH, TARGET_MIN = 390, 44
FAILING_IMPACTS = ('serious', 'critical')
SKIP_FOLDERS = {'node_modules', '.git', '.venv', '__pycache__'}


def unavailable(reason, **extra):
    return {'status': 'unavailable', 'reason': reason, **extra}


def missing(*names):
    """'' when Node.js and the named pinned tools are installed, else what is missing and how to install it."""
    if not shutil.which('node'): return 'Node.js is not installed (https://nodejs.org, version 22 or newer)'
    absent = [why for name in names if (why := _absent(name))]
    if absent: return f"not installed: {', '.join(absent)}; run: python -m eaos tools install --only {','.join(names)}"
    return ''


def _absent(name):
    """What is missing of one pinned tool: not at its version, or Playwright without its browser; '' when installed."""
    tool = next((t for t in toolchain.registry()['tools'] if t['name'] == name), None)
    found, reason = toolchain.found_version(tool) if tool else (None, 'not in eaos/data/toolchain.json')
    if found != (tool or {}).get('version'): return f"{name} ({reason or f'found {found}'})"
    if name == 'playwright' and toolchain.browser_missing(): return f'playwright ({toolchain.browser_missing()})'
    return ''


def _node(script, config, timeout, env=None):
    """(parsed stdout, error) of a helper script given its config as a JSON file."""
    with tempfile.TemporaryDirectory(prefix='eaos-screens-') as folder:
        path = Path(folder) / 'config.json'
        path.write_text(json.dumps(config, default=str), encoding='utf-8')
        try:
            done = run_command(['node', str(TEMPLATES / script), str(path)], timeout=timeout,
                                  env={**os.environ, 'PLAYWRIGHT_BROWSERS_PATH': str(toolchain.browsers()), **(env or {})})
        except (OSError, subprocess.TimeoutExpired) as problem:
            return None, f'{script}: {problem}'
    lines = [line for line in done.stdout.splitlines() if line.startswith('{')]
    if done.returncode or not lines: return None, f'{script} exited {done.returncode}: {(done.stderr or done.stdout)[-800:]}'
    try: return json.loads(lines[-1]), ''
    except ValueError as problem: return None, f'{script} printed no JSON: {problem}'


def variants(lang_key=None, lang_param=None, theme_key=None, theme_param=None, langs=('ar', 'en'), themes=(None,),
             lang_field=None, theme_field=None):
    """The page variants to audit. A language is set through a localStorage key or a query parameter, when one is
    named; a theme the same way, and always through prefers-color-scheme. By default one theme only, the app's own:
    nothing is set and the browser asks for light (a dark pass doubled the pictures and the review, for a theme the
    person rarely changes). A key with a field keeps a JSON object (the EAOS Studio keeps {"lang", "theme"} under
    "eaos.report.studio"): the variant's value is merged into that object, {key: {field: value}}, rather than set as the
    whole value."""
    languages = list(langs) if (lang_key or lang_param) else [None]
    keys = ((lang_key, lang_field), (theme_key, theme_field))
    return [_variant(lang, theme, keys, (lang_param, theme_param)) for theme in themes for lang in languages]


def _variant(lang, theme, keys, params):
    """One variant: its localStorage values (merged into a JSON object when the key has a field) and its query."""
    storage = _storage(keys, (lang, theme))
    query = {param: value for param, value in zip(params, (lang, theme)) if value and param}
    return {'name': '-'.join(part for part in (lang, theme) if part) or 'default', 'lang': lang, 'theme': theme,
            'color_scheme': theme if theme in ('light', 'dark') else 'light', 'storage': storage, 'query': query}


def _storage(keys, values):
    """The localStorage values of a variant: each value under its key, merged into a JSON object when the key has a field."""
    storage = {}
    for (key, field), value in zip(keys, values):
        if not (key and value): continue
        if field: storage[key] = {**(storage.get(key) if isinstance(storage.get(key), dict) else {}), field: value}
        else: storage[key] = value
    return storage


def _budget(row, height_budget, own_budget):
    """A row's height budget: its page's own, else the one for its URL, else the one for every page."""
    budget = height_budget.get(row['url'].split('?', 1)[0]) if isinstance(height_budget, dict) else height_budget
    return own_budget.get(row.get('page'), budget)


def page_audit(urls, viewports=VIEWPORTS, page_variants=None, out=None, **limits):
    """Every URL in every variant at every viewport, through the pinned Playwright and axe. Screenshots go to
    <out>/screenshots when `out` is given. `limits`, by name: phone_width, target_min, timeout (900 seconds) and
    height_budget, which caps a page's height at phone width, in phone screens:
    one number for every page, or {url: screens} for some (a URL without its query); storage_state, the browser's
    session; read_only, a published site: nothing but GET is sent.

    A URL may also be a page, {'url', 'name', 'actions', 'viewports', 'variants', 'wait_for', 'height_budget'}
    (eaos/templates/screens/audit.mjs): the actions run before the page is measured, the viewports and variants
    are the names it is audited in, and its own height budget wins over `height_budget`."""
    phone_width, height_budget = limits.get('phone_width', PHONE_WIDTH), limits.get('height_budget')
    urls = [urls] if isinstance(urls, (str, dict)) else list(urls)
    own_budget = _own_budgets(urls)
    absent = missing('playwright', 'axe-core')
    if absent: return unavailable(absent, rows=[])
    config = {'urls': _sent(urls), 'viewports': list(viewports), 'variants': page_variants or variants(),
              'phone_width': phone_width, 'target_min': limits.get('target_min', TARGET_MIN),
              'screenshots_dir': str(Path(out) / 'screenshots') if out else None,
              'storage_state': limits.get('storage_state'), 'read_only': bool(limits.get('read_only')),
              'modules': {'playwright': str(toolchain.home() / 'node/node_modules'), 'axe': str(toolchain.node_modules('axe-core'))}}
    result, error = _node('audit.mjs', config, limits.get('timeout', 900))
    if error: return {'status': 'error', 'reason': error, 'rows': []}
    tools = _versions(('playwright', 'axe-core'))
    for row in result['rows']: row['failures'] = failures(row, phone_width, _budget(row, height_budget, own_budget))
    return {'status': 'observed', 'tools': {**tools, 'chromium': result.get('chromium')}, 'rows': result['rows']}


def _own_budgets(urls):
    """{page name: its own height budget} of the pages that name one."""
    return {u['name']: u['height_budget'] for u in urls if isinstance(u, dict) and u.get('name') and u.get('height_budget')}


def _sent(urls):
    """The URLs and pages as the audit script reads them: a page without its height budget, which is checked here."""
    return [{k: v for k, v in u.items() if k != 'height_budget'} if isinstance(u, dict) else u for u in urls]


def _versions(names):
    """{tool: its pinned version} of the named tools."""
    return {name: next(t['version'] for t in toolchain.registry()['tools'] if t['name'] == name) for name in names}


def failures(row, phone_width=PHONE_WIDTH, height_budget=None):
    """What fails the gate in one audited row: a layout viewport wider than the configured one (mobile emulation
    widens it silently on an overflowing page), overflow, a shifted first scroll position, a serious or critical
    axe violation, an interactive target under 44x44 at phone width, clipped text not marked data-truncate (or
    marked without a path to its full text), letter-spaced Arabic, a script error, a request the gate had to
    block (the page needs the network), a language, direction or theme other than the variant expects, a phone page
    taller than `height_budget` screens, or a page that did not load. A fragment that starts with '/' is a route
    (#/problems), not an anchor: such a page must still open at the top."""
    if row.get('status') != 'observed': return [f"error: {row.get('reason', 'not audited')}"]
    found = _layout_failures(row) + _access_failures(row, phone_width) + _content_failures(row) + _variant_failures(row)
    if height_budget and row['width'] <= phone_width and row.get('page_height', 0) > height_budget * row['height']:
        found.append(f"height: {row['page_height']}px tall, over the budget of {height_budget:g} x {row['height']}px screens")
    return found


def _layout_failures(row):
    """The layout viewport, overflow and the first scroll position."""
    found = []
    if row.get('layout_width', row['width']) != row['width']:
        found.append(f"layout_width: the page laid out {row['layout_width']}px wide in a {row['width']}px viewport "
                     "(a phone browser zooms such a page out)")
    if row['scroll_width'] > row['inner_width'] or row['overflow_element_count']:
        found.append(f"overflow: page {row['scroll_width']}px wide in a {row['inner_width']}px viewport, "
                     f"{row['overflow_element_count']} element(s) outside it")
    scroll = row['scroll']
    anchor = urlsplit(row['url']).fragment
    if not (anchor and not anchor.startswith('/')) and (scroll['x'] or scroll['y']):
        found.append(f"initial_scroll: the page opens scrolled to x={scroll['x']}, y={scroll['y']}")
    return found


def _access_failures(row, phone_width):
    """Accessibility: the serious axe violations, and small targets at phone width."""
    found = []
    serious = [v for v in row['axe']['violations'] if v['impact'] in FAILING_IMPACTS]
    if serious:
        found.append('axe: ' + ', '.join(f"{v['id']} ({v['impact']}, {v['nodes']})" for v in serious))
    if row['width'] <= phone_width and row['small_target_count']:
        found.append(f"targets: {row['small_target_count']} interactive element(s) under {TARGET_MIN}x{TARGET_MIN}px")
    return found


def _content_failures(row):
    """Clipped text, letter-spaced Arabic, script errors and blocked requests."""
    found = []
    if row.get('truncated_count'):
        found.append(f"truncation: {row['truncated_count']} clipped text element(s) without data-truncate and a full-text path: "
                     + ', '.join(t['selector'] for t in row['truncated'][:3]))
    if row.get('arabic_tracking_count'):
        found.append(f"arabic_tracking: letter-spacing on {row['arabic_tracking_count']} Arabic text element(s): "
                     + ', '.join(row['arabic_tracking'][:3]))
    if row.get('page_errors'):
        found.append(f"script_errors: {len(row['page_errors'])}: {row['page_errors'][0][:200]}")
    if row.get('blocked_requests'):
        found.append(f"offline: {len(row['blocked_requests'])} request(s) outside the page's origin: {row['blocked_requests'][0][:200]}")
    return found


def _variant_failures(row):
    """The language, direction or theme the variant expects and the page did not apply."""
    expect = row.get('expect') or {}
    attributes = row.get('root_attributes') or {}
    wrong = [f'{name}={attributes.get(name)!r} (expected {value!r})' for name, value in (expect.get('attributes') or {}).items()
             if attributes.get(name) != value]
    if expect.get('dir') and row.get('dir') != expect['dir']: wrong.insert(0, f"dir={row.get('dir')!r} (expected {expect['dir']!r})")
    return ['variant: the page did not apply it: ' + ', '.join(wrong)] if wrong else []


def chromium_path():
    """The executable of the Chromium the pinned Playwright installed, or None."""
    script = "const r=require('module').createRequire(process.argv[1]+'/x.js');let p;try{p=r('playwright')}catch{p=r('@playwright/test')}" \
             ";process.stdout.write(p.chromium.executablePath())"
    try:
        done = subprocess.run(['node', '-e', script, str(toolchain.home() / 'node/node_modules')], capture_output=True, text=True,
                              timeout=60, env={**os.environ, 'PLAYWRIGHT_BROWSERS_PATH': str(toolchain.browsers())})
    except (OSError, subprocess.TimeoutExpired):
        return None
    path = done.stdout.strip()
    return path if done.returncode == 0 and path and Path(path).is_file() else None


LIGHTHOUSE_CATEGORIES = ('performance', 'accessibility', 'best-practices')



def failed_audits(data):
    """Per category, the weighted audits that did not score full marks: what pulled the score down."""
    found = {}
    for name in LIGHTHOUSE_CATEGORIES:
        for ref in (data['categories'].get(name) or {}).get('auditRefs', []):
            score = (data['audits'].get(ref['id']) or {}).get('score')
            if ref.get('weight') and score is not None and score < 1: found.setdefault(name, []).append(ref['id'])
    return found


def lighthouse(url, out=None, timeout=300, storage_state=None):
    """Lighthouse's mobile profile on one URL: the three category scores (0-100), LCP in ms and CLS."""
    absent = missing('playwright', 'lighthouse')
    if absent: return unavailable(absent)
    chrome = chromium_path()
    if not chrome: return unavailable('the Chromium of the pinned Playwright was not found; run: python -m eaos tools install --only playwright')
    with tempfile.TemporaryDirectory(prefix='eaos-lighthouse-') as folder:
        report = Path(out) / 'lighthouse.json' if out else Path(folder) / 'lighthouse.json'
        if storage_state:
            data, error = _node('lighthouse.mjs', {'url': url, 'out': str(report), 'folder': folder,
                'storage_state': str(storage_state), 'categories': LIGHTHOUSE_CATEGORIES,
                'modules': {'playwright': str(toolchain.home() / 'node/node_modules'),
                            'lighthouse': str(toolchain.node_modules('lighthouse'))}}, timeout)
        else: data, error = _run_lighthouse(url, report, chrome, folder, timeout)
    if error: return {'status': 'error', 'reason': error}
    if data.get('runtimeError'): return {'status': 'error', 'reason': f"lighthouse: {data['runtimeError'].get('message')}"}
    return _lighthouse_result(data, url, report if out else None)


def _run_lighthouse(url, report, chrome, folder, timeout):
    """(Lighthouse's JSON report, '') or (None, why it could not be read)."""
    flags = '--headless=new' + (' --no-sandbox' if hasattr(os, 'geteuid') and os.geteuid() == 0 else '')
    report.parent.mkdir(parents=True, exist_ok=True)
    argv = [str(toolchain.home() / 'bin/lighthouse'), url, '--output=json', f'--output-path={report}', '--quiet',
            '--form-factor=mobile', f"--only-categories={','.join(LIGHTHOUSE_CATEGORIES)}", f'--chrome-flags={flags}',
            '--no-enable-error-reporting']
    try:
        done = run_command(argv, timeout=timeout,
                              env={**os.environ, 'CHROME_PATH': chrome, 'TMPDIR': folder})
    except (OSError, subprocess.TimeoutExpired) as problem:
        return None, f'lighthouse: {problem}'
    try: return json.loads(report.read_text(encoding='utf-8')), ''
    except (OSError, ValueError):
        return None, f'lighthouse exited {done.returncode}: {(done.stderr or done.stdout)[-800:]}'


def _lighthouse_result(data, url, kept):
    """The category scores (0-100), LCP and CLS of a Lighthouse report; `kept` is the report's path when it is kept."""
    scores = {name: None if (data['categories'].get(name) or {}).get('score') is None else round(data['categories'][name]['score'] * 100)
              for name in LIGHTHOUSE_CATEGORIES}
    audit = lambda key: (data['audits'].get(key) or {}).get('numericValue')
    return {'status': 'observed', 'version': data.get('lighthouseVersion'), 'url': data.get('finalDisplayedUrl') or url,
            'form_factor': data.get('configSettings', {}).get('formFactor'), 'scores': scores,
            'failed_audits': failed_audits(data),
            'lcp_ms': None if audit('largest-contentful-paint') is None else round(audit('largest-contentful-paint')),
            'cls': None if audit('cumulative-layout-shift') is None else round(audit('cumulative-layout-shift'), 4),
            'report': str(kept) if kept else None}





COMPRESSED = ('.html', '.htm', '.js', '.mjs', '.css', '.json', '.svg', '.txt', '.map')


class _Quiet(SimpleHTTPRequestHandler):
    """Serves a folder as a static web server does: text files gzip-compressed when the browser accepts it, so
    Lighthouse weighs the bytes a person's browser would download."""
    def log_message(self, *args): pass

    def send_head(self):
        path = Path(self.translate_path(self.path))
        if (path.is_dir() or path.suffix.lower() not in COMPRESSED or not path.is_file()
                or 'gzip' not in self.headers.get('Accept-Encoding', '')):
            return super().send_head()
        body = gzip.compress(path.read_bytes(), compresslevel=6, mtime=0)
        self.send_response(200)
        self.send_header('Content-Type', self.guess_type(str(path)))
        self.send_header('Content-Encoding', 'gzip')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Vary', 'Accept-Encoding')
        self.end_headers()
        return io.BytesIO(body)


@contextmanager
def serve(folder):
    """A folder served over loopback HTTP for the length of the block: its base URL (http://127.0.0.1:<port>/).
    Text files are sent gzip-compressed to a browser that accepts it."""
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(_Quiet, directory=str(folder)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try: yield f'http://127.0.0.1:{server.server_address[1]}/'
    finally:
        server.shutdown()
        server.server_close()


def pages(folder):
    """The HTML pages of a folder, relative to it, without dependency folders."""
    found = []
    for base, directories, names in os.walk(folder):
        directories[:] = sorted(d for d in directories if d not in SKIP_FOLDERS)
        found += sorted((Path(base) / n).relative_to(folder).as_posix() for n in names if n.endswith(('.html', '.htm')))
    return found

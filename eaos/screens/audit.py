"""Rendered-screen checks through pinned tools that run as separate processes.

Three runners, each returning a plain dict with a `status` ('observed', 'unavailable' or 'error') and a `reason`
when it did not observe; a missing tool is reported as unavailable, it is not raised:

    page_audit(urls, viewports, variants, out)   Playwright + axe (eaos/templates/screens/audit.mjs): per page,
                                                 variant and viewport, the WCAG 2.2 A/AA violations, horizontal
                                                 overflow, the scroll position after load, interactive targets
                                                 under 44x44 CSS px at phone width, clipped text, the page height
                                                 and a full-page screenshot.
    lighthouse(url, out)                         Lighthouse, mobile profile: category scores, LCP and CLS.
    css_stats(folder)                            @projectwallace/css-analyzer (eaos/templates/screens/css.mjs):
                                                 distinct colors, font sizes, spacings and selector specificity.

`failures(row)` names what fails the gate in one audited row. The browser is allowed the tested URL's origin
only (file:// pages: file:// only); every other request is aborted and listed in the row.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .. import toolchain

TEMPLATES = Path(__file__).resolve().parent.parent / 'templates/screens'
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
    absent = []
    for name in names:
        tool = next((t for t in toolchain.registry()['tools'] if t['name'] == name), None)
        found, reason = toolchain.found_version(tool) if tool else (None, 'not in upstreams/toolchain.json')
        if found != (tool or {}).get('version'): absent.append(f"{name} ({reason or f'found {found}'})")
        elif name == 'playwright' and toolchain.browser_missing(): absent.append(f'playwright ({toolchain.browser_missing()})')
    if absent: return f"not installed: {', '.join(absent)}; run: python -m eaos tools install --only {','.join(names)}"
    return ''


def _node(script, config, timeout, env=None):
    """(parsed stdout, error) of a helper script given its config as a JSON file."""
    with tempfile.TemporaryDirectory(prefix='eaos-screens-') as folder:
        path = Path(folder) / 'config.json'
        path.write_text(json.dumps(config), encoding='utf-8')
        try:
            done = subprocess.run(['node', str(TEMPLATES / script), str(path)], capture_output=True, text=True, timeout=timeout,
                                  env={**os.environ, 'PLAYWRIGHT_BROWSERS_PATH': str(toolchain.browsers()), **(env or {})})
        except (OSError, subprocess.TimeoutExpired) as problem:
            return None, f'{script}: {problem}'
    lines = [line for line in done.stdout.splitlines() if line.startswith('{')]
    if done.returncode or not lines: return None, f'{script} exited {done.returncode}: {(done.stderr or done.stdout)[-800:]}'
    try: return json.loads(lines[-1]), ''
    except ValueError as problem: return None, f'{script} printed no JSON: {problem}'


def variants(lang_key=None, lang_param=None, theme_key=None, theme_param=None, langs=('ar', 'en'), themes=('light', 'dark')):
    """The page variants to audit. A language is set through a localStorage key or a query parameter, when one is
    named; a theme the same way, and always through prefers-color-scheme. With no theme key or parameter, the dark
    variant is audited only when the page declares a dark scheme (audit.mjs checks it on the light variant)."""
    languages = list(langs) if (lang_key or lang_param) else [None]
    rows = []
    for theme in themes:
        for lang in languages:
            storage, query = {}, {}
            if lang and lang_key: storage[lang_key] = lang
            if lang and lang_param: query[lang_param] = lang
            if theme_key: storage[theme_key] = theme
            if theme_param: query[theme_param] = theme
            rows.append({'name': '-'.join(part for part in (lang, theme) if part), 'lang': lang, 'theme': theme,
                         'color_scheme': theme if theme in ('light', 'dark') else 'light', 'storage': storage, 'query': query,
                         'if_page_supports_dark': theme == 'dark' and not (theme_key or theme_param)})
    return rows


def page_audit(urls, viewports=VIEWPORTS, page_variants=None, out=None, phone_width=PHONE_WIDTH, target_min=TARGET_MIN,
               timeout=900, height_budget=None):
    """Every URL in every variant at every viewport, through the pinned Playwright and axe. Screenshots go to
    <out>/screenshots when `out` is given. `height_budget` caps a page's height at phone width, in phone screens:
    one number for every page, or {url: screens} for some (a URL without its query)."""
    urls = [urls] if isinstance(urls, str) else list(urls)
    absent = missing('playwright', 'axe-core')
    if absent: return unavailable(absent, rows=[])
    config = {'urls': urls, 'viewports': list(viewports), 'variants': page_variants or variants(),
              'phone_width': phone_width, 'target_min': target_min,
              'screenshots_dir': str(Path(out) / 'screenshots') if out else None,
              'modules': {'playwright': str(toolchain.home() / 'node/node_modules'), 'axe': str(toolchain.node_modules('axe-core'))}}
    result, error = _node('audit.mjs', config, timeout)
    if error: return {'status': 'error', 'reason': error, 'rows': []}
    tools = {name: next(t['version'] for t in toolchain.registry()['tools'] if t['name'] == name) for name in ('playwright', 'axe-core')}
    for row in result['rows']:
        budget = height_budget.get(row['url'].split('?', 1)[0]) if isinstance(height_budget, dict) else height_budget
        row['failures'] = failures(row, phone_width, budget)
    return {'status': 'observed', 'tools': {**tools, 'chromium': result.get('chromium')}, 'rows': result['rows']}


def failures(row, phone_width=PHONE_WIDTH, height_budget=None):
    """What fails the gate in one audited row: a layout viewport wider than the configured one (mobile emulation
    widens it silently on an overflowing page), overflow, a shifted first scroll position, a serious or critical
    axe violation, an interactive target under 44x44 at phone width, clipped text not marked data-truncate (or
    marked without a path to its full text), a phone page taller than `height_budget` screens, or a page that did
    not load."""
    if row.get('status') == 'skipped': return []
    if row.get('status') != 'observed': return [f"error: {row.get('reason', 'not audited')}"]
    found = []
    if row.get('layout_width', row['width']) != row['width']:
        found.append(f"layout_width: the page laid out {row['layout_width']}px wide in a {row['width']}px viewport "
                     "(a phone browser zooms such a page out)")
    if row['scroll_width'] > row['inner_width'] or row['overflow_element_count']:
        found.append(f"overflow: page {row['scroll_width']}px wide in a {row['inner_width']}px viewport, "
                     f"{row['overflow_element_count']} element(s) outside it")
    scroll = row['scroll']
    if not urlsplit(row['url']).fragment and (scroll['x'] or scroll['y']):
        found.append(f"initial_scroll: the page opens scrolled to x={scroll['x']}, y={scroll['y']}")
    serious = [v for v in row['axe']['violations'] if v['impact'] in FAILING_IMPACTS]
    if serious:
        found.append('axe: ' + ', '.join(f"{v['id']} ({v['impact']}, {v['nodes']})" for v in serious))
    if row['width'] <= phone_width and row['small_target_count']:
        found.append(f"targets: {row['small_target_count']} interactive element(s) under {TARGET_MIN}x{TARGET_MIN}px")
    if row.get('truncated_count'):
        found.append(f"truncation: {row['truncated_count']} clipped text element(s) without data-truncate and a full-text path: "
                     + ', '.join(t['selector'] for t in row['truncated'][:3]))
    if height_budget and row['width'] <= phone_width and row.get('page_height', 0) > height_budget * row['height']:
        found.append(f"height: {row['page_height']}px tall, over the budget of {height_budget:g} x {row['height']}px screens")
    return found


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
LIGHTHOUSE_MINIMUMS = {'performance': 90, 'accessibility': 100}


def lighthouse_failures(result, minimums=None):
    """What fails the gate in one Lighthouse result: a category under its minimum score (the Studio's mobile
    budget: performance 90, accessibility 100), or a run that did not observe."""
    if result.get('status') != 'observed': return [f"lighthouse {result.get('status')}: {result.get('reason', '')[:300]}"]
    found = []
    for name, least in (LIGHTHOUSE_MINIMUMS if minimums is None else minimums).items():
        score = result['scores'].get(name)
        if score is None or score < least: found.append(f'lighthouse: {name} {score} under {least}')
    return found


def failed_audits(data):
    """Per category, the weighted audits that did not score full marks: what pulled the score down."""
    found = {}
    for name in LIGHTHOUSE_CATEGORIES:
        for ref in (data['categories'].get(name) or {}).get('auditRefs', []):
            score = (data['audits'].get(ref['id']) or {}).get('score')
            if ref.get('weight') and score is not None and score < 1: found.setdefault(name, []).append(ref['id'])
    return found


def lighthouse(url, out=None, timeout=300):
    """Lighthouse's mobile profile on one URL: the three category scores (0-100), LCP in ms and CLS."""
    absent = missing('playwright', 'lighthouse')
    if absent: return unavailable(absent)
    chrome = chromium_path()
    if not chrome: return unavailable('the Chromium of the pinned Playwright was not found; run: python -m eaos tools install --only playwright')
    flags = '--headless=new' + (' --no-sandbox' if hasattr(os, 'geteuid') and os.geteuid() == 0 else '')
    with tempfile.TemporaryDirectory(prefix='eaos-lighthouse-') as folder:
        report = Path(out) / 'lighthouse.json' if out else Path(folder) / 'lighthouse.json'
        report.parent.mkdir(parents=True, exist_ok=True)
        argv = [str(toolchain.home() / 'bin/lighthouse'), url, '--output=json', f'--output-path={report}', '--quiet',
                '--form-factor=mobile', f"--only-categories={','.join(LIGHTHOUSE_CATEGORIES)}", f'--chrome-flags={flags}',
                '--no-enable-error-reporting']
        try:
            done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                                  env={**os.environ, 'CHROME_PATH': chrome, 'TMPDIR': folder})
        except (OSError, subprocess.TimeoutExpired) as problem:
            return {'status': 'error', 'reason': f'lighthouse: {problem}'}
        try: data = json.loads(report.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {'status': 'error', 'reason': f'lighthouse exited {done.returncode}: {(done.stderr or done.stdout)[-800:]}'}
    if data.get('runtimeError'): return {'status': 'error', 'reason': f"lighthouse: {data['runtimeError'].get('message')}"}
    scores = {name: None if (data['categories'].get(name) or {}).get('score') is None else round(data['categories'][name]['score'] * 100)
              for name in LIGHTHOUSE_CATEGORIES}
    audit = lambda key: (data['audits'].get(key) or {}).get('numericValue')
    return {'status': 'observed', 'version': data.get('lighthouseVersion'), 'url': data.get('finalDisplayedUrl') or url,
            'form_factor': data.get('configSettings', {}).get('formFactor'), 'scores': scores,
            'failed_audits': failed_audits(data),
            'lcp_ms': None if audit('largest-contentful-paint') is None else round(audit('largest-contentful-paint')),
            'cls': None if audit('cumulative-layout-shift') is None else round(audit('cumulative-layout-shift'), 4),
            'report': str(report) if out else None}


STYLE = re.compile(r'<style[^>]*>(.*?)</style>', re.S | re.I)
SPACING = re.compile(r'(?:^|[;{\s])(?:margin|padding|gap|row-gap|column-gap)(?:-[a-z-]+)?\s*:\s*([^;}!]+)', re.I)
LENGTH = re.compile(r'-?\d*\.?\d+(?:px|rem|em|%|vh|vw|ch)\b|var\(--[\w-]+\)')


def site_css(folder):
    """(CSS files, inline <style> blocks) of a built site, without dependency folders."""
    files, inline = [], []
    for base, directories, names in os.walk(folder):
        directories[:] = sorted(d for d in directories if d not in SKIP_FOLDERS)
        for name in sorted(names):
            path = Path(base) / name
            if name.endswith('.css'): files.append(str(path))
            elif name.endswith(('.html', '.htm')): inline += STYLE.findall(path.read_text(encoding='utf-8', errors='replace'))
    return files, inline


def spacings(texts):
    """Distinct non-zero margin, padding and gap lengths (the analyzer has no spacing count of its own)."""
    seen = {}
    for text in texts:
        for value in SPACING.findall(text):
            for length in LENGTH.findall(value):
                number = re.match(r'-?\d*\.?\d+', length)
                if number is None or float(number.group()): seen[length] = seen.get(length, 0) + 1
    return {'unique': len(seen), 'values': dict(sorted(seen.items(), key=lambda kv: -kv[1]))}


def css_stats(folder, timeout=180):
    """Design-drift counts over every CSS file and inline <style> block of a built site."""
    absent = missing('css-analyzer')
    if absent: return unavailable(absent)
    files, inline = site_css(folder)
    if not files and not inline: return {'status': 'not_applicable', 'reason': f'no CSS in {folder}'}
    result, error = _node('css.mjs', {'files': files, 'inline': inline, 'modules': {'css': str(toolchain.node_modules('css-analyzer'))}},
                          timeout)
    if error: return {'status': 'error', 'reason': error}
    texts = [Path(f).read_text(encoding='utf-8', errors='replace') for f in files] + inline
    version = next(t['version'] for t in toolchain.registry()['tools'] if t['name'] == 'css-analyzer')
    return {'status': 'observed', 'version': version, 'files': len(files), 'inline_blocks': len(inline),
            **result, 'spacings': spacings(texts)}


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass


@contextmanager
def serve(folder):
    """A folder served over loopback HTTP for the length of the block: its base URL (http://127.0.0.1:<port>/)."""
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

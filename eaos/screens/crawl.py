"""Every page of a running app, found by Unlighthouse and measured with Lighthouse, through the pinned tools.

    crawl(base, out, max_routes)   unlighthouse-ci from `base` (the app's own address on this computer), driving the
                                   Chromium of the pinned Playwright: the routes it found by following the app's links
                                   and, for each, Lighthouse's mobile scores, LCP and CLS. Returns {status, reason?,
                                   routes: [{path, scores, lcp_ms, cls, report}]}; its own reports stay in `out`.

Lighthouse's numbers are comparable between two runs on an idle computer; the crawl records them as measured.
"""
import json
from pathlib import Path
from urllib.parse import urlsplit

from ..engines.process import run, which
from .audit import chromium_path, unavailable

CATEGORIES = ('performance', 'accessibility', 'best-practices', 'seo')


def config(base, out, chrome, max_routes):
    """Unlighthouse's configuration: the pinned Chromium, one sample, no throttling, no sitemap or robots.txt."""
    return {'site': base, 'outputPath': str(out), 'puppeteerOptions': {'executablePath': chrome, 'args': ['--no-sandbox']},
            'chrome': {'useSystem': False},
            'scanner': {'device': 'mobile', 'samples': 1, 'throttle': False, 'sitemap': False, 'robotsTxt': False,
                        'maxRoutes': max_routes},
            'ci': {'buildStatic': False, 'reporter': 'jsonExpanded'}}


def route_of(report, out):
    """{path, scores, lcp_ms, cls, report} of one route's lighthouse.json."""
    data = json.loads(report.read_text(encoding='utf-8'))
    audits = data.get('audits') or {}
    value = lambda key: (audits.get(key) or {}).get('numericValue')
    return {'path': urlsplit(data.get('finalDisplayedUrl') or data.get('requestedUrl') or '').path or '/',
            'scores': {name: None if (data.get('categories', {}).get(name) or {}).get('score') is None
                       else round(data['categories'][name]['score'] * 100) for name in CATEGORIES},
            'lcp_ms': None if value('largest-contentful-paint') is None else round(value('largest-contentful-paint')),
            'cls': None if value('cumulative-layout-shift') is None else round(value('cumulative-layout-shift'), 4),
            'report': report.relative_to(out).as_posix()}


def crawl(base, out, max_routes=200):
    binary = which('unlighthouse-ci')
    if not binary: return unavailable('unlighthouse-ci is not installed: python -m eaos tools install --only unlighthouse', routes=[])
    chrome = chromium_path()
    if not chrome: return unavailable('the Chromium of the pinned Playwright was not found', routes=[])
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'unlighthouse.config.ts').write_text('export default ' + json.dumps(config(base, out / 'unlighthouse', chrome, max_routes)) + '\n',
                                                encoding='utf-8')
    code, stdout, stderr, _ = run([binary, '--config-file', str(out / 'unlighthouse.config.ts')], cwd=out, timeout=3600)
    reports = sorted((out / 'unlighthouse/reports').glob('**/lighthouse.json'))
    if not reports: return {'status': 'error', 'reason': f'unlighthouse-ci exited {code} and measured no page: {(stderr or stdout)[-400:]}',
                            'routes': []}
    return {'status': 'observed', 'routes': [route_of(report, out) for report in reports]}

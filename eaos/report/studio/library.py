"""What the check wrote for people to read (studio/docs.json, studio/media.json): the Studio searches the documents and
opens each from the report page's files; the screens and the user's journeys place the pictures.

- docs: every Markdown document of the report, grouped by purpose, in the reading order the report's own index
  (README.md) gives, with its headings for search. The engines' working copies of the project (engines/) are not
  documents EAOS wrote, and are left out.
- beside them, the documents kept next to the report (BESIDE): the look the person chose (DESIGN.md), a build's
  blueprint (its parts, technologies and milestones) and the plan of a feature added to the project, in one group.
- media: the report's diagrams and images, the same way. The thumbnails an older crawl's Unlighthouse kept
  (`__screenshot-thumbnails__`, 760 of them on EAOS's own Studio) are its working files, not pictures of the check.
- Each document's title in both languages when the check wrote them (report/i18n/<lang>/,
  eaos/core/language/bilingual.py): docs `titles`.
"""
import re
from pathlib import Path

DOC_GROUPS = (('START-HERE.md', 'start'), ('README.md', 'start'), ('CURRENT-STATE.md', 'story'),
              ('TARGET-STATE.md', 'story'), ('GAP-AND-STRATEGY.md', 'story'), ('EXECUTION-PLAN.md', 'plan'))
SKIP = ('studio/', 'engines/')
BESIDE = ('blueprint/BLUEPRINT.md', 'DESIGN.md', 'extend/SOURCE.md')     # beside the report: the group `look`
SKIP_PARTS = ('__screenshot-thumbnails__',)
LINK = re.compile(r'\]\(([^)#\s]+\.md)(?:#[^)]*)?\)')
HEADING = re.compile(r'^(#{1,3})\s+(.+?)\s*#*\s*$')
FENCE = re.compile(r'^\s*(```|~~~)')
IMAGES = {'.png': 'png', '.svg': 'svg+xml', '.jpg': 'jpeg', '.jpeg': 'jpeg', '.gif': 'gif', '.webp': 'webp'}
DIAGRAMS = {'architecture/system.mmd': ('خريطة الصفحات والواجهات البرمجية', 'Map of pages and APIs'),
            'architecture/current/diagram.mmd': ('البنية اليوم', 'The architecture today'),
            'architecture/target/diagram.mmd': ('البنية المستهدفة', 'The target architecture')}


def _files(report, suffixes):
    report = Path(report)
    for path in sorted(p for suffix in suffixes for p in report.rglob(f'*{suffix}')):
        name = path.relative_to(report).as_posix()
        if name.startswith(SKIP) or any(part in name for part in SKIP_PARTS) or not path.is_file(): continue
        yield path, name


def _beside(report):
    for name in BESIDE:
        if (Path(report).parent / name).is_file(): yield Path(report).parent / name, name


def _source(report, name):
    """The file of a document: beside the report for BESIDE, else in it."""
    return Path(report).parent / name if name in BESIDE else Path(report) / name


def _headings(text):
    out, fenced = [], False
    for line in text.split('\n'):
        if FENCE.match(line): fenced = not fenced; continue
        if fenced: continue
        found = HEADING.match(line)
        if found: out.append({'level': len(found.group(1)), 'text': found.group(2).strip()[:200]})
    return out


def reading_order(report):
    """{document: position} from the report's index (README.md), every linked document in the order it is linked."""
    index = Path(report) / 'README.md'
    try: text = index.read_text(encoding='utf-8', errors='replace')
    except OSError: return {}
    order = {}
    for target in LINK.findall(text):
        target = target.removeprefix('./')
        if target not in order: order[target] = len(order)
    return order


def _doc_group(name, groups):
    """A document's group: the look for a file beside the report, else its listed group, else its folder (technical at
    the top)."""
    return 'look' if name in BESIDE else groups.get(name) or (name.split('/', 1)[0] if '/' in name else 'technical')


def docs(report):
    report = Path(report)
    groups, first = dict(DOC_GROUPS), {name: i for i, (name, _) in enumerate(DOC_GROUPS)}
    indexed = reading_order(report)
    out = []
    for path, name in [*_beside(report), *_files(report, ('.md',))]:
        text = path.read_text(encoding='utf-8', errors='replace')
        lines = text.lstrip().split('\n', 1)
        title = lines[0].lstrip('#').strip() if lines[0].startswith('#') else path.stem
        group = _doc_group(name, groups)
        order = first.get(name, len(first) + indexed[name] if name in indexed else None)
        out.append({'id': name, 'title': title[:200] or path.stem, 'path': name, 'group': group, 'bytes': path.stat().st_size,
                    'order': order, 'headings': [h for h in _headings(text) if h['level'] > 1][:60],
                    'titles': {lang: _title(text)[:200] for lang, text in _versions(report, name).items()}})
    return out


def _versions(report, name):
    """{lang: the document's text in that language}, for the languages the check wrote it in."""
    return {lang: path.read_text(encoding='utf-8', errors='replace') for lang in ('ar', 'en')
            if (path := Path(report) / 'i18n' / lang / name).is_file()}


def _title(text):
    first = text.lstrip().split('\n', 1)[0]
    return first.lstrip('#').strip() if first.startswith('#') else ''


def _pictured(report):
    """{picture path: (route, viewport)} of the check's screen pictures (live/screens.json): the route is the page's
    address without its host or query (/#/system for a hash route), so a picture belongs to its screen."""
    from urllib.parse import urlsplit
    from ...analysis.presentation.model import _load
    rows = (_load(Path(report) / 'live/screens.json', {}) or {}).get('rows') or []
    out = {}
    for row in rows:
        if not row.get('screenshot'): continue
        address = urlsplit(row.get('url') or '')
        route = (address.path or '/') + ('#' + address.fragment.split('?', 1)[0] if address.fragment else '')
        out[row['screenshot']] = (route, row.get('viewport'))
    return out


VIEWPORTS = {'phone': ('جوال', 'phone'), 'desktop': ('سطح المكتب', 'desktop')}


def _shot_title(route, viewport, lang):
    """A screen picture's title in the reader's words: its page (the address without the router's '/#', the home page by
    name) and the device, not the raw route and viewport id."""
    at = 0 if lang == 'ar' else 1
    page = route.lstrip('/#') or ('الصفحة الرئيسية', 'Home page')[at]
    return f'{page} · {VIEWPORTS.get(viewport, (viewport, viewport))[at]}'


def media(report, lang='ar'):
    out, pictured = [], _pictured(report)
    for path, name in _files(report, ('.mmd', *IMAGES)):
        known = DIAGRAMS.get(name)
        route, viewport = pictured.get(name, (None, None))
        title = (known[0] if lang == 'ar' else known[1]) if known else _shot_title(route, viewport, lang) if route else (name.rsplit('/', 2)[-2] if '/' in name else path.stem)
        out.append({'id': name, 'path': name, 'title': title, 'kind': 'diagram' if path.suffix in ('.mmd', '.svg') else 'screen',
                    'batch': None, 'phase': None, 'route': route, 'viewport': viewport, 'pair': None})
    return out

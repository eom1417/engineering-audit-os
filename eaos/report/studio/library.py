"""The Library's data: what the check wrote for people to read (studio/docs.json, studio/media.json) and their content
(studio/library.json, contract v2), so the Studio's reader shows them from its own folder, opened from a file or served.

- docs: every Markdown document of the report, grouped by purpose, in the reading order the report's own index
  (README.md) gives, with its headings for search. The engines' working copies of the project (engines/) are not
  documents EAOS wrote, and are left out.
- beside them, the documents kept next to the report (BESIDE): the look the person chose (DESIGN.md), a build's
  blueprint (its parts, technologies and milestones) and the plan of a feature added to the project, in one group.
- media: the report's diagrams and images, the same way. The thumbnails an older crawl's Unlighthouse kept
  (`__screenshot-thumbnails__`, 760 of them on EAOS's own Studio) are its working files, not pictures of the check.
- Each document in both languages when the check wrote them (report/i18n/<lang>/, eaos/core/language/bilingual.py): its title
  (docs `titles`) and its text (library `texts`), so the reader switches with the person's language at once.
- library: each document's text, and each image as a data URI (an <img> runs no script from it) or a diagram's source.
  A file too large to carry is listed with the reason; nothing is cut silently. The machine's own folders in the text
  (the project's absolute path, the home folder) are replaced by the project's name and `~`.
"""
import base64
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
SOURCES = {'.mmd': 'mermaid'}
TEXT_LIMIT = 400_000          # characters of one document
IMAGE_LIMIT = 2_000_000       # bytes of one image
SOURCE_LIMIT = 200_000        # characters of one diagram's source
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


def _private(text, project):
    """The text with this machine's folders replaced: the project's absolute path by its name, the home folder by ~."""
    if project:
        root = str(Path(project).resolve())
        text = text.replace(root, Path(root).name)
    home = str(Path.home())
    return text.replace(home + '/', '~/') if len(home) > 1 else text


def library(report, doc_rows, image_rows, project=None):
    """The library section's body: the text of each document and the content of each image or diagram."""
    report = Path(report)
    documents, images = [], []
    for row in doc_rows:
        text = _private(_source(report, row['path']).read_text(encoding='utf-8', errors='replace'), project)
        texts = {lang: _private(body, project)[:TEXT_LIMIT] for lang, body in _versions(report, row['path']).items()}
        documents.append({'id': row['id'], 'text': text[:TEXT_LIMIT], 'chars': len(text), 'truncated': len(text) > TEXT_LIMIT,
                          **({'texts': texts} if texts else {})})
    for row in image_rows:
        path = report / row['path']
        size = path.stat().st_size
        if path.suffix in SOURCES:
            source = _private(path.read_text(encoding='utf-8', errors='replace'), project)
            images.append({'id': row['id'], 'format': SOURCES[path.suffix], 'data': None, 'source': source[:SOURCE_LIMIT],
                           'bytes': size, 'embedded': len(source) <= SOURCE_LIMIT, 'reason': None if len(source) <= SOURCE_LIMIT else 'too_large'})
        elif size <= IMAGE_LIMIT:
            data = 'data:image/' + IMAGES[path.suffix.lower()] + ';base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
            images.append({'id': row['id'], 'format': IMAGES[path.suffix.lower()].split('+')[0], 'data': data, 'source': None,
                           'bytes': size, 'embedded': True, 'reason': None})
        else:
            images.append({'id': row['id'], 'format': IMAGES[path.suffix.lower()].split('+')[0], 'data': None, 'source': None,
                           'bytes': size, 'embedded': False, 'reason': 'too_large'})
    return {'documents': documents, 'images': images,
            'counts': {'documents': {'value': len(documents), 'src': 'docs.json#docs'}, 'images': {'value': len(images), 'src': 'media.json#images'},
                       'truncated': {'value': sum(d['truncated'] for d in documents) + sum(not i['embedded'] for i in images),
                                     'src': f'documents over {TEXT_LIMIT} characters, images over {IMAGE_LIMIT} bytes'}}}

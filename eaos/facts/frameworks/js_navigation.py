"""The links a JavaScript or TypeScript front end writes from one screen to another: the user's paths between pages.

Each link becomes a ``navigation`` fact at the file and line that writes it:
    link       a JSX attribute ``to=`` or ``href=`` (Link, NavLink, a, a Button…): ``<Link to="/app/drivers">``
    redirect   ``<Navigate to=…>`` or ``<Redirect to=…>``: the screen sends the person on without a click
    navigate   a call that moves the person: ``navigate("/x")``, ``navigate({ to: "/x" })``, ``router.push("/x")``,
               ``history.push("/x")``, ``redirect("/x")``
    menu       an object entry ``to: "/x"``, the routers' own word, in any file (a list of tabs or sections drawn as
               links); ``url``, ``href`` or ``link`` only in a navigation, menu or sidebar file
A target written with a template keeps its fixed parts and marks each ``${…}`` as ``:param`` (``dynamic``); a query or
a hash is dropped. A target that does not start with "/" is kept as written and marked ``relative``: the screen it is
relative to is the reader's to resolve. Comments are blanked before matching, so a link commented out is not a link.
Only links written in the source are reported: a target assembled from a variable (``navigate(next)``) is not guessed,
and an ``href`` to another site is not a screen of this app.
"""
import re

FACT_KIND = 'navigation'
LANGUAGES = ('javascript', 'typescript', 'tsx')
LIMITATIONS = [
    'Only links written in the source are read; a target held in a variable or assembled at runtime is not followed.',
    'A link inside a file is a link of every screen that renders that file; which button or state shows it is not read.',
    'Object entries count as menu links when their key is `to`, or (url, href, link) in files named for navigation, menus or sidebars.',
]
TARGET = r'''(?P<quote>['"`])(?P<target>[^'"`\n]*)(?P=quote)'''
ATTRIBUTE = re.compile(r'''\b(?P<attr>to|href)\s*=\s*(?:\{\s*)?''' + TARGET)
CALL = re.compile(r'''\b(?P<call>navigate|router\.push|router\.replace|history\.push|history\.replace|redirect|navigateTo)'''
                  r'''\s*\(\s*(?:\{\s*to\s*:\s*)?''' + TARGET)
MENU_ENTRY = re.compile(r'''\b(?P<key>url|href|to|link)\s*:\s*''' + TARGET)
MENU_FILE = re.compile(r'(?i)(nav|menu|sidebar|links?)[^/]*\.[jt]sx?$')
TAG_BEFORE = re.compile(r'<(?P<tag>[A-Za-z][\w.]*)[^<]*\Z')
REDIRECTS = ('Navigate', 'Redirect')
SCHEME = re.compile(r'^(?:[a-z][a-z0-9+.-]*:|//|#|\$\{)', re.I)
# A comment, or a string (a quoted one ends at its quote or the line's end; a template may span lines).
TOKEN = re.compile(r'''//[^\n]*|/\*.*?(?:\*/|\Z)|(['"])(?:\\.|(?!\1)[^\\\n])*\1?|`(?:\\.|[^\\`])*`?''', re.S)


def blank_comments(text):
    """The text with every // and /* */ comment replaced by spaces (newlines kept), strings left alone."""
    return TOKEN.sub(lambda m: m.group() if m.group()[0] != '/' else re.sub(r'[^\n]', ' ', m.group()), text)


def target_of(raw):
    """(target, dynamic, relative) of a written target, or None when it is not a screen of this app."""
    raw = raw.strip()
    if not raw or SCHEME.match(raw): return None
    dynamic = '${' in raw
    path = re.sub(r'(?::param)+', ':param', re.sub(r'\$\{[^}]*\}', ':param', raw))
    path = re.split(r'[?#]', path, 1)[0]
    if not path: return None
    return path, dynamic, not path.startswith('/')


def _links(text, rel):
    """(offset, written target, via) of every link the text writes: attributes, then calls, then menu entries."""
    yield from _attribute_links(text)
    for match in CALL.finditer(text):
        yield match.start(), match.group('target'), 'navigate'
    menu = bool(MENU_FILE.search(rel))
    for match in MENU_ENTRY.finditer(text):
        if match.group('target').startswith('/') and (menu or match.group('key') == 'to'):
            yield match.start(), match.group('target'), 'menu'


def _attribute_links(text):
    """A link or redirect a tag's attribute writes (an href only when it is a path of the app)."""
    for match in ATTRIBUTE.finditer(text):
        tag = TAG_BEFORE.search(text, max(0, match.start() - 400), match.start())
        if not tag or (match.group('attr') == 'href' and not match.group('target').startswith('/')): continue
        yield match.start(), match.group('target'), 'redirect' if tag.group('tag').split('.')[-1] in REDIRECTS else 'link'


def detect(context):
    found, seen = [], set()
    for offset, raw, via in _links(blank_comments(context.text), context.rel):
        parsed = target_of(raw)
        if not parsed: continue
        target, dynamic, relative = parsed
        line = context.line_of(offset)
        if (line, target) in seen: continue          # navigate({ to: "/x" }) is one link, not a call and a menu entry
        seen.add((line, target))
        found.append((offset, line, {'target': target, 'via': via, 'dynamic': dynamic, 'relative': relative,
                                     'symbol': context.symbol_at(line)}))
    return sorted(found, key=lambda row: row[0])

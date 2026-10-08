"""The links a JavaScript or TypeScript front end writes from one screen to another: the user's paths between pages.

Each link becomes a ``navigation`` fact at the file and line that writes it:
    link       a JSX attribute ``to=`` or ``href=`` (Link, NavLink, a, a Button…): ``<Link to="/app/drivers">``
    redirect   ``<Navigate to=…>`` or ``<Redirect to=…>``: the screen sends the person on without a click
    navigate   a call that moves the person: ``navigate("/x")``, ``navigate({ to: "/x" })``, ``router.push("/x")``,
               ``history.push("/x")``, ``redirect("/x")``
    menu       an object entry ``url: "/x"`` (or href, to, link) in a navigation, menu or sidebar file
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
    'Object entries (url, href, to, link) count as menu links only in files named for navigation, menus or sidebars.',
]
TARGET = r'''(?P<quote>['"`])(?P<target>[^'"`\n]*)(?P=quote)'''
ATTRIBUTE = re.compile(r'''\b(?P<attr>to|href)\s*=\s*(?:\{\s*)?''' + TARGET)
CALL = re.compile(r'''\b(?P<call>navigate|router\.push|router\.replace|history\.push|history\.replace|redirect|navigateTo)'''
                  r'''\s*\(\s*(?:\{\s*to\s*:\s*)?''' + TARGET)
MENU_ENTRY = re.compile(r'''\b(?:url|href|to|link)\s*:\s*''' + TARGET)
MENU_FILE = re.compile(r'(?i)(nav|menu|sidebar|links?)[^/]*\.[jt]sx?$')
TAG_BEFORE = re.compile(r'<(?P<tag>[A-Za-z][\w.]*)[^<]*\Z')
REDIRECTS = ('Navigate', 'Redirect')
SCHEME = re.compile(r'^(?:[a-z][a-z0-9+.-]*:|//|#|\$\{)', re.I)


def blank_comments(text):
    """The text with every // and /* */ comment replaced by spaces (newlines kept), strings left alone."""
    out, i, quote, n = list(text), 0, None, len(text)
    while i < n:
        ch = text[i]
        if quote:
            if ch == '\\': i += 2; continue
            if ch == quote or (ch == '\n' and quote != '`'): quote = None
        elif ch in '\'"`':
            quote = ch
        elif ch == '/' and i + 1 < n and text[i + 1] in '/*':
            end = text.find('\n', i) if text[i + 1] == '/' else text.find('*/', i + 2)
            end = n if end < 0 else end + (0 if text[i + 1] == '/' else 2)
            for j in range(i, end):
                if out[j] != '\n': out[j] = ' '
            i = end
            continue
        i += 1
    return ''.join(out)


def target_of(raw):
    """(target, dynamic, relative) of a written target, or None when it is not a screen of this app."""
    raw = raw.strip()
    if not raw or SCHEME.match(raw): return None
    dynamic = '${' in raw
    path = re.sub(r'(?::param)+', ':param', re.sub(r'\$\{[^}]*\}', ':param', raw))
    path = re.split(r'[?#]', path, 1)[0]
    if not path: return None
    return path, dynamic, not path.startswith('/')


def detect(context):
    text = blank_comments(context.text)
    found, seen = [], set()

    def add(offset, raw, via):
        parsed = target_of(raw)
        if not parsed: return
        target, dynamic, relative = parsed
        line = context.line_of(offset)
        if (line, target, via) in seen: return
        seen.add((line, target, via))
        found.append((offset, line, {'target': target, 'via': via, 'dynamic': dynamic, 'relative': relative,
                                     'symbol': context.symbol_at(line)}))

    for match in ATTRIBUTE.finditer(text):
        tag = TAG_BEFORE.search(text, max(0, match.start() - 400), match.start())
        if not tag: continue
        name = tag.group('tag').split('.')[-1]
        if match.group('attr') == 'href' and not match.group('target').startswith('/'): continue
        add(match.start(), match.group('target'), 'redirect' if name in REDIRECTS else 'link')
    for match in CALL.finditer(text):
        add(match.start(), match.group('target'), 'navigate')
    if MENU_FILE.search(context.rel):
        for match in MENU_ENTRY.finditer(text):
            if match.group('target').startswith('/'): add(match.start(), match.group('target'), 'menu')
    return sorted(found, key=lambda row: row[0])

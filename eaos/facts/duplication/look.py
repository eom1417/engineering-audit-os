"""The look as written (M15.4): every colour, font size, spacing, radius, shadow and z-index written outside the tokens
file, wherever it is written (a stylesheet, a `<style>` block, a style attribute, a JSX style object, a Tailwind
arbitrary value such as `text-[13px]`, a colour string in a script).

The tokens file is the home of the look: a stylesheet that declares custom properties (`--name: value`, eight or
more), an SCSS file of variables, or a theme file a script reads (tailwind.config, theme, tokens). What it holds is
never counted; a value elsewhere that names a token (`var(--accent)`, `theme.colors.x`) is not a value written.
"""
import re
from pathlib import Path

from ...core.contracts.code_laws import LOOK

STYLESHEETS = ('.css', '.scss', '.sass', '.less')
THEME_FILE = re.compile(r'(^|/)(tailwind\.config\.\w+|theme\.(js|ts|mjs|json)|tokens?\.(js|ts|mjs|json|css|scss)|_?variables\.(scss|less|css))$', re.I)
TOKENS_AT_LEAST = 8
COMMENT = re.compile(r'/\*.*?\*/', re.S)
DECLARATION = re.compile(r'(?<![\w-])(-?-?[A-Za-z][\w-]*)\s*:\s*([^;{}]+)')
CUSTOM = re.compile(r'(?<![\w-])(--[\w-]+|\$[\w-]+)\s*:')
STYLE_ATTRIBUTE = re.compile(r'\bstyle\s*=\s*"([^"]*)"|\bstyle\s*=\s*\'([^\']*)\'')
JSX_STYLE = re.compile(r'\bstyle\s*=\s*\{\{(.*?)\}\}', re.S)
JS_PAIR = re.compile(r'([A-Za-z]+)\s*:\s*(\'[^\']*\'|"[^"]*"|-?\d+(?:\.\d+)?)')
TAILWIND = re.compile(r'(?<![\w-])(?:[a-z]+:)*(text|bg|border(?:-[trblxyse])?|p[xytrblse]?|m[xytrblse]?|gap(?:-[xy])?|space-[xy]|'
                      r'rounded(?:-[a-z]+)?|shadow|z)-\[([^\]\s]+)\]')
COLOUR_STRING = re.compile(r'[\'"](#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|hsla?\([^)]*\))[\'"]')
HEX = r'#[0-9a-fA-F]{3,8}\b'
COLOUR = re.compile(HEX + r'|\b(?:rgba?|hsla?|oklch|oklab|lab|lch)\([^)]*\)|\b(?:white|black|red|green|blue|gray|grey|orange|yellow|'
                    r'purple|pink|brown|navy|teal|silver|maroon|olive|lime|aqua|fuchsia)\b', re.I)
LENGTH = re.compile(r'(?<![\w.-])-?(?:\d*\.)?\d+(?:px|rem|em|pt)\b')
NUMBER = re.compile(r'^-?\d+$')
# A CSS property (or a JSX style key) and the kind of the look it sets.
PROPERTY = [(re.compile(rx), kind) for rx, kind in (
    (r'^(color|background(-color)?|border(-(top|right|bottom|left|inline|block)(-(start|end))?)?(-color)?|outline(-color)?|fill|stroke|'
     r'accent-color|caret-color|text-decoration-color|backgroundColor|borderColor|outlineColor)$', 'color'),
    (r'^(font-size|fontSize)$', 'font_size'),
    (r'^(margin|padding)(-(top|right|bottom|left|inline|block)(-(start|end))?)?$|^(margin|padding)[A-Z]\w*$|^((row|column)-)?gap$|^(row|column)Gap$', 'spacing'),
    (r'^border(-(top|bottom)-(left|right)|-(start|end)-(start|end))?-radius$|^border\w*Radius$', 'radius'),
    (r'^(box-shadow|text-shadow|boxShadow|textShadow)$', 'shadow'),
    (r'^(z-index|zIndex)$', 'z_index'))]
TAILWIND_KIND = {'bg': 'color', 'border': 'color', 'rounded': 'radius', 'shadow': 'shadow', 'z': 'z_index', 'gap': 'spacing', 'space': 'spacing'}


def kind_of(name):
    return next((kind for pattern, kind in PROPERTY if pattern.match(name)), None)


def _shadow(value):
    return [re.sub(r'\s+', ' ', value.strip().lower())] if LENGTH.search(value) or COLOUR.search(value) else []


def _lengths(value):
    return [m.group(0).lower() for m in LENGTH.finditer(value) if float(re.sub(r'[a-z]+$', '', m.group(0))) != 0]


RAW = {'color': lambda value: [m.group(0).lower() for m in COLOUR.finditer(value)],
       'z_index': lambda value: [value.strip()] if NUMBER.match(value.strip()) and value.strip() not in ('0', '-1') else [],
       'shadow': _shadow}


def _raw(kind, value):
    """The literal values of the look in one declared value, tokens (var(), calc() over them) aside."""
    value = re.sub(r'var\([^()]*(\([^()]*\))?[^()]*\)|calc\([^()]*(\([^()]*\))?[^()]*\)|url\([^)]*\)', ' ', value)
    return RAW.get(kind, _lengths)(value)


def _line(text, offset): return text.count('\n', 0, offset) + 1


def declarations(text, first=0):
    """(kind, value, offset) of the look's literal values in CSS declarations; custom properties are tokens."""
    out = []
    for match in DECLARATION.finditer(COMMENT.sub(lambda m: ' ' * len(m.group(0)), text)):
        name = match.group(1)
        if name.startswith(('--', '$')): continue
        kind = kind_of(name)
        if kind: out += [(kind, value, first + match.start()) for value in _raw(kind, match.group(2))]
    return out


def _tailwind_kind(prefix, value):
    if prefix == 'text': return 'color' if COLOUR.search(value) else 'font_size'
    if prefix == 'border': return 'color' if COLOUR.search(value) else None       # a border's width, not its colour
    return TAILWIND_KIND.get(prefix, 'spacing')


def _tailwind(text):
    out = []
    for match in TAILWIND.finditer(text):
        prefix, value = match.group(1).split('-')[0], match.group(2).replace('_', ' ')
        kind = _tailwind_kind(prefix, value)
        if kind: out += [(kind, raw, match.start()) for raw in _raw(kind, value)]
    return out


def _jsx_styles(text):
    out = []
    for block in JSX_STYLE.finditer(text):
        for pair in JS_PAIR.finditer(block.group(1)):
            kind = kind_of(pair.group(1))
            value = pair.group(2).strip('\'"')
            if kind and NUMBER.match(value) and kind not in ('z_index',): value += 'px'   # React's unitless numbers are pixels
            if kind: out += [(kind, raw, block.start(1) + pair.start()) for raw in _raw(kind, value)]
    return out


def in_markup(text):
    """The look written in markup or a script: style attributes, JSX style objects, Tailwind arbitrary values."""
    found = []
    for match in STYLE_ATTRIBUTE.finditer(text):
        body = match.group(1) if match.group(1) is not None else match.group(2)
        found += declarations(body, match.start())
    return found + _jsx_styles(text) + _tailwind(text)


def in_script(text):
    """The look in a script: its markup's, and colour strings ('#1a2b3c', 'rgb(...)')."""
    return in_markup(text) + [('color', m.group(1).lower(), m.start()) for m in COLOUR_STRING.finditer(text)]


def is_tokens_file(path, text):
    """Whether a file is a home of the look: a theme file by name, or a stylesheet declaring its tokens."""
    if THEME_FILE.search(path): return True
    return Path(path).suffix in STYLESHEETS and len(CUSTOM.findall(text)) >= TOKENS_AT_LEAST


def in_page(text):
    """The look of a page or a component file (HTML, Vue, Svelte): its <style> blocks and its markup."""
    styles = [(m.start(1), m.group(1)) for m in re.finditer(r'<style\b[^>]*>(.*?)</style>', text, re.S)]
    return [row for start, body in styles for row in declarations(body, start)] + in_markup(text)


def _reader(path, language):
    suffix = Path(path).suffix.lower()
    if suffix in STYLESHEETS: return declarations
    if language in ('vue', 'svelte') or suffix in ('.html', '.htm'): return in_page
    return in_script if language in ('javascript', 'typescript', 'tsx') else None


def values(path, text, language):
    """[(kind, value, line)] of one file's look written outside the tokens file; [] for the tokens file itself."""
    read = _reader(path, language)
    if read is None or is_tokens_file(path, text): return []
    return [(kind, value, _line(text, offset)) for kind, value, offset in read(text) if kind in LOOK]

"""Raw values to tokens (M18.17, M18.18): every colour, size, corner and shadow a project writes by hand, in its stylesheets, style blocks, CSS-in-JS templates, inline
style objects and Tailwind's arbitrary values, becomes a variable of the same value, in one tokens file. No model is asked. A value is only named, so
nothing may look different: the style oracle proves it (eaos/live/behavior/look_oracle.py); `agreed`, what the person agreed to merge, moves a value to another.

    plan(root, tree, agreed)     {tokens: {value: name}, files: {path: new text}, uses: {kind: count}, home, refused}; nothing written
    apply(root, drawn)           the files written and the tokens file; the paths written
"""
import posixpath
import re
from collections import Counter
from pathlib import Path, PurePosixPath

from ...core.contracts.vocabulary import classify

STYLES = ('.css', '.scss', '.less')
BLOCKS = ('.html', '.vue', '.svelte', '.astro')
CODE = ('.js', '.jsx', '.ts', '.tsx', '.mjs')
SKIPPED = re.compile(r'(^|/)(node_modules|dist|build|out|\.next|vendor|third_party|public/assets|fixtures|coverage)(/|$)|\.min\.\w+$')
HOMES = ('tokens.css', 'variables.css', 'theme.css', 'vars.css')
GLOBAL = re.compile(r'(^|/)(globals?|index|app|main|styles?|base)\.(css|scss|less)$')
COMMENT = re.compile(r'/\*.*?\*/', re.S)
DECLARATION = re.compile(r'(?<![\w$-])(?P<prop>color|background(?:-color)?|border(?:-(?:top|right|bottom|left))?(?:-color)?|outline(?:-color)?|fill|stroke|box-shadow|font-size'
                         r'|padding(?:-(?:top|right|bottom|left))?|margin(?:-(?:top|right|bottom|left))?|gap|row-gap|column-gap|border(?:-[a-z]+){0,2}-radius)(?P<gap>\s*:\s*)(?P<value>[^;{}]+)')
HEX = re.compile(r'(?<![\w-])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b')
PX = re.compile(r'(?<![\w.#-])(?!0px)\d+(?:\.\d+)?px\b')
BLOCK = re.compile(r'(<style\b[^>]*>)(.*?)(</style>)', re.S | re.I)
TEMPLATE = re.compile(r'(?:styled(?:\.\w+|\([^)]*\))|\bcss|createGlobalStyle)`[^`]*`')
INLINE = re.compile(r'style=\{\{(.*?)\}\}', re.S)
INLINE_PAIR = re.compile(r"(?P<prop>[a-zA-Z]+)(?P<gap>\s*:\s*)(?P<quote>['\"])(?P<value>[^'\"]+)(?P=quote)")
TAILWIND = re.compile(r'(?<![\w-])(?P<prefix>bg|text|border|ring|fill|stroke|from|via|to|outline|p[xytrbl]?|m[xytrbl]?|gap(?:-[xy])?|rounded(?:-[a-z]+)?)-\[(?P<value>#[0-9a-fA-F]{3,8}|\d+(?:\.\d+)?px)\]')
TEXT_SIZE = 'text'


def _kind(prop):
    """The token kind a property's lengths are, None for one whose lengths are not a value of the look (a border's width)."""
    prop = prop.lower()
    if prop == 'font-size': return 'font-size'
    if 'radius' in prop: return 'radius'
    if prop.startswith(('padding', 'margin')) or prop.endswith('gap') or prop == 'gap': return 'spacing'
    return None


def _colour_role(prop):
    prop = prop.lower()
    if prop == 'color': return 'text'
    if prop.startswith('background'): return 'surface'
    if prop.startswith(('border', 'outline')): return 'border'
    return 'graphic'


def _normal(colour):
    colour = colour.lower()
    return '#' + ''.join(c * 2 for c in colour[1:]) if len(colour) == 4 else colour


def _camel(prop):
    return re.sub(r'[A-Z]', lambda m: '-' + m[0].lower(), prop)


class Namer:
    """Each distinct value once, named by its kind and how much it is used; `agreed` merges a value into another first."""

    def __init__(self, agreed):
        self.agreed, self.uses, self.names = {rule['from']: rule['to'] for rule in agreed or ()}, Counter(), {}

    def see(self, kind, value):
        value = _normal(value) if value.startswith('#') else value
        self.uses[(kind, self.agreed.get(value, value))] += 1

    def name(self, kind, value):
        value = _normal(value) if value.startswith('#') else value
        return self.names[(kind, self.agreed.get(value, value))]

    def settle(self):
        counters = Counter()
        for (kind, value), _ in self.uses.most_common():
            counters[kind] += 1
            self.names[(kind, value)] = f'--{kind}-{counters[kind]}'
        return {self.names[key]: key[1] for key in self.names}


def _shadow_value(value):
    return value.strip().rstrip(';').strip()


def _rewrite_value(prop, value, namer, naming):
    """`value` with what a token names replaced, or told to `namer` on its first read (naming False)."""
    if 'var(' in value or '$' in value or '@' in value or 'calc(' in value: return value
    def colour(match):
        if not naming: namer.see(f'color-{_colour_role(prop)}', match[0])
        return f"var({namer.name(f'color-{_colour_role(prop)}', match[0])})" if naming else match[0]
    kind = _kind(prop)
    def length(match):
        if not naming: namer.see(kind, match[0])
        return f'var({namer.name(kind, match[0])})' if naming else match[0]
    if prop.lower() == 'box-shadow' and value.strip() not in ('none', 'inherit'):
        whole = _shadow_value(value)
        if not naming: namer.see('shadow', whole)
        return value.replace(whole, f"var({namer.name('shadow', whole)})") if naming else value
    value = HEX.sub(colour, value)
    return PX.sub(length, value) if kind else value


def _in_css(text, namer, naming):
    """A stylesheet's text with its declarations named; comments, and a variable's own declaration, stay."""
    spans = [match.span() for match in COMMENT.finditer(text)]
    def one(match):
        if any(start <= match.start() < end for start, end in spans): return match[0]
        return f"{match['prop']}{match['gap']}{_rewrite_value(match['prop'], match['value'], namer, naming)}"
    return DECLARATION.sub(one, text)


def _in_code(text, namer, naming):
    """A script's CSS-in-JS templates, inline style objects and Tailwind's arbitrary values named."""
    text = TEMPLATE.sub(lambda match: _in_css(match[0], namer, naming), text)
    text = INLINE.sub(lambda match: 'style={{' + INLINE_PAIR.sub(lambda pair: _inline_pair(pair, namer, naming), match[1]) + '}}', text)
    return _in_tailwind(text, namer, naming)


def _inline_pair(pair, namer, naming):
    prop = _camel(pair['prop'])
    if not DECLARATION.fullmatch(f"{prop}: {pair['value']}"): return pair[0]
    return f"{pair['prop']}{pair['gap']}{pair['quote']}{_rewrite_value(prop, pair['value'], namer, naming)}{pair['quote']}"


TAILWIND_PROPS = {'bg': 'background', 'text': 'color', 'border': 'border-color', 'ring': 'border-color', 'outline': 'outline-color', 'fill': 'fill', 'stroke': 'stroke', 'from': 'background', 'via': 'background', 'to': 'background'}


def _tailwind_one(match, namer, naming):
    prefix, value = match['prefix'], match['value']
    if value.startswith('#'):
        kind = f"color-{_colour_role(TAILWIND_PROPS.get(prefix, 'background'))}"
        if not naming: namer.see(kind, value)
        return f'{prefix}-[var({namer.name(kind, value)})]' if naming else match[0]
    kind = 'font-size' if prefix == TEXT_SIZE else 'radius' if prefix.startswith('rounded') else 'spacing'
    if not naming: namer.see(kind, value)
    if not naming: return match[0]
    hint = 'length:' if prefix == TEXT_SIZE else ''
    return f'{prefix}-[{hint}var({namer.name(kind, value)})]'


def _in_tailwind(text, namer, naming):
    return TAILWIND.sub(lambda match: _tailwind_one(match, namer, naming), text)


def _in_block(text, namer, naming):
    return BLOCK.sub(lambda match: match[1] + _in_css(match[2], namer, naming) + match[3], text)


def _reader(path):
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in STYLES: return _in_css
    if suffix in CODE: return _in_code
    if suffix in BLOCKS: return lambda text, namer, naming: _in_tailwind(_in_block(text, namer, naming), namer, naming)
    return None


def _candidates(root, tree):
    """{path: text} of the files a value may be written in: neither a test, nor data, nor what a build makes, nor a tokens file."""
    found = {}
    for path in sorted(tree):
        if SKIPPED.search(path) or classify(path) == 'test' or PurePosixPath(path).name in HOMES or not _reader(path): continue
        try: found[path] = (Path(root) / path).read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError): continue
    return found


def _home(tree, edited):
    """(the tokens file, whether it exists): the project's, else beside its main stylesheet, else beside the first it edited."""
    existing = next((path for path in sorted(tree) if PurePosixPath(path).name in HOMES and not SKIPPED.search(path)), None)
    if existing: return existing, True
    sheets = _mains(tree) + [path for path in edited if PurePosixPath(path).suffix.lower() in STYLES]
    return (posixpath.join(posixpath.dirname(sheets[0]), 'tokens.css'), False) if sheets else (None, False)


def _mains(tree):
    """The project's main stylesheets, the shallowest first."""
    return sorted((path for path in tree if GLOBAL.search(path) and not SKIPPED.search(path)), key=lambda path: path.count('/'))


def _sheets_to_load(tree, edited, home):
    """The stylesheets that must import the tokens file: the edited ones, else the project's main one."""
    sheets = [path for path in edited if PurePosixPath(path).suffix.lower() in STYLES]
    return sheets or [path for path in sorted(tree) if GLOBAL.search(path) and not SKIPPED.search(path)][:1]


def _with_import(text, sheet, home):
    """`text` with the tokens file imported, after the lines a stylesheet must start with."""
    line = f'@import "{posixpath.relpath(home, posixpath.dirname(sheet) or ".")}";'
    if not line.split('"')[1].startswith('.'): line = line.replace('"', '"./', 1)
    if line in text: return text
    head = re.match(r'(?:\s*(?:@charset|@use|@forward)[^;]*;)*', text)
    return text[:head.end()] + ('\n' if head.end() else '') + line + '\n' + text[head.end():]


def _root_block(tokens):
    return ':root {\n' + ''.join(f'  {name}: {value};\n' for name, value in tokens.items()) + '}\n'


def _in_page(files, root, tree, root_block):
    """Where no stylesheet can load a tokens file (CSS in JS): its page holds the tokens, in its own style block or a new one. The path, or None."""
    pages = [path for path in sorted(tree) if PurePosixPath(path).suffix.lower() == '.html' and not SKIPPED.search(path)]
    for path in pages:
        text = files.get(path) if path in files else (Path(root) / path).read_text(encoding='utf-8')
        if BLOCK.search(text): files[path] = BLOCK.sub(lambda match: match[1] + root_block + match[2] + match[3], text, count=1)
        elif re.search(r'</head>', text, re.I): files[path] = re.sub(r'</head>', lambda _: f'<style>{root_block}</style></head>', text, count=1, flags=re.I)
        else: continue
        return path
    return None


def plan(root, tree, agreed=None):
    tree = set(tree)
    namer, texts = Namer(agreed), _candidates(root, tree)
    for path, text in texts.items(): _reader(path)(text, namer, False)
    tokens = namer.settle()
    files = {path: new for path, text in texts.items() if (new := _reader(path)(text, namer, True)) != text}
    uses = Counter()
    for (kind, _), count in namer.uses.items(): uses[kind.split('-')[0] if kind.startswith('color') else kind] += count
    drawn = {'tokens': tokens, 'files': files, 'uses': dict(uses), 'home': None, 'home_exists': False, 'refused': None}
    return _placed(drawn, root, tree) if tokens else {**drawn, 'refused': 'no value of the look is written by hand'}


def _placed(drawn, root, tree):
    files, block = drawn['files'], _root_block(drawn['tokens'])
    home, exists = _home(tree, list(files))
    if not home:
        page = _in_page(files, root, tree, block)
        return {**drawn, 'home': page, 'refused': None if page else 'no stylesheet of the project could load the tokens file'}
    for sheet in _sheets_to_load(tree, list(files), home):
        text = files.get(sheet) if sheet in files else (Path(root) / sheet).read_text(encoding='utf-8')
        files[sheet] = _with_import(text, sheet, home)
    return {**drawn, 'home': home, 'home_exists': exists}


def apply(root, drawn):
    root, written = Path(root), []
    for path, text in drawn['files'].items():
        (root / path).write_text(text, encoding='utf-8')
        written.append(path)
    if drawn['home'] and drawn['home'] not in drawn['files']:
        home = root / drawn['home']
        home.parent.mkdir(parents=True, exist_ok=True)
        before = home.read_text(encoding='utf-8') + '\n' if home.is_file() else ''
        home.write_text(before + _root_block(drawn['tokens']), encoding='utf-8')
        written.append(drawn['home'])
    return written

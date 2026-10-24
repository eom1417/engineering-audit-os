"""The Markdown of the four reports a client reads first (eaos/report/four_reports.py): a page with a blank line around
every block, prose wrapped at 80 columns, and every text from the project escaped, so it stays literal."""
import re
import textwrap

WIDTH = 80
CODE_SPAN = re.compile(r'(`[^`]*`)')


def escape(text):
    """Text from the project (identifiers, paths, titles) is literal in Markdown: `_x_` and `*x*` are not
    emphasis, `<T>` is not HTML. Code spans stay as written; a span cut open by clip() is closed."""
    text = str(text)
    if text.count('`') % 2: text += '`'
    return ''.join(part if CODE_SPAN.fullmatch(part) else re.sub(r'([_*<>])', r'\\\1', part)
                   for part in CODE_SPAN.split(text))


LEADING_MARKER = re.compile(r'^(\s*)(#|[-+>]\s|\d+[.)]\s)')


def wrap(text, **indents):
    """Wrapped lines, none of which starts with a Markdown marker the text did not mean: a line that wraps onto
    `#`, `- ` or `3. ` would turn into a heading or a list."""
    lines = textwrap.wrap(escape(text), WIDTH, break_long_words=False, break_on_hyphens=False, **indents)
    first = len(indents.get('initial_indent', ''))
    return [line if index == 0 and first else LEADING_MARKER.sub(lambda m: m.group(1) + '\\' + m.group(2), line, count=1)
            for index, line in enumerate(lines)]


class Page:
    """Markdown with a blank line around every block, prose wrapped at 80 columns, every text escaped."""

    def __init__(self, title):
        self.lines = [f'# {title}']

    def heading(self, text, level=2):
        self.lines += ['', '#' * level + ' ' + escape(text)]

    def para(self, text):
        self.lines += [''] + wrap(text)

    def items(self, rows):
        if not rows: return
        self.lines.append('')
        for row in rows:
            self.lines += wrap(row, initial_indent='- ', subsequent_indent='  ') or ['-']

    def block(self, language, text):
        self.lines += ['', f'```{language}', *text.rstrip().splitlines(), '```']

    def text(self):
        return '\n'.join(self.lines) + '\n'


def clip(text, n):
    """A text cut to n characters shows that it was cut."""
    text = ' '.join(str(text).split())
    return text if len(text) <= n else text[:n - 1].rstrip() + '…'

"""A document model with explicit size budgets, so a report stays readable by construction."""
from .labels import labels

MERMAID_SAFE = str.maketrans({'"': "'", '<': '(', '>': ')', '\n': ' ', '|': '/'})


def safe(text): return str(text).translate(MERMAID_SAFE)


class Document:
    """Sections render in order; tables truncate against a declared budget instead of overflowing."""

    def __init__(self, title, language='ar', budget_lines=None):
        self.title, self.language, self.budget_lines = title, language, budget_lines
        self.words = labels(language)
        self.blocks = [('title', title)]
        self.truncations = []

    def header(self, rows):
        self.blocks.append(('header', [row for row in rows if row]))
        return self

    def section(self, heading, level=2):
        self.blocks.append(('heading', (heading, level)))
        return self

    def text(self, body):
        if body: self.blocks.append(('text', body))
        return self

    def bullets(self, items):
        items = [item for item in items if item]
        self.blocks.append(('bullets', items) if items else ('text', self.words['no_rows']))
        return self

    def table(self, headers, rows, limit=None):
        rows = [[('' if cell is None else str(cell)) for cell in row] for row in rows]
        if not rows:
            self.blocks.append(('text', self.words['no_rows']))
            return self
        shown = rows if limit is None or len(rows) <= limit else rows[:limit]
        self.blocks.append(('table', (headers, shown)))
        if len(shown) < len(rows):
            note = self.words['truncated'] % {'shown': len(shown), 'total': len(rows)}
            self.truncations.append(note)
            self.blocks.append(('text', note))
        return self

    def mermaid(self, lines):
        self.blocks.append(('mermaid', lines))
        return self

    def render(self):
        out = []
        for kind, payload in self.blocks:
            if kind == 'title': out += ['# ' + payload, '']
            elif kind == 'header': out += ['> ' + row for row in payload] + ['']
            elif kind == 'heading': out += ['#' * payload[1] + ' ' + payload[0], '']
            elif kind == 'text': out += [payload, '']
            elif kind == 'bullets': out += ['- ' + item for item in payload] + ['']
            elif kind == 'mermaid': out += ['```mermaid'] + payload + ['```', '']
            elif kind == 'table':
                headers, rows = payload
                out += ['| ' + ' | '.join(headers) + ' |', '|' + '---|' * len(headers)]
                out += ['| ' + ' | '.join(cell.replace('|', '\\|') for cell in row) + ' |' for row in rows]
                out += ['']
        text = '\n'.join(out).rstrip() + '\n'
        if self.budget_lines and text.count('\n') > self.budget_lines:
            raise ValueError(f'{self.title}: rendered {text.count(chr(10))} lines over a budget of {self.budget_lines}; move detail into records')
        return text

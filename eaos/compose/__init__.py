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
        self.blocks.append(('table', (headers, shown, len(rows))))
        self._note(len(self.blocks) - 1)
        return self

    def _note(self, index):
        """Keep the 'showing N of M' line beside its own table, so trimming never loses the real total."""
        _, shown, total = self.blocks[index][1]
        after = index + 1
        if after < len(self.blocks) and self.blocks[after][0] == 'note':
            self.truncations.remove(self.blocks[after][1])
            del self.blocks[after]
        if len(shown) < total:
            note = self.words['truncated'] % {'shown': len(shown), 'total': total}
            self.truncations.append(note)
            self.blocks.insert(after, ('note', note))

    def mermaid(self, lines):
        self.blocks.append(('mermaid', lines))
        return self

    def _emit(self):
        out = []
        for kind, payload in self.blocks:
            if kind == 'title': out += ['# ' + payload, '']
            elif kind == 'header': out += ['> ' + row for row in payload] + ['']
            elif kind == 'heading': out += ['#' * payload[1] + ' ' + payload[0], '']
            elif kind in ('text', 'note'): out += [payload, '']
            elif kind == 'bullets': out += ['- ' + item for item in payload] + ['']
            elif kind == 'mermaid': out += ['```mermaid'] + payload + ['```', '']
            elif kind == 'table':
                headers, rows = payload[0], payload[1]
                out += ['| ' + ' | '.join(headers) + ' |', '|' + '---|' * len(headers)]
                out += ['| ' + ' | '.join(cell.replace('|', '\\|') for cell in row) + ' |' for row in rows]
                out += ['']
        return '\n'.join(out).rstrip() + '\n'

    def _longest_table(self):
        candidates = [index for index, (kind, payload) in enumerate(self.blocks)
                      if kind == 'table' and len(payload[1]) > 1]
        return max(candidates, key=lambda index: len(self.blocks[index][1][1])) if candidates else None

    def render(self):
        """Render, trimming the longest table until the budget holds; trimmed rows stay in the JSON records."""
        text = self._emit()
        while self.budget_lines and text.count('\n') > self.budget_lines:
            overflow = text.count('\n') - self.budget_lines
            index = self._longest_table()
            if index is None:
                raise ValueError(f'{self.title}: rendered {text.count(chr(10))} lines over a budget of '
                                 f'{self.budget_lines} with no table left to trim; move detail into records')
            headers, shown, total = self.blocks[index][1]
            keep = max(1, min(len(shown) - 1, len(shown) - overflow - 2))
            self.blocks[index] = ('table', (headers, shown[:keep], total))
            self._note(index)
            text = self._emit()
        return text

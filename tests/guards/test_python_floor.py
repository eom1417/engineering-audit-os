"""EAOS keeps the oldest Python it declares (pyproject.toml, requires-python): no syntax or module newer than that in
what it ships."""
import ast
import io
import sys
import tokenize
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHIPPED = [path for path in (ROOT / 'eaos').rglob('*.py') if path.relative_to(ROOT).parts[1] not in ('templates', 'rules')]
HOME_OF_TOML = ROOT / 'eaos/core/system/files.py'


def _reused_quotes(text):
    """The lines of an f-string that reuse its own quote inside itself: syntax only Python 3.12 reads."""
    open_quotes, lines = [], set()
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.FSTRING_START:
            quote = token.string.lstrip('rRfFbBuU')
            if quote in open_quotes: lines.add(token.start[0])
            open_quotes.append(quote)
        elif token.type == tokenize.FSTRING_END: open_quotes.pop()
        elif token.type == tokenize.STRING and open_quotes and token.string.lstrip('rRbBuU')[0] in open_quotes:
            lines.add(token.start[0])
    return lines


class TheOldestPythonDeclared(unittest.TestCase):
    @unittest.skipUnless(sys.version_info >= (3, 12), 'only Python 3.12 reads such an f-string to find it')
    def test_no_f_string_reuses_its_own_quote(self):
        found = {str(path.relative_to(ROOT)): lines for path in SHIPPED if (lines := _reused_quotes(path.read_text(encoding='utf-8')))}
        self.assertEqual(found, {})

    def test_toml_is_read_through_its_one_home_which_works_on_every_declared_python(self):
        found = [str(path.relative_to(ROOT)) for path in SHIPPED if path != HOME_OF_TOML
                 for node in ast.walk(ast.parse(path.read_text(encoding='utf-8')))
                 if isinstance(node, ast.ImportFrom) and node.module == 'tomllib'
                 or isinstance(node, ast.Import) and any(alias.name == 'tomllib' for alias in node.names)]
        self.assertEqual(found, [])


if __name__ == '__main__':
    unittest.main()

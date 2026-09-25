"""A fact's line is the line of the declaration it names, not the blank line before it."""
import re
from pathlib import Path

from shared_fixture import Workspace

from eaos.facts import domain
from eaos.facts.frameworks import go_cli, library_api, manifests, python_cli, python_jobs, python_web


def line_of(pattern, text):
    match = pattern.search(text)
    return text.count('\n', 0, match.start()) + 1


class DeclarationLineTests(Workspace):
    def test_a_declaration_after_blank_lines_is_found_on_its_own_line(self):
        cases = [(domain.TS_MODEL, 'export interface Vendor {\n  email: string;\n}'),
                 (domain.JS_CONST, 'export const API_URL = "/api";'),
                 (domain.ORM_MODEL, 'class User(Base):\n    pass'),
                 (library_api.JS_EXPORT, 'export function run() {}'),
                 (library_api.JS_REEXPORT, 'export { run } from "./run";'),
                 (library_api.PY_REEXPORT, 'from .core import run'),
                 (python_web.DECORATOR, '@app.get("/health")\ndef health(): pass'),
                 (python_web.DJANGO, 'path("users/", views.users),'),
                 (python_cli.CLICK, '@click.command("sync")\ndef sync(): pass'),
                 (python_jobs.TASK, '@shared_task\ndef job(): pass'),
                 (go_cli.FUNC_MAIN, 'func main() {'),
                 (manifests.DOCKER, 'CMD ["python", "app.py"]')]
        for pattern, declaration in cases:
            self.assertEqual(line_of(pattern, 'first = 1\n\n\n' + declaration + '\n'), 4, pattern.pattern)

    def test_every_multiline_pattern_starts_within_its_own_line(self):
        """`^\\s*` under re.M crosses newlines, so the match starts on the blank line before the declaration."""
        root = Path(domain.__file__).resolve().parent
        offenders = []
        for path in sorted(root.rglob('*.py')):
            for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                if 're.M' in line and re.search(r"re\.compile\(r?['\"]\^\\s\*", line):
                    offenders.append(f'{path.name}:{number}')
        self.assertEqual(offenders, [])

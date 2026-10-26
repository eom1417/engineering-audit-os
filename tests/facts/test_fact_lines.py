"""A fact's line is the line of the declaration it names, not the blank line before it."""
import unittest
import re
from pathlib import Path

from shared_fixture import Workspace

from eaos.facts.domain import model as domain
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
        # `^\s*` under re.M crosses newlines, so the match would start on the blank line before the declaration.
        root = Path(domain.__file__).resolve().parent
        offenders = []
        for path in sorted(root.rglob('*.py')):
            for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                if 're.M' in line and re.search(r"re\.compile\(r?['\"]\^\\s\*", line):
                    offenders.append(f'{path.name}:{number}')
        self.assertEqual(offenders, [])


class StarletteRouteTests(unittest.TestCase):
    def test_starlette_route_objects_are_http_entry_points_with_their_methods(self):
        # Found on EAOS's own server: its /api routes are Route(...) objects, and no route was found, so no load test ran.
        from eaos.facts.code.entrypoints import Context
        text = ("from starlette.routing import Route\n"
                "routes = [Route('/api/runs', runs, methods=['GET', 'POST']), Route('/health', health)]\n")
        found = python_web.detect(Context('app/server.py', text, 'python', []))
        self.assertEqual([(f['http_method'], f['route'], f['framework']) for f in found],
                         [('GET', '/api/runs', 'starlette'), ('POST', '/api/runs', 'starlette'), ('GET', '/health', 'starlette')])

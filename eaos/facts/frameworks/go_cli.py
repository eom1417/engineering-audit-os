"""Go `package main` + `func main()` is the binary's entry point.

We surface it as `cli/main` so a reader can see the program has a binary
even when no command-line library is in use; without it `cmd/.../main.go`
files are invisible to the report.
"""
import re

LANGUAGES = ('go',)
PACKAGE_MAIN = re.compile(r'^\s*package\s+main\b', re.M)
FUNC_MAIN = re.compile(r'^\s*func\s+main\s*\(\s*\)\s*\{', re.M)


def detect(context):
    found = []
    if not PACKAGE_MAIN.search(context.text): return found
    func = FUNC_MAIN.search(context.text)
    if not func: return found
    line = context.line_of(func.start())
    found.append({'surface': 'cli',
                  'route': context.rel.rsplit('/', 1)[-1].removesuffix('.go'),
                  'http_method': None,
                  'handler': 'main',
                  'framework': 'go_main',
                  'line': line})
    return found

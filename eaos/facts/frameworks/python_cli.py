"""argparse and click command surfaces."""
import re

LANGUAGES = ('python',)
SUBPARSER = re.compile(r'add_parser\(\s*(?P<quote>[\'"])(?P<name>[^\'"]+)(?P=quote)', re.M)
DYNAMIC = re.compile(r'add_parser\(\s*(?P<expr>[A-Za-z_][\w.\[\]]*)\s*[,)]', re.M)
CLICK = re.compile(r'^\s*@(?:click|typer|app)\.(?:command|group)\((?:\s*(?P<quote>[\'"])(?P<name>[^\'"]*)(?P=quote))?', re.M)
PARSER = re.compile(r'ArgumentParser\(\s*(?:prog\s*=\s*(?P<quote>[\'"])(?P<prog>[^\'"]+)(?P=quote))?')


def detect(context):
    found = []
    root = PARSER.search(context.text)
    if root:
        line = context.line_of(root.start())
        found.append({'surface': 'cli', 'route': root.group('prog') or context.rel.rsplit('/', 1)[-1].removesuffix('.py'),
                      'http_method': None, 'handler': context.symbol_at(line), 'framework': 'argparse', 'line': line})
    for match in SUBPARSER.finditer(context.text):
        line = context.line_of(match.start())
        found.append({'surface': 'cli', 'route': match.group('name'), 'http_method': None,
                      'handler': context.symbol_at(line), 'framework': 'argparse', 'line': line})
    for match in DYNAMIC.finditer(context.text):
        line = context.line_of(match.start())
        # A command name computed at runtime is a visible gap, not a silent omission.
        found.append({'surface': 'cli', 'route': None, 'http_method': None, 'handler': context.symbol_at(line),
                      'framework': 'argparse_dynamic', 'line': line, 'note': 'Command name is built at runtime from ' + match.group('expr')})
    for match in CLICK.finditer(context.text):
        line = context.line_of(match.start())
        handler = context.symbol_after(line)
        found.append({'surface': 'cli', 'route': match.group('name') or handler, 'http_method': None,
                      'handler': handler, 'framework': 'click', 'line': line})
    return found

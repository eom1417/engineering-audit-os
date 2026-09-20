"""argparse and click command surfaces."""
import re

LANGUAGES = ('python',)
SUBPARSER = re.compile(r'add_parser\(\s*(?P<quote>[\'"])(?P<name>[^\'"]+)(?P=quote)', re.M)
# argparse dispatches through set_defaults(func=...); without binding it, every command traces to
# the same parser function and the real handlers are never reached.
HANDLER = re.compile(r'set_defaults\(\s*func\s*=\s*(?P<handler>[A-Za-z_]\w*)')
LOOP_PAIRS = re.compile(r'for\s+\w+\s*,\s*(?P<variable>\w+)\s+in\s*\[(?P<pairs>[^\]]*)\]')
PAIR = re.compile(r'\(\s*[\'"](?P<name>[^\'"]+)[\'"]\s*,\s*(?P<handler>[A-Za-z_]\w*)\s*\)')
DYNAMIC = re.compile(r'add_parser\(\s*(?P<expr>[A-Za-z_][\w.\[\]]*)\s*[,)]', re.M)
CLICK = re.compile(r'^\s*@(?:click|typer|app)\.(?:command|group)\((?:\s*(?P<quote>[\'"])(?P<name>[^\'"]*)(?P=quote))?', re.M)
PARSER = re.compile(r'ArgumentParser\(\s*(?:prog\s*=\s*(?P<quote>[\'"])(?P<prog>[^\'"]+)(?P=quote))?')


def bound_handler(text, position, window=700):
    match = HANDLER.search(text, position, position + window)
    return match.group('handler') if match else None


def loop_commands(text):
    """Commands registered from a literal list of (name, handler) pairs."""
    found = []
    for loop in LOOP_PAIRS.finditer(text):
        if not HANDLER.search(text, loop.end(), loop.end() + 700): continue
        for pair in PAIR.finditer(loop.group('pairs')):
            found.append((pair.group('name'), pair.group('handler'), text.count('\n', 0, loop.start()) + 1))
    return found


def detect(context):
    found = []
    root = PARSER.search(context.text)
    if root:
        line = context.line_of(root.start())
        found.append({'surface': 'cli', 'route': root.group('prog') or context.rel.rsplit('/', 1)[-1].removesuffix('.py'),
                      'http_method': None, 'handler': context.symbol_at(line), 'framework': 'argparse', 'line': line})
    for match in SUBPARSER.finditer(context.text):
        line = context.line_of(match.start())
        handler = bound_handler(context.text, match.end())
        found.append({'surface': 'cli', 'route': match.group('name'), 'http_method': None,
                      'handler': handler or context.symbol_at(line), 'framework': 'argparse', 'line': line})
    for name, handler, line in loop_commands(context.text):
        found.append({'surface': 'cli', 'route': name, 'http_method': None, 'handler': handler,
                      'framework': 'argparse', 'line': line})
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

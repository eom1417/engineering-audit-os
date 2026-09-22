"""net/http, gorilla/mux, gin and chi route surfaces."""
import re

LANGUAGES = ('go',)
HANDLE = re.compile(r'\b(?:http|mux|r|router|e|app)\.(?P<method>HandleFunc|Handle|GET|POST|PUT|PATCH|DELETE)\(\s*"(?P<route>[^"]*)"\s*,\s*(?P<handler>[\w.]+)?', re.M)


def _strip_comments(text):
    """Strip Go line comments so the detector does not match example code in comments.

    Go has no block comments in the lexical sense (tree-sitter does, but the detector
    works on raw text); removing `// ...` lines is enough to drop every false positive
    we have observed in real codebases.
    """
    return '\n'.join('' if line.lstrip().startswith('//') else line for line in text.split('\n'))


def detect(context):
    found = []
    cleaned = _strip_comments(context.text)
    for match in HANDLE.finditer(cleaned):
        line = context.line_of(match.start())
        method = match.group('method')
        found.append({'surface': 'http', 'route': match.group('route'),
                      'http_method': 'ANY' if method in {'HandleFunc', 'Handle'} else method,
                      'handler': match.group('handler'), 'framework': 'go_http', 'line': line})
    return found

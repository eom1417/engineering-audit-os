"""net/http, gorilla/mux, gin and chi route surfaces."""
import re

LANGUAGES = ('go',)
HANDLE = re.compile(r'\b(?:http|mux|r|router|e|app)\.(?P<method>HandleFunc|Handle|GET|POST|PUT|PATCH|DELETE)\(\s*"(?P<route>[^"]*)"\s*,\s*(?P<handler>[\w.]+)?', re.M)


def detect(context):
    found = []
    for match in HANDLE.finditer(context.text):
        line = context.line_of(match.start())
        method = match.group('method')
        found.append({'surface': 'http', 'route': match.group('route'),
                      'http_method': 'ANY' if method in {'HandleFunc', 'Handle'} else method,
                      'handler': match.group('handler'), 'framework': 'go_http', 'line': line})
    return found

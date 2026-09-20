"""Spring and JAX-RS route surfaces."""
import re

LANGUAGES = ('java', 'kotlin')
MAPPING = re.compile(r'@(?P<kind>Get|Post|Put|Patch|Delete|Request)Mapping\(\s*(?:value\s*=\s*)?(?:"(?P<route>[^"]*)")?', re.M)
JAXRS = re.compile(r'@Path\(\s*"(?P<route>[^"]*)"\s*\)', re.M)


def detect(context):
    found = []
    for match in MAPPING.finditer(context.text):
        line = context.line_of(match.start())
        kind = match.group('kind')
        found.append({'surface': 'http', 'route': match.group('route') or '/', 
                      'http_method': 'ANY' if kind == 'Request' else kind.upper(),
                      'handler': context.symbol_after(line), 'framework': 'spring', 'line': line})
    for match in JAXRS.finditer(context.text):
        line = context.line_of(match.start())
        found.append({'surface': 'http', 'route': match.group('route'), 'http_method': 'ANY',
                      'handler': context.symbol_after(line), 'framework': 'jaxrs', 'line': line})
    return found

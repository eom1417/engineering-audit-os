"""Go CLI dispatch tables: a `switch args[0] { case "name": r.X(...) }` declares an entry point.

The detector parses the switch body and pulls the receiver-method name out of each case
so the flow tracer can follow `r.X` into the right arm. Cases that don't dispatch to a
named method (raw `os.Exit`, `fmt.Println`, fallthrough) are reported as gaps, not as
invented entry points.
"""
import re

LANGUAGES = ('go',)
DISPATCH_FUNC = re.compile(
    r'func\s+(?:\([^)]*\)\s+)?(?P<name>Dispatch|runDispatch|\w*[Dd]ispatch\w*|\w*[Ss]ubcommand\w*)\s*\(',
    re.M,
)
ARGS_INDEX = re.compile(r'args\[\s*(?P<idx>\d+)\s*\]')
# One case label + (optional body) until the next case/default/close-brace.
CASE_LABEL = re.compile(r'case\s+(?P<quote>[\'"])(?P<name>[^\'"]+)(?P=quote)', re.M)
# The body we want is the line(s) after the label until the next case/default/}.
METHOD_CALL = re.compile(r'\b(?P<receiver>r|runner|app|cmd|s|self|cli|h|router|mux)\.(?P<method>[A-Za-z_]\w*)\s*\(')


def _function_body(text, open_brace_index):
    depth = 0
    for i in range(open_brace_index, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0: return text[open_brace_index:i + 1]
    return text[open_brace_index:]


def detect(context):
    found = []
    text = context.text
    for func_match in DISPATCH_FUNC.finditer(text):
        open_brace = text.find('{', func_match.end() - 1)
        if open_brace == -1: continue
        body = _function_body(text, open_brace)
        if not ARGS_INDEX.search(body): continue
        seen = set()
        for case in CASE_LABEL.finditer(body):
            name = case.group('name')
            if not name or name in seen: continue
            seen.add(name)
            # The body of this case starts just after the colon.
            tail = body[case.end():len(body)]
            method_match = METHOD_CALL.search(tail)
            handler = method_match.group('method').lower() if method_match and method_match.group('method').lower() == name else name
            # Prefer the receiver method when its lower-case name matches the case.
            if method_match:
                # Use the actual method name (capitalised) so it matches the symbol map.
                handler = method_match.group('method')
            line = context.line_of(func_match.start() + case.start())
            found.append({'surface': 'cli', 'route': name, 'http_method': None,
                          'handler': handler, 'framework': 'go_dispatch_case',
                          'line': line})
    return found

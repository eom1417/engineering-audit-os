"""Detect Supabase client calls in TypeScript and JavaScript."""
import re

LANGUAGES = ('javascript', 'typescript', 'tsx')
FACT_KIND = 'data_access'

# A `.from(...)` followed by a data verb is a Supabase table access. Whitespace (including newlines)
# is allowed between `.from(...)` and the verb because the chain is often split across lines:
# `supabase.from("x")` on one line and `.select(...)` on the next. A `.from(...)` not followed by
# one of these verbs is a different chain (typically storage) and is reported by its own matcher
# below.
TABLE_CALL = re.compile(r'''\.from\s*\(\s*(?P<q>['"`])(?P<target>[^'"`]+)(?P=q)\s*\)\s*\.\s*(?P<op>select|insert|update|upsert|delete)\b''')
RPC_CALL = re.compile(r'''\.rpc\s*\(\s*(?P<q>['"`])(?P<target>[^'"`]+)(?P=q)''')
STORAGE_CALL = re.compile(r'''\.storage\.from\s*\(\s*(?P<q>['"`])(?P<target>[^'"`]+)(?P=q)''')
AUTH_CALL = re.compile(r'''\.auth\.(?P<op>signIn|signOut|signUp|signInWithPassword|signInWithOAuth|getSession|getUser|resetPasswordForEmail|updateUser|onAuthStateChange)\b''')
SB_NAME = re.compile(r'''\b[A-Za-z_$][\w$]*[Ss]upabase\b|\bsupabase\b''')


def _line_of(text, offset):
    """1-based line number for the offset within ``text``."""
    return text.count('\n', 0, offset) + 1


def _supabase_prefix(text, end):
    """Return the expression to the left of ``end`` if it contains a Supabase-flavored name.

    Newlines are not treated as boundaries: the chain is often split across lines
    (``supabase\\n  .from(...)``). The detector still walks back to the start of the statement
    (``;``, ``{``, ``}``, ``=``) so a Supabase identifier mentioned in an unrelated statement on
    an earlier line cannot make a non-Supabase chain look like one.
    """
    boundaries = (';', '{', '}', '=')
    start = end
    for index in range(end - 1, max(-1, end - 500), -1):
        if text[index] in boundaries:
            start = index + 1
            break
    else:
        start = max(0, end - 500)
    return text[start:end] if SB_NAME.search(text[start:end]) else None


def extract_calls(text):
    """Yield (offset, line, call_record) for every Supabase call matched in ``text``."""
    for match in TABLE_CALL.finditer(text):
        if _supabase_prefix(text, match.start()) is None: continue
        yield match.start(), _line_of(text, match.start()), \
            {'client': 'supabase', 'target': match.group('target'),
             'operation': match.group('op'), 'symbol': 'from'}
    for match in RPC_CALL.finditer(text):
        if _supabase_prefix(text, match.start()) is None: continue
        yield match.start(), _line_of(text, match.start()), \
            {'client': 'supabase', 'target': match.group('target'), 'operation': 'rpc', 'symbol': 'rpc'}
    for match in STORAGE_CALL.finditer(text):
        if _supabase_prefix(text, match.start()) is None: continue
        yield match.start(), _line_of(text, match.start()), \
            {'client': 'supabase', 'target': match.group('target'), 'operation': 'storage', 'symbol': 'storage'}
    for match in AUTH_CALL.finditer(text):
        if _supabase_prefix(text, match.start()) is None: continue
        yield match.start(), _line_of(text, match.start()), \
            {'client': 'supabase', 'target': 'auth', 'operation': match.group('op'), 'symbol': 'auth'}


def detect(context):
    """Framework detector contract: ``detect(context)`` returns iterable of ``(offset, line, record)``.

    Each record carries a ``client``, ``target``, ``operation`` and ``symbol``. The loop in
    ``entrypoints.run`` materialises them as ``data_access`` facts because this module declares
    ``FACT_KIND = 'data_access'``.
    """
    return extract_calls(context.text)

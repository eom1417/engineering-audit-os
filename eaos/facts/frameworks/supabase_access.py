"""Detect Supabase client calls in TypeScript and JavaScript."""
import re

LANGUAGES = ('javascript', 'typescript', 'tsx')

# A `.from(...)` followed immediately by a data verb is a Supabase table access. A `.from(...)` not
# followed by one of these verbs is a different chain (typically storage) and is reported by its own
# matcher below.
TABLE_CALL = re.compile(r'''\.from\s*\(\s*(?P<q>['"`])(?P<target>[^'"`]+)(?P=q)\s*\)\s*\.\s*(?P<op>select|insert|update|upsert|delete)\b''')
# `.rpc("fn")` is a standalone call; it does not chain further on the same line.
RPC_CALL = re.compile(r'''\.rpc\s*\(\s*(?P<q>['"`])(?P<target>[^'"`]+)(?P=q)''')
# `.storage.from("b")` is the storage access pattern. The `.from(...)` after `.storage` is part of
# the storage call, so it is NOT also reported as a table access by TABLE_CALL above (no data verb).
STORAGE_CALL = re.compile(r'''\.storage\.from\s*\(\s*(?P<q>['"`])(?P<target>[^'"`]+)(?P=q)''')
AUTH_CALL = re.compile(r'''\.auth\.(?P<op>signIn|signOut|signUp|signInWithPassword|signInWithOAuth|getSession|getUser|resetPasswordForEmail|updateUser|onAuthStateChange)\b''')
# A Supabase-flavored name appears as a separate word in the chain. `supabase` matches the bare client
# and `context.supabase` and `supabaseAdmin` (any identifier that ends in `supabase` or `Supabase`).
SB_NAME = re.compile(r'''\b[A-Za-z_$][\w$]*[Ss]upabase\b|\bsupabase\b''')


def _line_of(text, offset):
    """1-based line number for the offset within ``text``."""
    return text.count('\n', 0, offset) + 1


def _supabase_prefix(text, end):
    """Return the expression to the left of ``end`` if it contains a Supabase-flavored name.

    A non-Supabase chain is rejected even when the chain name happens to be near a Supabase
    identifier earlier on the same line; we walk back to the previous statement boundary
    (semicolon, brace, newline, or assignment) and check only that expression.
    """
    boundaries = (';', '{', '}', '\n', '=')
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

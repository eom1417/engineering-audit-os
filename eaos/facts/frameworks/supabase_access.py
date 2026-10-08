"""Detect Supabase client calls in TypeScript and JavaScript."""
import re

from .http_access import object_keys

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
SB_NAME = re.compile(r'''\b[A-Za-z_$][\w$]*[Ss]upabase\b|\bsupabase\b|\bsupabase[A-Z][\w$]*\b''')
# A client is often injected under another name (`this.client`, `db`, a parameter typed with an alias of
# SupabaseClient). The receiver of a `.from("table").<verb>` chain is resolved against the names the file,
# or a file it imports, binds to a Supabase client: no other name makes the chain a Supabase call.
IMPORT = re.compile(r'''(?:\bfrom|\bimport)\s*\(?\s*['"]([^'"]+)['"]''')
TYPE_ALIAS = re.compile(r'''\btype\s+([A-Za-z_$][\w$]*)\s*=\s*SupabaseClient\b''')
FROM_FACTORY = re.compile(r'''\b([A-Za-z_$][\w$]*)\s*=\s*(?:await\s+)?(?:createClient|createServerClient|createBrowserClient)\b''')
NAMED_IMPORT = re.compile(r'''\bimport\s*(?:type\s+)?\{([^}]*)\}\s*from\s*['"]([^'"]*supabase[^'"]*)['"]''', re.I)
RECEIVER = re.compile(r'''([A-Za-z_$][\w$]*)\s*$''')
# The row a write sends: `.insert({ ... })`, `.insert([{ ... }])`, `.update({ ... })`; its keys are the table's columns.
ROW = re.compile(r'''\s*\(\s*\[?\s*''')
WRITES = ('insert', 'update', 'upsert')
# Stems too common to carry a binding: importing any `types` or `index` says nothing about Supabase.
GENERIC_STEMS = {'index', 'types', 'utils', 'constants', 'config', 'helpers'}


def _stem(path):
    return path.rstrip('/').rsplit('/', 1)[-1].split('.')[0]


def client_names(text, inherited=()):
    """The identifiers this file binds to a Supabase client: typed fields and parameters, factory results."""
    types = {'SupabaseClient', *TYPE_ALIAS.findall(text)}
    names = set(inherited) | set(FROM_FACTORY.findall(text))
    # `import { supabaseAdmin as admin } from "@/integrations/supabase/client.server"`: the imported names.
    for listed, _ in NAMED_IMPORT.findall(text):
        names |= {part.split(' as ')[-1].strip() for part in listed.split(',') if part.strip() and not part.strip()[0].isupper()}
    for kind in types:
        names |= set(re.findall(r'([A-Za-z_$][\w$]*)\s*\??\s*:\s*' + re.escape(kind) + r'\b', text))
    return names


def bound_files(texts):
    """{file: the client names it can call}, for every file that reaches a Supabase client.

    A service that extends a `BaseService` holding the client calls it `this.client`, a name nothing in
    the service's own text ties to Supabase, so names flow along imports: three hops cover a base class,
    its subclass, and a facade.
    """
    bound = {rel: client_names(text) for rel, text in texts.items()}
    bound = {rel: names for rel, names in bound.items() if names}
    for _ in range(3):
        by_stem = {}
        for rel, names in bound.items():
            if _stem(rel) not in GENERIC_STEMS: by_stem.setdefault(_stem(rel), set()).update(names)
        grew = False
        for rel, text in texts.items():
            inherited = set().union(*(by_stem.get(_stem(spec), set()) for spec in IMPORT.findall(text)))
            if inherited - bound.get(rel, set()):
                bound[rel] = client_names(text, bound.get(rel, set()) | inherited); grew = True
        if not grew: break
    return bound


def prepare(texts):
    """Project-wide pass before any single file: the Supabase client names each file can call."""
    return bound_files(texts)


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


def extract_calls(text, names=()):
    """Yield (offset, line, call_record) for every Supabase call matched in ``text``.

    A table chain counts when a Supabase-named client sits in the same statement, or when its receiver
    is one of ``names``, the client names the file reaches (see bound_files).
    """
    names = set(names) | client_names(text)
    for match in TABLE_CALL.finditer(text):
        # The receiver decides, not a mention nearby: `myClient.from("t")` under a comment naming Supabase
        # is not a Supabase call, and `this.client.from("t")` in a service holding one is.
        receiver = RECEIVER.search(text[max(0, match.start() - 200):match.start()])
        if not receiver or not (SB_NAME.fullmatch(receiver.group(1)) or receiver.group(1) in names): continue
        # A read is bounded when its chain limits the rows: .limit, .range, .single or .maybeSingle before the
        # statement ends. None for writes, whose result size is not the question.
        chain = re.split(r';|\n\s*\n', text[match.end():match.end() + 600], maxsplit=1)[0]
        bounded = (bool(re.search(r'\.(?:limit|range|single|maybeSingle)\s*\(', chain))
                   if match.group('op') == 'select' else None)
        record = {'client': 'supabase', 'target': match.group('target'),
                  'operation': match.group('op'), 'symbol': 'from', 'bounded': bounded}
        row = ROW.match(text, match.end()) if match.group('op') in WRITES else None
        found = object_keys(text, row.end()) if row else None
        if found is not None: record.update(keys=found['keys'], keys_partial=found['partial'])
        yield match.start(), _line_of(text, match.start()), record
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
    return extract_calls(context.text, context.prepared.get(__name__) or ())

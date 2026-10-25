"""The data layer's rules, read from the migrations with no database (M6.5).

What lets anyone through the API Supabase serves, from the net state of every migration (eaos/facts/domain.py's tables
and policies, and the migrations' text): a table without row-level security, a write policy open to everyone (`true`),
security enabled with no policy, a security-definer function or view the public may run, a public storage bucket whose
files anyone may list. And for each table, who reads it and who writes it (the data-access facts, each with the side of
its file), so a table written from the browser is seen beside its rules.
"""
import re
from collections import defaultdict

from ...facts.domain import table_key

FUNCTION = re.compile(r'create\s+(?:or\s+replace\s+)?function\s+(?P<name>[\w."]+)\s*\((?P<args>[^)]*)\)(?P<body>.*?)(?:\$\w*\$.*?\$\w*\$|;)',
                      re.I | re.S)
DEFINER = re.compile(r'\bsecurity\s+definer\b', re.I)
TRIGGER = re.compile(r'\breturns\s+trigger\b', re.I)
REVOKE = re.compile(r'revoke\s+(?:all|execute)[^;]*?on\s+function\s+(?P<name>[\w."]+)[^;]*?from\s+(?P<roles>[^;]+);', re.I | re.S)
VIEW = re.compile(r'create\s+(?:or\s+replace\s+)?(?:materialized\s+)?view\s+(?:if\s+not\s+exists\s+)?(?P<name>[\w."]+)(?P<options>[^;]*?)\bas\b', re.I | re.S)
INVOKER = re.compile(r'security_invoker\s*=\s*(?:true|on)', re.I)
VIEW_INVOKER = re.compile(r'alter\s+view\s+(?P<name>[\w."]+)\s+set\s*\([^)]*security_invoker\s*=\s*(?:true|on)', re.I)
BUCKET = re.compile(r'insert\s+into\s+storage\.buckets\s*\((?P<columns>[^)]*)\)\s*values\s*\((?P<values>[^)]*)\)', re.I)
OBJECT_SELECT = re.compile(r'create\s+policy\s+"?[^"]*"?\s+on\s+storage\.objects\s+(?P<body>[^;]*)', re.I)
OWNER_CHECK = re.compile(r'auth\.uid\(\)|owner|foldername', re.I)
PUBLIC_ROLES = ('public', 'anon')


def _line(text, offset):
    return text.count('\n', 0, offset) + 1


def _public(name):
    name = name.replace('"', '').lower()
    return '.' not in name or name.startswith('public.')


def _revoked(texts):
    """The functions whose execute right a migration takes back from the public."""
    return {table_key(match.group('name')) for _, text in texts for match in REVOKE.finditer(text)
            if any(role in match.group('roles').lower() for role in PUBLIC_ROLES)}


def definer_functions(texts):
    revoked = _revoked(texts)
    found = []
    for path, text in texts:
        for match in FUNCTION.finditer(text):
            whole = match.group(0)
            if not DEFINER.search(whole) or TRIGGER.search(whole) or not _public(match.group('name')): continue
            if table_key(match.group('name')) in revoked: continue
            found.append({'rule': 'definer-function-public', 'path': path, 'line': _line(text, match.start()),
                          'evidence': 'security definer, execute not revoked from public or anon',
                          'params': {'name': match.group('name').replace('"', ''), 'path': path}})
    return found


def definer_views(texts):
    fixed = {table_key(m.group('name')) for _, text in texts for m in VIEW_INVOKER.finditer(text)}
    return [{'rule': 'definer-view', 'path': path, 'line': _line(text, match.start()), 'evidence': 'a view without security_invoker',
             'params': {'name': match.group('name').replace('"', ''), 'path': path}}
            for path, text in texts for match in VIEW.finditer(text)
            if _public(match.group('name')) and not INVOKER.search(match.group('options')) and table_key(match.group('name')) not in fixed]


def _public_buckets(texts):
    """{bucket id: (path, line)} of the buckets a migration makes public."""
    found = {}
    for path, text in texts:
        for match in BUCKET.finditer(text):
            columns = [c.strip().strip('"').lower() for c in match.group('columns').split(',')]
            values = [v.strip().strip("'\"").lower() for v in match.group('values').split(',')]
            row = dict(zip(columns, values))
            if row.get('public') == 'true' and row.get('id'): found[row['id']] = (path, _line(text, match.start()))
    return found


def listed_buckets(texts):
    buckets, found = _public_buckets(texts), []
    for path, text in texts:
        for match in OBJECT_SELECT.finditer(text):
            body = match.group('body')
            if not re.search(r'\bfor\s+(select|all)\b', body, re.I) or OWNER_CHECK.search(body): continue
            for bucket in buckets:
                if re.search(r"bucket_id\s*=\s*'" + re.escape(bucket) + "'", body):
                    found.append({'rule': 'public-bucket-listed', 'path': path, 'line': _line(text, match.start()),
                                  'evidence': 'a select policy on storage.objects with no owner check', 'params': {'bucket': bucket, 'path': path}})
    return found


def open_tables(project):
    """A Supabase table, still there, with row-level security off; and a write policy whose condition checks nothing."""
    found = []
    for fact in project.facts('domain'):
        value, where = fact['value'], fact['location']
        if fact['kind'] == 'data_table' and '/supabase/' in '/' + where['path'] and value.get('rls_enabled') is False and not value.get('dropped'):
            found.append({'rule': 'table-without-rls', 'path': where['path'], 'line': where.get('start_line'),
                          'evidence': 'no ALTER TABLE ... ENABLE ROW LEVEL SECURITY after every migration',
                          'params': {'table': value['name'], 'path': where['path']}})
        elif fact['kind'] == 'db_policy' and value.get('open') and value.get('command') in ('ALL', 'INSERT', 'UPDATE', 'DELETE'):
            found.append({'rule': 'open-write-policy', 'path': where['path'], 'line': where.get('start_line'),
                          'evidence': f"a {value['command']} policy whose condition is true",
                          'params': {'table': value['table'], 'policy': value.get('name'), 'command': value['command'], 'path': where['path']}})
    return found


def unpoliced(project):
    """Tables with row-level security on and no policy at all."""
    return [{'rule': 'rls-without-policy', 'path': f['location']['path'], 'line': f['location'].get('start_line'),
             'evidence': 'row-level security enabled, no policy', 'params': {'table': f['value']['name'], 'path': f['location']['path']}}
            for f in project.facts('domain', 'data_table')
            if f['value'].get('rls_enabled') and not f['value'].get('policies') and not f['value'].get('dropped')
            and '/supabase/' in '/' + f['location']['path']]


WRITES = ('insert', 'update', 'upsert', 'delete')


def _access(project):
    """{table: {'readers': {paths}, 'writers': {paths}}} of the Supabase calls in the code."""
    access = defaultdict(lambda: {'readers': set(), 'writers': set()})
    for fact in project.facts('entrypoints', 'data_access'):
        value = fact['value']
        if not value.get('target') or value.get('client') not in ('supabase', 'supabase-js', None): continue
        access[table_key(str(value['target']))]['writers' if value.get('operation') in WRITES else 'readers'].add(fact['location']['path'])
    return access


def _open_writes(project):
    return {table_key(f['value']['table']) for f in project.facts('domain', 'db_policy')
            if f['value'].get('open') and f['value'].get('command') in ('ALL', 'INSERT', 'UPDATE', 'DELETE')}


def _table(fact, seen, opened, sides):
    key = table_key(fact['value']['name'])
    return {'table': key, 'path': fact['location']['path'], 'line': fact['location'].get('start_line'),
            'rls': fact['value'].get('rls_enabled'), 'policies': fact['value'].get('policies') or 0, 'open_write': key in opened,
            'readers': sorted(seen['readers']), 'writers': sorted(seen['writers']),
            'written_from_browser': any(sides.get(path) in ('browser', 'shared') for path in seen['writers'])}


def tables(project, sides):
    """[{table, path, rls, policies, open_write, readers, writers, written_from_browser}] for every table the migrations make."""
    access, opened, empty = _access(project), _open_writes(project), {'readers': set(), 'writers': set()}
    return [_table(fact, access.get(table_key(fact['value']['name']), empty), opened, sides)
            for fact in project.facts('domain', 'data_table')
            if not fact['value'].get('dropped') and fact['location']['path'].endswith('.sql')]


def check(project, sides):
    """{'tables': [...], 'findings': [...]} of a project that uses Supabase."""
    texts = [(path, project.text(path)) for path in project.schemas if path.endswith('.sql')]
    findings = open_tables(project) + unpoliced(project) + definer_functions(texts) + definer_views(texts) + listed_buckets(texts) \
        if (project.root / 'supabase').is_dir() or project.packages & {'@supabase/supabase-js', '@supabase/ssr'} else []
    return {'tables': tables(project, sides), 'findings': findings}

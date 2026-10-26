"""What ships to the browser (M6.3): it holds no secret, no privileged key, no server code and no database.

The rules read the side of each file (placement.py): code the browser runs, and the built output a build wrote. They are
EAOS's own rules rather than Semgrep's, because each needs to know where a file runs, which a pattern cannot. The built
output is read when the project holds it (dist/, build/, .next/static ...) or a build in the isolated copy made it
(`built_root`); otherwise its absence is said, never taken for a clean result.
"""
import re
from pathlib import Path

from ...facts.defects.secrets import _classify_text
from .placement import BUILT

EXPOSED = r'(?:VITE_|NEXT_PUBLIC_|REACT_APP_|EXPO_PUBLIC_|PUBLIC_|NUXT_PUBLIC_|GATSBY_)'
SECRET_WORD = re.compile(r'SECRET|PRIVATE|SERVICE_ROLE|SERVICE_KEY|PASSWORD|PASSWD|DATABASE_URL|DB_URL|DB_PASS|ADMIN_KEY|'
                         r'SIGNING_KEY|JWT_KEY|WEBHOOK_KEY')
PUBLIC_WORD = re.compile(r'PUBLISHABLE|ANON|PUBLIC_KEY|SITE_KEY|CLIENT_ID')
ENV_USE = re.compile(r'\b(?:import\.meta\.env|process\.env)\.(?P<name>' + EXPOSED + r'?\w+)')
ENV_LINE = re.compile(r'^\s*(?:export\s+)?(?P<name>' + EXPOSED + r'\w+)\s*=\s*(?P<value>\S.*)$')
SQL_CALL = re.compile(r'''\.(?:query|execute|raw|unsafe|\$queryRaw\w*|\$executeRaw\w*)\s*\(\s*[`'"]\s*(?:select|insert|update|delete|with)\b'''
                      r'''|\bsql\s*`\s*(?:select|insert|update|delete|with)\b''', re.I)
BUILT_TEXT = ('.js', '.mjs', '.cjs', '.html', '.json', '.css', '.txt')
BUILT_LIMIT = 5_000_000
PRIVILEGED = {'secret'}


def _row(rule, path, line, evidence, **params):
    return {'rule': rule, 'path': path, 'line': line, 'evidence': evidence, 'params': {'path': path, **params}}


def _secret_name(name):
    return bool(SECRET_WORD.search(name)) and not PUBLIC_WORD.search(name)


def secrets_in_code(project, rows):
    """A secret-named setting a browser file reads, and a privileged key written in browser code."""
    found = []
    for row in rows:
        if row['side'] not in ('browser', 'shared'): continue
        for number, line in enumerate(project.lines(row['path']), start=1):
            found += [_row('secret-in-browser', row['path'], number, line.strip()[:160], name=m.group('name'))
                      for m in ENV_USE.finditer(line) if re.match(EXPOSED, m.group('name')) or row['side'] == 'browser'
                      if _secret_name(m.group('name'))]
            found += [_row('key-in-shipped-code', row['path'], number, f'a {family} key on this line (its value is not repeated)',
                           family=family) for family, severity in _classify_text(line, row['path']) if severity in PRIVILEGED]
    return found


def env_files(root):
    """A committed .env file that gives a secret-named value to a setting the build puts in the browser."""
    found = []
    for path in sorted(Path(root).glob('.env*')):
        if path.name.endswith(('.example', '.sample', '.template')) or not path.is_file(): continue
        for number, line in enumerate(path.read_text(encoding='utf-8', errors='replace').split('\n'), start=1):
            match = ENV_LINE.match(line)
            if match and _secret_name(match.group('name')) and match.group('value').strip('\'" ') not in ('', '""'):
                found.append(_row('secret-in-browser', path.name, number, f"{match.group('name')}=… (the value is not repeated)",
                                  name=match.group('name')))
    return found


def database_in_ui(project, rows):
    """A browser file that reaches the database itself: a database driver imported, or SQL run from it."""
    found = []
    for row in rows:
        if row['side'] != 'browser': continue
        if 'data' in row['marks']:
            driver = next(m for m in project.imports[row['path']] if _driver(m))
            found.append(_row('ui-database', row['path'], _line_of(project, row['path'], driver), f'imports {driver}', how=driver))
        else:
            hit = next(((n, l) for n, l in enumerate(project.lines(row['path']), start=1) if SQL_CALL.search(l)), None)
            if hit: found.append(_row('ui-database', row['path'], hit[0], hit[1].strip()[:160], how='SQL'))
    return found


def _driver(module):
    from .placement import DATABASE
    return bool(DATABASE.match(module))


def _line_of(project, path, text):
    return next((n for n, line in enumerate(project.lines(path), start=1) if text in line), 1)


def server_code_in_browser(project, rows):
    """A browser file that imports a file whose own code is the server's (an HTTP handler, a database client, Node's
    modules, 'use server' aside: a server action is called from the browser by design)."""
    by = {row['path']: row for row in rows}
    found = []
    for row in rows:
        if row['side'] != 'browser': continue
        for target in sorted(project.edges.get(row['path'], ())):
            other = by.get(target)
            if other and other['side'] == 'server' and {'endpoint', 'data', 'node'} & set(other['marks']) and 'server' not in other['marks']:
                found.append(_row('server-module-in-browser', row['path'], _import_line(project, row['path'], target),
                                  f'{row["path"]} → {target}', target=target))
    return found


def _import_line(project, path, target):
    stem = Path(target).stem
    return next((n for n, line in enumerate(project.lines(path), start=1) if 'import' in line and stem in line or 'require(' in line and stem in line), 1)


def built_folders(root):
    """The folders of built output the project holds."""
    return [Path(root) / prefix.rstrip('/') for prefix in BUILT if (Path(root) / prefix.rstrip('/')).is_dir()]


def built_output(root, label=''):
    """Privileged keys and source maps in the built output under `root`; paths relative to it, `label` before them."""
    found, maps = [], []
    for folder in built_folders(root):
        for path in sorted(p for p in folder.rglob('*') if p.is_file() and 'node_modules' not in p.parts):
            relative = label + path.relative_to(root).as_posix()
            if path.suffix == '.map': maps.append(relative); continue
            if path.suffix not in BUILT_TEXT or path.stat().st_size > BUILT_LIMIT: continue
            found += _keys_in(path, relative)
    if maps:
        found.append(_row('source-maps-shipped', maps[0], None, f'{len(maps)} .map files, the first {maps[0]}', count=len(maps)))
    return found


def _keys_in(path, relative):
    text = path.read_text(encoding='utf-8', errors='replace')
    families = sorted({family for family, severity in _classify_text(text, relative) if severity in PRIVILEGED})
    return [_row('key-in-built-output', relative, _key_line(text), f'a {family} key in this file (its value is not repeated)',
                 family=family) for family in families]


def _key_line(text):
    lines = text.split('\n')
    return next((n for n, line in enumerate(lines, start=1) if any(s == 'secret' for _, s in _classify_text(line, ''))), 1)


def check(project, rows, built_root=None):
    """{'findings': [...], 'built': {'read': [folders], 'gap': why or None}}."""
    findings = secrets_in_code(project, rows) + env_files(project.root) + database_in_ui(project, rows)
    findings += server_code_in_browser(project, rows)
    roots = [(project.root, '')] + ([(Path(built_root), 'built:')] if built_root else [])
    read = [str(folder.relative_to(root)) for root, _ in roots for folder in built_folders(root)]
    for root, label in roots: findings += built_output(root, label)
    gap = None if read else ('no built output was read: the project holds none, and the app was not built in an isolated '
                             'copy (it is built there when you agree to run it)')
    return {'findings': findings, 'built': {'read': read, 'gap': gap}}

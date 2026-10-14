"""studio/evidence.json: every fact a card cites, with the code around its line as the check read it and never a secret;
and the one rule for a path the Studio may show (relative to the project, never absolute, a home directory or `..`).
"""
import re
import subprocess
from pathlib import Path

from .. import indicators

SAFE = re.compile(r'^(?![/\\~])(?![A-Za-z]:)(?!(.*/)?\.\.(/|$)).+')
CODE_CONTEXT = 2           # lines shown before and after a fact's line
CODE_WIDTH = 240           # a longer line is cut: a minified file never fills the page
SECRET_KINDS = {'secret', 'credential', 'hardcoded_secret'}


def rel(path):
    """A path the Studio may show: relative to the project, else None."""
    path = str(path or '').replace('\\', '/')
    return path if path and SAFE.match(path) else None


def code_excerpt(source, path, line, kind, secrets=frozenset()):
    """{start, line, lines, hidden}: the lines around `line` of `path` as the check read them, or None: no line, a
    secret (its value is never written), or a file that cannot be read as text. A line where any fact found a secret
    (`secrets`: {(path, line)}) is written empty and named in `hidden`. `source(path)` returns the file's text or None."""
    if not path or not isinstance(line, int) or line < 1 or kind in SECRET_KINDS: return None
    text = source(path)
    if text is None or '\0' in text[:4096]: return None
    rows = text.splitlines()
    if line > len(rows): return None
    start = max(1, line - CODE_CONTEXT)
    shown = range(start, min(len(rows), line + CODE_CONTEXT) + 1)
    hidden = [n for n in shown if (path, n) in secrets]
    return {'start': start, 'line': line, 'lines': ['' if n in hidden else rows[n - 1][:CODE_WIDTH] for n in shown], 'hidden': hidden}


def sources(project, commit):
    """path -> text: the file at the scanned commit (git show), else the project's working copy; never a path
    outside the project. Cached, so each file is read once."""
    root = Path(project).resolve() if project else None
    cache = {}

    def read(path):
        if path in cache: return cache[path]
        text = None
        if root and commit:
            done = subprocess.run(['git', '-C', str(root), 'show', f'{commit}:{path}'], capture_output=True)
            if done.returncode == 0 and len(done.stdout) <= 2_000_000: text = done.stdout.decode('utf-8', 'replace')
        if text is None and root:
            file = (root / path).resolve()
            if file.is_relative_to(root) and file.is_file() and file.stat().st_size <= 2_000_000:
                text = file.read_text(encoding='utf-8', errors='replace')
        cache[path] = text
        return text
    return read


def summary(value, kind):
    """What a fact says: its message, its measurements, and how its engine knows it."""
    numbers = ', '.join(f'{k} {v}' for k, v in value.items() if isinstance(v, (int, float)) and not isinstance(v, bool))
    how = value.get('evidence') if isinstance(value.get('evidence'), str) else ''
    return '; '.join(part for part in (str(value.get('message') or value.get('rule') or kind or ''), numbers, how) if part)[:400]


def evidence(report, cited, source=None):
    source = source or (lambda path: None)
    rows = indicators.facts(report)
    secrets = _secret_lines(rows)
    return [_fact_evidence(row, source, secrets) for row in rows if row.get('id') in cited]


def _site_lines(where, value):
    """{(path, line)} of a fact's location and its sites."""
    lines = set()
    for site in [where, *(s for s in value.get('sites') or [] if isinstance(s, dict))]:
        path = rel(site.get('path'))
        lines |= {(path, n) for n in (site.get('start_line'), site.get('line')) if isinstance(n, int) and path}
    return lines


def _secret_lines(rows):
    """{(path, line)} where any fact found a secret: those lines are never written."""
    secrets = set()
    for row in rows:
        value, where = row.get('value') or {}, row.get('location') or {}
        if (value.get('kind') or row.get('kind')) in SECRET_KINDS: secrets |= _site_lines(where, value)
    return secrets


def _fact_evidence(row, source, secrets):
    value, where = row.get('value') or {}, row.get('location') or {}
    sites = [{'path': rel(s.get('path')), 'line': s.get('line') if isinstance(s.get('line'), int) else None}
             for s in value.get('sites') or [] if isinstance(s, dict) and rel(s.get('path'))]
    fact = {'id': row['id'], 'kind': value.get('kind') or row.get('kind') or '', 'engine': value.get('engine'),
            'path': rel(where.get('path')), 'line': next((n for n in (where.get('start_line'), where.get('line')) if isinstance(n, int)), None),
            'summary': summary(value, row.get('kind')), 'sites': sites[:20]}
    # the code around the fact's line, else around its first site in the same file
    line = fact['line'] or next((site['line'] for site in sites if site['path'] == fact['path'] and site['line']), None)
    fact['code'] = code_excerpt(source, fact['path'], line, fact['kind'], secrets)
    return fact

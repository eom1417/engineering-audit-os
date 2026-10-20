"""The views of an app, read from its code by the person's assistant: each set of pages one kind of user sees (a
clinic's reception, doctor, nurse, pharmacy, administration...), with the line of code that makes it a view, how a
person enters it (an account of its own, or a switch of profile, workspace or organization within one sign-in, and the
line of that switch) and the pages that are its own. One reading serves every check: the stage `session` makes a
session per view on the running app (eaos/test_users.py), the page stages open each view's pages with its own session
(share), and a page that did not open as itself (opened: a sign-in, a refusal, the app's page for an address it does
not have) is not seen, never a missing page; the coverage says which views the check saw and why not the others.

    <out>/roles.json   {"roles": [{"id", "name", "evidence": "file:line", "enter": "account" | "switch",
                                   "switch": "file:line", "pages": ["/admin", ...]}]}
"""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit

MOST = 10
ROUNDS = 3
SIGNS = re.compile(r'\b(roles?|is_?admin|admin|permissions?|rbac|authori[sz]\w*|guard\w*|superuser|staff|support|'
                   r'manager|owner|member|sessions?|cookies?|tokens?|profiles?|workspaces?|tenants?|organi[sz]ations?|'
                   r'orgs?|teams?|departments?|portals?|switch\w*|impersonat\w*|active_?\w+|current_?\w+)\b', re.I)
# An address no app has: the page an app shows for it is its page for an address it does not have (opened).
NOWHERE = '/eaos-no-such-page-7f3a'
SKIP = ('node_modules', 'dist', 'build', '.next', 'coverage', '.venv', '__pycache__', '.git', 'test', 'tests', '__tests__')
SOURCE = ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.vue', '.svelte', '.py', '.rb', '.php', '.go', '.prisma', '.sql')

SYSTEM = """You read a web app's code and name every view it has: each set of pages one kind of user sees (an
administrator, support staff, a customer; a clinic's reception, doctor, nurse, pharmacy, insurance...). A person may
enter a view with an account of its own, or by switching within one sign-in: an active profile, workspace,
organization, team, department or role the app keeps (a cookie, a stored value, a column, a route segment) and a
switch changes. Name every view, whichever way it is entered: a view missed is a part of the app never checked.
Answer with one JSON object:
{"roles": [{"id": "admin", "name": {"en": "Administrator", "ar": "المدير"}, "evidence": "path/to/file.ts:42",
             "enter": "account", "pages": ["/admin", "/admin/users"]},
           {"id": "programs", "name": {"en": "Programs", "ar": "البرامج"}, "evidence": "path/to/file.ts:88",
             "enter": "switch", "switch": "path/to/switch.ts:17", "pages": ["/programs"]}]}
"id" is a short lowercase word; "name" says it in English and in Arabic; "evidence" is the file and line of the code
that defines or checks that view; "enter" is "account" or "switch", and a switch view's "switch" is the file and line
of the code that switches into it; "pages" are the page routes from the list given that belong to that view alone by
what they are for (an /admin page is the administrator's even where the code forgets to check it: the check then finds
who else opens it), an empty list when it sees only shared pages. At most ten views. An app whose signed-in users all
see the same pages has one; an app with no sign-in has none: {"roles": []}."""


def read(out):
    """The kinds of users of the last reading, [] when it was not made (no assistant) or found none."""
    try: return json.loads((Path(out) / 'roles.json').read_text(encoding='utf-8')).get('roles') or [] if out else []
    except (OSError, ValueError): return []


def pages_of(out, served=True):
    """The app's static page routes (eaos/lock_specs.py surfaces): its pages, and with `served` a server's GET routes,
    which draw the pages of an app rendered on the server (the only routes a kind of user may name)."""
    from .lock_specs import surfaces
    return sorted(route for route, (kind, method, _) in surfaces(out).items()
                  if (kind == 'page' or (served and kind == 'http' and method == 'GET')) and route.startswith('/')
                  and not any(mark in route for mark in (':', '*', '[')))


def about_users(target, limit=40000):
    """The source lines that speak of users, their kinds and their sessions, the files with most of them first, with the lines around."""
    found = []
    for path in Path(target).rglob('*'):
        if path.suffix in SOURCE and path.is_file() and not any(part in SKIP for part in path.relative_to(target).parts):
            lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
            hits = [i for i, line in enumerate(lines) if SIGNS.search(line)]
            if hits: found.append((len(hits), path, lines, hits))
    parts, used = [], 0
    for _, path, lines, hits in sorted(found, key=lambda row: -row[0])[:15]:
        start, end = max(0, hits[0] - 5), min(len(lines), hits[0] + 60)
        text = f'=== {path.relative_to(target).as_posix()} (lines {start + 1}-{end})\n' + \
               '\n'.join(f'{n + 1}: {line}' for n, line in enumerate(lines[start:end], start))
        if used + len(text) > limit: break
        parts.append(text)
        used += len(text)
    return '\n\n'.join(parts)


def errors(answer, target, pages):
    """What is wrong with the assistant's answer: every kind must cite a real line and name pages of the list."""
    kinds = answer.get('roles') if isinstance(answer, dict) else None
    if not isinstance(kinds, list): return ['answer {"roles": [...]}']
    found = [] if len(kinds) <= MOST else [f'at most {MOST} kinds']
    found += [wrong for kind in kinds for wrong in _wrong(kind, target, pages)]
    if len({str(k.get('id')) for k in kinds if isinstance(k, dict)}) < len(kinds): found.append('each "id" once')
    return found


def _wrong(kind, target, pages):
    if not isinstance(kind, dict) or not re.fullmatch(r'[a-z0-9-]{1,20}', str(kind.get('id') or '')):
        return [f'{kind}: "id" is a short lowercase word']
    switch = kind.get('enter') == 'switch'
    wrong = [] if _line(target, kind.get('evidence')) else [f"{kind['id']}: evidence {kind.get('evidence')!r} is no line of the code"]
    if kind.get('enter') not in ('account', 'switch'): wrong.append(f'{kind["id"]}: "enter" is "account" or "switch"')
    if switch and not _line(target, kind.get('switch')): wrong.append(f"{kind['id']}: switch {kind.get('switch')!r} is no line of the code")
    return wrong + [f"{kind['id']}: {page!r} is not in the list of pages" for page in kind.get('pages') or [] if page not in pages]


def _line(target, cited):
    """Whether `cited` ("file:line") is a line of the project's code."""
    file, _, line = str(cited or '').rpartition(':')
    path = Path(target) / file
    return bool(file and line.isdigit() and path.is_file() and 0 < int(line) <= len(path.read_text(errors='replace').splitlines()))


def find(target, out, provider):
    """Ask the assistant for the kinds of users, its answer sent back with what is wrong with it, ROUNDS times at most;
    <out>/roles.json. The kinds."""
    pages = pages_of(out)
    messages = [{'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': 'The page routes:\n' + json.dumps(pages) + '\n\nThe code about users:\n' + about_users(target)}]
    for _ in range(ROUNDS):
        answer, _ = provider.complete(messages, stage='roles')
        wrong = errors(answer, target, pages)
        if not wrong: break
        messages += [{'role': 'assistant', 'content': json.dumps(answer)},
                     {'role': 'user', 'content': 'Correct these and answer again:\n' + '\n'.join(wrong[:20])}]
    else:
        raise ValueError('the kinds of users named no real line or page: ' + '; '.join(wrong[:3]))
    kinds = [{k: kind.get(k) for k in ('id', 'name', 'evidence', 'enter', 'switch') if kind.get(k)} | {'pages': kind.get('pages') or []}
             for kind in answer['roles']]
    (Path(out) / 'roles.json').write_text(json.dumps({'roles': kinds}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return kinds


def opened(path, landed, status=200, password=0, text=None, nowhere=None):
    """Whether a page opened as itself: it answered, it was not sent elsewhere (a sign-in, a refusal, the first page),
    it shows no password field, and it is not the page the app shows for an address it does not have (`nowhere`: the
    text of NOWHERE with the same session; an app answering every address 200 draws its "not found" itself)."""
    return 200 <= (status or 0) < 400 and not password and \
        (urlsplit(landed or '').path.rstrip('/') or '/') == (path.rstrip('/') or '/') and not absent(text, nowhere, path)


def nowhere_of(page):
    """The text of the app's page for an address it does not have, from a probe whose last address was NOWHERE; None
    when it is the first page (an app drawing its first page at any address says nothing by it)."""
    text = ((page.get('others') or [{}])[-1]).get('text')
    return None if absent(page.get('text'), text, '/') else text


def absent(text, nowhere, path):
    """Whether page text `text` of `path` is the app's page for an address it does not have (`nowhere`, NOWHERE's)."""
    words = lambda said, address: ' '.join(str(said or '').replace(address, ' ').split())
    seen, missing = words(text, path), words(nowhere, NOWHERE)
    return bool(missing) and SequenceMatcher(None, seen, missing).ratio() > 0.9


def coverage(kinds, sessions, seen):
    """Per kind of user: its pages, how many a session opened, and why it was not seen. `sessions`: the kinds a session
    was made for (local test users), None when the person signed in by hand; `seen`: the paths opened."""
    rows = []
    for kind in kinds:
        own = kind.get('pages') or []
        name = kind.get('name') or kind['id']
        row = {'id': kind['id'], 'name': name if isinstance(name, dict) else {'en': name, 'ar': name}, 'pages': len(own),
               'seen': sum(page in seen for page in own)}
        row['reached'] = row['seen'] > 0 or (not own and sessions is not None and kind['id'] in sessions)
        if not row['reached']:
            row['why'] = 'no_access' if sessions is None else 'no_test_user' if kind['id'] not in sessions else 'not_opened'
        rows.append(row)
    return rows


def unseen(screens):
    """The pages a check did not see as themselves, [{page, view}] (the screens record `screens`, eaos/pipeline/pages.py):
    what they show is unknown, never a page missing or to build."""
    rows = (screens or {}).get('rows') or []
    seen = {row.get('url') for row in rows if not row.get('unseen')}
    missed = sorted({(row.get('url'), row.get('kind')) for row in rows if row.get('unseen') and row.get('url') not in seen}, key=str)
    return [{'page': page, 'view': view} for page, view in missed]


def share(kinds, groups, kind, first, held=()):
    """The page groups ({template: pages}) a session pictures: a view its own pages and the first page, the first
    session the shared pages too, and the run's one session (kind None) every page but those of the views `held` by a
    session of their own, which only theirs opens."""
    own = {k['id']: set(k['pages']) for k in kinds}
    if kind is None: return {t: p for t, p in groups.items() if not any(p[0] in own.get(view, ()) for view in held)}
    anyone = set().union(*own.values())
    return {t: p for t, p in groups.items() if p[0] in own[kind] or p[0] == '/' or (first and p[0] not in anyone)}


def breaches(kinds, made, look):
    """Each page of one kind only that another kind's session opened: [{kind, page, of}]. `made`: [(kind, session)];
    `look(session, paths)`: the probe's rows of `paths` opened with it (read only)."""
    owner = {page: k['id'] for k in kinds for page in k['pages']}
    return [{'kind': kind, 'page': row['path'], 'of': owner[row['path']]} for kind, state in made
            for row in look(state, sorted(page for page, of in owner.items() if of != kind)[:8])
            if opened(row['path'], row.get('url'), row.get('status'), row.get('password'))]

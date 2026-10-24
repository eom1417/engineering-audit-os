"""The views of an app, read from its code by the person's assistant: each set of pages one kind of user sees (a
clinic's reception, doctor, nurse, pharmacy, administration...), with the line of code that makes it a view, how a
person enters it (an account of its own, or a switch of profile, workspace or organization within one sign-in, and the
line of that switch) and the pages that are its own. One reading serves every check: the stage `session` makes a
session per view on the running app (eaos/live/test_users.py), the page stages open each view's pages with its own session
(share), and a page that did not open as itself (opened: a sign-in, a refusal, the app's page for an address it does
not have) is not seen, never a missing page; the coverage says which views the check saw and why not the others.

    <out>/roles.json   {"roles": [{"id", "name", "evidence": "file:line", "enter": "account" | "switch",
                                   "switch": "file:line", "pages": ["/admin", ...]}],
                        "unreachable": [{"page", "why", "evidence": "file:line"}],   the pages the code proves no one reaches
                        "strategy": "one_account" | "account_per_view", "sign_in": "..."}   the way in (WAY_IN)
"""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

MOST = 10
WAY_IN = ('strategy', 'sign_in')
STRATEGIES = ('one_account', 'account_per_view')
ROUNDS = 3
SIGNS = re.compile(r'\b(roles?|is_?admin|admin|permissions?|rbac|authori[sz]\w*|guard\w*|superuser|staff|support|'
                   r'manager|owner|member|sessions?|cookies?|tokens?|profiles?|workspaces?|tenants?|organi[sz]ations?|'
                   r'orgs?|teams?|departments?|portals?|switch\w*|impersonat\w*|active_?\w+|current_?\w+)\b', re.I)
# An address no app has: the page an app shows for it is its page for an address it does not have (opened).
NOWHERE = '/eaos-no-such-page-7f3a'
# The words a page opens with when it is not the page asked for but the app's "not found" or a refusal (absent).
NOT_SEEN = re.compile(r'\b(404|403|not found|could not be found|does not exist|doesn.t exist|no longer exists|not available|'
                      r'no access|access denied|forbidden|not allowed|not authori[sz]ed|unauthori[sz]ed|no permission)\b|'
                      r'غير موجود|غير متاح|لا (توجد|يوجد)|ليس لديك|غير مصرح|لا تملك|لا يمكنك الوصول', re.I)
SKIP = ('node_modules', 'dist', 'build', '.next', 'coverage', '.venv', '__pycache__', '.git', 'test', 'tests', '__tests__')
SOURCE = ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.vue', '.svelte', '.py', '.rb', '.php', '.go', '.prisma', '.sql')

SYSTEM = """You read a web app's code and name every view it has: each set of pages one kind of user sees (an
administrator, support staff, a customer; a clinic's reception, doctor, nurse, pharmacy, insurance...). A person may
enter a view with an account of its own, or by switching within one sign-in: an active profile, workspace,
organization, team, department or role the app keeps (a cookie, a stored value, a column, a route segment) and a
switch changes. Pages that show anything only once a record is chosen (an active program, clinic, project or account
the user picks) are a view entered by a switch too, its session with one chosen. Name every view, whichever way it is
entered: a view missed is a part of the app never checked.
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
see the same pages has one; an app with no sign-in has none: {"roles": []}.
Read the project's files yourself (Read, Grep, Glob) wherever the excerpt below falls short: the sign-in, the session,
the profile or program chooser, the guards. And say the way in, at the top of the object: "sign_in", one line on how a
person signs in (a development sign-in as a fixed account, a code by mail, a password, an outside provider) with its
file:line; "strategy", "one_account" when one account may hold every view (several profiles, seats or memberships it
switches between), so one test account granted all of them reaches every view, or "account_per_view" when each account
enters one view only, so the check makes one account of each kind."""


def read(out):
    """The kinds of users of the last reading, [] when it was not made (no assistant) or found none."""
    return _record(out).get('roles') or []


def proven(out):
    """{page: why} of the pages the assistant proved from the code that no person reaches (prove)."""
    return {row['page']: row['why'] for row in _record(out).get('unreachable') or []}


def _record(out):
    try: return json.loads((Path(out) / 'roles.json').read_text(encoding='utf-8')) if out else {}
    except (OSError, ValueError): return {}


def pages_of(out, served=True):
    """The app's static page routes (eaos/live/lock_specs.py surfaces): its pages, and with `served` a server's GET routes,
    which draw the pages of an app rendered on the server (the only routes a kind of user may name)."""
    from .lock_specs import surfaces
    return sorted(route for route, (kind, method, _) in surfaces(out).items()
                  if (kind == 'page' or (served and kind == 'http' and method == 'GET')) and route.startswith('/')
                  and not any(mark in route for mark in (':', '*', '[')))


def about_users(target, limit=40000, out=None):
    """The source lines that speak of users, their kinds and their sessions, with the lines around: first the files that
    serve the app's routes (the facts of `out`: where it signs in, switches and chooses), the most such lines first,
    then the others, two of a folder at most, so that a folder of near-alike files (policies, fixtures) never hides the
    rest."""
    parts, used, folders = [], 0, {}
    for other, _, path, lines, hits in sorted(_speaking(target, out), key=lambda row: row[:2]):
        if other and (folders := {**folders, path.parent: folders.get(path.parent, 0) + 1})[path.parent] > 2: continue
        start, end = max(0, hits[0] - 5), min(len(lines), hits[0] + 60)
        text = f'=== {path.relative_to(target).as_posix()} (lines {start + 1}-{end})\n' + \
               '\n'.join(f'{n + 1}: {line}' for n, line in enumerate(lines[start:end], start))
        if used + len(text) > limit or len(parts) >= 15: break
        parts.append(text)
        used += len(text)
    return '\n\n'.join(parts)


def _speaking(target, out):
    """(not a file serving a route, -its lines about users, path, lines, those lines' numbers) of each source file
    with any (SIGNS)."""
    from .lock_specs import surfaces
    served = {file for _, _, file in surfaces(out).values() if file} if out else set()
    for path in Path(target).rglob('*'):
        if _source(path, target):
            lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
            hits = [i for i, line in enumerate(lines) if SIGNS.search(line)]
            if hits: yield path.relative_to(target).as_posix() not in served, -len(hits), path, lines, hits


def _source(path, target):
    """Whether a file of `target` is its own source code, outside the folders of builds, libraries and tests (SKIP)."""
    return path.suffix in SOURCE and path.is_file() and not any(part in SKIP for part in path.relative_to(target).parts)


def errors(answer, target, pages):
    """What is wrong with the assistant's answer: every kind must cite a real line and name pages of the list."""
    kinds = answer.get('roles') if isinstance(answer, dict) else None
    if not isinstance(kinds, list): return ['answer {"roles": [...]}']
    found = [] if len(kinds) <= MOST else [f'at most {MOST} kinds']
    found += [wrong for kind in kinds for wrong in _wrong(kind, target, pages)]
    if len({str(k.get('id')) for k in kinds if isinstance(k, dict)}) < len(kinds): found.append('each "id" once')
    if answer.get('strategy') not in (None, *STRATEGIES): found.append('"strategy" is "one_account" or "account_per_view"')
    return found


def _wrong(kind, target, pages):
    if not isinstance(kind, dict) or not re.fullmatch(r'[a-z0-9-]{1,20}', str(kind.get('id') or '')):
        return [f'{kind}: "id" is a short lowercase word']
    switch = kind.get('enter') == 'switch'
    wrong = [] if _line(target, kind.get('evidence')) else [f"{kind['id']}: evidence {kind.get('evidence')!r} is no line of the code"]
    if kind.get('enter') not in ('account', 'switch'): wrong.append(f'{kind["id"]}: "enter" is "account" or "switch"')
    if switch and not _line(target, kind.get('switch')): wrong.append(f"{kind['id']}: switch {kind.get('switch')!r} is no line of the code")
    return wrong + _unlisted(kind, pages)


def _unlisted(kind, pages):
    """What is wrong with the pages a kind names: each one not in the list."""
    return [f"{kind['id']}: {page!r} is not in the list of pages" for page in kind.get('pages') or [] if page not in pages]


def _line(target, cited):
    """Whether `cited` ("file:line") is a line of the project's code."""
    file, _, line = str(cited or '').rpartition(':')
    path = Path(target) / file
    return bool(file and line.isdigit() and path.is_file() and 0 < int(line) <= len(path.read_text(errors='replace').splitlines()))


def find(target, out, provider, lacking=None):
    """Ask the assistant for the kinds of users, its answer sent back with what is wrong with it, ROUNDS times at most;
    <out>/roles.json. The kinds. `lacking`: what the running app still lacks with the sessions made (eaos/live/test_users.py
    make), the reading asked again with it and the views so far, its answer added to them (add), never in their place."""
    pages = pages_of(out)
    told = f'\n\nThe views so far:\n{json.dumps(read(out), ensure_ascii=False)}\n\nOn the running app, still lacking:\n{lacking}' if lacking else ''
    messages = [{'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': 'The page routes:\n' + json.dumps(pages) + '\n\nThe code about users:\n' + about_users(target, out=out) + told}]
    for _ in range(ROUNDS):
        answer, _ = provider.complete(messages, stage='roles', reads=target, deep=True)
        wrong = errors(answer, target, pages)
        if not wrong: break
        messages += [{'role': 'assistant', 'content': json.dumps(answer)},
                     {'role': 'user', 'content': 'Correct these and answer again:\n' + '\n'.join(wrong[:20])}]
    else:
        raise ValueError('the kinds of users named no real line or page: ' + '; '.join(wrong[:3]))
    if lacking: add(out, target, answer['roles'])
    return _write(out, read(out) if lacking else [_kept(kind) for kind in answer['roles']],
                  **{k: answer.get(k) for k in WAY_IN if answer.get(k) or not lacking})


def add(out, target, found):
    """The views the assistant found missing on the running app (eaos/live/test_users.py) added to <out>/roles.json, each
    checked as the reading's are (_wrong), one of the same id replaced; why each other one was refused."""
    kinds, refused, pages = read(out), [], pages_of(out)
    for view in found if isinstance(found, list) else []:
        wrong = _wrong(view, target, pages) if isinstance(view, dict) else [f'{view}: a view is an object']
        if wrong or _full(kinds, view):
            refused += wrong[:2] or [f'at most {MOST} views']
            continue
        kinds = [kind for kind in kinds if kind['id'] != view['id']] + [_kept(view) | {'found': 'app'}]   # by the running app
    if found: _write(out, kinds)
    return refused


def _full(kinds, view):
    """Whether a new view finds no place: MOST views already, none of them of its id."""
    return len(kinds) >= MOST and all(k['id'] != view['id'] for k in kinds)


def prove(out, target, verdicts):
    """The pages the assistant says no person reaches, each kept when it is a page of the code and its evidence a line
    of it (a route never linked and guarded off, a page removed); why each other one was refused."""
    pages, kept, refused = pages_of(out), [], []
    for row in verdicts if isinstance(verdicts, list) else []:
        row = row if isinstance(row, dict) else {}
        if _proved(row, pages, target):
            kept.append({k: row[k] for k in ('page', 'why', 'evidence')})
        else: refused.append(f"unreachable {row.get('page')!r}: a page of the list, a why and its evidence, a line of the code")
    if kept: _write(out, read(out), {r['page']: r for r in _record(out).get('unreachable') or []} | {r['page']: r for r in kept})
    return refused


def _proved(row, pages, target):
    """Whether a verdict stands: a page of the list, a why, and its evidence a line of the code."""
    return row.get('page') in pages and str(row.get('why') or '').strip() and _line(target, row.get('evidence'))


def claim(out, owned):
    """Each page a view's session opened and no session before it (eaos/live/test_users.py unreached) made that view's own,
    so the pictures open it with that session: {view: [pages]}."""
    kinds = read(out)
    grown = [{**kind, 'pages': list(dict.fromkeys(kind['pages'] + owned.get(kind['id'], [])))} for kind in kinds]
    if grown != kinds: _write(out, grown)


def _kept(kind):
    return {k: kind.get(k) for k in ('id', 'name', 'evidence', 'enter', 'switch', 'found') if kind.get(k)} | {'pages': kind.get('pages') or []}


def way_in(out):
    """{strategy, sign_in} the reading said, {} when it did not."""
    record = _record(out)
    return {k: record[k] for k in WAY_IN if record.get(k)}


def _write(out, kinds, unreachable=None, **said):
    """<out>/roles.json with `kinds`, the pages proved unreachable ({page: row}) and the way in (WAY_IN) kept unless
    given anew."""
    rows = list(unreachable.values()) if unreachable is not None else _record(out).get('unreachable') or []
    way = {k: v for k, v in {**way_in(out), **said}.items() if v}
    record = {'roles': kinds, **way, **({'unreachable': rows} if rows else {})}
    (Path(out) / 'roles.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return kinds


def opened(path, landed, status=200, password=0, text=None, nowhere=None):
    """Whether a page opened as itself: it answered, it was not sent elsewhere (a sign-in, a refusal, the first page),
    it shows no password field, and it is not the page the app shows for an address it does not have (`nowhere`: the
    lines of NOWHERE's page with the same session, nowhere_of; an app answering every address 200 draws its "not found"
    itself, and often inside its menus)."""
    return 200 <= (status or 0) < 400 and not password and \
        (urlsplit(landed or '').path.rstrip('/') or '/') == (path.rstrip('/') or '/') and not absent(text, nowhere, path)


def nowhere_of(page):
    """What tells the app's "not found" from its pages, from a probe whose first address is its first page and last
    NOWHERE: {'menus': the first page's lines, which its other pages share (bars, menus), 'missing': NOWHERE's lines
    the first page lacks, none when it draws its first page at any address}."""
    menus = _lines(page.get('text'), '/')
    gone = _lines(((page.get('others') or [{}])[-1]).get('text'), NOWHERE)
    return {'menus': menus, 'missing': [line for line in gone if line not in set(menus)]}


def absent(text, nowhere, path):
    """Whether page text `text` of `path` is not the page itself but the app's "not found" or a refusal: it shows every
    line of NOWHERE's page (`nowhere`, nowhere_of), whatever menus are drawn around them, or its own few lines, the
    menus left out, open by saying so (an app drawing a "not found" of its own inside its menus)."""
    if not nowhere: return False
    shown = _lines(text, path)
    own = [line for line in shown if line not in set(nowhere['menus'])]
    return (bool(nowhere['missing']) and set(nowhere['missing']) <= set(shown)) or \
        (0 < len(' '.join(own).split()) <= 40 and any(NOT_SEEN.search(line) for line in own[:2]))


def _lines(text, address):
    """The lines of a page's text, each with its spaces made one and its own address left out."""
    return [line for raw in str(text or '').splitlines() if (line := ' '.join(raw.replace(address, ' ').split()))]


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
        if not row['reached']: row['why'] = _why_unseen(kind, sessions)
        rows.append(row)
    return rows


def _why_unseen(kind, sessions):
    """Why no session saw a kind of user: no session at all (signed in by hand), no test user of its own, or not opened."""
    return 'no_access' if sessions is None else 'no_test_user' if kind['id'] not in sessions else 'not_opened'


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
    if kind is None: return _not_held(groups, own, held)
    anyone = set().union(*own.values())
    return {t: p for t, p in groups.items() if p[0] in own[kind] or p[0] == '/' or (first and p[0] not in anyone)}


def _not_held(groups, own, held):
    """The page groups of the run's one session: every one but those of a view `held` by a session of its own."""
    return {t: p for t, p in groups.items() if not any(p[0] in own.get(view, ()) for view in held)}


def breaches(kinds, made, look):
    """Each page of one view only that another account's session opened as itself: [{kind, page, of}]. `made`: [(kind,
    session)]; `look(session, paths)`: the probe of `paths` with it (read only), NOWHERE last, so that the app's page for
    an address it does not have, which another view's page often shows, is never taken for that page opened."""
    owner = {page: k['id'] for k in kinds for page in k['pages']}
    switched = {k['id'] for k in kinds if k.get('enter') == 'switch'}     # the same account in another view: its pages too
    found = []
    for kind, state in [(kind, state) for kind, state in made if kind not in switched]:
        page = look(state, sorted(page for page, of in owner.items() if of != kind)[:8] + [NOWHERE])
        found += _opened_others(kind, page, owner)
    return found


def _opened_others(kind, page, owner):
    """[{kind, page, of}] of the other views' pages a session's probe (`page`, NOWHERE last) opened as themselves."""
    nowhere = nowhere_of(page)
    return [{'kind': kind, 'page': row['path'], 'of': owner[row['path']]} for row in (page.get('others') or [])[:-1]
            if opened(row['path'], row.get('url'), row.get('status'), row.get('password'), row.get('text'), nowhere)]

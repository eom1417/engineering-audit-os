"""The page stages: the app opened in a browser, once as each kind of user of its code (eaos/live/access/roles.py, live_app
sessions), its pages walked, crawled and pictured. The published address the person named is read only."""
import json
import re
from pathlib import Path

from .live_app import _keep, _live, _ran
from ..stages import SkipStage

VISITOR = re.compile(r'/(login|log-in|signin|sign-in|sign_in|register|signup|sign-up|sign_up|join|auth)(\b|/|\?|$)', re.I)   # pages a visitor sees


def _published(context):
    """The published address the person named for this check, read by the stages that only read pages (S9)."""
    return (context.get('sign_in') or {}).get('published')


def journeys(context):
    """Each feature's pages walked once more, rrweb recording and the trace of a failure kept, capped in size
    (eaos/live/behavior/lock.py run_journeys)."""
    runtime = _live(context)
    plan = json.loads((context.out / 'behavior-lock/plan.json').read_text(encoding='utf-8')) \
        if (context.out / 'behavior-lock/plan.json').is_file() else {}
    if not any(spec.get('tool') == 'playwright' and spec.get('path') for spec in plan.get('specs') or []):
        raise SkipStage('the lock has no page to walk through', code='no_pages')
    from ...live.behavior.lock import run_journeys
    from .live_app import shared_app
    try:     # one session, as the lock it compares with was recorded: each kind's pages are walked by the crawl
        result = run_journeys(context.out, context.target, runtime, context.out / 'live/journeys', app=shared_app(context))
    except FileNotFoundError as problem:
        raise SkipStage(str(problem)[:300], code='browser_missing') from None
    _keep(context, 'journeys.json', result)
    return {'specs': result['specs'], 'failed': result['failed'], 'recordings': len(result['recordings']),
            'traces': len(result['traces'])}


def screens(context):
    """Each distinct page of the running app (one picture per template: /items/1 stands for /items/2) at phone and
    desktop width, in the app's own theme, with axe; Lighthouse on the entry, unless the crawl measured it already
    (eaos/live/screens/audit.py, eaos/live/screens/crawl.py distinct). Each kind of user of the code pictures its own pages, the
    first one the shared pages too (eaos/live/access/roles.py share); the published address the person named, read only."""
    if not _published(context): _live(context)
    from .live_app import sessions
    live, base, made = sessions(context, published=True)
    groups, measured = _screen_pages(context)
    rows, speed, audit = _pictured(context, (live, base, made), groups, measured)
    covered = _coverage(context, live, base, made, rows)
    from ...live.access.roles import proven
    _keep(context, 'screens.json', {'schema_version': 1, 'base': '/', 'tools': audit['tools'], 'rows': rows, 'coverage': covered,
                                    'unreachable': [{'page': page, 'why': why} for page, why in proven(context.out).items()],
                                    'pages': [{'path': paths[0], 'template': template, 'same_as': paths[1:]} for template, paths in groups.items()],
                                    'lighthouse': {k: v for k, v in speed.items() if k != 'report'}})
    from .live_app import studio
    studio(context)
    return {'pages': len(groups), 'screens': len(rows), 'failing': sum(bool(r.get('failures')) for r in rows),
            'lighthouse': (speed.get('scores') or {}).get('performance'),
            'kinds': covered and sum(k['reached'] for k in covered['kinds'])}


def _pictured(context, app, groups, measured):
    """(rows, the entry's speed, the last audit) of every session of `app` (live run, address, [(view, session)]), each
    picturing its view's pages (eaos/live/access/roles.py share)."""
    from ...live.access.roles import read, share
    live, base, made = app
    rows, speed, held = [], None, {kind for kind, _ in made if kind}
    for n, (kind, state) in enumerate(made):
        audit, measure = _audit_pages(context, app, (kind, state), (share(read(context.out), groups, kind, n == 0, held), measured), n == 0)
        if audit['status'] != 'observed' and not rows:
            raise SkipStage(f"the pages could not be opened: {audit.get('reason')}"[:300], code='screens_unavailable')
        speed = speed or measure
        nowhere = _nowhere(live, base, state)
        rows += [_seen(context, row, kind, nowhere) for row in audit.get('rows') or []]
    return rows + _visitor(context, app, groups, measured), speed, audit


def _visitor(context, app, groups, measured):
    """The sign-in and sign-up pages as a visitor sees them, kind `visitor`: a signed-in session is sent away from them
    (microblog's /auth/login opened its home page), so they are pictured with no session; [] when no session signed in."""
    made = app[2]
    own = {template: paths for template, paths in groups.items() if VISITOR.search(paths[0])}
    if not own or not any(Path(state).is_file() for _, state in made): return []
    audit, _ = _audit_pages(context, app, ('visitor', context.out / 'live/.no-session'), (own, measured), False)
    return [_as_visitor(_seen(context, row, 'visitor', None)) for row in audit.get('rows') or []]


def _as_visitor(row):
    """A visitor's picture of a sign-in page: its password field is the page itself, seen when it stayed where it was."""
    from urllib.parse import urlsplit
    if (urlsplit(row.get('landed') or row['url']).path.rstrip('/') or '/') == (urlsplit(row['url']).path.rstrip('/') or '/'): row.pop('unseen', None)
    return row


def _seen(context, row, kind, nowhere):
    """A picture's row, with the view that saw it, its file within the report, and `unseen` when the page did not open
    as itself (eaos/live/access/roles.py opened): a sign-in, a refusal or the app's page for an address it does not have is the
    page not seen with that session, never the page itself."""
    from urllib.parse import urlsplit
    from ...live.access.test_users import _reached
    path = urlsplit(row['url']).path or '/'
    shown = row.get('status') != 'observed' or _reached({'path': path, 'url': row.get('landed'), 'status': row.get('http'),
                                                         'password': row.get('password'), 'text': row.pop('text', None)}, nowhere)
    return {**row, 'kind': kind, 'screenshot': Path(row['screenshot']).relative_to(context.out).as_posix() if row.get('screenshot') else None,
            **({} if shown else {'unseen': True})}


def _nowhere(live, base, state):
    """The lines of the app's page for an address it does not have, opened with session `state` (eaos/live/access/roles.py
    nowhere_of); None read only."""
    from ...live.app.setup import probe
    from ...live.access.roles import NOWHERE, nowhere_of
    return nowhere_of(probe(live, base, state, None, [NOWHERE])) if live else None


def _coverage(context, live, base, made, rows):
    """{kinds, breaches} (eaos/live/access/roles.py), None when the kinds of users are not known: which kinds the pictures saw and
    why not the others, and each page of one kind another kind's session opened (a session per kind is local only)."""
    from urllib.parse import urlsplit
    from ...live.app.setup import probe
    from ...live.access.roles import breaches, coverage, read
    kinds = read(context.out)
    if not kinds: return None
    seen = {urlsplit(row['url']).path for row in rows if row.get('status') == 'observed' and not row.get('unseen')}
    tested = [(kind, state) for kind, state in made if kind]
    look = lambda state, paths: probe(live, base, state, None, paths)
    return {'kinds': coverage(kinds, {kind for kind, _ in tested} or None, seen),
            'breaches': breaches(kinds, tested, look) if len(tested) > 1 else []}


def _screen_pages(context):
    """({template: its pages}, the crawl's measured entry or None): the app's static page routes, each kind of user's
    own pages (eaos/live/access/roles.py) and the crawled ones, never one the code proves no person reaches."""
    from ...live.screens.crawl import distinct
    named = _named_pages(context)
    record = json.loads((context.out / 'live/crawl.json').read_text(encoding='utf-8')) if _ran(context, 'crawl') else {}
    crawled = record.get('routes') or []
    pages = ['/'] + named + [row['path'] for row in crawled]
    pages = _kept(context, pages)
    measured = next((row for row in crawled if row.get('measured') and row.get('template') == '/'), None)
    return distinct(pages, named + (record.get('seeds') or [])), measured


def _kept(context, pages):
    """The pages but those the code proves no person reaches, and those that sign out or delete: the session is shared."""
    from ...live.behavior.specs import LEAVES
    from ...live.access.roles import proven
    gone = proven(context.out)
    return [page for page in pages if page not in gone and not re.search(LEAVES, page, re.I)]


def _named_pages(context):
    """The page routes the code names and each kind of user's own pages, at the address that shows each: '/#/x' in an
    app that routes by the hash (CoreUI's were opened at /x, its dashboard each time)."""
    from ...live.access.roles import pages_of, read
    from ...live.screens.crawl import as_screen, hash_routed
    hashed = hash_routed(context.target)
    return [as_screen(page, hashed) for page in pages_of(context.out, served=False) + [page for kind in read(context.out) for page in kind['pages']]]


def _audit_pages(context, app, session, pages, speed):
    """(the page audit, the entry's speed) of `pages` ({template: its pages}, the crawl's measured entry) opened on `app`
    (live run, address, sessions) with `session` (kind of user, its browser state): Lighthouse only with `speed`, and
    only when the crawl did not measure the entry already."""
    from ...live.screens.audit import VIEWPORTS, page_audit, variants
    (live, base, _), (kind, state), (groups, measured) = app, session, pages
    state = state if state.is_file() else None
    folder = context.out / 'live/screens' / (kind or '')
    audit = page_audit([base + paths[0] for paths in groups.values()], [v for v in VIEWPORTS if v['name'] != 'tablet'],
                       variants(**((live.profile.get('screens') if live else None) or {})), out=folder, storage_state=state,
                       read_only=not live)
    return audit, _entry_speed(measured, base, folder, state, live) if speed else None


def _entry_speed(measured, base, folder, state, live):
    """The entry's speed: what the crawl measured, else Lighthouse's, with session `state` (a published address as a visitor)."""
    from ...live.screens.audit import lighthouse
    if measured: return {'status': 'observed', 'source': 'live/crawl.json', **{k: measured.get(k) for k in ('scores', 'lcp_ms', 'cls')}}
    return lighthouse(base + '/', out=folder, storage_state=state if live else None)


def _ran_file(context, kind, live):
    """The file a crawl of the app EAOS runs writes the JavaScript its pages ran into (M13.2), one per kind of user;
    None for a published address."""
    if not live: return None
    folder = Path(context.runtime) / 'ran-browser'
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{kind or 'visitor'}.json"


def _browser_ran(context):
    """live/ran-browser.json: the project's functions the pages ran as any kind of user; the raw coverage removed."""
    import shutil
    from ...live.testing.ran import browser, merged, record
    folder = Path(context.runtime) / 'ran-browser'
    parts = [browser(json.loads(path.read_text(encoding='utf-8')), context.target) for path in sorted(folder.glob('*.json'))]
    record(context.out, 'browser', merged(*parts), '' if any(parts) else 'the pages loaded no script EAOS can name as a '
           'file of the project (a built bundle names none)')
    shutil.rmtree(folder, ignore_errors=True)


def crawl(context):
    """Every page of the running app found in layers: the pages its code and files name and a server's GET routes
    (eaos/live/screens/crawl.py code_routes), its links followed once as each kind of user (eaos/live/access/roles.py), then the
    screens behind its buttons by the browser agent (_explored); Lighthouse on the entry and the first page of each
    distinct template, ten at most. Each route with the kinds that reached it. The published address the person named,
    read only, a few, by its links alone."""
    if not _published(context): _live(context)
    from .live_app import sessions
    from ...live.screens.crawl import MEASURED, crawl as find
    live, base, made = sessions(context, published=True)
    seeds, founds, routes = _seeds(context, live) if live else [], [], {}
    for kind, state in made:
        found = find(base, context.out / 'live/crawl' / (kind or ''), measured=0 if founds else MEASURED,
                     storage_state=_file(state), read_only=not live, seeds=seeds,
                     coverage=_ran_file(context, kind, live))
        if found['status'] != 'observed': continue
        founds.append(found)
        _merge_routes(routes, found, kind)
    if not founds:
        raise SkipStage(f"the pages could not be crawled: {found.get('reason')}"[:300], code='screens_unavailable')
    if live: _merge_explored(routes, _explored(context, base, made[0][1])); _browser_ran(context)
    from ...live.screens.crawl import distinct
    _keep(context, 'crawl.json', {'schema_version': 1, **founds[0], 'routes': list(routes.values()),
                                  'pages': [paths[0] for paths in distinct(routes, seeds).values()], 'seeds': seeds})     # one per template: the lock's stand-in
    return {'pages': len(routes)}


def _seeds(context, live):
    """The screens the code and files name, and a server's GET routes (Flask's own list of them when it is Flask):
    those that answer with a page are its pages (Flask's /hello, linked from nowhere); never one that signs out or
    deletes, which would end the session every page stage shares."""
    from ...live.behavior.specs import LEAVES
    from ...live.access.roles import pages_of
    from ...live.screens.crawl import code_routes
    from ...live.app.detect_python import served_pages
    found = code_routes(context.target) + served_pages(live) + pages_of(context.out)
    return [route for route in dict.fromkeys(found) if not route.startswith('/api') and not re.search(LEAVES, route, re.I)]


def _file(path):
    """`path` when it is a file (a session saved), else None."""
    return path if Path(path).is_file() else None


def _merge_explored(routes, paths):
    """The screens the browser agent reached, each a route once."""
    for path in paths: routes.setdefault(path, {'path': path, 'depth': None, 'status': 'observed', 'explored': True, 'kinds': []})


def _merge_routes(routes, found, kind):
    """Each route one crawl found into `routes`, once, with every kind of user that reached it."""
    for row in found['routes']:
        merged = routes.setdefault(row['path'], {**row, 'kinds': []})
        if kind: merged['kinds'].append(kind)


def _explored(context, base, state):
    """The screens behind buttons, tabs and welcomes no link reaches (eaos/live/agent.py): the steps saved in the runtime
    replayed with no assistant; explored by the assistant and saved again when there are none or they broke. [] with
    neither steps nor assistant. The steps and their pictures are one folder, replaced each time."""
    from ...live.agent import SCREENS, Browser, explore, replay
    folder = Path(context.runtime) / 'explore'
    saved = folder / 'screens.json'
    try: record = json.loads(saved.read_text(encoding='utf-8'))
    except (OSError, ValueError): record = None
    if not record and not context.provider: return []
    with Browser(base, folder, _file(state)) as browser:
        done = replay(browser, record) if record else {'broken_at': 0, 'screens': []}
        if 'broken_at' not in done or not context.provider: return done['screens']
        record = explore(browser, SCREENS, context.provider)
    if not record.get('stopped'): saved.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return record['screens']       # an exploration the assistant could not finish is never replayed as the app's steps

"""The page stages: the app opened in a browser, once as each kind of user of its code (eaos/roles.py, live_app
sessions), its pages walked, crawled and pictured. The published address the person named is read only."""
import json
from pathlib import Path

from .live_app import _keep, _live, _ran
from .stages import SkipStage


def _published(context):
    """The published address the person named for this check, read by the stages that only read pages (S9)."""
    return (context.get('sign_in') or {}).get('published')


def journeys(context):
    """Each feature's pages walked once more, rrweb recording and the trace of a failure kept, capped in size
    (eaos/behavior_lock.py run_journeys)."""
    runtime = _live(context)
    plan = json.loads((context.out / 'behavior-lock/plan.json').read_text(encoding='utf-8')) \
        if (context.out / 'behavior-lock/plan.json').is_file() else {}
    if not any(spec.get('tool') == 'playwright' and spec.get('path') for spec in plan.get('specs') or []):
        raise SkipStage('the lock has no page to walk through', code='no_pages')
    from ..behavior_lock import run_journeys
    from .live_app import shared_app
    try:     # one session, as the lock it compares with was recorded: each kind's pages are walked by the crawl
        result = run_journeys(context.out, context.target, runtime, context.out / 'live/journeys', app=shared_app(context))
    except FileNotFoundError as problem:
        raise SkipStage(str(problem)[:300], code='no_engine_installed') from None
    _keep(context, 'journeys.json', result)
    return {'specs': result['specs'], 'failed': result['failed'], 'recordings': len(result['recordings']),
            'traces': len(result['traces'])}


def screens(context):
    """Each distinct page of the running app (one picture per template: /items/1 stands for /items/2) at phone and
    desktop width, in the app's own theme, with axe; Lighthouse on the entry, unless the crawl measured it already
    (eaos/screens/audit.py, eaos/screens/crawl.py distinct). Each kind of user of the code pictures its own pages, the
    first one the shared pages too (eaos/roles.py share); the published address the person named, read only."""
    if not _published(context): _live(context)
    from .live_app import sessions
    live, base, made = sessions(context, published=True)
    groups, measured = _screen_pages(context)
    rows, speed, audit = _pictured(context, (live, base, made), groups, measured)
    covered = _coverage(context, live, base, made, rows)
    from ..roles import proven
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
    picturing its view's pages (eaos/roles.py share)."""
    from ..roles import read, share
    live, base, made = app
    rows, speed, held = [], None, {kind for kind, _ in made if kind}
    for n, (kind, state) in enumerate(made):
        audit, measure = _audit_pages(context, share(read(context.out), groups, kind, n == 0, held), measured, live, base, state, kind, n == 0)
        if audit['status'] != 'observed' and not rows:
            raise SkipStage(f"the pages could not be opened: {audit.get('reason')}"[:300], code='screens_unavailable')
        speed = speed or measure
        nowhere = _nowhere(live, base, state)
        rows += [_seen(context, row, kind, nowhere) for row in audit.get('rows') or []]
    return rows, speed, audit


def _seen(context, row, kind, nowhere):
    """A picture's row, with the view that saw it, its file within the report, and `unseen` when the page did not open
    as itself (eaos/roles.py opened): a sign-in, a refusal or the app's page for an address it does not have is the
    page not seen with that session, never the page itself."""
    from urllib.parse import urlsplit
    from ..test_users import _reached
    path = urlsplit(row['url']).path or '/'
    shown = row.get('status') != 'observed' or _reached({'path': path, 'url': row.get('landed'), 'status': row.get('http'),
                                                         'password': row.get('password'), 'text': row.pop('text', None)}, nowhere)
    return {**row, 'kind': kind, 'screenshot': Path(row['screenshot']).relative_to(context.out).as_posix() if row.get('screenshot') else None,
            **({} if shown else {'unseen': True})}


def _nowhere(live, base, state):
    """The lines of the app's page for an address it does not have, opened with session `state` (eaos/roles.py
    nowhere_of); None read only."""
    from ..live_setup import probe
    from ..roles import NOWHERE, nowhere_of
    return nowhere_of(probe(live, base, state, None, [NOWHERE])) if live else None


def _coverage(context, live, base, made, rows):
    """{kinds, breaches} (eaos/roles.py), None when the kinds of users are not known: which kinds the pictures saw and
    why not the others, and each page of one kind another kind's session opened (a session per kind is local only)."""
    from urllib.parse import urlsplit
    from ..live_setup import probe
    from ..roles import breaches, coverage, read
    kinds = read(context.out)
    if not kinds: return None
    seen = {urlsplit(row['url']).path for row in rows if row.get('status') == 'observed' and not row.get('unseen')}
    tested = [(kind, state) for kind, state in made if kind]
    look = lambda state, paths: probe(live, base, state, None, paths)
    return {'kinds': coverage(kinds, {kind for kind, _ in tested} or None, seen),
            'breaches': breaches(kinds, tested, look) if len(tested) > 1 else []}


def _screen_pages(context):
    """({template: its pages}, the crawl's measured entry or None): the app's static page routes, each kind of user's
    own pages (eaos/roles.py) and the crawled ones, never one the code proves no person reaches."""
    from ..roles import pages_of, proven, read
    from ..screens.crawl import distinct
    pages = ['/'] + pages_of(context.out, served=False) + [page for kind in read(context.out) for page in kind['pages']]
    crawled = json.loads((context.out / 'live/crawl.json').read_text(encoding='utf-8'))['routes'] if _ran(context, 'crawl') else []
    pages += [row['path'] for row in crawled]
    pages = [page for page in pages if page not in proven(context.out)]
    measured = next((row for row in crawled if row.get('measured') and row.get('template') == '/'), None)
    return distinct(pages), measured


def _audit_pages(context, groups, measured, live, base, state, kind, speed):
    """(the page audit, the entry's speed) of `groups` opened with session `state` (as kind of user `kind`): Lighthouse
    only with `speed`, and only when the crawl did not measure the entry already."""
    from ..screens.audit import VIEWPORTS, lighthouse, page_audit, variants
    state = state if state.is_file() else None
    folder = context.out / 'live/screens' / (kind or '')
    audit = page_audit([base + paths[0] for paths in groups.values()], [v for v in VIEWPORTS if v['name'] != 'tablet'],
                       variants(**((live.profile.get('screens') if live else None) or {})), out=folder, storage_state=state,
                       read_only=not live)
    speed = None if not speed else ({'status': 'observed', 'source': 'live/crawl.json', **{k: measured.get(k) for k in ('scores', 'lcp_ms', 'cls')}}
                                    if measured else lighthouse(base + '/', out=folder, storage_state=state if live else None))   # published: as a visitor
    return audit, speed


def crawl(context):
    """Every page of the running app found by following its links, Lighthouse on the entry and the first page of each
    distinct template, ten at most (eaos/screens/crawl.py), once as each kind of user (eaos/roles.py): each route with
    the kinds that reached it. The published address the person named, read only, a few."""
    if not _published(context): _live(context)
    from .live_app import sessions
    from ..screens.crawl import MEASURED, crawl as find
    live, base, made = sessions(context, published=True)
    founds, routes = [], {}
    for kind, state in made:
        found = find(base, context.out / 'live/crawl' / (kind or ''), measured=0 if founds else MEASURED,
                     storage_state=state if state.is_file() else None, read_only=not live)
        if found['status'] != 'observed': continue
        founds.append(found)
        for row in found['routes']:
            merged = routes.setdefault(row['path'], {**row, 'kinds': []})
            if kind: merged['kinds'].append(kind)
    if not founds:
        raise SkipStage(f"the pages could not be crawled: {found.get('reason')}"[:300], code='screens_unavailable')
    from ..screens.crawl import distinct
    _keep(context, 'crawl.json', {'schema_version': 1, **founds[0], 'routes': list(routes.values()),
                                  'pages': [paths[0] for paths in distinct(routes).values()]})     # one per template: the lock's stand-in
    return {'pages': len(routes)}

"""The test users of a check, made by the person's assistant on the app as it runs in its isolated copy (the stage
`session`, eaos/pipeline/sign_in_stage.py): the assistant writes the seed script that signs a user in, and a session in
each view of the code (eaos/roles.py): a user of that kind, switched into it when the view is entered by a switch within
one sign-in. EAOS runs it on the running app and tells what is still lacking, until every session opens its view's own
pages (never the app's page for an address it does not have) or SECONDS pass. Then the person is asked to sign in by
hand; when they did, the script only switches their session into each view a switch enters. Each try takes seconds:
the app is never installed or started again for it.
"""
import json
import re
import time

from .live_assist import _excerpt
from .live_run import kinds_folder
from .roles import NOWHERE, about_users, add, claim, nowhere_of, opened, pages_of, proven, prove, read, way_in
from .run_profile import apply, safe

SECONDS = 300                 # one round of tries; ROUNDS of them at most: fifteen minutes, as before
ROUNDS = 3
PAGES = 150                   # the pages of the code each session is tried on, the views' own first

SYSTEM = """You make the test users of a web app that runs on this computer, in an isolated copy, for automated
checks. The copy and its database are the check's own and reach no real account or service: finding a way in is your
job, and refusing is not an answer. Answer with one JSON object: {"seed_script": "<a Node.js script>"}.
The script runs with Node against the running app, with BASE_URL, EAOS_STORAGE_STATE and EAOS_SESSIONS_DIR in its
environment, DATABASE_URL (the copy's own PostgreSQL) when the app has one, AUTH_SECRET (the run's own secret) when it
uses one, and require('playwright') and the app's own packages available. Use whatever works, preferring the first:
a development sign-in the docs describe; signing up and in through the app's pages; the app's own seed or admin
scripts; writing the user straight into the database; making a session the app accepts (its session table, or a token
signed with AUTH_SECRET). An app that signs in only through an outside provider (Google...) gets its user and its
session made in the database. The run's own session, saved with context.storageState({ path:
process.env.EAOS_STORAGE_STATE }), opens every page: its user holds, granted in the copy's database, every role, seat
and membership the code knows, in every organization, program or workspace (one made when none is there), so nothing
is refused to it; an app that signs in by itself as one fixed account (a development sign-in) has that account granted
all of it. Then for each view listed, a session in that view saved to EAOS_SESSIONS_DIR/<id>.json, by the way in
given: "one_account", that same account switched into the view; "account_per_view", an account of that kind alone,
granted its own role only, so a page of another kind it opens is seen. A user of that kind signed in and, for a view
entered by a switch, switched into it the way
the app switches (its "switch" line: the request it sends, the cookie or the stored value it keeps; a record chosen, an
active program or clinic made in the copy's database when none is there), so that the
session opens that view's own pages, never the app's page for an address it does not have. A page of the code that
no session opens tells you a view is missing: find how a person reaches it (its file says what it needs: a profile, a
program or a record chosen, a role, another account), and add that view to your answer, "views": [{"id", "name":
{"en", "ar"}, "evidence": "file:line", "enter": "account" | "switch", "switch": "file:line", "pages": [...]}], with its
session saved to EAOS_SESSIONS_DIR/<id>.json. Every such page gets one of two answers, never none: the view
that opens it, or, only when its code proves no person reaches it (a route no page links to and that refuses every
user, a page left from a removed feature), "unreachable": [{"page", "why", "evidence": "file:line"}]. The output may
end with one JSON line of the fixture values it created ({"E2E_PROFILEID": "..."}). Every address is http://127.0.0.1
or localhost; nothing deploys or reaches a hosted service."""
# When the person signed in themselves: their session is theirs alone, the script only switches it into each view.
BY_HAND = ('The person signed in themselves: EAOS_STORAGE_STATE holds a copy of their session. Never sign in, sign up or '
           'make a user: open that state, switch it into each view listed, and save each to EAOS_SESSIONS_DIR/<id>.json.')


def views(report, hand):
    """The views a seed makes sessions for: every view, or with the person signed in by `hand` those a switch enters."""
    return [view for view in read(report) if not hand or view.get('enter') == 'switch']


def lacking(live, base, state, report, hand=False):
    """What the sessions still lack, '' when nothing: the run's session must open the app, and each view's its own
    pages (or the first page for a view with none)."""
    from .sign_in import works
    if not works(live, base, state, report):
        return 'the browser state saved to EAOS_STORAGE_STATE does not open the app: its pages are sent to the sign-in'
    missing = [view for view in views(report, hand) if not _opens(live, base, kinds_folder(state) / f"{view['id']}.json", view['pages'])]
    if missing:
        return ('these views have no session that opens their own pages (a page showing what the app shows for an address '
                'it does not have is not opened: the session is not in that view): ' + json.dumps(missing))
    alone = unreached(live, base, state, report)
    return ('these pages of the code open with no session (each shows the app\'s "not found", a refusal or the sign-in): '
            'grant the run\'s own user what they need (every role and seat) and add the view that is missing, or answer '
            'each "unreachable" with the line that proves it. Their files:\n'
            + _sources(live.sandbox.copy, alone)) if alone else ''


def unreached(live, base, state, report):
    """The pages of the code (PAGES at most, every view's own first) that open as themselves with none of the sessions
    made: {page: its file}. The running app says which views the reading of the code missed; each page a view's session
    opened, and no session before it, becomes that view's own (eaos/roles.py claim)."""
    from .live_setup import probe
    from .lock_specs import surfaces
    left, owned = _tried(report), {}
    for session in [state, *sorted(kinds_folder(state).glob('*.json'))]:
        page = probe(live, base, session, None, left + [NOWHERE]) if left and (session.is_file() or session == state) else {}
        nowhere = nowhere_of(page)
        shown = {row.get('path') for row in (page.get('others') or [])[:-1] if _reached(row, nowhere)}
        if session != state: owned[session.stem] = [path for path in left if path in shown]
        left = [path for path in left if path not in shown]
    claim(report, owned)
    known = surfaces(report)
    return {path: (known.get(path) or (None, None, None))[2] for path in left}


def _tried(report):
    """The pages a session is tried on: every view's own first, then the others of the code, never an interface, the
    sign-in, a page that signs out or deletes, or one proved unreachable; PAGES at most."""
    from .live_setup import LEAVES, SIGN_IN_PAGE
    owned, gone = [page for view in read(report) for page in view['pages']], proven(report)
    return [page for page in dict.fromkeys(owned + pages_of(report)) if not page.startswith('/api/') and page not in gone
            and not re.search(LEAVES, page, re.I) and not SIGN_IN_PAGE.search(page)][:PAGES]


def _reached(row, nowhere):
    """Whether a probed page was reached: opened as itself, or sent on to a page of its own under its address (/settings
    to /settings/profile, never /admin to /dashboard), never to the sign-in, nor showing the app's "not found" or a
    refusal. The one rule of a page seen: the sessions' and the pictures' (eaos/pipeline/pages.py _seen)."""
    from urllib.parse import urlsplit
    from .live_setup import SIGN_IN_PAGE
    path, landed = row.get('path') or '/', urlsplit(row.get('url') or '').path.rstrip('/') or '/'
    if opened(path, row.get('url'), row.get('status'), row.get('password'), row.get('text'), nowhere): return True
    return 200 <= (row.get('status') or 0) < 400 and landed.startswith(path.rstrip('/') + '/') and not row.get('password') \
        and not SIGN_IN_PAGE.search(landed) \
        and opened(landed, row.get('url'), row.get('status'), 0, row.get('text'), nowhere)


def _sources(root, pages, limit=12000):
    """Each page with its file and the start of that file, `limit` characters in all."""
    parts, used = [], 0
    for path, file in pages.items():
        try: text = (root / file).read_text(encoding='utf-8', errors='replace')[:2500] if file else ''
        except OSError: text = ''
        part = f'=== {path} ({file or "file not known"})\n{text}'
        if used + len(part) > limit: parts.append(f'=== {path} ({file})'); continue
        parts.append(part)
        used += len(part)
    return '\n'.join(parts)


def _opens(live, base, session, pages):
    from .live_setup import probe
    page = probe(live, base, session, None, pages[:3] + [NOWHERE]) if session.is_file() else {}
    nowhere, rows = nowhere_of(page), (page.get('others') or [])[:-1] if pages else [page]
    return any(opened(row.get('path') or '/', row.get('url'), row.get('status'), row.get('password'), row.get('text'), nowhere)
               for row in rows if row)


def make(project, live, base, state, report, provider, hand=False):
    """The assistant's seed script, run on the running app and told what is still lacking, round by round (ROUNDS at
    most): a round that ends with something lacking goes back to the node that owns the views and the way in, the
    reading of the code (eaos/roles.py find), with what lacks, and the next round goes on with its answer. What is still
    lacking ('' when every session works). `hand`: the person signed in themselves (BY_HAND)."""
    from .roles import find
    wrong = lacking(live, base, state, report, hand)
    for again in range(ROUNDS):
        if not wrong: break
        if again:
            try: find(project, report, provider, wrong)
            except ValueError: pass                # an answer with no real line: the views stay as they were
        wrong = _round(project, live, base, state, report, provider, hand, wrong)
    return wrong


def _round(project, live, base, state, report, provider, hand, wrong):
    """One round of make: the assistant told what lacks until nothing does, SECONDS pass or the same lack comes twice."""
    end = time.monotonic() + SECONDS
    messages = [{'role': 'system', 'content': SYSTEM + ('\n' + BY_HAND if hand else '')},
                {'role': 'user', 'content': 'The way in: ' + json.dumps(way_in(report), ensure_ascii=False)
                 + '\n\nThe views:\n' + json.dumps(views(report, hand), ensure_ascii=False)
                 + '\n\nThe documentation:\n' + _excerpt(project, live.profile.get('app') or '.', 12000)
                 + '\n\nThe code about its users and sessions:\n' + about_users(project, 30000, report)
                 + '\n\nThe seed script today (keep what it makes that still applies):\n' + (_today(live) or '(none)')}]
    tried = []
    while wrong and time.monotonic() < end and tried[-2:] != [wrong, wrong]:    # twice the same lack: nothing more comes
        tried.append(wrong)
        messages.append({'role': 'user', 'content': 'What is still lacking: ' + wrong})
        answer, _ = provider.complete(messages, stage='session', reads=live.sandbox.copy, deep=True)
        answer = answer.get('result') or answer
        refused = add(report, project, answer.get('views') or []) + prove(report, project, answer.get('unreachable') or [])
        script = answer.get('seed_script') or _today(live)        # a verdict alone keeps the script
        messages.append({'role': 'assistant', 'content': json.dumps({k: answer.get(k) for k in ('seed_script', 'views', 'unreachable')})})
        wrong = ('these were not kept: ' + '; '.join(refused) + '. ' if refused else '') + _try(live, base, state, report, script, hand)
    return wrong


def _today(live):
    seed = live.runtime / 'setup' / 'seed.cjs'
    return seed.read_text(encoding='utf-8') if seed.is_file() else ''


def _try(live, base, state, report, script, hand):
    """Run `script` as the seed on the running app (on a copy of the person's session when they signed in themselves);
    what is still lacking after it."""
    from .sign_in import seeding
    refused = safe({'seed_script': script}) if script else ['no seed_script was given']
    if refused: return 'nothing ran: ' + '; '.join(refused)
    live.profile['seed'] = apply(live.runtime, {'seed_script': script})['seed']
    seeded = seeding(state)
    try: live.seed(base, seeded)
    except RuntimeError as problem: return str(problem)[-2000:]
    finally:
        if seeded != state: seeded.unlink(missing_ok=True)
    return lacking(live, base, state, report, hand)

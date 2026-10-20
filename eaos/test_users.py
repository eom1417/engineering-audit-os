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
from .roles import NOWHERE, about_users, add, nowhere_of, opened, pages_of, read
from .run_profile import apply, safe

SECONDS = 300
PAGES = 24                    # the pages of the code each session is tried on, the views' own first

SYSTEM = """You make the test users of a web app that runs on this computer, in an isolated copy, for automated
checks. The copy and its database are the check's own and reach no real account or service: finding a way in is your
job, and refusing is not an answer. Answer with one JSON object: {"seed_script": "<a Node.js script>"}.
The script runs with Node against the running app, with BASE_URL, EAOS_STORAGE_STATE and EAOS_SESSIONS_DIR in its
environment, DATABASE_URL (the copy's own PostgreSQL) when the app has one, AUTH_SECRET (the run's own secret) when it
uses one, and require('playwright') and the app's own packages available. Use whatever works, preferring the first:
a development sign-in the docs describe; signing up and in through the app's pages; the app's own seed or admin
scripts; writing the user straight into the database; making a session the app accepts (its session table, or a token
signed with AUTH_SECRET). An app that signs in only through an outside provider (Google...) gets its user and its
session made in the database. Save a signed-in browser state with context.storageState({ path:
process.env.EAOS_STORAGE_STATE }), and for each view listed, a session in that view saved to
EAOS_SESSIONS_DIR/<id>.json: a user of that kind signed in and, for a view entered by a switch, switched into it the way
the app switches (its "switch" line: the request it sends, the cookie or the stored value it keeps; a record chosen, an
active program or clinic made in the copy's database when none is there), so that the
session opens that view's own pages, never the app's page for an address it does not have. A page of the code that
no session opens tells you a view is missing: find how a person reaches it (its file says what it needs: a profile, a
program or a record chosen, a role, another account), and add that view to your answer, "views": [{"id", "name":
{"en", "ar"}, "evidence": "file:line", "enter": "account" | "switch", "switch": "file:line", "pages": [...]}], with its
session saved to EAOS_SESSIONS_DIR/<id>.json. The output may end with one JSON line of the fixture values it created
({"E2E_PROFILEID": "..."}). Every address is http://127.0.0.1 or localhost; nothing deploys or reaches a hosted
service."""
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
            'a view is missing. Their files:\n' + _sources(live.sandbox.copy, alone)) if alone else ''


def unreached(live, base, state, report):
    """The pages of the code (PAGES at most, every view's own first) that open as themselves with none of the sessions
    made: {page: its file}. The running app says which views the reading of the code missed."""
    from .live_setup import probe
    from .lock_specs import surfaces
    left = _tried(report)
    for session in [state, *sorted(kinds_folder(state).glob('*.json'))]:
        page = probe(live, base, session, None, left + [NOWHERE]) if left and session.is_file() else {}
        nowhere = nowhere_of(page)
        shown = {row.get('path') for row in (page.get('others') or [])[:-1] if _reached(row, nowhere)}
        left = [path for path in left if path not in shown]
    known = surfaces(report)
    return {path: (known.get(path) or (None, None, None))[2] for path in left}


def _tried(report):
    """The pages a session is tried on: every view's own first, then the others of the code, never an interface, the
    sign-in or a page that signs out or deletes; PAGES at most."""
    from .live_setup import LEAVES, SIGN_IN_PAGE
    owned = [page for view in read(report) for page in view['pages']]
    return [page for page in dict.fromkeys(owned + pages_of(report)) if not page.startswith('/api/')
            and not re.search(LEAVES, page, re.I) and not SIGN_IN_PAGE.search(page)][:PAGES]


def _reached(row, nowhere):
    """Whether a probed page was reached: opened as itself, or sent on to a page of its own (/settings to its first tab),
    never to the first page or the sign-in, nor showing the app's "not found" or a refusal."""
    from urllib.parse import urlsplit
    from .live_setup import SIGN_IN_PAGE
    landed = urlsplit(row.get('url') or '').path.rstrip('/') or '/'
    if opened(row.get('path') or '/', row.get('url'), row.get('status'), row.get('password'), row.get('text'), nowhere): return True
    return 200 <= (row.get('status') or 0) < 400 and landed != '/' and not row.get('password') and not SIGN_IN_PAGE.search(landed) \
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
    """The assistant's seed script, run on the running app and told what is still lacking, until nothing is or SECONDS
    pass; what is still lacking ('' when every session works). `hand`: the person signed in themselves (BY_HAND)."""
    end, wrong = time.monotonic() + SECONDS, lacking(live, base, state, report, hand)
    messages = [{'role': 'system', 'content': SYSTEM + ('\n' + BY_HAND if hand else '')},
                {'role': 'user', 'content': 'The views:\n' + json.dumps(views(report, hand), ensure_ascii=False)
                 + '\n\nThe documentation:\n' + _excerpt(project, live.profile.get('app') or '.', 12000)
                 + '\n\nThe code about its users and sessions:\n' + about_users(project, 30000, report)
                 + '\n\nThe seed script today (keep what it makes that still applies):\n' + _today(live)}]
    tried = []
    while wrong and time.monotonic() < end and tried[-2:] != [wrong, wrong]:    # twice the same lack: nothing more comes
        tried.append(wrong)
        messages.append({'role': 'user', 'content': 'What is still lacking: ' + wrong})
        answer, _ = provider.complete(messages, stage='session')
        answer = answer.get('result') or answer
        script, refused = answer.get('seed_script') or '', add(report, project, answer.get('views') or [])
        messages.append({'role': 'assistant', 'content': json.dumps({'seed_script': script, 'views': answer.get('views') or []})})
        wrong = ('these views were not added: ' + '; '.join(refused) + '. ' if refused else '') + _try(live, base, state, report, script, hand)
    return wrong


def _today(live):
    seed = live.runtime / 'setup' / 'seed.cjs'
    return seed.read_text(encoding='utf-8') if seed.is_file() else '(none)'


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

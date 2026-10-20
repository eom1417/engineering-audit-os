"""The test users of a check, made by the person's assistant on the app as it runs in its isolated copy (the stage
`session`, eaos/pipeline/sign_in_stage.py): the assistant writes the seed script that signs a user in, and a session in
each view of the code (eaos/roles.py): a user of that kind, switched into it when the view is entered by a switch within
one sign-in. EAOS runs it on the running app and tells what is still lacking, until every session opens its view's own
pages (never the app's page for an address it does not have) or SECONDS pass. Then the person is asked to sign in by
hand; when they did, the script only switches their session into each view a switch enters. Each try takes seconds:
the app is never installed or started again for it.
"""
import json
import time

from .live_assist import _excerpt
from .live_run import kinds_folder
from .roles import NOWHERE, about_users, nowhere_of, opened, read
from .run_profile import apply, safe

SECONDS = 300

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
session opens that view's own pages, never the app's page for an address it does not have. The output may end with one JSON line of the fixture values it created
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
    return ('these views have no session that opens their own pages (a page showing what the app shows for an address it '
            'does not have is not opened: the session is not in that view): ' + json.dumps(missing)) if missing else ''


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
                 + '\n\nThe code about its users and sessions:\n' + about_users(project, 30000)
                 + '\n\nThe seed script today (keep what it makes that still applies):\n' + _today(live)}]
    while wrong and time.monotonic() < end:
        messages.append({'role': 'user', 'content': 'What is still lacking: ' + wrong})
        answer, _ = provider.complete(messages, stage='session')
        script = (answer.get('result') or answer).get('seed_script') or ''
        messages.append({'role': 'assistant', 'content': json.dumps({'seed_script': script})})
        wrong = _try(live, base, state, report, script, hand)
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

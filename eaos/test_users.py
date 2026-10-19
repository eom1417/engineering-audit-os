"""The test users of a check, made by the person's assistant on the app as it runs in its isolated copy (the stage
`session`, eaos/pipeline/sign_in_stage.py): the assistant writes the seed script that signs a user in, and one of each
kind of user of the code (eaos/roles.py); EAOS runs it on the running app and tells what is still lacking, until every
session opens its pages or SECONDS pass. Then the person is asked to sign in by hand. Each try takes seconds: the app is
never installed or started again for it.
"""
import json
import time

from .live_assist import _excerpt
from .live_run import kinds_folder
from .roles import about_users, opened, read
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
process.env.EAOS_STORAGE_STATE }), and for each kind of user listed, a user of that kind signed in and saved to
EAOS_SESSIONS_DIR/<id>.json. The output may end with one JSON line of the fixture values it created
({"E2E_PROFILEID": "..."}). Every address is http://127.0.0.1 or localhost; nothing deploys or reaches a hosted
service."""


def lacking(live, base, state, report):
    """What the sessions still lack, '' when nothing: the run's session must open the app, and each kind's its own
    pages (or the first page for a kind with none)."""
    from .sign_in import works
    if not works(live, base, state, report):
        return 'the browser state saved to EAOS_STORAGE_STATE does not open the app: its pages are sent to the sign-in'
    kinds = [kind for kind in read(report) if not _opens(live, base, kinds_folder(state) / f"{kind['id']}.json", kind['pages'])]
    return 'these kinds of users have no session that opens their own pages: ' + json.dumps(kinds) if kinds else ''


def _opens(live, base, session, pages):
    from .live_setup import probe
    page = probe(live, base, session, None, pages[:3]) if session.is_file() else {}
    return any(opened(row.get('path') or '/', row.get('url'), row.get('status'), row.get('password'))
               for row in (page.get('others') if pages else [page]) or [])


def make(project, live, base, state, report, provider):
    """The assistant's seed script, run on the running app and told what is still lacking, until nothing is or SECONDS
    pass; what is still lacking ('' when every session works)."""
    end, wrong = time.monotonic() + SECONDS, lacking(live, base, state, report)
    messages = [{'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': 'The kinds of users:\n' + json.dumps(read(report), ensure_ascii=False)
                 + '\n\nThe documentation:\n' + _excerpt(project, live.profile.get('app') or '.', 12000)
                 + '\n\nThe code about its users and sessions:\n' + about_users(project, 30000)
                 + '\n\nThe seed script today (keep what it makes that still applies):\n' + _today(live)}]
    while wrong and time.monotonic() < end:
        messages.append({'role': 'user', 'content': 'What is still lacking: ' + wrong})
        answer, _ = provider.complete(messages, stage='session')
        script = (answer.get('result') or answer).get('seed_script') or ''
        messages.append({'role': 'assistant', 'content': json.dumps({'seed_script': script})})
        wrong = _try(live, base, state, report, script)
    return wrong


def _today(live):
    seed = live.runtime / 'setup' / 'seed.cjs'
    return seed.read_text(encoding='utf-8') if seed.is_file() else '(none)'


def _try(live, base, state, report, script):
    """Run `script` as the seed on the running app; what is still lacking after it."""
    refused = safe({'seed_script': script}) if script else ['no seed_script was given']
    if refused: return 'nothing ran: ' + '; '.join(refused)
    live.profile['seed'] = apply(live.runtime, {'seed_script': script})['seed']
    try: live.seed(base, state)
    except RuntimeError as problem: return str(problem)[-2000:]
    return lacking(live, base, state, report)

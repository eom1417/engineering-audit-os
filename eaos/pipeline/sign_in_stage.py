"""The stage `session`, right after the app is set up: whether its pages need a sign-in, and the one session every page
stage opens them with (eaos/sign_in.py). It uses a session that still works; else, unless the person chose a test user
or no sign-in, it asks them (the Studio's Waiting for you, the assistant's status, `eaos watch` and `eaos sign-in`) and
waits while every stage that opens no page goes on. Nobody signing in within the wait ends it with that reason, and the
page stages see the app signed out, which the report says.
"""
import json
from pathlib import Path

from .. import sign_in
from .live_app import _keep, _live, close_app, shared_app
from .stages import SkipStage

CHOSEN_OUT = 'the person chose no sign-in: the pages behind it were seen signed out, as a visitor sees them'
NOBODY = ('nobody signed in within {minutes} minutes: the pages behind the sign-in were seen signed out, as a visitor '
          'sees them; sign in when the next check asks (or choose a test user)')
SAID_OUT = 'the person chose to go on without signing in: the pages behind the sign-in were seen signed out'
SEED_OUT = "the test user's seed script did not sign in: the pages behind the sign-in were seen signed out"
PUBLISHED = ('the crawl and the screens read {address} signed in, read only (GET, its own links, never a link that signs '
             'out, deletes or changes); the lock, the journeys and the load test never run against it, only on the isolated '
             'copy')


def session(context):
    chosen = context.setdefault('sign_in', {})
    if chosen.get('published'): return _published(context, chosen)
    _live(context)
    if chosen.get('how') == 'none': raise SkipStage(CHOSEN_OUT, code='sign_in_declined')
    evidence = sign_in.from_code(context.out) + sign_in.from_pages(_setup_page(context))
    if not evidence: return _record(context, {'needed': False})
    try:
        live, base, state = shared_app(context)          # seeded, or the person's session checked (asked once when expired)
        if not sign_in.works(live, base, state, context.out):
            if chosen.get('how') == 'test_user': raise SkipStage(SEED_OUT, code='signed_out')
            _ask(context, chosen, live, base, state)
    finally:
        close_app(context)                               # the lock runs its own copy next: never two apps at once
    return _record(context, {'needed': True, 'evidence': evidence, 'how': 'hand' if sign_in.by_hand(state) else 'test_user'})


def _ask(context, chosen, live, base, state):
    """The person asked to sign in, once a check, and waited for; SkipStage when the pages are seen signed out."""
    outcome = 'timeout'
    if not chosen.get('gave_up'):
        folder = chosen.get('folder') or live.runtime.parent
        sign_in.ask(folder, base, state, 'needed', log=sign_in.service_log(live), mail=live.mail())
        outcome = sign_in.wait(folder)
        if outcome == sign_in.SIGNED_IN and sign_in.works(live, base, state, context.out): return
    chosen['gave_up'] = True
    raise SkipStage(SAID_OUT if outcome == sign_in.SIGNED_OUT else NOBODY.format(minutes=sign_in.WAIT // 60), code='signed_out')


def _setup_page(context):
    """The first page and screens the setup's probe opened (live/setup.json), signed out unless a seed signed in."""
    try: return json.loads((context.out / 'live/setup.json').read_text(encoding='utf-8')).get('page')
    except (OSError, ValueError): return None


def _published(context, chosen):
    """The published address: the person signs in there on the sign-in page; nothing of the app runs here, and the
    session is for this check only (close_app removes it)."""
    state = Path(chosen['folder']) / sign_in.PUBLISHED
    sign_in.ask(chosen['folder'], chosen['published'], state, 'published', published=True)
    if sign_in.wait(chosen['folder']) != sign_in.SIGNED_IN:
        address, chosen['published'] = chosen['published'], None     # never opened without the person's session
        raise SkipStage(f'nobody signed in to {address}, so it was not read: ' + NOBODY.format(minutes=sign_in.WAIT // 60), code='signed_out')
    return _record(context, {'needed': True, 'how': 'hand', 'published': chosen['published'],
                             'note': PUBLISHED.format(address=chosen['published'])})


def _record(context, record):
    """live/sign-in.json: whether a sign-in was needed and how the pages were opened; never the session itself."""
    _keep(context, 'sign-in.json', {'schema_version': 1, **record})
    return {key: record[key] for key in ('needed', 'how', 'published') if key in record}

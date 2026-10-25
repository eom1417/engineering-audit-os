"""The stage `session`, right after the app is set up: whether its pages need a sign-in, and the sessions every page
stage opens them with (eaos/live/sign_in.py). Unless the person chose to sign in themselves, a test account is made by
rules on the app's own sign-up and sign-in pages (eaos/live/test_account.py), then the assistant makes the test
users on the running app, one of each kind of user (eaos/live/test_users.py), for five minutes at most; a session still
missing then, the person is asked (the Studio's Waiting for you, the assistant's status, `eaos watch` and `eaos
sign-in`) and waited for while every stage that opens no page goes on. Nobody signing in within the wait ends it with
that reason, and the page stages see the app signed out, which the report says.
"""
import json
from pathlib import Path

from ..live import sign_in
from .live_app import _keep, _live, shared_app
from .stages import SkipStage

CHOSEN_OUT = 'the person chose no sign-in: the pages behind it were seen signed out, as a visitor sees them'
NOBODY = ('nobody signed in within {minutes} minutes: the pages behind the sign-in were seen signed out, as a visitor '
          'sees them; sign in when the next check asks (or choose a test user)')
SAID_OUT = 'the person chose to go on without signing in: the pages behind the sign-in were seen signed out'
PUBLISHED = ('the crawl and the screens read {address} signed in, read only (GET, its own links, never a link that signs '
             'out, deletes or changes); Lighthouse, which cannot be held to reading, measures it signed out as any visitor; '
             'the lock, the journeys and the load test never run against it, only on the isolated copy')


def session(context):
    chosen = context.setdefault('sign_in', {})
    if chosen.get('published'): return _published(context, chosen)
    _live(context)
    if chosen.get('how') == 'none': raise SkipStage(CHOSEN_OUT, code='sign_in_declined')
    evidence = sign_in.from_code(context.out) + sign_in.from_pages(_setup_page(context))
    if not evidence: return _record(context, _views_alone(context))
    live, base, state = shared_app(context)              # seeded, or the person's session checked; kept for the page stages
    lacking = '' if sign_in.by_hand(state) or chosen.get('how') == 'hand' else _test_users(context, live, base, state)
    if not sign_in.works(live, base, state, context.out): _ask(context, chosen, live, base, state)
    if sign_in.by_hand(state): lacking = _test_users(context, live, base, state, hand=True)     # its switches into each view
    return _record(context, {'needed': True, 'evidence': evidence, 'how': 'hand' if sign_in.by_hand(state) else 'test_user',
                             **({'test_users': lacking[:300]} if lacking else {})})


def _by_rules(context, live, base, state):
    """A test account by rules (eaos/live/test_account.py) when the run's session does not open the pages: no assistant
    needed; what it tried is kept for the question the person may be asked."""
    if sign_in.works(live, base, state, context.out): return
    from ..live.test_account import by_rules
    try: context['sign_in']['tried'] = by_rules(live, base, state, sign_in.page_of(_setup_page(context), base))
    except Exception: context['sign_in']['tried'] = [{'did': 'no_form'}]      # rules never decide the check: the person is asked


def _views_alone(context):
    """No sign-in asked for (an app that opens signed in by itself, a development sign-in): the views are still made
    when the code has some, or when pages of the code open as none of themselves (chief-ops opened as support alone,
    its program's pages a "not found", and no view was ever looked for). Never asks the person to sign in."""
    from ..live.roles import read
    from ..live.test_users import unreached
    live, base, state = shared_app(context)              # the page stages start it anyway: no cost of its own
    alone = unreached(live, base, state, context.out)
    if not read(context.out) and not alone: return {'needed': False}
    lacking = _test_users(context, live, base, state)
    return {'needed': False, 'views': 'test_user', **({'unreached': sorted(alone)[:24]} if alone else {}),
            **({'test_users': lacking[:300]} if lacking else {})}


def _test_users(context, live, base, state, hand=False):
    """The assistant's test users on the running app (eaos/live/test_users.py), or with the person's own session (`hand`) its
    switches into each view a switch enters; what is still lacking, '' when nothing."""
    from ..live.test_users import lacking, make, views
    if hand and not views(context.out, True): return ''
    if not hand: _by_rules(context, live, base, state)
    if not context.provider: return lacking(live, base, state, context.out, hand)
    try: return make(context.target, live, base, state, context.out, context.provider, hand)
    except Exception as problem:          # the assistant never decides the fate of the check: the person is asked
        return f'the assistant could not make the test users ({type(problem).__name__}: {problem})'[:300]


def _ask(context, chosen, live, base, state):
    """The person asked to sign in, once a check, and waited for: on the sign-in page their pages are sent to, and asked
    again when they said they signed in but the pages still are not open (it once gave up as if nobody had come);
    SkipStage when the pages are seen signed out."""
    outcome, why = 'timeout', 'needed'
    while not chosen.get('gave_up'):
        folder = chosen.get('folder') or live.runtime.parent
        sign_in.ask(folder, sign_in.page_of(_setup_page(context), base), state, why, log=sign_in.service_log(live), mail=live.mail())
        sign_in.tell(folder, tried=chosen.get('tried') or [])     # what EAOS did before asking: the person sees why it asks
        outcome = sign_in.wait(folder)
        if outcome != sign_in.SIGNED_IN: break
        if sign_in.works(live, base, state, context.out): return
        why = 'not_signed_in'
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

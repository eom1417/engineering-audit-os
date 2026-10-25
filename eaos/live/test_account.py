"""A test account made by rules, before any assistant and without one (M5.3): the app's own sign-in page filled the way
a person fills it, after its own sign-up page when the account is not there yet (eaos/templates/setup/sign-up.cjs); a
Django app gets the account from its own command first (setup_python.py). So an app that signs in with a name or an
e-mail and a password is checked signed in on any computer: the corpus' sign-in app was seen signed out without an
assistant. The account is the run's own (EAOS_TEST_USER, a password the run chose, both in run.json -> env), made again
in each run's database; the script becomes the run's seed, so every later start signs in the same way."""
import json
import secrets
from pathlib import Path

from .run_profile import write_profile

SCRIPT = Path(__file__).resolve().parents[1] / 'templates/setup/sign-up.cjs'
USER = 'demo'


def account(profile):
    """The run's test account in `profile`'s environment, chosen once and kept (setup.kept keeps a password)."""
    env = profile.setdefault('env', {})
    env.setdefault('EAOS_TEST_USER', USER)
    env.setdefault('EAOS_TEST_PASSWORD', secrets.token_urlsafe(12) + 'Aa1!')
    return env['EAOS_TEST_USER'], env['EAOS_TEST_PASSWORD']


def by_rules(live, base, state, sign_in_page):
    """Sign in by rules on the running app, the session saved to `state`, the run's seed from now on: [] once in, else
    what was tried ([{did: signed_up | signed_in | no_form, at: its page}]), run.json as it was, for the question the person
    is asked (the Studio's words ac.si.did.*)."""
    seed = live.runtime / 'setup' / SCRIPT.name
    seed.parent.mkdir(parents=True, exist_ok=True)
    seed.write_text(SCRIPT.read_text(encoding='utf-8'), encoding='utf-8')
    profile = json.loads((live.runtime / 'run.json').read_text(encoding='utf-8'))
    account(profile)
    live.profile['env'] = {**(live.profile.get('env') or {}), **profile['env']}
    live.__dict__.pop('_extra', None)
    code, out, _ = live.run(['node', str(seed)], timeout=300, env={'BASE_URL': base, 'EAOS_STORAGE_STATE': str(state),
                                                                 'EAOS_SIGN_IN_PAGE': sign_in_page or ''})
    if code or not Path(state).is_file(): return _tried(out)
    profile['seed'] = live.profile['seed'] = [['node', str(seed)]]
    write_profile(live.runtime, profile)
    return []


def _tried(out):
    """What the script tried, from the last line it printed; at least that it tried."""
    try: return json.loads(out.strip().splitlines()[-1]).get('tried') or [{'did': 'no_form'}]
    except (ValueError, IndexError, AttributeError): return [{'did': 'no_form'}]

"""The person's choices for a check, and the options a check runs with: one place for the terminal (eaos start), the
assistant (the MCP audit tool) and the Studio.

    keep(state, mode=None, sign_in=None)   the mode (normal or speed) and the way to sign in, kept for the next checks;
                                           True when they changed, and the caller saves the state
    options(state, progress, failed, provider, runtime, paths=None, engines=None)
                                           pipeline.check's options: the language, the engines, the assistant's provider,
                                           the isolated copy, the tools started without, the paths and the kept mode
    estimate(report, paths=None, mode=None) the minutes such a check takes here, from the last check's seconds
    offered(state)                         what the start of a check offers: the paths, and the kept mode and sign-in

The paths are asked for each check (a focused check is a choice of the moment); the mode and the sign-in are kept. The
state comes from its callers (eaos/guided.py loads and saves it), so this module sits below them.
"""
from .pipeline.paths import PATHS, resolve
from .pipeline.schedule import MODES, forecast
from .pipeline.stages import ORDER
from .progress import previous_seconds

SIGN_IN = ('hand', 'test_user', 'none')        # by hand on the sign-in page, the assistant's seed script, no sign-in


def kept(state):
    """The choices kept for this project: {'mode', 'sign_in'}."""
    return {'mode': 'normal', 'sign_in': None, **(state.get('check') or {})}


def keep(state, mode=None, sign_in=None):
    """Keep the person's mode and way to sign in for this project's checks in `state`; True when they changed."""
    if mode is not None and mode not in MODES[:2]: raise ValueError(f'mode is one of normal, speed, not {mode!r}')
    if sign_in is not None and sign_in not in SIGN_IN: raise ValueError(f"sign_in is one of {', '.join(SIGN_IN)}, not {sign_in!r}")
    chosen = {k: v for k, v in (('mode', mode), ('sign_in', sign_in)) if v is not None}
    if not chosen or {**kept(state), **chosen} == kept(state): return False
    state['check'] = {**kept(state), **chosen}
    return True


def options(state, progress, failed, provider, runtime, paths=None, engines=None):
    """The options of pipeline.check for this project now (`failed`: the tools started without; `provider`, `runtime`: the
    assistant's and the isolated copy's, eaos/guided.py check_provider and check_runtime; `engines`: those to run again
    with again_from)."""
    resolve(paths)                                  # an unknown path stops the check before anything runs
    return dict(language=state.get('lang') or 'en', engines=engines or [], progress=progress, provider=provider, runtime=runtime,
                without_tools=sorted(failed), paths=paths, mode=kept(state)['mode'])


def estimate(report, paths=None, mode='normal'):
    """{'minutes_low', 'minutes_high', 'basis'} of a check of `paths` in `mode` on this project: its stages as the
    schedule runs them, each taking what it took in the last check (15% either side); None before a first check."""
    seconds = previous_seconds(report)
    if not seconds: return None
    stages = resolve(paths)['stages'] or ORDER
    minutes = forecast({name: seconds.get(name) or 0.0 for name in stages}, mode or 'normal') / 60
    return {'minutes_low': int(minutes * 0.85), 'minutes_high': int(minutes * 1.15) + 1,
            'basis': {'en': "this project's last check, each step as long as it took then",
                      'ar': 'آخر فحص لهذا المشروع، كل خطوة بالوقت الذي أخذته فيه'}}


def offered(state):
    """What the start of a check offers the person (the Studio's preview): each path with what it looks at, in both
    languages, and the mode and the way to sign in kept for this project."""
    paths = [{'id': key, 'name': dict(zip(('en', 'ar'), path['names'])), 'looks_at': dict(zip(('en', 'ar'), path['looks_at']))}
             for key, path in PATHS.items()]
    return {'paths': paths, **kept(state)}

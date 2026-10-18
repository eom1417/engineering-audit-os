"""The person's choices for a check, and the options a check runs with: one place for the terminal (eaos start), the
assistant (the MCP audit tool) and the Studio.

    keep(state, mode=None, sign_in=None)   the mode (normal or speed) and the way to sign in, kept for the next checks;
                                           True when they changed, and the caller saves the state
    options(state, progress, failed, provider, runtime, paths=None, engines=None, published=None)
                                           pipeline.check's options: the language, the engines, the assistant's provider,
                                           the isolated copy, the tools started without, the paths, the kept mode and
                                           how the page stages sign in
    estimate(report, paths=None, mode=None) the minutes such a check takes here, from the last check's seconds
    offered(state, report)                 what the start of a check offers: the paths, the kept mode and sign-in, and
                                           the sign-in the code shows

The paths are asked for each check (a focused check is a choice of the moment); the mode and the sign-in are kept. The
state comes from its callers (eaos/guided.py loads and saves it), so this module sits below them.
"""
import json
from pathlib import Path

from . import sign_in
from .pipeline.paths import PATHS, resolve
from .pipeline.schedule import MODES, forecast
from .pipeline.stages import BY_NAME, ORDER, dependents
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


def options(state, progress, failed, provider, runtime, paths=None, engines=None, published=None):
    """The options of pipeline.check for this project now (`failed`: the tools started without; `provider`, `runtime`: the
    assistant's and the isolated copy's, eaos/guided.py check_provider and check_runtime; `engines`: those to run again
    with again_from; `published`: the published address the person named for this check, read signed in, read only)."""
    resolve(paths)                                  # an unknown path stops the check before anything runs
    return dict(language=state.get('lang') or 'en', engines=engines or [], progress=progress, provider=provider, runtime=runtime,
                without_tools=sorted(failed), paths=paths, mode=kept(state)['mode'],
                sign_in={'how': kept(state)['sign_in'], 'published': published, 'folder': state['workspace']})


def estimate(report, paths=None, mode='normal', again_from=None):
    """{'minutes_low', 'minutes_high', 'basis'} of a check of `paths` in `mode` on this project: its stages as the
    schedule runs them, each taking what it took in the last check (15% either side); None before a first check.
    `again_from`: only that stage and the stages reading it run again (eaos/pipeline/run.py again)."""
    seconds = previous_seconds(report)
    if not seconds: return None
    stages = ((again_from, *dependents(again_from, reading=True)) if again_from in BY_NAME
              else resolve(paths)['stages'] or ORDER)
    minutes = forecast({name: seconds.get(name) or 0.0 for name in stages}, mode or 'normal') / 60
    return {'minutes_low': int(minutes * 0.85), 'minutes_high': int(minutes * 1.15) + 1,
            'basis': {'en': "this project's last check, each step as long as it took then",
                      'ar': 'آخر فحص لهذا المشروع، كل خطوة بالوقت الذي أخذته فيه'}}


def without_ai_kept(report, without_ai, again_from, chosen):
    """Whether a check runs without the assistant: when asked, or when it goes on (`again_from`) from a check that ran
    without it (its AI stages say so) and no assistant was chosen now, so a redo never stops on one never used."""
    if without_ai or not again_from or chosen: return bool(without_ai)
    try: stages = json.loads((Path(report) / 'run-manifest.json').read_text(encoding='utf-8')).get('stages') or {}
    except (OSError, ValueError, TypeError): return False
    return any((row or {}).get('reason_code') == 'ai_skipped' for row in stages.values())


def offered(state, report=None):
    """What the start of a check offers the person (the Studio's preview): each path with what it looks at, in both
    languages, the mode and the way to sign in kept for this project, and the sign-in its code shows (`report`: the last
    check's, eaos/sign_in.py from_code), when the ways to sign in are offered."""
    paths = [{'id': key, 'name': dict(zip(('en', 'ar'), path['names'])), 'looks_at': dict(zip(('en', 'ar'), path['looks_at']))}
             for key, path in PATHS.items()]
    return {'paths': paths, **kept(state), 'sign_in_seen': sign_in.from_code(report) if report else []}

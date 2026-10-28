"""The person's choices for a check, and the options a check runs with: one place for the terminal (eaos start), the
assistant (the MCP audit tool) and the Studio.

    keep(state, mode=None, sign_in=None)   the mode (normal or speed) and the way to sign in, kept for the next checks;
                                           True when they changed, and the caller saves the state
    options(state, progress, failed, provider, runtime, paths=None, engines=None, published=None)
                                           pipeline.check's options: the language, the engines, the assistant's provider,
                                           the isolated copy, the tools started without, the paths, the kept mode and
                                           how the page stages sign in
    estimate(report, paths=None, mode=None) the minutes such a check takes here, from the last check's seconds
    adds(paths)                            what the experience adds at most (minutes, assistant calls), when chosen
    offered(state, report)                 what the start of a check offers: the paths, the kept mode and sign-in, and
                                           the sign-in the code shows

The paths are asked for each check (a focused check is a choice of the moment); the mode and the sign-in are kept. The
state comes from its callers (eaos/journeys/guided/ loads and saves it), so this module sits below them.
"""
from datetime import datetime, timezone
from pathlib import Path

from ..live.access import sign_in
from ..core.contracts.check_paths import COMPLETE, PATHS
from ..pipeline.loops import switched_off
from ..pipeline.path_choice import resolve
from ..pipeline.schedule import MODES, forecast
from ..pipeline.stages import BY_NAME, ORDER, dependents
from ..core.progress import previous_seconds
from ..core.system.files import read_json

SIGN_IN = ('hand', 'test_user', 'none')        # by hand on the sign-in page, the assistant's seed script, no sign-in


def kept(state):
    """The choices kept for this project: {'mode', 'sign_in'}."""
    return {'mode': 'normal', 'sign_in': None, **(state.get('check') or {})}


def agreed_to_run(state):
    """Whether the person agreed to run their app in an isolated copy: asked by `eaos next` (question `run_app`), or given
    to the assistant, the Studio or the check's window (consent `run_and_fix`, agree_to_run)."""
    return any(q['id'] == 'run_app' and q.get('answer') for q in state.get('questions') or []) or \
        bool((state.get('consent') or {}).get('run_and_fix'))


def agree_to_run(state, via):
    """The person's yes to running their app in an isolated copy, kept for the project in `state` (asked once, not once
    a run; eaos/journeys/guided/ check_runtime reads it): the Studio's check window, `eaos check --run-app`, or the assistant."""
    state['consent'] = {**(state.get('consent') or {}), 'run_and_fix': True, 'at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    if not any(q.get('id') == 'run_and_fix' for q in state.setdefault('questions', [])):
        state['questions'].append({'id': 'run_and_fix', 'kind': 'yes_no', 'answer': True, 'via': via})


def keep(state, mode=None, sign_in=None, run_app=False):
    """Keep the person's mode, way to sign in and yes to running their app for this project's checks in `state`; True
    when they changed."""
    if mode is not None and mode not in MODES[:2]: raise ValueError(f'mode is one of normal, speed, not {mode!r}')
    if sign_in is not None and sign_in not in SIGN_IN: raise ValueError(f"sign_in is one of {', '.join(SIGN_IN)}, not {sign_in!r}")
    if run_app: agree_to_run(state, 'check')
    chosen = {k: v for k, v in (('mode', mode), ('sign_in', sign_in)) if v is not None}
    if not chosen or {**kept(state), **chosen} == kept(state): return bool(run_app)
    state['check'] = {**kept(state), **chosen}
    return True


def options(state, progress, failed, provider, runtime, paths=None, engines=None, published=None):  # limits: parameters -- builds pipeline.check's options, one parameter per source of them
    """The options of pipeline.check for this project now (`failed`: the tools started without; `provider`, `runtime`: the
    assistant's and the isolated copy's, eaos/journeys/guided/ check_provider and check_runtime; `engines`: those to run again
    with again_from; `published`: the published address the person named for this check, read signed in, read only)."""
    resolve(paths)                                  # an unknown path stops the check before anything runs
    return dict(language=state.get('lang') or 'en', engines=engines or [], progress=progress, provider=provider, runtime=runtime,
                without_tools=sorted(failed), paths=paths, mode=kept(state)['mode'],
                sign_in={'how': kept(state)['sign_in'], 'published': published, 'folder': state['workspace']})


def estimate(report, paths=None, mode='normal', again_from=None):
    """{'minutes_low', 'minutes_high', 'basis', 'experience'?} of a check of `paths` in `mode` on this project: its stages
    as the schedule runs them, each taking what it took in the last check (15% either side), the experience at its most
    when it never ran here (`experience`: what it costs, adds); None before a first check. `again_from`: only that stage
    and the stages reading it run again (eaos/pipeline/run.py again)."""
    seconds = previous_seconds(report)
    if not seconds: return None
    stages = _running(paths, again_from)
    cost = adds(paths) if 'experience' in stages else {}
    most = {'experience': cost['experience']['minutes'] * 60} if cost else {}
    minutes = forecast({name: seconds.get(name) or most.get(name, 0.0) for name in stages}, mode or 'normal') / 60
    return {'minutes_low': int(minutes * 0.85), 'minutes_high': int(minutes * 1.15) + 1,
            'basis': {'en': "this project's last check, each step as long as it took then",
                      'ar': 'آخر فحص لهذا المشروع، كل خطوة بالوقت الذي أخذته فيه'}, **cost}


def _running(paths, again_from):
    """The stages a check of `paths` runs: `again_from` and those reading it, else the paths' with their options on."""
    if again_from in BY_NAME: return (again_from, *dependents(again_from, reading=True))
    chosen = resolve(paths)
    return [name for name in chosen['stages'] or ORDER if name not in switched_off(chosen['paths'])]


def adds(paths):
    """{'experience': {simulation, minutes, calls}} when a check of `paths` tries the experience, else {}: what it adds at
    most, said before the check starts even on a first check. Beside `complete` the short option (eaos/analysis/
    experience/simulation.py SHORT: its steps on the light tier, one ruling on the deep one), alone the whole run's budget."""
    chosen = resolve(paths)['paths']
    if 'experience' not in chosen: return {}
    from ..analysis.experience import simulation
    from ..live.experience import cast
    if COMPLETE in chosen:
        return {'experience': {'simulation': 'short', 'minutes': simulation.SHORT['seconds'] // 60,
                               'calls': {'light': simulation.SHORT['steps'], 'deep': 1}}}
    return {'experience': {'simulation': 'whole', 'minutes': cast.BUDGET['seconds'] // 60, 'calls': {'most': cast.BUDGET['calls']}}}


def without_ai_kept(report, without_ai, again_from, chosen):
    """Whether a check runs without the assistant: when asked, or when it goes on (`again_from`) from a check that ran
    without it (its AI stages say so) and no assistant was chosen now, so a redo never stops on one never used."""
    if without_ai or not again_from or chosen: return bool(without_ai)
    stages = (read_json(Path(report) / 'run-manifest.json') or {}).get('stages') or {}
    return any((row or {}).get('reason_code') == 'ai_skipped' for row in stages.values())


def offered(state, report=None):
    """What the start of a check offers the person (the Studio's preview): each path with what it looks at, in both
    languages, the mode and the way to sign in kept for this project, the sign-in its code shows (`report`: the last
    check's, eaos/live/access/sign_in.py from_code), when the ways to sign in are offered, and whether the person already agreed
    to run their app (`run_app`): without it the pages, sign-in and speed are not checked, so the start asks it."""
    paths = [{'id': key, 'name': dict(zip(('en', 'ar'), path['names'])), 'looks_at': dict(zip(('en', 'ar'), path['looks_at']))}
             for key, path in PATHS.items()]
    return {'paths': paths, **kept(state), 'sign_in_seen': sign_in.from_code(report) if report else [],
            'run_app': agreed_to_run(state)}

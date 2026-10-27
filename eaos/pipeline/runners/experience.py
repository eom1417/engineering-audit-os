"""The experience's stage (M10.9): simulated users on the check's running app, signed in as the page stages are
(eaos/pipeline/runners/live_app.py sessions). Followed alone (the `experience` path) it is the whole simulation (the plan,
the run, the judging); beside `complete` it is the short one (eaos/analysis/experience/simulation.py short). Either way
the experience report is written. The replays of the saved journeys are not here: every full check runs them with the
behaviour lock (eaos/pipeline/runners/by_rules.py record)."""
from .by_assistant import _absent
from .live_app import _live, sessions


def app_of(context):
    """{'base', 'sessions': {kind of user: browser state}, 'runtime'}: the check's running app. A kind of user with no
    session of its own opens with the run's one session (the person's, or the seed's) when there is one."""
    from ...live.access.roles import read
    runtime = _live(context)
    _, base, made = sessions(context)
    states = {kind: path for kind, path in made}
    if None in states:
        states.update({kind['id']: states[None] for kind in read(context.out) if kind['id'] not in states})
    return {'base': base, 'sessions': states, 'runtime': runtime}


def experience(context):
    """The simulated users' run on the app, judged, and EXPERIENCE.md: whole when the check follows this path alone,
    short as an option of the full check."""
    if not context.provider: raise _absent(context.provider)
    from ...analysis.experience import simulation
    from ...report.experience.document import write
    app = app_of(context)
    if 'complete' in (context.get('paths') or ['complete']):
        ran, kind = simulation.short(context.out, context.target, app, context.provider), 'short'
    else:
        simulation.prepare(context.out, context.provider)
        ran, kind = simulation.simulate(context.out, context.target, app, context.provider), 'whole'
        ran['judged'] = simulation.judged(context.out, app, context.provider)
    write(context.out, context.language)
    goals = ran.get('goals') or []
    return {'simulation': kind, 'goals': len(goals), 'reached': sum(g['status'] == 'reached' for g in goals),
            'calls': ran.get('calls', 0), 'confirmed': (ran.get('judged') or {}).get('confirm', 0)}


def replayed(context, lock):
    """The lock's record (run_lock's answer) with every saved journey replayed on the check's app, no assistant asked,
    each a row of behavior-lock/results.json; as it was when no journey is saved."""
    from ...analysis.experience import simulation
    from ...live.experience import replay
    if not replay.saved(context.out): return lock
    app = app_of(context)
    return replay.join_lock(app['runtime'], lock, simulation.replays(context.out, app))

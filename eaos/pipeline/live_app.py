"""One app, database and sign-in for a check's page stages; owned by the check, never by a page stage."""
from pathlib import Path

PAGE_STAGES = frozenset(('session', 'journeys', 'crawl', 'screens'))


def shared_app(context, published=False):
    """(live run, address, browser state), started and seeded once. The state is the run's one session
    (eaos/sign_in.py): the seed's, written again at each start, or the person's, kept and checked before use (renewed
    once when it expired). `published`: a stage that only reads pages gets the published address the person named
    instead, (None, that address, its session), with nothing started. Page stages hold the declared app resource."""
    from .. import sign_in
    chosen = context.setdefault('sign_in', {})
    if published and chosen.get('published'): return None, chosen['published'], Path(chosen['folder']) / sign_in.PUBLISHED
    if 'page_app' not in context:
        from ..live_run import LiveRun
        live = LiveRun(context.target, context.runtime, 'S05')
        state = sign_in.session(context.runtime)
        try:
            live.setup()
            base = live.start()
            kept = sign_in.by_hand(state)
            seeded = state.with_name('.seeded.json') if kept else state      # a seed still makes its data; its session goes
            seeded.unlink(missing_ok=True)
            live.seed(base, seeded)
            if kept: seeded.unlink(missing_ok=True)
            if state.is_file(): state.chmod(0o600)
            if kept and not chosen.get('gave_up'): chosen['gave_up'] = not sign_in.renew(live, base, state, context.out, chosen.get('folder'))
        except BaseException:
            live.stop()
            raise
        context['page_app'] = live, base, state
    return context['page_app']


def close_app(context):
    """Release the shared app after the last page stage, or when the check stops or breaks; the published address's
    session, which is for one check only, goes with it."""
    app = context.pop('page_app', None)
    if app: app[0].stop()
    from ..sign_in import PUBLISHED
    chosen = context.get('sign_in') or {}
    if chosen.get('published'): (Path(chosen['folder']) / PUBLISHED).unlink(missing_ok=True)

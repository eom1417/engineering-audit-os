"""One app, database and sign-in for a check's page stages; owned by the check, never by a page stage."""
from pathlib import Path

PAGE_STAGES = frozenset(('journeys', 'crawl', 'screens'))


def shared_app(context):
    """(live run, address, browser state), started and seeded once. Page stages hold the declared app resource."""
    if 'page_app' not in context:
        from ..live_run import LiveRun
        live = LiveRun(context.target, context.runtime, 'S05')
        state = Path(context.runtime) / 'page-storage.json'
        try:
            live.setup()
            base = live.start()
            state.unlink(missing_ok=True)
            live.seed(base, state)
            if state.is_file(): state.chmod(0o600)
        except BaseException:
            live.stop()
            raise
        context['page_app'] = live, base, state
    return context['page_app']


def close_app(context):
    """Release the shared app after the last page stage, or when the check stops or breaks."""
    app = context.pop('page_app', None)
    if app: app[0].stop()

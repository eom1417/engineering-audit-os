"""One app, database and sign-in for a check's page stages; owned by the check, never by a page stage."""
from pathlib import Path

from ..stages import SkipStage

NO_RUN = ('the person has not agreed to run the app in an isolated copy (eaos next asks once), so nothing was run and '
          'the check reads the code alone')

# One app from the sign-in to the last page stage: an app that keeps its sessions in memory forgot the person's at
# each restart, so the check asked them to sign in again for every stage
PAGE_STAGES = frozenset(('session', 'record', 'journeys', 'crawl', 'screens', 'experience'))


def shared_app(context, published=False):
    """(live run, address, browser state), started and seeded once. The state is the run's one session
    (eaos/live/access/sign_in.py): the seed's, written again at each start, or the person's, kept and checked before use (renewed
    once when it expired). `published`: a stage that only reads pages gets the published address the person named
    instead, (None, that address, its session), with nothing started. Page stages hold the declared app resource."""
    from ...live.access import sign_in
    chosen = context.setdefault('sign_in', {})
    if published and chosen.get('published'): return None, chosen['published'], Path(chosen['folder']) / sign_in.PUBLISHED
    if 'page_app' not in context:
        from ...live.app.run import LiveRun
        live = LiveRun(context.target, context.runtime, 'S05')
        live.freeze()                                    # the lock records on it: the folders it reads, kept as they are
        state = sign_in.session(context.runtime)
        try:
            live.setup()
            base = live.start()
            kept = sign_in.by_hand(state)
            seeded = sign_in.seeding(state)               # a seed still makes its data; the person's session stays theirs
            live.seed(base, seeded)
            if kept: seeded.unlink(missing_ok=True)
            if kept and not chosen.get('gave_up'): chosen['gave_up'] = not sign_in.renew(live, base, state, context.out, chosen.get('folder'))
        except BaseException:
            live.stop()
            raise
        context['page_app'] = live, base, state
    return context['page_app']


def sessions(context, published=False):
    """(live run, address, [(kind, browser state)]): the app opened once as each kind of user of its code (eaos/live/access/roles.py)
    the seed made a session for, and with the run's one session (kind None) when it made none or the person signed in
    by hand: theirs is opened too."""
    from ...live.access import sign_in
    from ...live.app.run import kinds_folder
    from ...live.access.roles import read
    live, base, state = shared_app(context, published)
    made = [(kind['id'], path) for kind in (read(context.out) if live else [])
            if (path := kinds_folder(state) / f"{kind['id']}.json").is_file()]
    return live, base, made + ([(None, state)] if not made or sign_in.by_hand(state) else [])


def close_app(context):
    """Release the shared app after the last page stage, or when the check stops or breaks; the published address's
    session, which is for one check only, goes with it."""
    app = context.pop('page_app', None)
    if app: app[0].stop()
    from ...live.access.sign_in import PUBLISHED
    chosen = context.get('sign_in') or {}
    if chosen.get('published'): (Path(chosen['folder']) / PUBLISHED).unlink(missing_ok=True)


def _keep(context, name, record):
    """A live stage's record under <out>/live/."""
    from ...core.project.workspace import write
    (context.out / 'live').mkdir(exist_ok=True)
    write(context.out / 'live' / name, record)


def _live(context):
    """The runtime folder of an app this check started; else the reason no live stage can run."""
    if not context.get('runtime'):
        raise SkipStage(NO_RUN, code='no_run_consent')
    if not _ran(context, 'setup'):
        raise SkipStage('the app is not running in an isolated copy in this check: ' + (
            (context.get('manifest_so_far') or {}).get('stages', {}).get('setup', {}).get('reason') or 'its setup did not end ok'),
            code='app_not_running')
    return Path(context.runtime)


def _ran(context, name):
    """Whether stage `name` ended ok in this run: a record an earlier check left on disk is never read as this one's."""
    return ((context.get('manifest_so_far') or {}).get('stages') or {}).get(name, {}).get('status') == 'ok'


def studio(context):
    """The Studio's data of this check so far (eaos/report/studio/export.py): after the screens are pictured, so the person sees
    them while the check goes on (a real check showed 0 screens until the end); the proposals stage's record too."""
    from ...report.studio.export import export
    return export(context.out, context.language, Path(context.target).name, context.target)

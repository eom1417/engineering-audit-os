"""Set up a project's run with nothing written by hand (NS9.T3): run.json, a local database, sign-in, consent.

What a person once had to write for chief-ops (a run profile, a database, a seed script, an authorization),
this module finds or makes, in three passes:

  1. detect() (eaos/live/setup_detect.py): the app's folder, its package manager, how it installs, starts, builds
     and is checked, the environment names it reads (from .env.example files and the code; never from a real .env),
     and the database it needs. Deterministic, from the files alone.
  2. verify(): the draft is run for real in the sandbox (the project started, its first page opened in a
     browser that reaches 127.0.0.1 only). The page answers, or it does not; it asks for a sign-in, or not.
  3. assist(): when the page does not answer, or asks for a sign-in, the person's own AI assistant reads the
     project's documentation and the failure, and proposes changes: environment values, commands, and a seed
     script that signs in and adds sample data. Every proposal passes safe() before it runs: no command that
     deploys or reaches production, no address that is not 127.0.0.1, no file outside the run's folder. Then
     verify() runs again, at most ATTEMPTS times.

Nothing is guessed silently: what could not be made to work is written to run.json -> limitations, and shown.
The project folder is never written; everything goes to the run's folder (the guided workspace's runtime/).

setup() is the flow `setup` of the live map (eaos/core/progress/flow.py): its stages are FLOW, written as they happen to
<runtime>/progress/setup.jsonl, each attempt a step with its outcome.
"""
import json
import os
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path

from ..core import progress
from .assist import assist_messages, read_json
from .lock_specs import LEAVES
from ..core.progress.flow import OPTIONAL, Stage
from .run_profile import apply, safe, write_profile
from .setup_detect import SECRETISH, _unknown_app, detect, free_port, production_commands, script_is_safe  # noqa: F401  (detect's names others read here)

ATTEMPTS = 5


# ---------------------------------------------------------------- 2. verify

# The page a verify opens in a browser that reaches 127.0.0.1 only: the first page and a few screens, as JSON.
PROBE = (Path(__file__).resolve().parents[1] / 'templates/setup/probe.cjs').read_text(encoding='utf-8')




def routes(report, limit=4):
    """A few of the lock's screens and server pages (`GET /notes`) without parameters, to see that each one is a screen
    of its own and opens signed in; never one that signs out or changes (LEAVES), which would end the session the probe
    checks. A server app's pages left out, the probe saw only its public first page and took an empty session for one."""
    plan = read_json(Path(report) / 'behavior-lock/plan.json') if report else {}
    paths = [s.split(' (')[0].removeprefix('GET ') for spec in plan.get('specs') or [] for s in spec.get('surfaces') or []]
    return list(dict.fromkeys(s for s in paths if _openable(s)))[:limit]


def _openable(path):
    """Whether the probe may open a lock surface: a path of its own without parameters, that neither signs out nor in."""
    return (path.startswith('/') and path != '/' and not re.search(r'[:*$\[{]', path)
            and not re.search(LEAVES, path, re.I) and not re.search(SIGN_IN_PAGE, path))


def stuck(page):
    """Every screen visited shows the first page's text: a chooser or a gate stands in front of the app."""
    others = page.get('others') or []
    words = lambda text: ' '.join((text or '').split())
    return len(others) >= 2 and all(words(o.get('text')) == words(page.get('text')) for o in others)


SIGN_IN_PAGE = re.compile(r'/(login|signin|sign-in|auth)(\b|/|\?|$)', re.I)     # an address that is the sign-in itself


def signed_out(page):
    """The first page asks for a sign-in: a password field, or a login address it was sent to."""
    return bool(page.get('password')) or bool(SIGN_IN_PAGE.search(page.get('url') or ''))


# The words of a page that shows nothing yet: no data, no report, an empty list.
SHORT = 40                      # words: a longer first page is the app itself, never an empty state
EMPTY = re.compile(r'\b(no (data|reports?|results?|items?|records?|content|entries)\b|nothing (here|to show|yet)|is empty\b|'
                   r'(not|none) (found|available|loaded) yet)|لا (يوجد|توجد|شيء|بيانات)|فارغ', re.I)


def empty_state(page, unset):
    """Why the first page is no working app although it answered: it shows an empty, "no data" state while the run
    has no value for a name the app reads, so every screen would be pictured empty. '' otherwise: a page of more than
    SHORT words is the app, whatever "no ... yet" it shows (chief-ops' command center, "No new cases", was refused)."""
    text = ' '.join((page.get('text') or '').split())
    if not unset or len(text.split()) > SHORT or not (EMPTY.search(text) or len(text.split()) < 3): return ''
    return ('the first page shows an empty, no-data state while the app runs without a value for: ' + ', '.join(unset[:12])
            + '. Give it one (often a folder or address the app reads its data from); the page says: ' + (text[:400] or '(nothing)'))


def probe(live, base, state, report, paths=None):
    """What the probe saw of the first page and a few screens, or `paths` (with the browser state `state` when it is a
    file)."""
    script = live.sandbox.copy / '.eaos-probe.cjs'
    script.write_text(PROBE, encoding='utf-8')
    code, out, err = live.run(['node', str(script)], timeout=600, env={
        'BASE_URL': base, 'EAOS_STORAGE_STATE': str(state) if state.is_file() else '',
        'EAOS_ROUTES': json.dumps(routes(report) if paths is None else paths)})
    return json.loads(out.strip().splitlines()[-1]) if code == 0 and out.strip() else {'status': 0, 'errors': [(out + err)[-800:]]}


def _failure(page, empty):
    """Why the page is no working app, '' when it is one. A page asking for a sign-in is the app working: the stage
    `session` signs in to it (eaos/live/test_users.py)."""
    bad = _bad_answers(page)
    if stuck(page) and not signed_out(page):         # every screen sent to the sign-in is the app, signed out
        return ('every screen shows the same page, so something (a chooser, a gate) stands in front of the app: the seed '
                'picks one and saves the browser state to EAOS_STORAGE_STATE. The page says:\n' + '\n'.join(l for l in (page.get('text') or '').splitlines() if l.strip())[:600])
    if bad: return f"{bad[0].get('path', '/')} answered {bad[0].get('status')}: {'; '.join(page.get('errors') or [])[:600]}"
    return empty


def _bad_answers(page):
    """The first page and screens that did not answer: neither a page nor a sign-in asked."""
    # a page asking for a sign-in or a token (401), or refusing this user (403), is the app answering
    return [o for o in [page, *(page.get('others') or [])] if not 200 <= o.get('status', 0) < 400 and o.get('status') not in (401, 403)]


def verify(project, runtime, attempt, report=None, mode='lock'):
    """Run the draft: install (and, for the baseline, build), start, seed, open the first page and a few screens.
    {'ok', 'page', 'fixtures', 'failure'}"""
    from .run import LiveRun
    runtime = Path(runtime)
    live = LiveRun(project, runtime, 'S05', mode=mode)
    served, report = (report, None) if mode == 'baseline' else (None, report)    # the load opens the pages anonymously
    record = {'attempt': attempt, 'fixtures': {}}
    try:
        live.setup()
        base = live.start()
        from .runtime_baseline import refuse_a_page_server
        refuse_a_page_server(served, base)
        state = runtime / 'setup' / 'storage-state.json'
        if state.exists(): state.unlink()
        record['fixtures'] = dict(live.seed(base, state))
        record['seed_output'] = getattr(live, 'seed_output', '')
        page = record['page'] = probe(live, base, state, report)
        empty = '' if mode == 'baseline' else empty_state(page, _unset(runtime, live))
        failure = _failure(page, empty)
        record['ok'] = not failure
        if failure: record['failure'] = failure
    except Exception as problem:            # a failed start is the evidence the assistant needs, not a crash
        record['ok'] = False
        record['failure'] = f'{type(problem).__name__}: {problem}'[-2500:]
    finally:
        _with_seed(record)
        live.stop()
        live.record(f"setup/{'baseline-' if mode == 'baseline' else ''}attempt-{attempt}.json")
    return record


def _unset(runtime, live):
    """The environment names the app reads that the run gives no value."""
    names = (read_json(runtime / 'setup/detected.json').get('facts') or {}).get('env_names') or []
    return [n for n in names if n not in live.profile.get('env', {}) and n != 'NODE_ENV']


def _with_seed(record):
    """A failed attempt's failure followed by what the seed script said."""
    if not record.get('ok') and record.get('seed_output') and record.get('failure'):
        record['failure'] += '\nThe seed script said:\n' + record['seed_output'][-1500:]


# ---------------------------------------------------------------- 3. assist (what the assistant is told: eaos/live/assist.py)

def fixtures_needed(report):
    """The E2E_* names the lock's specs skip without."""
    names = set()
    for spec in (Path(report) / 'behavior-lock/playwright').glob('*.spec.ts') if report else []:
        names |= set(re.findall(r'needs_fixture: set (E2E_[A-Z0-9_]+)', spec.read_text(encoding='utf-8')))
    return sorted(names)


# ---------------------------------------------------------------- consent, and the whole setup

FLOW = (
    Stage('detect', description='Find, from the files alone, how the app installs, starts and builds, the environment '
                                'names it reads and the database it needs'),
    Stage('attempt', requires=('detect',),
          description=f'Start the app in the separate copy and open its first screens; when it does not answer, ask '
                      f'the assistant what to change and try again (at most {ATTEMPTS} attempts)'),
    Stage('baseline', requires=('attempt',), necessity=OPTIONAL,
          absent_when='the app has no production build, or it did not start in development',
          description='Build the production version of the app, start it from the build and open its first page, '
                      'for the speed test'),
)

def setup_baseline(project, runtime, detected, provider, say, report=None, attempts=3):
    """The production run the load baseline needs: built, started from the build, the first page answering, and the
    server routes of the code (`report`) served, not answered with the page. Marked in run.json -> baseline.verified,
    so the load test only runs on a production run that works; the assistant reads why an attempt failed."""
    runtime, record, refusal = Path(runtime), {'ok': False, 'failure': ''}, ''
    (runtime / 'setup').mkdir(parents=True, exist_ok=True)
    for attempt in range(1, attempts + 1):
        say(f'baseline-{attempt}')
        progress.step(f'attempt {attempt}', attempt - 1, attempts, 'running')
        record = verify(project, runtime, attempt, report, mode='baseline')
        progress.step(f'attempt {attempt}', attempt, attempts, 'ok' if record['ok'] else 'failed',
                      reason=(record.get('failure') or '')[:200], reason_code='' if record['ok'] else 'baseline_failed')
        if record['ok'] or provider is None: break
        refused = _ask(project, runtime, provider, detected, record['failure'], refusal, [], f'baseline-proposal-{attempt}', 'baseline')
        refusal = '; '.join(refused)
        if attempt == attempts:
            record = verify(project, runtime, attempt + 1, report, mode='baseline')
            if refused and not record['ok']: record['failure'] = 'the assistant proposed something unsafe, which was refused: ' + refused[0]
    profile = json.loads((runtime / 'run.json').read_text(encoding='utf-8'))
    profile['baseline']['verified'] = record['ok']
    write_profile(runtime, profile)
    return record


def owner(project):
    """Who gives the consent to run the app: the project's git user, else this computer's, else 'the owner'."""
    done = subprocess.run(['git', '-C', str(project), 'config', 'user.name'], capture_output=True, text=True)
    return done.stdout.strip() or os.environ.get('USER') or 'the owner'


def authorize(project, runtime, granted_by, days=30):
    """authorization.json for the project's current commit: the run stages, nothing passed from the environment."""
    from .sandbox import head
    commit = head(project)
    if not commit: raise RuntimeError(f'{project} is not a git repository')
    grant = {'schema_version': 1, 'project': Path(project).name, 'commit': commit, 'granted_by': granted_by,
             'stages': ['S05', 'S08', 'S09', 'S10', 'S11', 'S12', 'S13', 'S14'], 'env_allow': [],
             'expires': (date.today() + timedelta(days=days)).isoformat(),
             'note': 'Granted by answering yes in eaos next: runs happen in an isolated copy on this computer.'}
    path = Path(runtime) / 'authorization.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(grant, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return grant


def setup(project, runtime, report=None, provider=None, say=print):
    """Detect, verify, and ask the assistant when needed: run.json that works, or one whose limits are written.
    {'ok', 'attempts', 'limitations', 'page'}. Written as it happens as the flow `setup` (FLOW)."""
    with progress.Flow(runtime, 'setup', FLOW):
        return _setup(project, Path(runtime), report, provider, say)


def _setup(project, runtime, report, provider, say):
    (runtime / 'setup').mkdir(parents=True, exist_ok=True)
    progress.begin('detect')
    detected = detect(project, report)
    needs = fixtures_needed(report)
    write_profile(runtime, kept(runtime, detected['profile']))
    (runtime / 'setup/detected.json').write_text(json.dumps(detected, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    limitations = list(detected['limitations'])
    progress.begin('attempt')
    record, attempts, missing = _attempts(project, runtime, report, provider, say, detected, needs, limitations)
    ok = bool(record['ok'])
    if ok: progress.end('attempt')
    else: progress.end('attempt', 'failed', (record.get('failure') or 'the app did not answer')[:300],
                       'no_assistant' if provider is None else 'app_not_answering')
    _baseline(project, runtime, report, provider, say, detected, ok, limitations)
    if not ok and record.get('failure') and not any(record['failure'] in text for text in limitations):
        limitations.append('the app could not be made to answer: ' + record['failure'][:300])
    return _close(runtime, detected, ok, attempts, record, missing, limitations)


def kept(runtime, profile):
    """The new draft with what the last setup's run.json holds that must stay: the production run that worked (often
    the assistant's), and every secret the run chose, so a session signed with it (the person's sign-in) outlives it."""
    before = read_json(runtime / 'run.json') or {}
    if (before.get('baseline') or {}).get('verified'): profile['baseline'] = before['baseline']
    env = profile.get('env') or {}
    env.update({name: value for name, value in (before.get('env') or {}).items() if name in env and SECRETISH.search(name)})
    return profile


def _attempts(project, runtime, report, provider, say, detected, needs, limitations):
    """Verify the run, and while it fails ask the assistant for a safe change, at most ATTEMPTS times.
    (the last record, the attempts made, the fixtures still missing)."""
    refusal = ''
    for attempts in range(1, ATTEMPTS + 1):
        say(attempts)
        progress.step(f'attempt {attempts}', attempts - 1, ATTEMPTS, 'running')
        record = verify(project, runtime, attempts, report)
        known = {**json.loads((runtime / 'run.json').read_text())['env'], **record['fixtures']}
        missing = [name for name in needs if name not in known]
        failure, code = _lacking(record, missing)
        progress.step(f'attempt {attempts}', attempts, ATTEMPTS, 'failed' if failure else 'ok', reason=failure[:200], reason_code=code)
        if not failure: break
        if provider is None:
            limitations.append('no AI assistant was available to work out: ' + (record.get('failure') or 'the fixtures ' + ', '.join(missing)))
            break
        refused = _ask(project, runtime, provider, detected, failure, refusal, needs, f'proposal-{attempts}')
        refusal = '; '.join(refused)
        if refused:
            limitations.append('the assistant proposed something unsafe, which was refused: ' + refused[0])
            progress.step(f'attempt {attempts}', attempts, ATTEMPTS, 'failed', reason=refused[0][:200], reason_code='proposal_refused')
    return record, attempts, missing


def _lacking(record, missing):
    """(what the run still lacks, its reason code), ('', '') when nothing: the app not answering, or the fixture
    values the checks need."""
    if not record['ok']: return record.get('failure') or 'the app did not answer', 'app_not_answering'
    if missing: return 'the checks need fixture values: ' + ', '.join(missing), 'fixtures_missing'
    return '', ''


def _ask(project, runtime, provider, detected, failure, refusal, needs, name, mode='lock'):
    """Ask the assistant for a change, write it with what safe() refused to setup/<name>.json, and apply it when safe.
    The refusals, none when it was applied; the last refusal is told on the next ask."""
    if refusal: failure += f'. Your previous proposal was refused and not applied: {refusal}'
    answer, _ = provider.complete(assist_messages(project, runtime, detected, failure, needs, mode=mode), stage='setup', reads=project)
    proposal = answer.get('result') or {}
    refused = safe(proposal)
    (runtime / f'setup/{name}.json').write_text(json.dumps({'proposal': proposal, 'refused': refused}, ensure_ascii=False, indent=1) + '\n',
                                               encoding='utf-8')
    if not refused: apply(runtime, proposal, mode=mode)
    return refused


def _baseline(project, runtime, report, provider, say, detected, ok, limitations):
    """The stage `baseline`: the production run, once the app answered in development and has a build."""
    if not ok:
        progress.skip('baseline', 'the app did not start in development, so its production build was not tried', 'app_not_answering')
    elif not (detected['profile'].get('baseline') or {}).get('start'):
        progress.skip('baseline', 'no command starts the app as it runs in production', 'no_build')
    else:
        progress.begin('baseline')
        speed = setup_baseline(project, runtime, detected, provider, say, report)
        if speed['ok']:
            progress.end('baseline')
        else:
            limitations.append('speed cannot be measured: ' + speed['failure'][:300])
            progress.end('baseline', 'failed', speed['failure'][:300], 'baseline_failed')


def _close(runtime, detected, ok, attempts, record, missing, limitations):
    """Write the run's final limitations into run.json, and the setup's answer."""
    profile = json.loads((runtime / 'run.json').read_text(encoding='utf-8'))
    # Names the first draft left without a value may have one now.
    unset = [n for n in detected['facts']['env_names'] if n not in profile['env'] and n != 'NODE_ENV']
    limitations = [text for text in limitations if not text.startswith('no value was chosen for')]
    if unset and ok: limitations.append('run without a value for: ' + ', '.join(unset[:12]) + (' …' if len(unset) > 12 else ''))
    if missing: limitations.append('screens that need these values are not recorded: ' + ', '.join(missing))
    profile['limitations'] = sorted(set(limitations))
    write_profile(runtime, profile)
    return {'ok': ok, 'attempts': attempts, 'limitations': profile['limitations'], 'page': record.get('page')}

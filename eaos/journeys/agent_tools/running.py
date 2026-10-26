"""The app run in its isolated copy (run_setup, run_try) and the safety net recorded on it."""
import json

from .. import check_choices, guided
from ...live.app import assist as live_assist, profile as run_profile, setup as live_setup
from ...core.project import state as project_state
from .project import _head, _read, _start, state_of


# ---------------------------------------------------------------- running the app

CONSENT = ('May I run your app in a separate copy on this computer, with a temporary database and none of your secrets, '
           'and prepare fixes there that reach your project only as a new branch (your current branch and files stay as they are)?')


def _consented(state):
    return bool((state.get('consent') or {}).get('run_and_fix'))


def run_setup(project=None, person_agreed=False):
    state = state_of(project)
    if not person_agreed and not _consented(state):
        return {'status': 'needs_agreement', 'ask_the_person': CONSENT,
                'what_now': 'Ask the person this, in their language. Only if they say yes, call run_setup again with person_agreed=true.'}
    head = _head(state)
    if not head: raise RuntimeError(f"{state['project']}: fatal: not a git repository")
    check_choices.agree_to_run(state, 'assistant')
    guided.save(state)
    runtime = project_state.runtime_of(state)
    source = guided.source(state)
    live_setup.authorize(source, runtime, live_setup.owner(state['project']))
    detected = live_setup.detect(source, guided.report_of(state))
    (runtime / 'setup').mkdir(parents=True, exist_ok=True)
    (runtime / 'setup/detected.json').write_text(json.dumps(detected, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    run_profile.write_profile(runtime, live_setup.kept(runtime, detected['profile']))     # its secrets kept: a session holds
    return _start('run_try', state, {'proposal': None, 'mode': 'lock'}, watch=True)


def run_try(proposal=None, mode='lock', project=None):
    """Try the assistant's proposal (see live_assist.ASSIST_SYSTEM for its fields), refused when unsafe."""
    state = state_of(project)
    runtime = project_state.runtime_of(state)
    if not (runtime / 'run.json').is_file(): return {'status': 'not_set_up', 'what_now': 'Call run_setup first.'}
    if mode not in ('lock', 'baseline'): raise ValueError("mode is 'lock' (the app as developers run it) or 'baseline' (the production build)")
    refused = run_profile.safe(proposal or {})
    if refused:
        return {'status': 'refused', 'reasons': refused,
                'rules': 'Every address is 127.0.0.1 or localhost; commands start with npm, npx, pnpm, yarn, bun, node, corepack, python, '
                         'pip, uv, poetry, uvicorn or gunicorn; '
                         'nothing deploys or reaches a hosted service; no real secret. Use {database_url} and {run_dir}.'}
    return _start('run_try', state, {'proposal': proposal, 'mode': mode})


def _limitations(profile, record, runtime, missing):
    """The profile's limitations, the ones a run decides again replaced by what this run found."""
    unset = _unset(profile, runtime)
    limitations = [l for l in profile.get('limitations') or [] if not l.startswith(('run without a value', 'screens that need', 'the app could not'))]
    if unset and record['ok']: limitations.append('run without a value for: ' + ', '.join(unset[:12]))
    if missing: limitations.append('screens that need these values are not recorded: ' + ', '.join(missing))
    if not record['ok']: limitations.append('the app could not be made to answer: ' + (record.get('failure') or '')[:300])
    return sorted(set(limitations))


def _unset(profile, runtime):
    """The environment names the app reads that the profile gives no value (NODE_ENV aside)."""
    return [n for n in (_read(runtime / 'setup/detected.json')['facts'].get('env_names') or []) if n not in profile['env'] and n != 'NODE_ENV']


def _lock_run(project, runtime, report, record, profile, attempt):
    """After a run as developers run it: the profile's values and limitations, and the project's setup record.
    The fixtures the screens need and nobody gave."""
    needs = live_setup.fixtures_needed(report) if (report / 'plan.json').is_file() else []
    known = {**profile.get('env', {}), **record.get('fixtures', {})}
    missing = [name for name in needs if name not in known]
    if record.get('fixtures'):
        profile.setdefault('env', {}).update({k: str(v) for k, v in record['fixtures'].items()})
    profile['limitations'] = _limitations(profile, record, runtime, missing)
    run_profile.write_profile(runtime, profile)
    state = project_state.load(project)
    state['setup'] = {'commit': _head(state), 'ok': record['ok'], 'attempts': attempt, 'limitations': profile['limitations']}
    state.pop('safety', None)
    guided.save(state)
    return missing


def _production_build(source, runtime, answer, progress):
    """Build and start the production version once, to measure speed later; the profile as it is after."""
    progress(1, 2, 'building and starting the production version, to measure speed later')
    base = live_setup.verify(source, runtime, 1, mode='baseline')
    profile = _read(runtime / 'run.json')
    profile['baseline']['verified'] = base['ok']
    run_profile.write_profile(runtime, profile)
    answer['production_build_runs'] = base['ok']
    if not base['ok']: answer['production_failure'] = (base.get('failure') or '')[-2500:]
    return profile


def _first_page(page):
    if not page: return None
    return {'status': page.get('status'), 'url': page.get('url'), 'text': (page.get('text') or '')[:800],
            'others': [{k: o.get(k) for k in ('path', 'status', 'url')} for o in page.get('others') or []],
            'errors': (page.get('errors') or [])[:5]}


def _run_what_now(ok, mode):
    if ok and mode == 'lock': return 'The app runs: call safety_net.'
    if ok: return 'The production build runs.'
    return ('Read the failure and the code, then call run_try with a proposal: {"env": {...complete environment...}, '
            '"start": [...], "install": [[...]], "prepare": [[...]], "database": "postgres"|"none", '
            '"seed_script": "<node script that signs in and saves storage state>", "fixtures": {...}}'
            + (' (mode="baseline", with "build": [[...]] too)' if mode == 'baseline' else ''))


def _run_job(project, arguments, progress):
    runtime, report = project_state.runtime_of(state := project_state.load(project)), guided.report_of(state)
    mode, proposal = arguments.get('mode') or 'lock', arguments.get('proposal')
    if proposal: run_profile.apply(runtime, proposal, mode=mode)
    attempt = len(list((runtime / 'setup').glob(f"{'baseline-' if mode == 'baseline' else ''}attempt-*.json"))) + 1
    progress(0, 1, 'installing and starting the app in the isolated copy')
    source = guided.source(state)
    record = live_setup.verify(source, runtime, attempt, report if (report / 'plan.json').is_file() else None, mode=mode)
    profile = _read(runtime / 'run.json')
    answer = {'mode': mode, 'attempt': attempt, 'runs': record['ok']}
    if mode == 'baseline':
        profile.setdefault('baseline', {})['verified'] = record['ok']
        run_profile.write_profile(runtime, profile)
    else:
        answer['fixtures_missing'] = _lock_run(project, runtime, report, record, profile, attempt)
        if record['ok'] and (profile.get('baseline') or {}).get('build') and 'verified' not in profile['baseline']:
            profile = _production_build(source, runtime, answer, progress)
    return _run_answer(answer, record, profile, source, mode)


def _run_answer(answer, record, profile, source, mode):
    """The rest of a run's answer: its first page, its failure with the code that raised it, the profile, what now."""
    answer['first_page'] = _first_page(record.get('page') or {})
    if not record['ok']:
        answer['failure'] = (record.get('failure') or '')[-3000:]
        folder = profile.get('app') or '.'
        answer['code_that_raised_it'] = live_assist.relevant_source(source, folder, record.get('failure') or '', limit=2, context=30)[:8000]
    if record.get('seed_output'): answer['seed_output'] = record['seed_output'][-1500:]
    answer['profile'] = {k: profile.get(k) for k in ('app', 'install', 'prepare', 'start', 'port', 'env', 'database', 'seed', 'checks', 'baseline', 'limitations')}
    answer['what_now'] = _run_what_now(record['ok'], mode)
    return answer


def safety_net(project=None):
    state = state_of(project)
    if not guided.set_up(state, _head(state)): return {'status': 'not_set_up', 'what_now': 'Call run_setup first.'}
    return _start('safety_net', state, {}, watch=True)


def _safety_job(project, arguments, progress):
    state = project_state.load(project)
    outcome = guided.safety_run(state, lambda n: progress(n - 1, 2, 'recording every screen' if n == 1 else 'measuring speed under load'))
    outcome['record'] = str(project_state.runtime_of(state) / 'behavior-lock/results.json')
    outcome['what_now'] = 'Call fix_start to open a batch of fixes.'
    return outcome

"""The layers tried on the running app (M6.3's built output, M6.6, M6.7): an option of the check, the `layers` path, whose
time is said before it starts (eaos/data/words.json). The static part (eaos/analysis/layers/) named every endpoint and
table; this tries them:

- the built output: the app built in an isolated copy, as its production build, and read for privileged keys and maps;
- the data rules: the migrations applied to the run's own database, then the Supabase advisors and pgTAP per table
  (eaos/live/data_trial.py);
- the API: the app started in a copy of its own with two test accounts, then Schemathesis over its OpenAPI or the one
  derived from the endpoint table (eaos/live/api_trial.py).

Every failure is a finding with its evidence, joined to layers.json and the `boundaries` fact set.
"""
import json
from pathlib import Path

from .live_app import _live
from .stages import SkipStage

ADVISED = {'rls_disabled_in_public', 'rls_policy_always_true', 'security_definer_view', 'rls_enabled_no_policy'}
LEVELS = {'ERROR': 'high', 'WARN': 'medium', 'INFO': 'low'}


def _record(context):
    try: return json.loads((context.out / 'layers.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): raise SkipStage('the layers were not read in this check', code='no_layers')


def built(context, runtime):
    """(findings, what was read): the production build in an isolated copy, read like the project's own built output."""
    from ..analysis.layers.browser import built_output, built_folders
    from ..live.run import LiveRun
    live = LiveRun(context.target, runtime, 'S05', mode='baseline', apart='layers')
    if not (live.profile.get('baseline') or {}).get('verified'):
        return [], {'gap': 'the app has no production build the setup verified, so its built output was not read'}
    try:
        live.setup()
        return built_output(live.sandbox.copy, 'built:'), {'read': [str(f.relative_to(live.sandbox.copy)) for f in built_folders(live.sandbox.copy)]}
    finally:
        live.stop()


def _made_at(record, migrations):
    """where(table) -> (the migration that makes the table, its line), the first migration when none names it."""
    made = {row['table']: row for row in record['tables']}
    first = migrations[0] if migrations else '*'
    def where(table):
        row = made.get(table) or made.get('public.' + table) or {}
        return row.get('path') or first, row.get('line')
    return where


def _failed_tests(tried, where):
    return [{'rule': 'policy-failed-live', 'path': where(test['table'])[0], 'line': where(test['table'])[1],
             'evidence': f"pgTAP: not ok - {test['test']} (as {test['role']})", 'params': {'table': test['table'], 'test': test['test']}}
            for test in tried.get('tests') or [] if test['passed'] is False]


def _advised(tried, first):
    """The advisors' findings no static rule of the data layer already states."""
    return [{'rule': 'database-advisor', 'path': first, 'line': None, 'severity': LEVELS.get(row['level'], 'medium'),
             'evidence': f"supabase db advisors: {row['name']}", 'params': {'name': row['name'], 'detail': row['detail']}}
            for row in tried.get('advisors') or [] if row['name'] not in ADVISED]


def data(context, runtime, record):
    from ..live.data_trial import trial
    migrations = [row['path'] for row in record['map'] if row['side'] == 'database' and row['path'].endswith('.sql')]
    tried = trial(runtime, context.target, migrations)
    return _failed_tests(tried, _made_at(record, migrations)) + _advised(tried, migrations[0] if migrations else '*'), tried


def _accounts(live, base, runtime):
    """{name: request headers} of the run's two test accounts: its own (the seed's session) and a second one the sign-up
    script makes the same way, by rules."""
    from ..live import sign_in, test_account
    from ..live.api_trial import headers
    state = sign_in.session(runtime)
    live.seed(base, sign_in.seeding(state))
    found = {'first': headers(state)}
    seed = runtime / 'setup' / test_account.SCRIPT.name
    if seed.is_file():
        other = runtime / 'layers' / 'second.json'
        other.parent.mkdir(parents=True, exist_ok=True)
        live.run(['node', str(seed)], timeout=300, env={'BASE_URL': base, 'EAOS_STORAGE_STATE': str(other), 'EAOS_SIGN_IN_PAGE': '',
                                                        'EAOS_TEST_USER': 'demo2', 'EAOS_TEST_PASSWORD': 'Second-account-1'})
        found['second'] = headers(other)
    return {name: sent for name, sent in found.items() if sent}


def api(context, runtime, record):
    from ..live import api_trial
    from ..live.run import LiveRun
    folder = context.out / 'live' / 'api-trial'
    spec = api_trial.own_spec(context.target)
    if spec is None:
        folder.mkdir(parents=True, exist_ok=True)
        spec = folder / 'openapi.derived.json'
        spec.write_text(json.dumps(api_trial.derived(record['endpoints']), indent=1), encoding='utf-8')
    live = LiveRun(context.target, runtime, 'S05', apart='layers')
    try:
        live.setup()
        base = live.start()
        accounts = _accounts(live, base, Path(runtime))
        tried = api_trial.run(folder, spec, base, accounts)
    finally:
        live.stop()
    tried.update(spec=str(spec.relative_to(context.target)) if spec.is_relative_to(context.target) else 'derived from the endpoint table',
                 accounts=len(accounts))
    return [_api_finding(f, record['endpoints'], api_trial) for f in tried['failures']], tried


def _api_finding(failure, endpoints, api_trial):
    """One failed check, at the handler of its endpoint when the table names it."""
    row = next((r for r in endpoints if api_trial._openapi_path(r['route']) == failure['path']
                and r['method'] in (failure['method'], 'ANY')), {})
    return {'rule': api_trial.RULES[failure['check']], 'path': row.get('path') or '*', 'line': row.get('line'),
            'evidence': f"{failure['request']} -> {failure['status']} {failure['response'][:200]}",
            'params': {'method': failure['method'], 'route': failure['path'], 'status': failure['status'],
                       'detail': failure['detail'] or failure['title']}}


def layers_trial(context):
    """The `layers` option: the built output, the data rules and the API tried; what each could not try, said."""
    from ..analysis.layers import amend
    runtime = _live(context)
    record = _record(context)
    findings, live = [], {}
    for name, part in (('built', lambda: built(context, runtime)), ('data', lambda: data(context, runtime, record)),
                       ('api', lambda: api(context, runtime, record))):
        try:
            found, said = part()
        except Exception as failed:          # one part's failure is said, never the others' loss
            found, said = [], {'gap': f'{type(failed).__name__}: {str(failed)[-300:]}'}
        findings += found
        live[name] = said
    summary = amend(context.out, {'findings': findings, **live})
    return {'findings': len(findings), **{name: 'gap' if 'gap' in said else 'tried' for name, said in live.items()},
            'total': summary['findings'] if summary else None}

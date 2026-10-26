"""The eight questions every load model must answer for every entry point.

A load model is not a single number. It is a record that says, for each
reachable entry point, how it behaves under load: how much data it pulls,
how it repeats, whether its results are bounded, what its complexity class
is, whether it shares mutable state, whether its outbound calls are
protected, whether it caches, and whether it is rate-limited.

The eight questions live here as a constant; the schema lives in
eaos/data/schemas/load-model.schema.json. Anything that wants to answer a question
must do so in the agreed shape, with evidence and (when undetectable) a
reason that names what would have been needed to answer it. The projection at a multiple of
today's traffic and the load blockers it implies are in eaos/analysis/readiness/load_projection.py.
"""
from .load_projection import BLOCKERS, blockers, project  # noqa: F401  (the pipeline, the report and the tests read them here)

NAME = 'load_model'
VERSION = '1'

# The eight questions. Order matters: changing it is a contract change.
QUESTIONS = ('data_access_calls', 'repeats_per_iteration', 'result_is_bounded',
             'complexity_class', 'shared_mutable_state', 'outbound_calls_protected',
             'cached', 'rate_limited')

# The languages whose vocabulary each detector has. When the path is in one of these
# languages, the flow was traced, and the detector found nothing, the answer is "no"
# (answered with value=False); "undetectable" is reserved for paths we could not parse or
# whose language is outside the detector's vocabulary.
DETECTOR_LANGUAGES = {
    'data_access_calls': frozenset({'python', 'javascript', 'typescript', 'tsx', 'go', 'java', 'kotlin', 'scala'}),
    'repeats_per_iteration': frozenset({'python', 'javascript', 'typescript', 'tsx', 'go', 'java', 'kotlin', 'scala'}),
    'result_is_bounded': frozenset({'python', 'javascript', 'typescript', 'tsx', 'go', 'java', 'kotlin', 'scala'}),
    # `complexity_class` is driven by external engines; they only cover languages their
    # parsers support. We list the same set syntax extracts; when no fact arrives it is
    # because the engine could not measure, not because the function has no complexity.
    'complexity_class': frozenset({'python', 'javascript', 'typescript', 'tsx', 'go', 'java', 'kotlin', 'scala', 'c', 'cpp', 'csharp', 'php', 'ruby'}),
    # mutable_global/external_state_write are emitted by facts/domain/model.py for Python, Go, JavaScript and TypeScript.
    'shared_mutable_state': frozenset({'python', 'go', 'javascript', 'typescript', 'tsx'}),
    # resilience_policy runs over python/js/ts/go; integration_target is python/js/ts.
    'outbound_calls_protected': frozenset({'python', 'javascript', 'typescript', 'tsx', 'go'}),
    # cache_policy and rate_limit: facts/runtime/operations.py emits across python/js/ts/go + yaml manifests.
    'cached': frozenset({'python', 'javascript', 'typescript', 'tsx', 'go'}),
    'rate_limited': frozenset({'python', 'javascript', 'typescript', 'tsx', 'go'}),
}

ANSWER_STATUSES = ('answered', 'not_applicable', 'undetectable')

# Surfaces nobody can send a request to faster. A rate limit is a property of inbound traffic,
# and a surface with no inbound traffic has none to bound.
UNTHROTTLED_SURFACES = frozenset({'cli', 'cron', 'job', 'script', 'batch'})


# When a detector looked and did not find anything, the answer is still "answered" with
# value=False — provided the flow was traced AND every file in the path is in the
# detector's vocabulary. "undetectable" stays reserved for paths we could not trace or
# whose language the detector has no vocabulary for. The evidence is the trace's fact
# IDs so the reader can audit exactly what was searched.


def _supported(question, files):
    """True when every file in the path is in the detector's vocabulary."""
    supported = DETECTOR_LANGUAGES.get(question, frozenset())
    if not supported: return False
    from ...facts.source import language_of as _language_of
    for path in files:
        if _language_of(path) not in supported: return False
    return True


def _no_answer(question, evidence_ids, reason):
    return {'status': 'answered', 'value': False, 'evidence': evidence_ids,
            'reason': reason}


LIMITATIONS = (
    'A load model is a structured guess. It cannot replace a real load test.',
    '`undetectable` answers must carry a non-empty reason; silence is not allowed here.',
    'Each answer references the fact IDs that justify it. A claim without evidence is not an answer.',
    'An answered `value=False` means the detector looked and found nothing in its vocabulary. '
    'It does not prove the behaviour is absent in production: it proves the static evidence '
    'the detector covers is absent. A path whose language is outside `DETECTOR_LANGUAGES` '
    'stays undetectable, not answered-False, for that question.',
)


def blank_answer(question, status='undetectable', reason='not yet wired'):
    """Build one answer in the agreed shape, with sensible defaults for tests."""
    return {'question': question, 'status': status, 'value': None, 'evidence': [], 'reason': reason}


def validate(record):
    """Return a list of problems. Empty list means the record is well-formed.

    The check is the only contract; nothing else may silently accept a record.
    """
    problems = []
    for index, entry in enumerate(record.get('entry_points', [])): problems += _entry_problems(index, entry)
    return problems


def _entry_problems(index, entry):
    eid = entry.get('id', f'#{index}')
    answers = entry.get('answers') or {}
    missing = [q for q in QUESTIONS if q not in answers]
    problems = [f'entry_point {eid} is missing answers for {missing}'] if missing else []
    for question, answer in answers.items(): problems += _answer_problems(eid, question, answer)
    return problems


def _answer_problems(eid, question, answer):
    problems = []
    if question not in QUESTIONS:
        problems.append(f'entry_point {eid} answers an unknown question: {question}')
    status = answer.get('status')
    if status not in ANSWER_STATUSES:
        problems.append(f'entry_point {eid}/{question} has invalid status {status!r}')
    if status == 'undetectable' and not (answer.get('reason') or '').strip():
        problems.append(f'entry_point {eid}/{question} is undetectable but has no reason')
    if status == 'answered' and not (answer.get('evidence') or []):
        problems.append(f'entry_point {eid}/{question} is answered but has no evidence')
    return problems


# NS3.T5: build the load model on user-reachable surfaces only. NPM scripts and library
# entry points (a public API exposed to other code, not a person) are declared so the audit
# knows they exist; they are not what a load model is for.
USER_REACHABLE_SURFACES = {'page', 'http', 'cli'}
NON_USER_FRAMEWORKS = {'npm_script', 'public_api'}
DATA_ACCESS_NAMES = {
    'execute', 'executemany', 'fetchone', 'fetchall', 'fetchmany',
    'query', 'save', 'create', 'update', 'delete', 'insert', 'get', 'find', 'findOne', 'findMany',
    'select', 'all', 'one',
    'Exec', 'Query', 'QueryRow', 'Scan', 'Find', 'First',
}
LOOKED = '; the detector looked, the path is in a language whose vocabulary it covers'
OUTSIDE = ' and the path is outside the detectors vocabulary'


def _read_facts(facts_dir, name):
    import json
    path = facts_dir / f'{name}.json'
    if not path.is_file(): return {'facts': [], 'summary': {}}
    return json.loads(path.read_text(encoding='utf-8'))


def _user_reachable(fact):
    value = fact['value']
    return (fact['kind'] == 'entry_point' and value.get('category') != 'test'
            and value.get('surface') in USER_REACHABLE_SURFACES and value.get('framework') not in NON_USER_FRAMEWORKS)


def _last_by_path(payload, kind):
    return {f['location']['path']: f for f in payload.get('facts', []) if f['kind'] == kind}


def _bucket(facts, keep):
    """path -> every fact `keep` accepts there, in order."""
    out = {}
    for fact in facts:
        if keep(fact): out.setdefault(fact['location']['path'], []).append(fact)
    return out


def _flows_by_handler(flows):
    out = {}
    for flow in flows:
        out.setdefault((flow['location']['path'], flow['location'].get('symbol')), []).append(flow)
    return out


def _is_n_plus_one(fact):
    # A redundancy fact's kind is 'redundancy'; which redundancy it is lives in value.kind.
    # Testing the outer kind meant repeats_per_iteration never fired, on any project.
    return fact['kind'] == 'redundancy' and (fact.get('value') or {}).get('kind') == 'n_plus_one'


def _index(read):
    """Every fact the eight answers read, bucketed by path once."""
    entries, runtime, domain = read('entrypoints'), read('runtime'), read('domain')
    return {
        'entries': [f for f in entries.get('facts', []) if _user_reachable(f)],
        'flows_by_handler': _flows_by_handler(read('flows').get('facts', [])),
        'query_bound': _last_by_path(runtime, 'query_bound'),
        # Reads through Supabase or the app's own HTTP client carry whether their result is bounded
        # (facts/code/entrypoints.py, from facts/frameworks): a select with .limit/.range/.single, a GET of one resource.
        'reads': _bucket(entries.get('facts', []),
                         lambda f: f['kind'] == 'data_access' and f['value'].get('operation') in ('select', 'get')),
        'resilience': _last_by_path(runtime, 'resilience_policy'),
        'cache': _last_by_path(runtime, 'cache_policy'),
        'rate_limit': _last_by_path(runtime, 'rate_limit'),
        # Shared mutable state is a domain fact, not a runtime one. Looking for it in the runtime set
        # meant shared_mutable_state answered "undetectable" on every project that has it.
        'mutable': _last_by_path(domain, 'mutable_global'),
        'external_write': _last_by_path(domain, 'external_state_write'),
        'call_sites': _bucket(read('structure').get('facts', []), lambda f: f['kind'] == 'call_site'),
        'n_plus_one': _bucket(read('redundancy').get('facts', []), _is_n_plus_one),
        # Engine rule=performance facts
        'perf': [f for f in read('external').get('facts', [])
                 if f['value'].get('rule') == 'performance' or 'complexity' in str(f.get('value', {}))],
    }


def _paths_for(entry, flows_by_handler):
    """Files reachable from this entry point, plus the entry file itself."""
    handler = entry['location'].get('symbol') or entry['value'].get('handler')
    flow = flows_by_handler.get((entry['location']['path'], handler), [None])[0]
    if not flow:
        return [], []
    steps = flow['value'].get('steps', [])
    in_codebase = [s for s in steps if s.get('resolution') in {'local', 'imported'}]
    files = {entry['location']['path']} | {s['path'] for s in in_codebase if s.get('path')}
    return sorted(files), in_codebase


def _on_path(table, files): return [table[p] for p in files if p in table]


def _nothing_found(question, ctx, what):
    """No observation: answered no when the detector covers every file on the path, else undetectable."""
    if _supported(question, ctx['files']): return _no_answer(question, [ctx['own']], what + LOOKED)
    return blank_answer(question, status='undetectable', reason=what + OUTSIDE)


def _data_access_calls(ctx):
    # Count call_sites in the entry point's own file that match DATA_ACCESS_NAMES.
    path = ctx['path']
    ids = [cs['id'] for cs in ctx['index']['call_sites'].get(path, [])
           if (cs['value'].get('callee') or '').split('.')[-1] in DATA_ACCESS_NAMES]
    if ids:
        return {'status': 'answered', 'value': len(ids), 'evidence': ids,
                'reason': f'{len(ids)} data-access call sites in {path}'}
    return _nothing_found('data_access_calls', ctx, 'no data-access call sites recorded in this entry path')


def _repeats_per_iteration(ctx):
    # Any n_plus_one fact on the entry path -> True; False otherwise.
    n1 = ctx['index']['n_plus_one'].get(ctx['path'], [])
    if n1:
        return {'status': 'answered', 'value': True, 'evidence': [f['id'] for f in n1],
                'reason': f'{len(n1)} n+1 redundancy site(s) in this entry'}
    return _nothing_found('repeats_per_iteration', ctx, 'no n+1 redundancy observation in this entry path')


def _bounded_verdict(verdicts, evidence):
    if False in verdicts:
        unbounded = sum(v is False for v in verdicts)
        return {'status': 'answered', 'value': False, 'evidence': evidence,
                'reason': f'{unbounded} of {len(verdicts)} read(s) on this path return every matching row'}
    if all(v is True for v in verdicts):
        return {'status': 'answered', 'value': True, 'evidence': evidence,
                'reason': f'every read on this path ({len(verdicts)}) is limited or fetches one row'}
    return {'status': 'undetectable', 'value': None, 'evidence': evidence,
            'reason': 'a collection read whose size only the server decides'}


def _result_is_bounded(ctx):
    # Every read on the path, from SQL query_bound facts and from Supabase and HTTP reads. One unbounded read
    # answers no: that read is the risk. All bounded answers yes. A read whose bound only the server knows (a
    # collection GET) leaves it undetectable. No read at all, on a path the detectors cover, answers yes: there is
    # nothing to bound, and the evidence is the searched path.
    index, files = ctx['index'], ctx['files']
    found = _on_path(index['query_bound'], files) + [f for p in files for f in index['reads'].get(p, [])]
    if found: return _bounded_verdict([f['value'].get('bounded') for f in found], [f['id'] for f in found])
    if _supported('result_is_bounded', files):
        return {'status': 'answered', 'value': True, 'evidence': [ctx['own']],
                'reason': 'no data read on this path: the SQL, Supabase and HTTP-client detectors covered every file'}
    return blank_answer('result_is_bounded', status='undetectable',
                        reason='the path is in a language outside the read detectors')


def _complexity_class(ctx):
    perf = [f for f in ctx['index']['perf'] if f['location']['path'] in ctx['files']]
    if not perf:
        return blank_answer('complexity_class', status='undetectable',
                            reason='no engine performance observation on this path')
    return {'status': 'answered', 'value': perf[0]['value'].get('complexity') or perf[0]['value'].get('kind') or 'measured',
            'evidence': [f['id'] for f in perf],
            'reason': f'{len(perf)} performance observation(s) on the path'}


def _shared_mutable_state(ctx):
    # facts/domain/model.py models module-level state for Python, Go, JavaScript and TypeScript;
    # for other languages the question is honestly 'not applicable'.
    if not _supported('shared_mutable_state', ctx['files']):
        return {'question': 'shared_mutable_state', 'status': 'not_applicable', 'value': None,
                'evidence': [ctx['own']],
                'reason': 'the entry path is in a language outside the shared_mutable_state vocabulary (Python, Go, JavaScript, TypeScript)'}
    mut = _on_path(ctx['index']['mutable'], ctx['files'])
    ext_w = _on_path(ctx['index']['external_write'], ctx['files'])
    if not (mut or ext_w):
        return _no_answer('shared_mutable_state', [ctx['own']],
                          'no mutable_global or external_state_write on this path' + LOOKED)
    return {'status': 'answered', 'value': True, 'evidence': [f['id'] for f in mut + ext_w],
            'reason': f'{len(mut)} mutable global(s), {len(ext_w)} external-state write(s)'}


def _outbound_calls_protected(ctx):
    protections = _on_path(ctx['index']['resilience'], ctx['files'])
    if protections:
        value = {'timeout': any(f['value'].get('has_timeout') for f in protections),
                 'retry': any(f['value'].get('has_retry') for f in protections),
                 'circuit_breaker': any(f['value'].get('has_circuit_breaker') for f in protections)}
        return {'status': 'answered', 'value': value, 'evidence': [f['id'] for f in protections],
                'reason': 'resilience policy observed for at least one outbound call on the path'}
    if _supported('outbound_calls_protected', ctx['files']):
        # No outbound call on the path: nothing is left unprotected. Answering False here read as
        # "an unprotected call" and made every page without a call a load blocker.
        return {'status': 'answered', 'value': True, 'evidence': [ctx['own']],
                'reason': 'no outbound call on this path, so none is unprotected' + LOOKED}
    return blank_answer('outbound_calls_protected', status='undetectable',
                        reason='no integration_target on this path' + OUTSIDE)


def _cached(ctx):
    caches = _on_path(ctx['index']['cache'], ctx['files'])
    if caches:
        return {'status': 'answered', 'value': True, 'evidence': [f['id'] for f in caches],
                'reason': f'{len(caches)} cache site(s) on the path'}
    if _supported('cached', ctx['files']):
        return _no_answer('cached', [ctx['own']], 'no cache site found on this path' + LOOKED)
    return blank_answer('cached', status='undetectable', reason='no cache site on this path' + OUTSIDE)


def _rate_limited(ctx):
    limits = _on_path(ctx['index']['rate_limit'], ctx['files'])
    if limits:
        return {'status': 'answered', 'value': True, 'evidence': [f['id'] for f in limits],
                'reason': f'{len(limits)} rate-limit site(s) on the path'}
    if ctx['surface'] in UNTHROTTLED_SURFACES:
        # A command-line program answers one invocation from one operator. Reporting "no rate
        # limit" for it produced a bottleneck on every row of a CLI project's load table and
        # recommended throttling a script. The question does not apply, and saying so is an
        # answer rather than a finding.
        return {'question': 'rate_limited', 'status': 'not_applicable', 'value': None,
                'evidence': [ctx['own']],
                'reason': f"a {ctx['surface']} entry point has no inbound request rate to bound"}
    return _nothing_found('rate_limited', ctx, 'no rate-limit or concurrency bound on this path')


# One function per question, in QUESTIONS order.
ANSWERERS = (('data_access_calls', _data_access_calls), ('repeats_per_iteration', _repeats_per_iteration),
             ('result_is_bounded', _result_is_bounded), ('complexity_class', _complexity_class),
             ('shared_mutable_state', _shared_mutable_state), ('outbound_calls_protected', _outbound_calls_protected),
             ('cached', _cached), ('rate_limited', _rate_limited))


def _entry_record(entry, index):
    handler = entry['location'].get('symbol') or entry['value'].get('handler') or entry.get('id', '?')
    surface = entry['value'].get('surface') or 'unknown'
    path = entry['location']['path']
    files, _steps = _paths_for(entry, index['flows_by_handler'])
    if files:
        ctx = {'index': index, 'path': path, 'files': files, 'surface': surface, 'own': entry.get('id') or f'EP-{path}'}
        answers = {question: answer(ctx) for question, answer in ANSWERERS}
    else:
        answers = {q: blank_answer(q, status='undetectable', reason='the flow could not be traced from this entry point')
                   for q in QUESTIONS}
    return {'id': entry.get('id', f'EP-{path}:{handler}'),
            # A reader ranking entry points needs to know which entry point, not which fact.
            'label': entry['value'].get('route') or handler or path,
            'surface': surface,
            'handler': handler,
            'path': path,
            'answers': answers}


def compute(record_root):
    """Build a load-model record by reading facts already produced for this project.

    `record_root` is the report directory (the one with facts/ and dossier.json inside it).
    One entry per non-test entry point; every answer carries fact_ids; flows that could
    not be traced produce an "undetectable" set with a single shared reason.

    This module only reads the facts; it never makes a measurement of its own.
    """
    from pathlib import Path
    facts_dir = Path(record_root) / 'facts'
    if not facts_dir.is_dir():
        return {'schema_version': 1, 'entry_points': []}
    index = _index(lambda name: _read_facts(facts_dir, name))
    return {'schema_version': 1, 'entry_points': [_entry_record(entry, index) for entry in index['entries']]}

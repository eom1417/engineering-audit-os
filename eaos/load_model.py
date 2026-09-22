"""The eight questions every load model must answer for every entry point.

A load model is not a single number. It is a record that says, for each
reachable entry point, how it behaves under load: how much data it pulls,
how it repeats, whether its results are bounded, what its complexity class
is, whether it shares mutable state, whether its outbound calls are
protected, whether it caches, and whether it is rate-limited.

The eight questions live here as a constant; the schema lives in
schemas/load-model.schema.json. Anything that wants to answer a question
must do so in the agreed shape, with evidence and (when undetectable) a
reason that names what would have been needed to answer it.
"""
import json
from pathlib import Path

NAME = 'load_model'
VERSION = '1'

# The eight questions. Order matters: changing it is a contract change.
QUESTIONS = ('data_access_calls', 'repeats_per_iteration', 'result_is_bounded',
             'complexity_class', 'shared_mutable_state', 'outbound_calls_protected',
             'cached', 'rate_limited')

ANSWER_STATUSES = ('answered', 'not_applicable', 'undetectable')

LIMITATIONS = (
    'A load model is a structured guess. It cannot replace a real load test.',
    '`undetectable` answers must carry a non-empty reason; silence is not allowed here.',
    'Each answer references the fact IDs that justify it. A claim without evidence is not an answer.',
)


def blank_answer(question, status='undetectable', reason='not yet wired'):
    """Build one answer in the agreed shape, with sensible defaults for tests."""
    return {'question': question, 'status': status, 'value': None, 'evidence': [], 'reason': reason}


def validate(record):
    """Return a list of problems. Empty list means the record is well-formed.

    The check is the only contract; nothing else may silently accept a record.
    """
    problems = []
    for index, entry in enumerate(record.get('entry_points', [])):
        eid = entry.get('id', f'#{index}')
        answers = entry.get('answers') or {}
        missing = [q for q in QUESTIONS if q not in answers]
        if missing:
            problems.append(f'entry_point {eid} is missing answers for {missing}')
        for question, answer in answers.items():
            if question not in QUESTIONS:
                problems.append(f'entry_point {eid} answers an unknown question: {question}')
            status = answer.get('status')
            if status not in ANSWER_STATUSES:
                problems.append(f'entry_point {eid}/{question} has invalid status {status!r}')
            if status == 'undetectable' and not (answer.get('reason') or '').strip():
                problems.append(f'entry_point {eid}/{question} is undetectable but has no reason')
            evidence = answer.get('evidence') or []
            if status == 'answered' and not evidence:
                problems.append(f'entry_point {eid}/{question} is answered but has no evidence')
    return problems


def load_schema():
    """The JSON Schema the load-model record must satisfy."""
    path = Path(__file__).resolve().parents[1] / 'schemas' / 'load-model.schema.json'
    return json.loads(path.read_text(encoding='utf-8'))
def compute(record_root):
    """Build a load-model record by reading facts already produced for this project.

    `record_root` is the report directory (the one with facts/ and dossier.json inside it).
    One entry per non-test entry point; every answer carries fact_ids; flows that could
    not be traced produce an "undetectable" set with a single shared reason.

    This module only reads the facts; it never makes a measurement of its own.
    """
    import json
    from pathlib import Path
    facts_dir = Path(record_root) / 'facts'
    if not facts_dir.is_dir():
        return {'schema_version': 1, 'entry_points': []}

    def _read(name):
        path = facts_dir / f'{name}.json'
        if not path.is_file(): return {'facts': [], 'summary': {}}
        return json.loads(path.read_text(encoding='utf-8'))

    entries_payload = _read('entrypoints')
    flows_payload = _read('flows')
    structure_payload = _read('structure')
    redundancy_payload = _read('redundancy')
    runtime_payload = _read('runtime')
    domain_payload = _read('domain')
    external_payload = _read('external')

    entries = [f for f in entries_payload.get('facts', [])
               if f['kind'] == 'entry_point' and f['value'].get('category') != 'test']
    flows_by_handler = {}
    for flow in flows_payload.get('facts', []):
        key = (flow['location']['path'], flow['location'].get('symbol'))
        flows_by_handler.setdefault(key, []).append(flow)

    # Pre-bucket runtime facts by path
    def _by_path(name):
        return {f['location']['path']: f for f in runtime_payload.get('facts', [])
                if f['kind'] == name}

    query_bound_by_path = _by_path('query_bound')
    resilience_by_path = _by_path('resilience_policy')
    cache_by_path = _by_path('cache_policy')
    rate_limit_by_path = _by_path('rate_limit')
    mutable_by_path = _by_path('mutable_global')
    external_write_by_path = _by_path('external_state_write')
    call_sites_by_path = {}
    for fact in structure_payload.get('facts', []):
        if fact['kind'] == 'call_site':
            call_sites_by_path.setdefault(fact['location']['path'], []).append(fact)
    loops_by_path = {}
    for fact in structure_payload.get('facts', []):
        if fact['kind'] == 'loop':
            loops_by_path.setdefault(fact['location']['path'], []).append(fact)
    n_plus_one_by_path = {}
    for fact in redundancy_payload.get('facts', []):
        if fact['kind'] == 'n_plus_one':
            n_plus_one_by_path.setdefault(fact['location']['path'], []).append(fact)
    # Engine rule=performance facts
    perf_facts = [f for f in external_payload.get('facts', [])
                  if f['value'].get('rule') == 'performance' or 'complexity' in str(f.get('value', {}))]

    DATA_ACCESS_NAMES = {
        'execute', 'executemany', 'fetchone', 'fetchall', 'fetchmany',
        'query', 'save', 'create', 'update', 'delete', 'insert', 'get', 'find', 'findOne', 'findMany',
        'select', 'all', 'one',
    }

    def _paths_for(entry):
        """Files reachable from this entry point, plus the entry file itself."""
        handler = entry['location'].get('symbol') or entry['value'].get('handler')
        flow_key = (entry['location']['path'], handler)
        flow = flows_by_handler.get(flow_key, [None])[0]
        if not flow:
            return [], []
        steps = flow['value'].get('steps', [])
        in_codebase = [s for s in steps if s.get('resolution') in {'local', 'imported'}]
        files = {entry['location']['path']} | {s['path'] for s in in_codebase if s.get('path')}
        return sorted(files), in_codebase

    out_entries = []
    for entry in entries:
        handler = entry['location'].get('symbol') or entry['value'].get('handler') or entry.get('id', '?')
        path = entry['location']['path']
        files, steps = _paths_for(entry)
        if not files:
            out_entries.append({
                'id': entry.get('id', f'EP-{path}:{handler}'),
                'path': path,
                'answers': {q: blank_answer(q, status='undetectable',
                                              reason='the flow could not be traced from this entry point')
                             for q in QUESTIONS},
            })
            continue

        # Build each answer
        answers = {}

        # data_access_calls: count call_sites in entry point's own file that match DATA_ACCESS_NAMES
        data_access_ids = []
        access_count = 0
        for cs in call_sites_by_path.get(path, []):
            callee = (cs['value'].get('callee') or '').split('.')[-1]
            if callee in DATA_ACCESS_NAMES:
                access_count += 1
                data_access_ids.append(cs['id'])
        if data_access_ids:
            answers['data_access_calls'] = {
                'status': 'answered', 'value': access_count, 'evidence': data_access_ids,
                'reason': f'{access_count} data-access call sites in {path}',
            }
        else:
            answers['data_access_calls'] = blank_answer(
                'data_access_calls', status='undetectable',
                reason='no data-access call sites recorded in this entry path')

        # repeats_per_iteration: any n_plus_one fact on the entry path -> True; False otherwise
        n1 = n_plus_one_by_path.get(path, [])
        if n1:
            answers['repeats_per_iteration'] = {
                'status': 'answered', 'value': True,
                'evidence': [f['id'] for f in n1],
                'reason': f'{len(n1)} n+1 redundancy site(s) in this entry',
            }
        else:
            answers['repeats_per_iteration'] = blank_answer(
                'repeats_per_iteration', status='undetectable',
                reason='no n+1 redundancy observation in this entry path; cannot confirm or deny')

        # result_is_bounded: any query_bound with bounded=True on path -> True; bounded=False -> False; unknown -> unknown
        bounds = [query_bound_by_path[p] for p in files if p in query_bound_by_path]
        if bounds:
            all_bounded = all(f['value']['bounded'] is True for f in bounds)
            all_unbounded = all(f['value']['bounded'] is False for f in bounds)
            if all_bounded:
                answers['result_is_bounded'] = {
                    'status': 'answered', 'value': True,
                    'evidence': [f['id'] for f in bounds],
                    'reason': 'every query in this entry is bounded',
                }
            elif all_unbounded:
                answers['result_is_bounded'] = {
                    'status': 'answered', 'value': False,
                    'evidence': [f['id'] for f in bounds],
                    'reason': 'at least one query in this entry is unbounded',
                }
            else:
                answers['result_is_bounded'] = {
                    'status': 'undetectable', 'value': None,
                    'evidence': [f['id'] for f in bounds],
                    'reason': 'some queries are bounded, others are not; mixed result',
                }
        else:
            answers['result_is_bounded'] = blank_answer(
                'result_is_bounded',
                status='undetectable',
                reason='no query_bound fact on the path; this entry does not appear to query')

        # complexity_class: any perf fact on the path
        perf = [f for f in perf_facts if f['location']['path'] in files]
        if perf:
            answers['complexity_class'] = {
                'status': 'answered', 'value': perf[0]['value'].get('complexity') or perf[0]['value'].get('kind') or 'measured',
                'evidence': [f['id'] for f in perf],
                'reason': f'{len(perf)} performance observation(s) on the path',
            }
        else:
            answers['complexity_class'] = blank_answer(
                'complexity_class',
                status='undetectable',
                reason='no engine performance observation on this path')

        # shared_mutable_state
        mut = [mutable_by_path[p] for p in files if p in mutable_by_path]
        ext_w = [external_write_by_path[p] for p in files if p in external_write_by_path]
        if mut or ext_w:
            answers['shared_mutable_state'] = {
                'status': 'answered', 'value': True,
                'evidence': [f['id'] for f in mut + ext_w],
                'reason': f'{len(mut)} mutable global(s), {len(ext_w)} external-state write(s)',
            }
        else:
            answers['shared_mutable_state'] = blank_answer(
                'shared_mutable_state',
                status='undetectable',
                reason='no mutable_global or external_state_write on this path')

        # outbound_calls_protected
        protections = [resilience_by_path[p] for p in files if p in resilience_by_path]
        if protections:
            any_timeout = any(f['value'].get('has_timeout') for f in protections)
            any_retry = any(f['value'].get('has_retry') for f in protections)
            any_breaker = any(f['value'].get('has_circuit_breaker') for f in protections)
            value = {'timeout': any_timeout, 'retry': any_retry, 'circuit_breaker': any_breaker}
            answers['outbound_calls_protected'] = {
                'status': 'answered', 'value': value,
                'evidence': [f['id'] for f in protections],
                'reason': 'resilience policy observed for at least one outbound call on the path',
            }
        else:
            answers['outbound_calls_protected'] = blank_answer(
                'outbound_calls_protected',
                status='undetectable',
                reason='no integration_target on this path; nothing to protect')

        # cached
        caches = [cache_by_path[p] for p in files if p in cache_by_path]
        if caches:
            answers['cached'] = {
                'status': 'answered', 'value': True,
                'evidence': [f['id'] for f in caches],
                'reason': f'{len(caches)} cache site(s) on the path',
            }
        else:
            answers['cached'] = blank_answer(
                'cached', status='undetectable', reason='no cache site on this path')

        # rate_limited
        limits = [rate_limit_by_path[p] for p in files if p in rate_limit_by_path]
        if limits:
            answers['rate_limited'] = {
                'status': 'answered', 'value': True,
                'evidence': [f['id'] for f in limits],
                'reason': f'{len(limits)} rate-limit site(s) on the path',
            }
        else:
            answers['rate_limited'] = blank_answer(
                'rate_limited', status='undetectable',
                reason='no rate-limit or concurrency bound on this path')

        out_entries.append({
            'id': entry.get('id', f'EP-{path}:{handler}'),
            'path': path,
            'answers': answers,
        })

    return {'schema_version': 1, 'entry_points': out_entries}

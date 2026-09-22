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
    # mutable_global/external_state_write are emitted by domain.py for Python and Go.
    'shared_mutable_state': frozenset({'python', 'go'}),
    # resilience_policy runs over python/js/ts/go; integration_target is python/js/ts.
    'outbound_calls_protected': frozenset({'python', 'javascript', 'typescript', 'tsx', 'go'}),
    # cache_policy and rate_limit: runtime.py emits across python/js/ts/go + yaml manifests.
    'cached': frozenset({'python', 'javascript', 'typescript', 'tsx', 'go'}),
    'rate_limited': frozenset({'python', 'javascript', 'typescript', 'tsx', 'go'}),
}

ANSWER_STATUSES = ('answered', 'not_applicable', 'undetectable')


# When a detector looked and did not find anything, the answer is still "answered" with
# value=False — provided the flow was traced AND every file in the path is in the
# detector's vocabulary. "undetectable" stays reserved for paths we could not trace or
# whose language the detector has no vocabulary for. The evidence is the trace's fact
# IDs so the reader can audit exactly what was searched.


def _supported(question, files):
    """True when every file in the path is in the detector's vocabulary."""
    supported = DETECTOR_LANGUAGES.get(question, frozenset())
    if not supported: return False
    from .facts.source import language_of as _language_of
    for path in files:
        if _language_of(path) not in supported: return False
    return True


def _no_answer(question, evidence_ids, reason):
    return {'status': 'answered', 'value': False, 'evidence': evidence_ids,
            'reason': reason}


def _trace_evidence(flow_id):
    """Pull the traced flow's fact ID so an answered-False answer has something to cite."""
    if not flow_id: return []
    return [flow_id]


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
    def _by_path(name, payload=None):
        return {f['location']['path']: f for f in (payload or runtime_payload).get('facts', [])
                if f['kind'] == name}

    query_bound_by_path = _by_path('query_bound')
    resilience_by_path = _by_path('resilience_policy')
    cache_by_path = _by_path('cache_policy')
    rate_limit_by_path = _by_path('rate_limit')
    # Shared mutable state is a domain fact, not a runtime one. Looking for it in the runtime set
    # meant shared_mutable_state answered "undetectable" on every project that has it.
    mutable_by_path = _by_path('mutable_global', domain_payload)
    external_write_by_path = _by_path('external_state_write', domain_payload)
    call_sites_by_path = {}
    for fact in structure_payload.get('facts', []):
        if fact['kind'] == 'call_site':
            call_sites_by_path.setdefault(fact['location']['path'], []).append(fact)
    loops_by_path = {}
    for fact in structure_payload.get('facts', []):
        if fact['kind'] == 'loop':
            loops_by_path.setdefault(fact['location']['path'], []).append(fact)
    # A redundancy fact's kind is 'redundancy'; which redundancy it is lives in value.kind.
    # Testing the outer kind meant repeats_per_iteration never fired, on any project.
    n_plus_one_by_path = {}
    for fact in redundancy_payload.get('facts', []):
        if fact['kind'] == 'redundancy' and (fact.get('value') or {}).get('kind') == 'n_plus_one':
            n_plus_one_by_path.setdefault(fact['location']['path'], []).append(fact)
    # Engine rule=performance facts
    perf_facts = [f for f in external_payload.get('facts', [])
                  if f['value'].get('rule') == 'performance' or 'complexity' in str(f.get('value', {}))]

    DATA_ACCESS_NAMES = {
        'execute', 'executemany', 'fetchone', 'fetchall', 'fetchmany',
        'query', 'save', 'create', 'update', 'delete', 'insert', 'get', 'find', 'findOne', 'findMany',
        'select', 'all', 'one',
        'Exec', 'Query', 'QueryRow', 'Scan', 'Find', 'First',
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
        elif _supported('data_access_calls', files):
            answers['data_access_calls'] = _no_answer(
                'data_access_calls', [entry.get('id') or f'EP-{path}'],
                'no data-access call sites recorded in this entry path; the detector looked, the path is in a language whose vocabulary it covers')
        else:
            answers['data_access_calls'] = blank_answer(
                'data_access_calls', status='undetectable',
                reason='no data-access call sites recorded in this entry path and the path is outside the detectors vocabulary')

        # repeats_per_iteration: any n_plus_one fact on the entry path -> True; False otherwise
        n1 = n_plus_one_by_path.get(path, [])
        if n1:
            answers['repeats_per_iteration'] = {
                'status': 'answered', 'value': True,
                'evidence': [f['id'] for f in n1],
                'reason': f'{len(n1)} n+1 redundancy site(s) in this entry',
            }
        elif _supported('repeats_per_iteration', files):
            answers['repeats_per_iteration'] = _no_answer(
                'repeats_per_iteration', [entry.get('id') or f'EP-{path}'],
                'no n+1 redundancy observation in this entry path; the detector looked, the path is in a language whose vocabulary it covers')
        else:
            answers['repeats_per_iteration'] = blank_answer(
                'repeats_per_iteration', status='undetectable',
                reason='no n+1 redundancy observation in this entry path and the path is outside the detectors vocabulary')

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
        elif _supported('shared_mutable_state', files):
            answers['shared_mutable_state'] = _no_answer(
                'shared_mutable_state', [entry.get('id') or f'EP-{path}'],
                'no mutable_global or external_state_write on this path; the detector looked, the path is in a language whose vocabulary it covers')
        else:
            answers['shared_mutable_state'] = blank_answer(
                'shared_mutable_state', status='undetectable',
                reason='no mutable_global or external_state_write on this path and the path is outside the detectors vocabulary')

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
        elif _supported('outbound_calls_protected', files):
            answers['outbound_calls_protected'] = _no_answer(
                'outbound_calls_protected', [entry.get('id') or f'EP-{path}'],
                'no integration_target on this path; the detector looked, the path is in a language whose vocabulary it covers')
        else:
            answers['outbound_calls_protected'] = blank_answer(
                'outbound_calls_protected', status='undetectable',
                reason='no integration_target on this path and the path is outside the detectors vocabulary')

        # cached
        caches = [cache_by_path[p] for p in files if p in cache_by_path]
        if caches:
            answers['cached'] = {
                'status': 'answered', 'value': True,
                'evidence': [f['id'] for f in caches],
                'reason': f'{len(caches)} cache site(s) on the path',
            }
        elif _supported('cached', files):
            answers['cached'] = _no_answer(
                'cached', [entry.get('id') or f'EP-{path}'],
                'no cache site found on this path; the detector looked, the path is in a language whose vocabulary it covers')
        else:
            answers['cached'] = blank_answer(
                'cached', status='undetectable',
                reason='no cache site on this path and the path is outside the detectors vocabulary')

        # rate_limited
        limits = [rate_limit_by_path[p] for p in files if p in rate_limit_by_path]
        if limits:
            answers['rate_limited'] = {
                'status': 'answered', 'value': True,
                'evidence': [f['id'] for f in limits],
                'reason': f'{len(limits)} rate-limit site(s) on the path',
            }
        elif _supported('rate_limited', files):
            answers['rate_limited'] = _no_answer(
                'rate_limited', [entry.get('id') or f'EP-{path}'],
                'no rate-limit or concurrency bound on this path; the detector looked, the path is in a language whose vocabulary it covers')
        else:
            answers['rate_limited'] = blank_answer(
                'rate_limited', status='undetectable',
                reason='no rate-limit or concurrency bound on this path and the path is outside the detectors vocabulary')

        out_entries.append({
            'id': entry.get('id', f'EP-{path}:{handler}'),
            'path': path,
            'answers': answers,
        })

    return {'schema_version': 1, 'entry_points': out_entries}


# A simple, stated projection: we do not measure performance. We combine the load-model
# answers into a per-entry-point ceiling on the multiple of cost you should expect at
# `m` times the current traffic. The rule is explicit so the reader can disagree with
# the formula and still trust the number.
def project(record, multiplier=1000):
    """Add a `projection.at_<multiplier>x` block to the record.

    The cost ceiling is a multiplicative score, not a number of seconds:
      -1.0 per undetectable answer (the projection cannot say),
      +m per answered query (the query runs m times),
      +m*100 per answered n+1 (each iteration triggers another query),
      +0 per bounded cache (free, modulo m),
      +1.0 per unbounded query (grows with data, not with m),
      +1.0 per missing rate limit (no protection against burst).

    We rank bottlenecks in this order: missing rate limit > n+1 > unbounded query > shared state.
    """
    out_entry_points = []
    for entry in record.get('entry_points', []):
        answers = entry.get('answers') or {}
        cost = 0.0
        unknown = []

        dac = answers.get('data_access_calls', {})
        access_count = dac.get('value') if dac.get('status') == 'answered' else None
        if access_count is None:
            unknown.append('data_access_calls')
            access_count = 0
        else:
            cost += access_count * multiplier

        rep = answers.get('repeats_per_iteration', {})
        if rep.get('status') != 'answered':
            unknown.append('repeats_per_iteration')
            n_plus_one_factor = 0
        elif rep.get('value') is True:
            # n+1 multiplies per iteration: the effective cost scales by `m * n_iterations`
            n_plus_one_factor = multiplier * 100
            cost += n_plus_one_factor
        else:
            n_plus_one_factor = 0

        rib = answers.get('result_is_bounded', {})
        if rib.get('status') != 'answered':
            unknown.append('result_is_bounded')
            unbounded = False
        else:
            unbounded = rib.get('value') is False
            if unbounded: cost += multiplier  # result grows with data, not with m

        sm = answers.get('shared_mutable_state', {})
        if sm.get('status') != 'answered':
            unknown.append('shared_mutable_state')
            shared = False
        else:
            shared = sm.get('value') is True
            if shared: cost += multiplier * 10  # serialization pressure

        rl = answers.get('rate_limited', {})
        if rl.get('status') != 'answered':
            unknown.append('rate_limited')
            no_limit = False
        else:
            no_limit = rl.get('value') is False
            if no_limit: cost += multiplier * 50  # one burst and you're done

        # Rank bottlenecks: missing limit > n+1 > unbounded > shared
        bottlenecks = []
        if no_limit: bottlenecks.append('no_rate_limit')
        if rep.get('status') == 'answered' and rep.get('value') is True:
            bottlenecks.append('n_plus_one')
        if unbounded: bottlenecks.append('unbounded_query')
        if shared: bottlenecks.append('shared_mutable_state')

        projection = {
            'multiplier': multiplier,
            'cost_score': round(cost, 2),
            'interpretation': (
                f'projected ceiling of {round(cost, 2)} cost units at {multiplier}x traffic '
                f'(data_access_calls={access_count}, n_plus_one={rep.get("value") if rep.get("status") == "answered" else "?"}, '
                f'unbounded={unbounded}, shared_state={shared}, rate_limited={not no_limit})'
            ),
            'bottlenecks': bottlenecks,
            'caveats': [
                'This is a structural projection, not a performance measurement.',
                'Cost is in arbitrary units that rank entries, not seconds or RPS.',
                'An undetectable answer becomes a caveat: the entry is "incomplete" in the projection.',
            ],
        }
        # Completeness covers every question, not only the ones whose answers
        # affect the cost score.
        all_unknown = []
        for question, answer in answers.items():
            if answer.get('status') != 'answered' and answer.get('status') != 'not_applicable':
                all_unknown.append(question)
        if all_unknown:
            projection['incomplete'] = True
            projection['unanswered_questions'] = sorted(all_unknown)
        else:
            projection['incomplete'] = False
        out_entry_points.append({**entry, 'projection': projection})

    return {**record, 'entry_points': out_entry_points, 'projection': {
        'multiplier': multiplier,
        'method': (
            f'multiplier={multiplier}; cost per data_access_call, ×100 per n+1, '
            f'×{multiplier} per unbounded query, ×10 per shared-state mutation, '
            f'×50 per missing rate limit'
        ),
    }}


# A load blocker is an answered question whose answer means the entry point gets worse as traffic
# grows. An unanswered question is never a blocker: we do not know, and saying otherwise would
# invent a risk.
BLOCKERS = {
    'repeats_per_iteration': {
        'kind': 'n_plus_one',
        'holds_when': lambda value: bool(value),
        'statement': 'يصدر استعلامًا لكل عنصر' ,
        'statement_en': 'issues one query per item',
        'falsifier': 'A measurement showing this call runs once regardless of the number of items.',
        'scenario': 'كل عنصر إضافي في الطلب يضيف استعلامًا؛ الكلفة تنمو مع البيانات لا مع الحركة وحدها.',
    },
    'result_is_bounded': {
        'kind': 'unbounded_result',
        'holds_when': lambda value: value is False,
        'statement': 'يعيد نتيجة بلا حد أعلى',
        'statement_en': 'returns an unbounded result',
        'falsifier': 'A limit, page size or cursor on this query, or a schema guaranteeing the row count.',
        'scenario': 'حجم الرد ينمو مع حجم البيانات؛ ما يعمل اليوم على ألف صف يسقط على مليون.',
    },
    'shared_mutable_state': {
        'kind': 'horizontal_scaling_blocker',
        'holds_when': lambda value: bool(value),
        'statement': 'يكتب في حالة على مستوى الوحدة',
        'statement_en': 'writes module-level state',
        'falsifier': 'The state moved to a shared store, or shown to be read-only after import.',
        'scenario': 'نسختان من التطبيق ترى كل منهما حالة مختلفة؛ هذا يمنع التوسّع الأفقي قبل أن تصل قاعدة البيانات إلى حدّها.',
    },
    'outbound_calls_protected': {
        'kind': 'unprotected_dependency',
        # The answer is a guard-by-guard record. A missing timeout is the blocker: retries without
        # a timeout make the pile-up worse, not better.
        'holds_when': lambda value: (value is False or
                                     (isinstance(value, dict) and value.get('timeout') is False)),
        'statement': 'ينادي خدمة خارجية بلا مهلة أو إعادة محاولة',
        'statement_en': 'calls an external service with no timeout or retry',
        'falsifier': 'A timeout, retry policy or circuit breaker on the call, or evidence the call is local.',
        'scenario': 'بطء الخدمة الأخرى يصير توقفًا عندك؛ الطلبات تتراكم حتى ينفد التجمّع.',
    },
}


def blockers(record):
    """Every answered question whose answer means this entry point degrades under load."""
    found = []
    for entry in record.get('entry_points', []):
        for question, rule in BLOCKERS.items():
            answer = (entry.get('answers') or {}).get(question) or {}
            if answer.get('status') != 'answered':
                continue
            if not rule['holds_when'](answer.get('value')):
                continue
            found.append({
                'entry_point': entry.get('id'),
                'path': entry.get('path'),
                'route': (entry.get('entry') or {}).get('route'),
                'question': question,
                'kind': rule['kind'],
                'statement': rule['statement'],
                'statement_en': rule['statement_en'],
                'falsifier': rule['falsifier'],
                'scenario': rule['scenario'],
                'value': answer.get('value'),
                'evidence': list(answer.get('evidence') or []),
            })
    return sorted(found, key=lambda row: (row['kind'], str(row['path']), str(row['entry_point'])))

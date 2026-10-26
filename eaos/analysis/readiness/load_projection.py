"""The load model projected (eaos/analysis/readiness/load_model.py answers its eight questions): each entry point's cost ceiling at
a multiple of today's traffic, and the load blockers its answers imply.
"""


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
    out_entry_points = [{**entry, 'projection': _projection(entry.get('answers') or {}, multiplier)}
                        for entry in record.get('entry_points', [])]
    return {**record, 'entry_points': out_entry_points, 'projection': {
        'multiplier': multiplier,
        'method': (
            f'multiplier={multiplier}; cost per data_access_call, ×100 per n+1, '
            f'×{multiplier} per unbounded query, ×10 per shared-state mutation, '
            f'×50 per missing rate limit'
        ),
    }}


def _answered(answers, question, otherwise):
    """The answer's value when the question was answered, else `otherwise`."""
    answer = answers.get(question, {})
    return answer.get('value') if answer.get('status') == 'answered' else otherwise


def _answer_is(answers, question, value):
    answer = answers.get(question, {})
    return answer.get('status') == 'answered' and answer.get('value') is value


def _projection(answers, multiplier):
    """One entry's cost ceiling at `multiplier` times today's traffic (see project)."""
    access_count = _answered(answers, 'data_access_calls', None)
    if access_count is None: access_count = 0
    n_plus_one = _answer_is(answers, 'repeats_per_iteration', True)
    unbounded = _answer_is(answers, 'result_is_bounded', False)
    shared = _answer_is(answers, 'shared_mutable_state', True)
    no_limit = _answer_is(answers, 'rate_limited', False)
    cost = 0.0 + access_count * multiplier
    # n+1 multiplies per iteration (m * n_iterations); an unbounded result grows with data, not with m;
    # shared state adds serialization pressure; with no rate limit one burst and you're done.
    for flag, weight in ((n_plus_one, 100), (unbounded, 1), (shared, 10), (no_limit, 50)):
        if flag: cost += multiplier * weight
    # Rank bottlenecks: missing limit > n+1 > unbounded > shared
    bottlenecks = [name for flag, name in ((no_limit, 'no_rate_limit'), (n_plus_one, 'n_plus_one'),
                                           (unbounded, 'unbounded_query'), (shared, 'shared_mutable_state')) if flag]
    shown = _answered(answers, 'repeats_per_iteration', '?')
    projection = {
        'multiplier': multiplier,
        'cost_score': round(cost, 2),
        'interpretation': (
            f'projected ceiling of {round(cost, 2)} cost units at {multiplier}x traffic '
            f'(data_access_calls={access_count}, n_plus_one={shown}, '
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
    all_unknown = [question for question, answer in answers.items()
                   if answer.get('status') not in ('answered', 'not_applicable')]
    projection['incomplete'] = bool(all_unknown)
    if all_unknown: projection['unanswered_questions'] = sorted(all_unknown)
    return projection


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
        'holds_when': lambda value: isinstance(value, dict) and value.get('timeout') is False,
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

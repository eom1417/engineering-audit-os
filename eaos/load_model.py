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

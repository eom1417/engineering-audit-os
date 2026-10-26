"""The hunt: what the assistant reads, what it is asked, and the second pass that tries to disprove each candidate.

The method is Cloudflare's security-audit skill's (https://github.com/cloudflare/security-audit-skill, MIT), its ideas
only: work from a concrete invariant (who, with what, past which control, to what effect), the business-logic classes
scanners cannot find, the lowest-trust surfaces first, and no finding kept that a second reading can refute. The
assistant is passed in (its deep tier), never imported; it reads the project itself, read only.
"""
import json
from pathlib import Path

CLASSES = ('skipped-step', 'race', 'quantity', 'wrong-check', 'trusted-input', 'time', 'fallback', 'feature-abuse')
SEVERITIES = ('low', 'medium', 'high')
LIMIT = {'endpoints': 60, 'tables': 40, 'features': 30, 'flaws': 12}
_TEXT = {'type': 'string'}
FLAW = {'type': 'object', 'additionalProperties': False,
        'required': ['title', 'title_ar', 'class', 'severity', 'principal', 'invariant', 'path', 'line', 'steps', 'impact',
                     'fix', 'fix_ar', 'test'],
        'properties': {'title': _TEXT, 'title_ar': _TEXT, 'class': {'type': 'string', 'enum': list(CLASSES)},
                       'severity': {'type': 'string', 'enum': list(SEVERITIES)}, 'principal': _TEXT, 'invariant': _TEXT,
                       'path': _TEXT, 'line': {'type': 'integer'}, 'steps': {'type': 'array', 'items': _TEXT},
                       'impact': _TEXT, 'fix': _TEXT, 'fix_ar': _TEXT, 'test': _TEXT}}
SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['flaws', 'reviewed'],
          'properties': {'flaws': {'type': 'array', 'items': FLAW}, 'reviewed': {'type': 'array', 'items': _TEXT}}}
VERDICTS = {'type': 'object', 'additionalProperties': False, 'required': ['verdicts'],
            'properties': {'verdicts': {'type': 'array', 'items': {
                'type': 'object', 'additionalProperties': False, 'required': ['number', 'verdict', 'why'],
                'properties': {'number': {'type': 'integer'}, 'verdict': {'type': 'string', 'enum': ['holds', 'unsure', 'refuted']},
                               'why': _TEXT}}}}}

TASK = '''GOAL
You hunt logic flaws in this project: flaws in what the program allows, which no scanner finds because every line is
valid code. You may read and search the project's files (read only). Find only flaws the code shows.

WHAT YOU ARE GIVEN
`endpoints`: the project's HTTP endpoints as EAOS read them (method, route, file and line, whether it writes, whether
it takes an id, and the guards EAOS read: authentication, authorisation, validation), the lowest-trust ones first.
`tables`: the data and its rules. `features`: what the program is for. Start from them and read the handlers at depth:
follow each input through identity, authorisation, state and the final write, and read the sibling paths (batch, retry,
cancel, error, the other endpoint with the same effect).

THE CLASSES
skipped-step: a workflow's step skipped, done twice, replayed or done backwards (pay once, ship twice; approve a draft
never submitted). race: a check then an act that are not atomic (double spend, double approve, a lost update).
quantity: zero, negative, huge, fractional or text numbers accepted (a negative quantity refunds). wrong-check: a check
exists but is not the one the rule needs (any signed-in user approves; the owner check on read, not on update).
trusted-input: a value the browser sends trusted as the server's (price, role, owner id, status). time: expiry, windows,
time zones, the exact boundary moment. fallback: missing configuration, a flag off or a dependency down leaves it open.
feature-abuse: export, search, invite or reset used to read or enumerate what the person may not.

WORK FROM A CONCRETE INVARIANT
For each flaw: `principal` the lower-trust person and what they start with; `invariant` the rule the business needs;
`path` and `line` the exact place the control is missing or wrong (a file of the project, the line in it); `steps` the
requests or actions, in order, that break it with dummy data; `impact` the smallest wrong effect (one other user's
order read, one refund too many); `fix` the source change in one plain line (and `fix_ar`, the same in Arabic);
`test` the regression test that proves the fix. `title` one plain sentence (and `title_ar` in Arabic). `severity`:
high when another person's data or money is reached, medium when the person's own state is corrupted, low otherwise.
`reviewed`: the routes you read.

DO NOT
Report what a rule already finds (a missing sign-in check, an injection, a secret in code), a style issue, or a flaw
you could not point to by file and line. Fewer real flaws beat many plausible ones; none is a good answer.'''

CRITIC = '''GOAL
Each candidate below is a logic flaw another reviewer claims in this project. Try to disprove each one by reading the
code (read only): find the control that stops it (a guard, a transaction, a unique key, a check elsewhere on the same
path, the framework doing it), or a step of its sequence that cannot happen.

Answer per candidate, by its number: "holds" when the code shows it and nothing you found stops it; "refuted" when you
found what stops it (name it in `why`, with its file and line); "unsure" when the code does not settle it. `why`: one
or two plain sentences.'''


def _rank(row):
    """The lowest-trust and most valuable endpoints first: open writes, then writes by id, then the rest."""
    return (bool(row.get('authentication')), not row.get('writes'), not row.get('by_id'), str(row.get('route')))


def brief(out):
    """What the hunt reads of a check's record (layers.json, features.json), bounded."""
    layers = _read(Path(out) / 'layers.json') or {}
    keys = ('method', 'route', 'path', 'line', 'writes', 'by_id', 'public', 'authentication', 'authorisation', 'validation', 'data')
    endpoints = [{k: row.get(k) for k in keys} for row in sorted(layers.get('endpoints') or [], key=_rank)]
    return {'endpoints': endpoints[:LIMIT['endpoints']], 'tables': (layers.get('tables') or [])[:LIMIT['tables']],
            'features': _features(out), 'more_endpoints': max(0, len(endpoints) - LIMIT['endpoints'])}


def _features(out):
    """The names of what the program does (features.json), bounded."""
    rows = (_read(Path(out) / 'features.json') or {}).get('features') or []
    return [name for name in (f.get('name') or f.get('title') for f in rows if isinstance(f, dict)) if name][:LIMIT['features']]


def _read(path):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


def _answer(provider, system, content, project, stage):
    """The assistant's answer on its deep tier, reading the project itself."""
    messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': json.dumps(content, ensure_ascii=False)}]
    answer = provider.complete(messages, deep=True, stage=stage, reads=str(project))[0]
    return answer.get('result') or answer


def candidates(provider, out, project):
    """{flaws, reviewed}: the assistant's candidates, unchecked."""
    answer = _answer(provider, TASK + '\n\nANSWER\n' + json.dumps(SCHEMA), brief(out), project, 'logic_flaws')
    return {'flaws': [f for f in answer.get('flaws') or [] if isinstance(f, dict)][:LIMIT['flaws']],
            'reviewed': [str(r) for r in answer.get('reviewed') or []]}


def critique(provider, flaws, project):
    """{number: (verdict, why)}: the second, independent reading of each candidate."""
    if not flaws: return {}
    shown = [{'number': n, **{k: f.get(k) for k in ('title', 'class', 'principal', 'invariant', 'path', 'line', 'steps', 'excerpt')}}
             for n, f in enumerate(flaws, 1)]
    answer = _answer(provider, CRITIC + '\n\nANSWER\n' + json.dumps(VERDICTS), {'candidates': shown}, project, 'logic_flaws_critic')
    return {v['number']: (v.get('verdict'), str(v.get('why') or '')) for v in answer.get('verdicts') or []
            if isinstance(v, dict) and isinstance(v.get('number'), int)}

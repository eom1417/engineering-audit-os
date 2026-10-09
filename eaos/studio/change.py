"""studio/gaps.json and studio/operations.json: what separates each component from the ideal, and the operations that
close it in the order the plan runs them (contract v2, docs/STUDIO.md D7, NS46.T3).

Read only from the check's own records: target-architecture.json (each component of today, its relation to the target
and why, and the target's components), gap-matrix.json (the cards that close each gap and how far they cover it),
plan.json (its milestones in order and its waves) and the cards' ledger states. Nothing is invented:

- a gap no card covers has no closure measure (null, with the reason in its source), never 0 or 100%;
- an operation is placed in the step that holds most of its cards, else in the plan's own "build:<target>" step, else
  in none (shown as not planned);
- an operation waits for another only where one of its cards waits for one of the other's: a prerequisite the plan
  records, or an earlier task on the same file (the order the plan's waves set).
"""
from collections import Counter, defaultdict

from .model import CLOSED

OPERATION = {'retain': 'retain', 'modify': 'refactor', 'rebuild': 'rebuild', 'delete': 'delete', 'retire': 'delete'}
SEQUENCE = ('delete', 'refactor', 'rebuild', 'merge', 'new', 'retain')    # inside one step and one wave
COVER = ('covered', 'partial', 'missing')
CARD_STATE = {'done': 'done', 'resolved': 'done', 'on_branch': 'active', 'in_batch': 'active', 'open': 'todo', 'skipped': 'blocked'}


def _text(lang, ar, en):
    return ar if lang == 'ar' else en


def _ratio(done, total, src):
    return {'value': round(done / total, 4) if total else None, 'src': src}


def _state(states):
    if not states: return 'todo'
    if all(s == 'done' for s in states): return 'done'
    if any(s in ('active', 'done') for s in states): return 'active'
    return 'blocked' if all(s == 'blocked' for s in states) else 'todo'


def _waits(plan):
    """{task: {earlier tasks it waits for}}: its prerequisites and, per file, the last task of an earlier wave on it."""
    waves = sorted((w for w in plan.get('waves') or [] if isinstance(w, dict) and isinstance(w.get('wave'), int)),
                   key=lambda w: w['wave'])
    tasks = {t['id']: t for t in plan.get('tasks') or [] if isinstance(t, dict) and t.get('id')}
    out, seen, last = defaultdict(set), set(), {}
    for wave in waves:
        members = [tid for tid in wave.get('tasks') or [] if tid in tasks]
        for tid in members:
            for ref in tasks[tid].get('prerequisites') or []:
                if isinstance(ref, dict) and ref.get('task_id') in seen: out[tid].add(ref['task_id'])
            out[tid] |= {last[p] for p in tasks[tid].get('paths') or [] if isinstance(p, str) and p in last}
        for tid in members:
            seen.add(tid)
            last.update({p: tid for p in tasks[tid].get('paths') or [] if isinstance(p, str)})
    return out, {tid: w['wave'] for w in waves for tid in w.get('tasks') or []}


def change(m, card_rows, lang='ar'):
    """(gaps body, operations body), or (None, None) when the check computed no target to measure a gap against."""
    target, plan = m['target'] or {}, m['plan'] or {}
    current = [c for c in target.get('current_components') or [] if isinstance(c, dict) and c.get('name')]
    if not current: return None, None
    targets = {t['name']: t for t in target.get('target_components') or [] if isinstance(t, dict) and t.get('name')}
    rows = {r.get('current_id'): r for r in m['gap_matrix'].get('rows') or target.get('gap_matrix') or [] if isinstance(r, dict)}
    decision = {}
    for d in target.get('decisions') or []:
        if isinstance(d, dict) and d.get('component_id') and d.get('id'): decision.setdefault(d['component_id'], str(d['id']))
    state = {c['id']: CARD_STATE.get(c['state'], 'todo') for c in card_rows}
    stones = [s for s in plan.get('milestones') or [] if isinstance(s, dict) and s.get('id')]
    step_of = {t: s['id'] for s in stones for t in s.get('tasks') or []}
    rank = {s['id']: i for i, s in enumerate(stones)}
    build = {str(s.get('name') or '')[len('build:'):]: s['id'] for s in stones if str(s.get('name') or '').startswith('build:')}
    waits, wave_of = _waits(plan)

    def cards_of(row):
        return [t for t in (row or {}).get('blocking_tasks') or [] if isinstance(t, str) and t in state]

    def steps_of(cards, goes_to=None, builds=False):
        """The steps holding the cards, most first; the plan's step that builds `goes_to` is added (first when the
        operation builds that target itself)."""
        held = Counter(step_of[t] for t in cards if t in step_of)
        steps = sorted(held, key=lambda s: (-held[s], rank[s]))
        if goes_to in build:
            steps = [s for s in steps if s != build[goes_to]]
            steps.insert(0 if builds else len(steps), build[goes_to])
        return steps

    gaps, ops = [], []
    feeds = defaultdict(list)
    for c in current:
        if c.get('target_component'): feeds[c['target_component']].append(c)
    for c in sorted(current, key=lambda c: c['name']):
        row, op = rows.get(c.get('id')) or {}, OPERATION.get(c.get('relation'), 'refactor')
        cards = cards_of(row)
        closed = sum(state[t] == 'done' for t in cards)
        to = c.get('target_component') or row.get('target_component')
        steps = steps_of(cards, to if op in ('refactor', 'rebuild') else None)
        why = str(c.get('reason') or '')[:600]
        oid = f'{op}:{c["name"]}' if op != 'retain' else None
        gaps.append({'id': c['name'], 'component': c['name'], 'operation': op, 'to': to,
                     'responsibility': (str((targets.get(to) or {}).get('responsibility') or '')[:400] or None),
                     'reason': why or None, 'files': int(c.get('files') or 0), 'cards': cards, 'cards_closed': closed,
                     'cover': row.get('gap') if row.get('gap') in COVER else None,
                     'steps': steps, 'operations': [oid] if oid else [], 'decision': decision.get(c.get('id')),
                     'closed': _ratio(closed, len(cards), 'gap-matrix.json#rows[].blocking_tasks: cards done / cards'
                                      if cards else 'gap-matrix.json#rows[].blocking_tasks is empty: no card closes this gap yet')})
        if oid:
            ops.append({'id': oid, 'op': op, 'subject': c['name'], 'subject_kind': 'component', 'target': to,
                        'reason': why or _text(lang, 'العلاقة بالهدف من target-architecture.json', 'The relation to the target in target-architecture.json'),
                        'plan': 'fix', 'step': steps[0] if steps else None, 'gap': c['name'], 'cards': cards, 'files': int(c.get('files') or 0),
                        'sources': [], 'branch': None, 'state': _state([state[t] for t in cards])})
    for name, t in sorted(targets.items()):
        sources = sorted(feeds.get(name) or [], key=lambda c: c['name'])
        if len(sources) == 1: continue
        op = 'merge' if sources else 'new'
        cards = sorted({t for c in sources for t in cards_of(rows.get(c.get('id')))})
        closed = sum(state[t] == 'done' for t in cards)
        files = sum(int(c.get('files') or 0) for c in sources)
        names = [c['name'] for c in sources]
        oid, gid = f'{op}:{name}', f'target:{name}'
        reason = (_text(lang, f'{len(names)} مكوّنات من اليوم تصبح مكوّنًا واحدًا: {", ".join(names[:6])}' + ('…' if len(names) > 6 else ''),
                        f'{len(names)} components of today become one: {", ".join(names[:6])}' + ('…' if len(names) > 6 else ''))
                  if sources else _text(lang, 'الهدف يضيفه ولا يقابله شيء في الكود اليوم.', 'The target adds it; nothing in the code today matches it.'))
        steps = steps_of(cards, name, builds=True)
        gaps.append({'id': gid, 'component': name, 'operation': op, 'to': name,
                     'responsibility': str(t.get('responsibility') or '')[:400] or None, 'reason': reason, 'files': files,
                     'cards': cards, 'cards_closed': closed, 'cover': None, 'steps': steps, 'operations': [oid], 'decision': None,
                     'closed': _ratio(closed, len(cards), 'the cards of the components it merges: done / cards' if cards else
                                      'no card closes this gap yet')})
        ops.append({'id': oid, 'op': op, 'subject': name, 'subject_kind': 'component', 'target': name, 'reason': reason,
                    'plan': 'fix', 'step': steps[0] if steps else None, 'gap': gid, 'cards': cards, 'files': files,
                    'sources': names, 'branch': None, 'state': _state([state[t] for t in cards])})
    # A merge carries its sources' cards: a card belongs to the operation on its own component.
    owner = defaultdict(set)
    for o in ops:
        if o['op'] != 'merge':
            for t in o['cards']: owner[t].add(o['id'])
    for o in ops:
        o['after'] = sorted({other for t in o['cards'] for before in waits.get(t, ()) for other in owner[before] if other != o['id']})
    return {'gaps': gaps}, {'operations': ordered(ops, rank, wave_of, len(stones))}


def ordered(ops, rank, wave_of, last):
    """The operations in the order they run, numbered from 1: none before what it waits for (a cycle of waits is broken
    at the operation that comes first), else by the plan's step order, the first wave of its cards, then its kind."""
    first = lambda o: min((wave_of[t] for t in o['cards'] if t in wave_of), default=10 ** 6)
    key = {o['id']: (rank.get(o['step'], last), first(o), SEQUENCE.index(o['op']), o['subject']) for o in ops}
    by_id, done, out = {o['id']: o for o in ops}, set(), []
    while len(out) < len(ops):
        left = sorted((o for o in ops if o['id'] not in done), key=lambda o: key[o['id']])
        ready = [o for o in left if all(a in done or a not in by_id for a in o['after'])]
        pick = (ready or left)[0]
        done.add(pick['id'])
        out.append(pick)
    position = {o['id']: i for i, o in enumerate(out)}
    for i, o in enumerate(out):
        o['order'] = i + 1
        o['after'] = sorted(o['after'], key=position.get)
    return out

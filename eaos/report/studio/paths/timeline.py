"""The plan's timeline: the fix plan (plan.json) in the order it runs, its waves, each task's step and what each task
waits for (a prerequisite, or the last task of an earlier wave on the same file)."""
from collections import Counter, defaultdict

from ..change import _members, _objects, _paths
from .graph import _measure

MAX_WAITS = 6


def _plan_parts(plan):
    """(the waves in order, {id: task}, the milestones) of a plan, each kept only when it is well formed."""
    waves = sorted((w for w in _objects(plan.get('waves')) if isinstance(w.get('wave'), int)), key=lambda w: w['wave'])
    return waves, {t['id']: t for t in _objects(plan.get('tasks'), 'id')}, _objects(plan.get('milestones'), 'id')


def _timeline_rows(waves, tasks, step_of, card):
    """Every task in the order its wave runs, with what it waits for: a prerequisite, or the last earlier task on a file."""
    rows, wave_of, last = [], {}, {}
    for wave in waves:
        members = [tid for tid in _members(wave) if tid in tasks]
        for tid in members:
            task, shown, waits = tasks[tid], card.get(tid) or {}, _waits(tasks[tid], wave_of, last)
            rows.append({'id': tid, 'step': step_of.get(tid), 'wave': wave['wave'], 'title': str(shown.get('title') or task.get('title') or tid)[:300],
                         'state': shown.get('state') or 'open', 'waits': waits[:MAX_WAITS], 'more': max(len(waits) - MAX_WAITS, 0)})
        _ran(members, wave['wave'], tasks, wave_of, last)
    return rows


def _ran(members, wave, tasks, wave_of, last):
    """Once a wave ran: each of its tasks is of that wave, and the last task on each of its files."""
    for tid in members:
        wave_of[tid] = wave
        for path in _paths(tasks[tid]): last[path] = tid


def _waits(task, wave_of, last):
    waits = [{'task': ref['task_id'], 'why': 'prerequisite', 'detail': str(ref.get('reason') or '')[:200]}
             for ref in task.get('prerequisites') or [] if isinstance(ref, dict) and ref.get('task_id') in wave_of]
    for path in sorted(set(_paths(task))):
        if (before := last.get(path)) and before not in {w['task'] for w in waits}: waits.append({'task': before, 'why': 'same_file', 'detail': path})
    return waits


def _timeline_steps(stones, rows, lang):
    """Each milestone with its tasks and the first and last wave they run in."""
    steps = []
    for m in stones:
        mine = [row['wave'] for row in rows if row['step'] == m['id']]
        steps.append({'id': m['id'], 'title': str(m.get('goal_ar' if lang == 'ar' else 'goal') or m.get('name') or m['id'])[:300],
                      'name': str(m.get('name') or ''), 'tasks': len(mine), 'first': min(mine) if mine else None,
                      'last': max(mine) if mine else None})
    return steps


def _timeline_waves(waves, rows):
    """Each wave with its tasks counted by step."""
    by_wave = defaultdict(Counter)
    for row in rows: by_wave[row['wave']][row['step'] or ''] += 1
    return [{'wave': w['wave'], 'tasks': sum(by_wave[w['wave']].values()),
             'steps': [{'step': s or None, 'tasks': n} for s, n in sorted(by_wave[w['wave']].items())]} for w in waves]


def timeline(plan, card_rows, lang='ar'):
    """The fix plan in the order it runs, or None when the plan has no waves."""
    waves, tasks, stones = _plan_parts(plan if isinstance(plan, dict) else {})
    if not waves: return None
    step_of = {tid: m['id'] for m in stones for tid in m.get('tasks') or []}
    rows = _timeline_rows(waves, tasks, step_of, {c['id']: c for c in card_rows or []})
    out_waves = _timeline_waves(waves, rows)
    return {'plan': 'fix', 'waves': out_waves, 'steps': _timeline_steps(stones, rows, lang), 'tasks': rows,
            'counts': {'waves': _measure(len(out_waves), 'plan.json#waves (count)'),
                       'tasks': _measure(len(rows), 'plan.json#waves[].tasks (count)'),
                       'waits': _measure(sum(len(row['waits']) + row['more'] for row in rows),
                                         'plan.json#tasks[].prerequisites + the last earlier task on the same file (count)')}}

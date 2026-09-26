"""The twenty-five steps as a measured flow: each step's weight, completion, output quality and exit gate.

Every number here is computed from docs/north-star.json; nothing is estimated by hand.

    weight        declared points per step, summing to 100, each with its reason (weight_why)
    completion    the size-weighted mean of the step's tasks (S = 1, M = 2, L = 3). A closed task counts 1.
                  An open task counts the progress of its gate indicators toward their thresholds
                  (value / threshold, at most 1), capped at OPEN_CAP until its acceptance command passes
                  and it is closed: an indicator at its threshold is not yet a closed task.
    points        weight x completion; the product's progress is the sum over the steps, out of 100
    quality       the mean of value / threshold over the step's gate indicators, as measured now
    gate          what must hold before the next step starts: every indicator threshold named by an
                  acceptance command of the step's tasks (--min), every indicator it only requires measured,
                  and every acceptance test they run
"""
import re

SIZE_POINTS = {'S': 1, 'M': 2, 'L': 3}
DEFAULT_SIZE = 'M'
OPEN_CAP = 0.9
MEASURE = re.compile(r'north_star\.py measure --only (\w+)(?: --min ([0-9.]+))?')
CHECK = re.compile(r'tools/acceptance\.py (\w+) (\S+)|unittest (\S+)')


def indicator_rows(record):
    return {row['id']: row for capability in record['capabilities'] for row in capability['indicators']}


def criteria(task, record):
    """The measurable conditions a task's acceptance command enforces: indicator thresholds, then checks."""
    rows = indicator_rows(record)
    found, seen = [], set()
    for indicator, floor in MEASURE.findall(task['acceptance']):
        row = rows.get(indicator)
        if row is None or indicator in seen: continue
        seen.add(indicator)
        value = row.get('value')
        if not floor:
            # `measure --only X` without --min passes once X has a value: a condition, not a threshold
            found.append({'kind': 'measured', 'id': indicator, 'name': row['name'], 'value': value, 'holds': value is not None})
            continue
        threshold = float(floor)
        found.append({'kind': 'indicator', 'id': indicator, 'name': row['name'], 'min': threshold, 'value': value,
                      'holds': value is not None and value >= threshold})
    for kind, name, unittest_name in CHECK.findall(task['acceptance']):
        found.append({'kind': 'check', 'id': f'{kind} {name}' if kind else f'unittest {unittest_name}',
                      'holds': task['status'] == 'done'})
    return found


def ratio(item):
    if item['value'] is None: return 0.0
    return 1.0 if item['min'] <= 0 else min(item['value'] / item['min'], 1.0)


def task_completion(task, record):
    if task['status'] == 'done': return 1.0
    measured = [item for item in criteria(task, record) if item['kind'] == 'indicator']
    if not measured: return 0.0
    return round(OPEN_CAP * sum(ratio(item) for item in measured) / len(measured), 3)


def gate(milestone, record):
    """Every criterion of the step, one row per indicator (the strictest threshold wins), then the checks."""
    rows, checks = {}, []
    for task in milestone['tasks']:
        for item in criteria(task, record):
            if item['kind'] != 'indicator':
                if item['id'] not in {other['id'] for other in checks}: checks.append(item)
            elif item['id'] not in rows or item['min'] > rows[item['id']]['min']:
                rows[item['id']] = item
    # an indicator the step holds to a threshold needs no separate "is measured" row
    return list(rows.values()) + [item for item in checks if not (item['kind'] == 'measured' and item['id'] in rows)]


def step(milestone, record):
    sizes = [SIZE_POINTS[task.get('size') or DEFAULT_SIZE] for task in milestone['tasks']]
    done = sum(size * task_completion(task, record) for size, task in zip(sizes, milestone['tasks']))
    completion = done / sum(sizes) if sizes else 0.0
    measured = [item for item in gate(milestone, record) if item['kind'] == 'indicator']
    quality = sum(ratio(item) for item in measured) / len(measured) if measured else None
    return {'weight': milestone['weight'], 'completion': round(completion, 3),
            'points': round(milestone['weight'] * completion, 2), 'quality': None if quality is None else round(quality, 3),
            'gate': gate(milestone, record)}


def overall(record):
    return round(sum(step(milestone, record)['points'] for milestone in record['milestones']), 1)


def gate_text(items, language='ar', limit=6):
    """A gate as it reads on an arrow: indicator thresholds, and how many acceptance tests stand with them."""
    parts = [f"{item['id']}{'=' if item['min'] >= 1 else '≥'}{item['min']:g}" for item in items if item['kind'] == 'indicator']
    checks = sum(item['kind'] != 'indicator' for item in items)
    if len(parts) > limit: parts = parts[:limit] + ['…']
    if checks: parts.append((f'+{checks} اختبار قبول' if language == 'ar' else f'+{checks} acceptance test' + ('s' if checks > 1 else '')))
    return ' · '.join(parts) or ('أمر القبول' if language == 'ar' else 'acceptance command')


def problems(record, order, states):
    """The gate, enforced: weights sum to 100; each step says what it does, with which tools, into which output;
    no step closes before the one before it; and a closed step's gate still holds on today's measurement."""
    found = []
    if sum(milestone.get('weight', 0) for milestone in record['milestones']) != 100:
        found.append('step weights must sum to 100')
    for milestone in record['milestones']:
        for field in ('weight_why', 'does', 'tools', 'outputs'):
            if not milestone.get(field): found.append(f"{milestone['id']}: no {field}")
        if not isinstance(milestone.get('weight'), int) or milestone['weight'] <= 0:
            found.append(f"{milestone['id']}: weight must be a positive whole number of points")
    by_id = {milestone['id']: milestone for milestone in record['milestones']}
    for index, name in enumerate(order):
        milestone = by_id[name]
        if any(task['status'] == 'done' for task in milestone['tasks']):
            earlier = [other for other in order[:index] if states[other] != 'done']
            if earlier: found.append(f"{name}: has a closed task while an earlier step is open ({', '.join(earlier)})")
        for task in milestone['tasks']:
            if task['status'] != 'done': continue
            for item in criteria(task, record):
                if item['kind'] != 'check' and not item['holds']:
                    found.append(f"{task['id']}: closed, but its gate no longer holds: {item['id']} = {item['value']}"
                                 + (f" < {item['min']}" if 'min' in item else ' (not measured)'))
    return found

"""What the inventory earns as cards (M18.11, M18.12, M18.19): a part drawn many ways, a date shown in several forms, two libraries for one job. Each is LIKELY, hidden until
its precision is judged (tools/judging/precision.py); the inventory shows the facts either way. And what the person may agree to merge: near colours, sizes off the scale.

    findings(out)     [{kind, place, line, severity, evidence}], the one-source shape
    merges(drawn)     [{kind, from, to, uses, where}]: what a design batch would move, each only with the person's yes
"""
from pathlib import Path

from ..assessments.one_source_look import rgb, scale
from ...core.system.files import read_json

MANY_LOOKS, MANY_USES = 4, 8       # a part used this much, drawn this many ways: a kit of variants is smaller
FORMATTED = ('date', 'time', 'currency', 'relative')
SCALED = ('font_size', 'radius')
FEW = 8


def _looks(drawn):
    return [{'kind': 'looks', 'place': role, 'line': None, 'severity': 'medium' if part['distinct'] >= 2 * MANY_LOOKS else 'low',
             'evidence': {'role': role, 'looks': part['distinct'], 'count': part['count'], 'places': [{'path': where['page']} for look in part['looks'] for where in look['where'][:1]][:FEW]}}
            for role, part in drawn['components'].items() if part['distinct'] >= MANY_LOOKS and part['count'] >= MANY_USES]


def _formats(drawn):
    return [{'kind': 'formats', 'place': kind, 'line': None, 'severity': 'low', 'evidence': {'format': kind, 'forms': ', '.join(row['form'] for row in rows), 'count': len(rows), 'places': []}}
            for kind, rows in drawn['formats'].items() if kind in FORMATTED and len(rows) > 1]


def _libraries(drawn):
    return [{'kind': 'libraries', 'place': job, 'line': None, 'severity': 'low', 'evidence': {'job': job, 'names': ', '.join(names), 'places': []}}
            for job, names in drawn['libraries'].items()]


def findings(out):
    drawn = read_json(Path(out) / 'design' / 'inventory.json') if out else None
    return (_looks(drawn) + _formats(drawn) + _libraries(drawn)) if drawn else []


def _hex(value):
    colour = rgb(value)
    return '#%02x%02x%02x' % tuple(colour[:3]) if colour else value


def _uses(rows):
    return {row['value']: row['uses'] for row in rows}


def _colour_merges(drawn):
    uses = _uses(drawn['values'].get('color', {}).get('rows') or [])
    found = []
    for group in drawn['near_colours']:
        head = max(group, key=lambda value: uses.get(value, 0))
        found += [{'kind': 'color', 'from': _hex(value), 'to': _hex(head), 'uses': uses.get(value, 0)} for value in group if value != head]
    return found


def _nearest(value, steps):
    px = lambda text: float(str(text).replace('px', ''))
    return min(steps, key=lambda step: abs(px(step) - px(value)))


def _scale_merges(drawn):
    found = []
    for kind in SCALED:
        uses = _uses([row for row in drawn['values'].get(kind, {}).get('rows') or [] if str(row['value']).endswith('px')])
        steps, off = scale(uses, kind) if uses else ([], [])
        found += [{'kind': kind, 'from': value, 'to': _nearest(value, steps), 'uses': uses[value]} for value in off]
    return found


def merges(drawn):
    return _colour_merges(drawn) + _scale_merges(drawn) if drawn else []

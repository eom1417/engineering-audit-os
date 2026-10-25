"""studio/layers.json: the system in layers for the Studio (M6.11), read from layers.json (eaos/analysis/layers/); every
number a measure with its source, the broken critical boundaries first."""
import json
from pathlib import Path

from ...analysis.layers.catalog import BOUNDARIES

SRC = 'layers.json'
ENDPOINTS_SHOWN = 300
KEPT = ('method', 'route', 'path', 'line', 'framework', 'authentication', 'authorisation', 'validation', 'data', 'writes')


def _measure(value, field):
    return {'value': value, 'src': f'{SRC}#{field}'}


def _finding(f):
    return {key: f.get(key) for key in ('rule', 'severity', 'path', 'line', 'en', 'ar', 'fix_en', 'fix_ar', 'evidence', 'live')}


def _counts(record):
    return {'files': _measure(len(record['map']), 'map'), 'placed': _measure(len(record['map']) - len(record['gaps']), 'map[].layer'),
            'gaps': _measure(len(record['gaps']), 'gaps'), 'endpoints': _measure(len(record['endpoints']), 'endpoints'),
            'tables': _measure(len(record['tables']), 'tables'), 'findings': _measure(len(record['findings']), 'findings'),
            'critical': _measure(sum(f['severity'] == 'high' for f in record['findings']), 'findings[].severity')}


def layers(report, lang='ar'):
    """The section, or None when the check did not read the layers."""
    try: record = json.loads((Path(report) / SRC).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None
    boundaries = [{'id': name, 'name': {'en': en, 'ar': ar},
                   'findings': [_finding(f) for f in record['findings'] if f['boundary'] == name]} for name, (en, ar) in BOUNDARIES.items()]
    return {'type': record.get('type'), 'live': bool(record.get('live')), 'counts': _counts(record),
            'layers': [{k: layer.get(k) for k in ('name', 'role', 'responsibility', 'allowed', 'files')} for layer in record['layers']],
            'boundaries': boundaries,
            'questions': [{'en': q['question'], 'ar': q['question_ar'], 'path': q.get('path')} for q in record['questions']],
            'endpoints': [{k: row.get(k) for k in KEPT} for row in record['endpoints'][:ENDPOINTS_SHOWN]],
            'tables': record['tables']}

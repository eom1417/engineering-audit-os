"""Engagement contract: the declared priority formula and the quality scenarios.

A consulting engagement declares what "good" means for *this* codebase before
the work begins. The contract carries:

  targets       the six-indicator sustainability targets the engagement commits to
  scenarios     numbered quality scenarios: stimulus, response, measurable outcome
  priority      reach × confidence × origin ÷ cost with every input exposed
  scope         files in scope vs files declared out of scope
  priorities    a derived list, ordered for triage

Nothing here is a verdict on the code. The contract is the team's own statement
about what they will pay attention to, and the engine reads it back as input
to the transform plan and the dashboard.
"""
from pathlib import Path
import json


NAME = 'engagement'
VERSION = '1'
LIMITATIONS = [
    'The contract is a declaration; the engine does not validate it against the codebase.',
    'Quality scenarios are subjective scenarios until a probe confirms them; the engine labels them '
    'as HYPOTHESIS until a verdict lands.',
    'The priority formula is a declared ranking, not a measurement of risk; the engine never '
    'invents a formula the engagement did not state.',
    'Scope declarations are read but not enforced; an excluded file still shows in facts unless '
    '`analysis.exclude` in the policy also excludes it.',
]

DEFAULT_TARGETS = {
    'single_source': 0.0, 'minimal_path': 0.0, 'data_owners': 0,
    'honest_boundaries': 0, 'verifiable_paths': 0.0, 'understandable_units': 0,
}


def read_contract(path):
    """Read an engagement contract from a JSON file, or return sensible defaults."""
    path = Path(path) if path else None
    if path is None or not path.is_file():
        return _default_contract()
    contract = json.loads(path.read_text())
    if not isinstance(contract, dict) or contract.get('schema_version') != 1:
        raise ValueError('Unsupported engagement contract; the original file was preserved')
    if not isinstance(contract.get('targets'), dict): contract['targets'] = dict(DEFAULT_TARGETS)
    if not isinstance(contract.get('scenarios'), list): contract['scenarios'] = []
    if not isinstance(contract.get('priority'), dict): contract['priority'] = _default_priority()
    if not isinstance(contract.get('scope'), dict): contract['scope'] = {'in': [], 'out': []}
    return contract


def _default_contract():
    return {'schema_version': 1, 'name': 'default', 'targets': dict(DEFAULT_TARGETS),
            'scenarios': [], 'priority': _default_priority(), 'scope': {'in': [], 'out': []}}


def _default_priority():
    return {'formula': 'reach × confidence × origin ÷ cost',
             'scales': {'reach': 'lines of code touched',
                         'confidence': '0..1 (probe verdicts)',
                         'origin': '0..1 (signal strength)',
                         'cost': 'engineering hours'}}


def render_contract(path=None):
    """Return a starter engagement contract the team can edit."""
    return _default_contract()


def write(path, contract):
    Path(path).write_text(json.dumps(contract, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def rank(scenarios, contract):
    """Apply the priority formula (reach × confidence × origin ÷ cost) and order by score."""
    import math
    formula = contract['priority'].get('formula')
    if formula != 'reach × confidence × origin ÷ cost': raise ValueError('Unsupported priority formula')
    ranked = []
    for index, scenario in enumerate(scenarios):
        values = [scenario.get(key) for key in ('reach', 'confidence', 'origin', 'cost')]
        known = all(type(value) in (int, float) and math.isfinite(value) and value >= 0 for value in values)
        weighted = values[0] * values[1] * values[2] / values[3] if known and values[3] > 0 else None
        ranked.append({'id': scenario.get('id', f'SCEN-{index+1:03d}'),
                        'name': scenario.get('name', ''),
                        'stimulus': scenario.get('stimulus', ''),
                        'response': scenario.get('response', ''),
                        'measure': scenario.get('measure', ''),
                        'score': round(weighted, 4) if weighted is not None else None,
                        'formula': formula, 'estimate_status': 'measured_inputs' if weighted is not None else 'unknown_inputs'})
    ranked.sort(key=lambda row: (row['score'] is None, -(row['score'] or 0)))
    return ranked

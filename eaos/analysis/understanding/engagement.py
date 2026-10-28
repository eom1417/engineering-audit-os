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


# Rules the audit applies unless the project says otherwise in eaos.engagement.json at its root. Each is a
# declared default, not a judgement about this project: the owner turns one off by writing it as false.
DEFAULT_RULES = {
    'remove_dead_code': {
        'value': True, 'source': 'default',
        'why': 'Code no production path reaches and no text names is read, maintained and reviewed for nothing; '
               'the evidence is mechanical and the removal reverts in one commit.'},
    'consolidate_duplicates': {
        'value': True, 'source': 'default',
        'why': 'The same behaviour or rule written in several places changes in one and not the others; '
               'one definition is checked by the audit that found the copies.'},
    'reduce_hotspots': {
        'value': True, 'source': 'default',
        'why': 'A function past its declared branch threshold is where change breaks things; the threshold is the check.'},
    'bound_load_paths': {
        'value': True, 'source': 'default',
        'why': 'An unbounded read, an unprotected call or repeated work fails first under load; the load model re-answers the question.'},
    'fix_broken_code': {
        'value': True, 'source': 'default',
        'why': 'A reference that does not resolve fails the first time it runs; the audit re-resolves it.'},
    'untangle_dependencies': {
        'value': True, 'source': 'default',
        'why': 'Import cycles and module state changed at runtime make parts impossible to test or change alone; '
               'the resolved graph shows when they are gone.'},
    'keep_person_rules': {
        'value': True, 'source': 'default',
        'why': 'The person stated this rule and wrote, or had written, its guard; the guard run again on the copy is the check (M16).'},
    'upgrade_vulnerable_dependencies': {
        'value': True, 'source': 'default',
        'why': 'A locked version with a published, fixed vulnerability is a known risk with a known repair; '
               'the evidence is a database lookup and the upgrade reverts in one commit.'},
}
PROJECT_FILENAME = 'eaos.engagement.json'


def rules_for(target):
    """(rules, where they came from): the project's eaos.engagement.json rules over the defaults."""
    rules = {name: dict(rule) for name, rule in DEFAULT_RULES.items()}
    location = Path(target) / PROJECT_FILENAME if target else None
    if location is not None and location.is_file():
        declared = (json.loads(location.read_text(encoding='utf-8')) or {}).get('rules') or {}
        for name, value in declared.items():
            if name in rules: rules[name].update(value=bool(value), source=str(location))
        return rules, str(location)
    return rules, 'default'





def write(path, contract):
    Path(path).write_text(json.dumps(contract, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _ranked(index, scenario, formula):
    """One scenario's row, scored when its four inputs are finite, non-negative numbers and its cost is above zero."""
    import math
    values = [scenario.get(key) for key in ('reach', 'confidence', 'origin', 'cost')]
    known = all(type(value) in (int, float) and math.isfinite(value) and value >= 0 for value in values)
    weighted = values[0] * values[1] * values[2] / values[3] if known and values[3] > 0 else None
    return {'id': scenario.get('id', f'SCEN-{index+1:03d}'),
            'name': scenario.get('name', ''),
            'stimulus': scenario.get('stimulus', ''),
            'response': scenario.get('response', ''),
            'measure': scenario.get('measure', ''),
            'score': round(weighted, 4) if weighted is not None else None,
            'formula': formula, 'estimate_status': 'measured_inputs' if weighted is not None else 'unknown_inputs'}


def rank(scenarios, contract):
    """Apply the priority formula (reach × confidence × origin ÷ cost) and order by score."""
    formula = contract['priority'].get('formula')
    if formula != 'reach × confidence × origin ÷ cost': raise ValueError('Unsupported priority formula')
    ranked = [_ranked(index, scenario, formula) for index, scenario in enumerate(scenarios)]
    ranked.sort(key=lambda row: (row['score'] is None, -(row['score'] or 0)))
    return ranked

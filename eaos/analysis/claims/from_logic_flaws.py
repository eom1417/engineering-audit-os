"""The claims the logic-flaw hunt earns (M9.2): one per flaw of the `logic_flaws` fact set (eaos/analysis/logic_flaws/),
read only when it was found on the code being checked. Found by an assistant, never by a rule: LIKELY when its second
reading held it, a HYPOTHESIS (and medium at most) when it was unsure; the card triage rules on each before it reaches
the plan. A flaw that reaches another person's data or money (high) is a security finding, the rest reliability."""
from pathlib import Path

from ..logic_flaws.hunt import SEVERITIES
from ..logic_flaws.record import current


def _params(fact):
    """The card's words and place: the flaw's own, its category and its severity (capped at medium when unsure)."""
    value, where = fact['value'], fact['location']
    severity = value.get('severity') if value.get('severity') in SEVERITIES else 'medium'
    if value.get('verdict') != 'holds' and severity == 'high': severity = 'medium'
    return {'class': value.get('class'), 'severity': severity, 'category': 'security' if severity == 'high' else 'reliability',
            'en': value['title'], 'ar': value.get('title_ar') or value['title'], 'fix_en': value['fix'],
            'fix_ar': value.get('fix_ar') or value['fix'], 'path': where['path'], 'line': where.get('start_line')}


def logic_flaws(fact_sets, add, target):
    """One claim per logic flaw found on this code (eaos/analysis/claims/ledger.py BUILDERS)."""
    for fact in current(fact_sets.get('logic_flaws'), target):
        value, where = fact['value'], fact['location']
        confidence = 'LIKELY' if value.get('verdict') == 'holds' else 'HYPOTHESIS'
        add(value['title'], 'risk', confidence, ['model_inference'],
            f"The cited line gone from {where['path']}, or a new hunt not finding it; not reproduced by: {value.get('test')}",
            fact_ids=[fact['id']], confidence_ceiling=confidence, render={'key': 'logic_flaw', 'params': _params(fact)},
            probe_spec={'probe_type': 'graph_query',
                        'specification': {'query': 'logic_flaw_present', 'path': where['path'], 'title': value['title'],
                                          'cited': value.get('cited') or '', 'expected': 'The last hunt still holds this flaw.'}},
            impact={'scenario': value['impact']})


def present(specification, sets):
    """The probe of a logic-flaw card. Over a hunt's set (the check's): CONFIRMED while it lists the flaw at its place.
    Over the code read again (eaos/analysis/claims/recheck.py, `reread`): REFUTED once the cited line is gone from the
    file, INCONCLUSIVE while it is still there, since only a new hunt can say whether the flaw still holds."""
    found = sets.get('logic_flaws') or {}
    if 'reread' in found:
        if found['reread']: return 'INCONCLUSIVE', f"the cited line is still in {specification['path']}: only a new hunt can tell"
        return 'REFUTED', f"the cited line is no longer in {specification['path']}"
    facts = found.get('facts') or []
    if any(f['location']['path'] == specification['path'] and f['value']['title'] == specification['title'] for f in facts):
        return 'CONFIRMED', f"the last hunt still holds it at {specification['path']}"
    return 'REFUTED', f"the last hunt no longer finds it at {specification['path']}"


def reread(root, specification):
    """The `logic_flaws` set a recheck reads (present): whether the cited line is still in the cited file."""
    cited, root = str(specification.get('cited') or '').strip(), Path(root).resolve()
    if not cited: return {'reread': True}                     # nothing cited to look for: never closed by a reading
    try:
        file = (root / specification['path']).resolve()
        text = file.read_text(encoding='utf-8', errors='replace') if file.is_relative_to(root) else ''
    except (OSError, ValueError): return {'reread': False}
    return {'reread': any(line.strip() == cited for line in text.split('\n'))}

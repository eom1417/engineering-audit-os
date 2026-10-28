"""The final target (eaos/report/target_architecture/picture.py drew the rules' proposal): each component as the rules and, when
the ideal was planned, the person's assistant decided it, within the owner's guards (protected files, the cards the
triage set aside), with the gap matrix drawn again from it."""
import re
from pathlib import Path

from .decisions import decisions
from .gaps import current_gap
from ...core.system.files import read_json

# The ideal planner's operations as the target's relations; "new" names no component of today's code.
RELATION_OF = {'retain': 'retain', 'refactor': 'modify', 'merge': 'modify', 'rebuild': 'rebuild', 'delete': 'delete'}


def _slug(text):
    return re.sub(r'[^A-Za-z0-9_.:-]+', '-', str(text)).strip('-') or 'root'


def protected_paths(out, policy_path=None):
    """The files the owner protects: those of the critical features (features.json, and the intake's answer) and those
    the project's architecture policy places in a layer. A decision may not delete them."""
    from fnmatch import fnmatch
    out = Path(out)
    files = _critical_files(out)
    policy = read_json(policy_path, {}) if policy_path else {}
    globs = [g for paths in (policy.get('layers') or {}).values() for g in paths or []]
    return lambda path: path in files or any(fnmatch(path, g) for g in globs)


def _critical_names(out):
    """The features the owner named critical in the intake's answer."""
    named = {q.get('id'): q.get('answer') for q in read_json(out / 'intake.json', {}).get('questions') or [] if isinstance(q, dict)}
    return set(named.get('critical_features') or []) if isinstance(named.get('critical_features'), list) else set()


def _critical_files(out):
    """The files of the critical features: marked so in features.json, or named in the intake."""
    critical = _critical_names(out)
    return {f for feature in read_json(out / 'features.json', {}).get('features') or [] if isinstance(feature, dict)
            and (feature.get('critical') or feature.get('name') in critical) for f in feature.get('files') or []}


def _view(out):
    """The system view of this check's planned ideal, with the departures that say why: ([elements], {id: why})."""
    import json
    try: record = json.loads((Path(out) / 'ideal/plan.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return [], {}
    ideal = record.get('ideal') or {}
    because = {str(d.get('element')): d.get('because') for d in ideal.get('departures') or []
               if isinstance(d, dict) and d.get('view') == 'system'}
    return _system_elements(ideal), because


def _system_elements(ideal):
    """The elements of the planned ideal's system view."""
    return [e for e in ((ideal.get('views') or {}).get('system') or {}).get('elements') or [] if isinstance(e, dict)]


def _decide_current(component, element, why, protected, aside=frozenset()):
    """(label, why) of one of today's components: the rule stands when the assistant said nothing or when its decision
    breaks a guard (it stands only on cards or claims the triage set aside: two of the assistant's steps would
    contradict each other); otherwise the assistant's relation is the target's and the rule's is kept beside it."""
    rule = component['relation']
    if element is None: return 'rule_only', ''
    relation = RELATION_OF.get(element.get('operation'))
    if relation is None:
        return 'disagreement', f"\"{element.get('operation')}\" is not an operation on a component that exists today"
    if relation == rule: return 'agreed', why       # the same answer is never a disagreement, whatever it is
    against = _against_guard(component, element, relation, protected, aside)
    if against: return 'disagreement', against
    component.update(relation=relation, reason=why or element.get('detail') or component.get('reason'),
                     evidence_ids=sorted(set(component.get('evidence_ids') or []) | set(element.get('cites') or [])))
    return 'ai_modified', why


def _against_guard(component, element, relation, protected, aside):
    """Why the assistant's different relation breaks a guard: it stands only on what the triage set aside, or it
    deletes protected files; None when it breaks none."""
    cites = set(element.get('cites') or [])
    if cites and cites <= aside: return 'it stands only on cards the triage set aside as false alarms'
    if relation == 'delete' and any(protected(path) for path in component.get('paths') or []):
        return 'it would delete files the owner protects (a critical feature or the architecture policy)'
    return None


def _why(element, because):
    """Why the assistant decided as it did: its departure's words, else its element's detail."""
    return because.get(str((element or {}).get('id'))) or (element or {}).get('detail') or ''


def _cites(element):
    """What the assistant's element cites."""
    return list((element or {}).get('cites') or [])


def _decide_targets(targets, on, because, moving_to, disagreements):
    """The reference's target components the assistant kept, rejected or did not judge: a rejected one leaves the
    target unless today's components still move into it, then it stays as a disagreement."""
    kept = []
    for key, target in targets.items():
        element = on.get(key)
        rejected = element is not None and element.get('operation') == 'delete'
        label = _target_label(element, rejected, target.get('name') in moving_to)
        why = _why(element, because)
        if label == 'disagreement': why = "today's components still move into it, so it stays: " + why
        target['decided_by'] = {'label': label, 'rule': 'new', 'assistant': (element or {}).get('operation'), 'why': why,
                                'cites': _cites(element)}
        if rejected:
            disagreements.append({'element': key, 'rule': 'new', 'assistant': 'delete', 'label': label, 'why': why,
                                  'final': 'new' if label == 'disagreement' else 'delete', 'cites': target['decided_by']['cites']})
        if label != 'ai_modified': kept.append(target)
    return kept


def _target_label(element, rejected, moved_into):
    """rule_only when the assistant said nothing, agreed when it kept it; a rejected target leaves (ai_modified) unless
    today's components still move into it (disagreement)."""
    if element is None: return 'rule_only'
    if not rejected: return 'agreed'
    return 'disagreement' if moved_into else 'ai_modified'


def _added(elements, known, because):
    """The target components the assistant added: operation "new" on nothing that exists, each with its evidence."""
    out, seen = [], set()
    for element in elements:
        if element.get('operation') != 'new' or element.get('id') in known | seen or element.get('subject') in known: continue
        seen.add(element.get('id'))
        out.append({'name': element.get('title') or element['id'], 'layer': None, 'responsibility': element.get('detail', ''),
                    'paths': [], 'evidence_ids': list(element.get('cites') or []),
                    'decided_by': {'label': 'ai_added', 'rule': None, 'assistant': 'new', 'cites': list(element.get('cites') or []),
                                   'why': because.get(element['id']) or element.get('detail', '')}})
    return out


def _redraw_gaps(out, record, current):
    """The gap rows of today's components drawn again from their final relation, the confirmed cards and the claims
    the triage did not set aside; the rows of introduced components stay as proposed."""
    out = Path(out)
    def load(name, default):
        return read_json(out / name, default)
    aside = {row.get('claim_id') for row in load('cards.json', {}).get('set_aside') or []}
    claims = [c for c in load('dossier.json', {}).get('claims', []) if c.get('id') not in aside]
    tasks = load('plan.json', {}).get('tasks', [])
    by_id = {c['id']: c for c in current}
    rows = []
    for row in record.get('gap_matrix') or []:
        component = by_id.get(row.get('current_id'))
        if component is not None:
            row = {**row, **current_gap(component, row.get('target_ids') or [], claims, tasks),
                   'decided_by': component['decided_by']['label']}
        rows.append(row)
    return rows


def _elements_on(elements, known):
    """{component or target id: the assistant's first element about it} (by its own id, else by its subject)."""
    on = {}
    for element in elements:
        on.setdefault(element.get('id') if element.get('id') in known else element.get('subject'), element)
    return on


def _set_aside(out):
    """The cards and claims the triage set aside (cards.json)."""
    import json
    try: set_aside = json.loads((Path(out) / 'cards.json').read_text(encoding='utf-8')).get('set_aside') or []
    except (OSError, ValueError): set_aside = []
    return {row.get(key) for row in set_aside for key in ('card', 'claim_id') if row.get(key)}


def _decide_currents(current, on, because, guards):
    """Each of today's components decided (its `decided_by`); the disagreements between the rule and the assistant.
    `guards`: (protected path test, the set-aside cards and claims)."""
    protected, aside = guards
    disagreements = []
    for component in current:
        element = on.get(component['id'])
        rule, why = component['relation'], _why(element, because)
        label, said = _decide_current(component, element, why, protected, aside)
        component['decided_by'] = {'label': label, 'rule': rule, 'why': said, 'cites': _cites(element),
                                   'assistant': RELATION_OF.get((element or {}).get('operation'), (element or {}).get('operation'))}
        if label in ('ai_modified', 'disagreement'):
            disagreements.append({'element': component['id'], 'rule': rule, 'assistant': component['decided_by']['assistant'],
                                  'final': component['relation'], 'label': label, 'why': said, 'cites': component['decided_by']['cites']})
    return disagreements


def _label_counts(rows):
    counts = {}
    for row in rows: counts[row['decided_by']['label']] = counts.get(row['decided_by']['label'], 0) + 1
    return counts


def _named_targets(record):
    """{TC-<name>: target component} of the rules' proposal."""
    return {f"TC-{_slug(t.get('name') or t.get('id'))}": t for t in record.get('target_components') or [] if isinstance(t, dict)}


def _explicit(record, ids):
    """The components the record lists beside today's (`ids`)."""
    return [c for c in record.get('components') or [] if c.get('id') not in ids]


def reconcile(out, planned=False, policy_path=None):
    """The final target from the rules' proposal (target-proposal.json) and, when the ideal was planned in this check,
    the assistant's decision on each of its components; the gap matrix is drawn again from it, without the claims of
    the cards the triage set aside (cards.json). Returns the record (render writes it) with `decided`, the count per
    label: agreed, ai_modified, rule_only, disagreement, ai_added, and `disagreements`, the rule's view beside the
    assistant's wherever they differ, and `aspects`: every aspect of the program with its verdict, keep or improve, and
    who gave it (eaos/analysis/understanding/aspects.py final)."""
    import json
    out = Path(out)
    source = out / 'target-proposal.json'
    record = json.loads((source if source.is_file() else out / 'target-architecture.json').read_text(encoding='utf-8'))
    elements, because = _view(out) if planned else ([], {})
    current = record['current_components']
    ids = {c['id'] for c in current}
    targets = _named_targets(record)
    on = _elements_on(elements, ids | set(targets))
    disagreements = _decide_currents(current, on, because, (protected_paths(out, policy_path), _set_aside(out)))
    final = _decide_targets(targets, on, because, {c.get('target_component') for c in current}, disagreements)
    added = _added(elements, ids | set(targets), because)
    final += added
    explicit = _explicit(record, ids)
    # Every proposal is counted, the target components the assistant rejected (no longer in the target) too.
    counts = _label_counts([*current, *targets.values(), *added])
    from ...analysis.understanding.aspects import final as aspects
    from ...ai.ideal.planner import current as planned_ideal
    plan, state = planned_ideal(out) if planned else (None, 'not_planned')
    record.update(target_components=final, components=explicit or current, gap_matrix=_redraw_gaps(out, record, current),
                  decisions=decisions([*current, *explicit]), decided={'by': 'assistant' if elements else 'rules', **counts},
                  disagreements=disagreements, aspects=aspects(out, plan if state == 'planned' else None))
    return record

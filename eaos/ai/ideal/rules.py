"""The rules' target of each view of the ideal, read from the records the rules wrote; `views(report)` puts the views
together. The assistant plans on top of it (eaos/ai/ideal/planner.py); without one it is the ideal shown."""
import re
from pathlib import Path

from .base import EVIDENCE, LIMIT, OPERATIONS, _facts, _load, _slug
from ..nodes.framework import short

RELATION_OP = {'retain': 'retain', 'modify': 'refactor', 'refactor': 'refactor', 'rebuild': 'rebuild', 'delete': 'delete',
               'retire': 'delete', 'introduce': 'new', 'new': 'new', 'merge': 'merge', 'unassessed': 'refactor'}
PATH_RANK = {op: i for i, op in enumerate(('retain', 'refactor', 'merge', 'rebuild', 'delete'))}
STORE_CHANGE = {'single_already': 'retain', 'merged_in_target': 'merge', 'still_multiple': 'refactor'}


def _element(id_, kind, title, operation, subject=None, detail='', cites=(), rule_ids=()):
    return {'id': str(id_), 'kind': kind, 'title': short(title, 160) or str(id_), 'operation': RELATION_OP.get(operation, operation)
            if RELATION_OP.get(operation, operation) in OPERATIONS else 'refactor', 'subject': subject, 'detail': short(detail, 220),
            'cites': [c for c in dict.fromkeys(cites) if isinstance(c, str) and EVIDENCE.match(c)][:8], 'rules': list(rule_ids)}


def proposal(report):
    """The rules' target as the rules proposed it (target-proposal.json), before the reconcile decided it; a report from
    before that stage has only target-architecture.json."""
    report = Path(report)
    return _load(report / 'target-proposal.json', None) or _load(report / 'target-architecture.json', {}) or {}


def views(report):
    """{view: (summary, [elements])}: the rules' target of every view, from the records the rules wrote."""
    report = Path(report)
    studio, target = report / 'studio', proposal(report)
    found = system(target, studio)
    return {'system': found, 'change': change(found), 'journeys': journeys(report, studio), 'paths': paths(studio),
            'data_paths': data_paths(report, studio), 'infra': infra(target), 'pipeline': pipeline(studio),
            'plan_order': plan_order(report)}


def _dicts(rows):
    """The rows that are objects (none when there are no rows)."""
    return [row for row in rows or [] if isinstance(row, dict)]


def _by(rows, key):
    """{row[key]: row} of the rows that are objects."""
    return {row.get(key): row for row in _dicts(rows)}


# ---------------------------------------------------------------- system and change

def system(target, studio):
    found = _load(studio / 'system.json', {}) or {}
    return ("Today's components with the rules' disposition, and the target components of the reference.",
            _current_components(target, found) + _target_components(target, found))


def change(system_view):
    return ("What changes from today to the rules' target: every component that is not retained.",
            [dict(e, id=f"chg-{e['id']}", kind='change') for e in system_view[1] if e['kind'] == 'component' and e['operation'] != 'retain'])


def _current_components(target, found):
    gap = _by(target.get('gap_matrix'), 'component')
    current = _by((found.get('current') or {}).get('nodes'), 'id')
    return [_component(comp, current.get(comp.get('name')) or {}, gap) for comp in _dicts(target.get('current_components'))]


def _component(comp, node, gap):
    relation = comp.get('relation') or node.get('op') or 'unassessed'
    return _element(comp.get('id') or comp.get('name'), 'component', comp.get('name'), relation, node.get('target'),
                    comp.get('reason'), (gap.get(comp.get('id')) or {}).get('evidence') or [],
                    [f"RULE-disposition-{relation}"] if relation in ('delete', 'rebuild', 'retain', 'modify') else [])


def _target_components(target, found):
    """The system map's target components, else (when it has none) the reference's."""
    nodes = (found.get('target') or {}).get('nodes')
    if nodes: return [_target_node(node) for node in nodes if isinstance(node, dict)]
    return [_element(f"TC-{_slug(comp['name'])}", 'target_component', comp['name'], 'new', None, comp.get('responsibility'), (),
                     _layer_rule(comp)) for comp in target.get('target_components') or [] if isinstance(comp, dict) and comp.get('name')]


def _target_node(node):
    return _element(f"TC-{_slug(node.get('id'))}", 'target_component', node.get('id'), node.get('op') or 'new', None,
                    f"{node.get('responsibility') or ''} (from: {', '.join(node.get('sources') or []) or 'nothing today'})",
                    (), _layer_rule(node))


def _layer_rule(row):
    return [f"RULE-layer-{_slug(row.get('layer'))}"] if row.get('layer') else []


# ---------------------------------------------------------------- journeys and paths

def journeys(report, studio):
    screens = _dicts((_load(studio / 'journeys.json', {}) or {}).get('screens'))
    if screens:
        return ("Every screen with its folder's operation toward the target (studio/journeys.json).", [_screen(s) for s in screens])
    pages = [f for f in _facts(report, 'entrypoints') if f.get('kind') == 'entry_point'
             and (f.get('value') or {}).get('surface') in ('page', 'route')]
    return ('Every page the user reaches, as the facts list them; the rules give screens no target yet.', [_page(f) for f in pages])


def _screen(s):
    return _element(s.get('id') or s.get('route'), 'screen', s.get('route') or s.get('title') or s.get('id'),
                    s.get('op') or s.get('operation') or 'retain', s.get('target'), s.get('title') or '',
                    [s.get('fact')] + list(s.get('facts') or []))


def _page(f):
    return _element(f['id'], 'screen', (f.get('value') or {}).get('route'), 'retain', None, (f.get('location') or {}).get('path'), [f['id']])


def paths(studio):
    found = _load(studio / 'paths.json', {}) or {}
    ops = {name: row.get('op') for name, row in (found.get('components') or {}).items() if isinstance(row, dict)}
    nodes = _by(found.get('nodes'), 'id')
    return ('Every code path with the hardest operation the rules give the parts it crosses (studio/paths.json).',
            [_path(path, ops, nodes) for path in _dicts(found.get('paths'))])


def _path(path, ops, nodes):
    members = [nodes.get(n) or {} for column in path.get('columns') or [] for n in column]
    found = [ops.get(n.get('component')) for n in members if ops.get(n.get('component'))]
    op = max(found, key=lambda o: PATH_RANK.get(o, 0)) if found else 'retain'
    return _element(path.get('id'), 'path', path.get('title'), op, path.get('entry'),
                    f"{path.get('gaps') or 0} gap(s) where the records stop", [path.get('fact'), path.get('flow_fact')]
                    + [n.get('fact') for n in members[:6]])


# ---------------------------------------------------------------- data and infrastructure

def data_paths(report, studio):
    data = _load(studio / 'data_paths.json', {}) or {}
    stores = _dicts(data.get('stores'))
    if not stores: return _stores_from_facts(report)
    # A store's evidence is on its endpoints' call sites (studio/data_paths.json endpoints[].sites[].fact); `sites` on
    # the store itself is their count.
    sites = {}
    for endpoint in _dicts(data.get('endpoints')):
        sites.setdefault(endpoint.get('store'), []).extend(x.get('fact') for x in _dicts(endpoint.get('sites')))
    return ('Every store with its writers and its change toward one owner (studio/data_paths.json).', [_store(s, sites) for s in stores])


def _count(value):
    return len(value) if isinstance(value, list) else value if isinstance(value, int) else 0


def _store(s, sites):
    own = s.get('sites') if isinstance(s.get('sites'), list) else []
    return _element(s.get('id') or s.get('name'), 'store', s.get('name') or s.get('id'), STORE_CHANGE.get(s.get('change'), 'retain'), None,
                    f"{_count(s.get('writers'))} writer(s), {_count(s.get('readers'))} reader(s)",
                    [s.get('fact')] + [x.get('fact') for x in own if isinstance(x, dict)] + sites.get(s.get('id'), []))


def _stores_from_facts(report):
    """The stores the data calls reach, when no data map was written: by table, else by the resource the call names."""
    stores = {}
    for f in _facts(report, 'entrypoints'):
        if f.get('kind') == 'data_access': stores.setdefault(_store_name(f.get('value') or {}), []).append(f)
    return ('Every store the data calls reach, with the calls and the files they come from; the rules give '
            'data no target yet (one owner per store is the plan\'s to propose).',
            [_element(f'STORE-{_slug(name)}', 'store', name, 'retain', None, _calls(rows), [r['id'] for r in rows])
             for name, rows in sorted(stores.items())][:LIMIT['elements']])


def _store_name(value):
    called = str(value.get('target') or value.get('route') or '')
    called = called.split('://', 1)[-1].split('/', 1)[-1] if '://' in called else called
    resource = next((part for part in re.split(r'[/?]', called) if part and not part.startswith((':', '$', '{'))), None)
    return str(value.get('table') or (f"{value.get('client') or 'api'}:{resource.lower()}" if resource else '?'))


def _calls(rows):
    return (f"{len(rows)} call(s) from {len({(r.get('location') or {}).get('path') for r in rows})} file(s): "
            + ', '.join(sorted({str((r.get('location') or {}).get('path')) for r in rows}))[:160])


def infra(target):
    areas = [i for i in _dicts(target.get('infrastructure')) if i.get('area')]
    return ("The reference's infrastructure baseline: each area kept or introduced, with the tool that fits.",
            [_element(f"INFRA-{_slug(i['area'])}", 'infra', f"{i['area']}: {i.get('tool') or i.get('tool_reason') or ''}",
                      'retain' if i.get('present') else 'new', i['area'], f"{i.get('decision') or ''} ({i.get('evidence') or ''})",
                      (), [f"RULE-infra-{_slug(i['area'])}"]) for i in areas])


# ---------------------------------------------------------------- pipeline and plan

def pipeline(studio):
    found = _load(studio / 'pipeline.json', {}) or {}
    gaps = _pipeline_gaps(found)
    stages = [s for s in _dicts(found.get('stages')) if s.get('kind') not in ('router', 'fork', 'join')]
    if gaps: return ("The pipeline rules' gap: one entry per broken rule (studio/pipeline.json#views.gap).", [_gap(g) for g in gaps])
    if found.get('detected') and stages:
        return ("A pipeline that breaks none of the pipeline rules: every stage is kept (studio/pipeline.json).",
                [_kept_stage(s) for s in stages][:LIMIT['elements']])
    return ('The check looked for a pipeline and found none: there is no pipeline to plan.', []) if found \
        else ('No pipeline map was written for this check.', [])


def _pipeline_gaps(found):
    # The pipeline section keeps its gap under views.gap (eaos/analysis/maps/pipeline.py section); a flat `gap` is the older shape.
    return [g for g in (found.get('views') or {}).get('gap') or found.get('gap') or found.get('gaps') or [] if isinstance(g, dict)]


def _evidence_fact(row):
    return (row.get('evidence') or {}).get('fact') if isinstance(row.get('evidence'), dict) else None


def _gap(g):
    return _element(g.get('id'), 'pipeline_gap', g.get('title') or g.get('detail') or g.get('rule'),
                    g.get('operation') or g.get('op') or 'refactor', g.get('stage') or g.get('subject'),
                    g.get('detail') or g.get('why') or '',
                    [g.get('fact'), _evidence_fact(g), g.get('card')] + list(g.get('facts') or []) + list(g.get('cards') or []),
                    _pipeline_rule(g))


def _pipeline_rule(gap):
    return [f"RULE-pipeline-{_slug(gap['rule'])}"] if gap.get('rule') else []


def _kept_stage(s):
    return _element(s.get('id'), 'stage', s.get('label') or s.get('title') or s.get('id'), 'retain', s.get('id'),
                    s.get('kind') or '', [_evidence_fact(s)])


def plan_order(report):
    plan = _load(report / 'plan.json', {}) or {}
    return ("The fix plan's milestones in the rules' order.",
            [_element(m.get('id'), 'step', f"{m.get('id')}: {m.get('name') or m.get('goal') or ''}", 'retain', m.get('id'),
                      m.get('goal'), [t for t in m.get('tasks') or [] if isinstance(t, str)], ['RULE-plan-order'])
             for m in plan.get('milestones') or [] if isinstance(m, dict)])

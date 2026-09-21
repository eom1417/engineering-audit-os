"""Target architecture: the picture of what the codebase should look like.

Three things every target component must carry:

  origin         the file in the current codebase this component descends from
  relation       retain / modify / introduce / retire, the kind of move needed
  contracts      what the component promises: inputs, outputs, invariants

The matrix is the gap between current and target: every current component has
an origin in the target, every target component has an origin in the current.
The matrix is a fact about plans, not a claim about the future.
"""
from collections import defaultdict
from pathlib import Path
from .facts.store import read_set
from .facts import digest


NAME = 'target-architecture'
VERSION = '1'
LIMITATIONS = [
    'A target component is a proposal, not a guarantee; the engine does not write code.',
    'The relation (retain/modify/introduce/retire) is the engine\'s best read of the gap; a human '
    'reviewer may move a component from modify to retire or vice versa.',
    'A target component\'s contracts are derived from the source it descends from; new components '
    'have empty contracts until the engagement writes them.',
]


def _gather(out):
    sets = {}
    for name in ['syntax', 'graph', 'domain', 'fingerprint']:
        path = Path(out) / 'facts' / f'{name}.json'
        if path.is_file(): sets[name] = read_set(Path(out), name)
    return sets


def components(sets, contracts_by_path=None):
    """A target component per source symbol, with the smallest useful metadata.

    `contracts_by_path` lets the engagement declare contracts for known files; a
    file absent from the contract map gets an empty contract the reviewer fills in.
    """
    contracts_by_path = contracts_by_path or {}
    out = []
    seen = set()
    for fact in sets.get('syntax', {}).get('facts', []):
        if fact['kind'] != 'symbol': continue
        loc = fact['location']
        key = (loc['path'], loc.get('start_line'))
        if key in seen: continue
        seen.add(key)
        value = fact['value']
        out.append({
            'id': f"T-{loc['path'].replace('/', '.').replace('.py', '')}-{loc.get('start_line', 0)}",
            'name': value.get('name', ''), 'kind': value.get('kind', 'function'),
            'origin': loc['path'],
            'relation': 'unassessed',
            'responsibility': '',
            'owner': '',
            'paths': [loc['path']],
            'contracts': contracts_by_path.get(loc['path'], []),
            'depends_on': [], 'evidence_ids': [fact['id']], 'source_component_id': None,
        })
    return out


def decisions(sets, components_list):
    """One ADR per fingerprint cluster and per dependency cycle."""
    decisions = []
    for fact in sets.get('fingerprint', {}).get('facts', []):
        if fact['kind'] != 'duplicate_cluster': continue
        occs = fact['value']['occurrences']
        if len(occs) < 2: continue
        decisions.append({
            'id': 'ADR-FP-' + fact['value']['shape_sha'][:8],
            'problem': 'Symbols share an AST pattern; equivalence of their business rules is not established.',
            'options': ['Canonicalize at the most-imported site.',
                         'Introduce a shared module both sites import from.',
                         'Keep both, document the divergence.'],
            'chosen': None, 'status': 'investigate',
            'tradeoffs': 'Smallest cut; the chosen site must satisfy the layering policy.',
            'migration_steps': ['Add a public name at the chosen site.',
                                'Replace each duplicate body with an import-and-call.',
                                'Add an equivalence test that holds both call sites.'],
            'compatibility': 'Unknown until equivalence and contract checks are completed.',
            'rollback': 'Revert one commit; nothing else depends on the move.',
            'success_measures': ['single_source indicator falls to 0 for this cluster.',
                                  'All call sites still produce the same outputs.'],
            'finding_ids': [f['id'] for f in [fact]],
            'evidence_ids': [f['id'] for f in [fact]],
        })
    for fact in sets.get('graph', {}).get('facts', []):
        if fact['kind'] != 'graph_cycle': continue
        decisions.append({
            'id': 'ADR-CYCLE-' + str(fact.get('id', ''))[-8:],
            'problem': 'Files form a dependency cycle.',
            'options': ['Lift shared code into a common module.',
                         'Invert one edge with an interface.',
                         'Accept the cycle and document the boundary.'],
            'chosen': None, 'status': 'investigate',
            'tradeoffs': 'Lift is invasive; inversion keeps the boundary but adds indirection.',
            'migration_steps': ['Identify the smallest shared symbol on the cycle.',
                                 'Move it to a new module that both sides import.',
                                 'Run policy check to confirm the new edges are allowed.'],
            'compatibility': 'Unknown until public import contracts are checked.',
            'rollback': 'Revert one commit; the cycle returns and the policy check fails.',
            'success_measures': ['policy check passes.',
                                  'honest_boundaries stays at 0.'],
            'finding_ids': [f['id'] for f in [fact]],
            'evidence_ids': [f['id'] for f in [fact]],
        })
    return decisions


def gap_matrix(current_components, target_components):
    """For each current component, what target component descends from it, if any."""
    by_source = defaultdict(list)
    for target in target_components:
        if target.get('source_component_id'):
            by_source[target['source_component_id']].append(target)
    rows = []
    for current in current_components:
        matches = by_source[current['id']]
        complete = matches and all(t.get('contracts') and t.get('responsibility') and t.get('evidence_ids')
                                   and t.get('relation') in {'retain', 'modify', 'retire'} for t in matches)
        rows.append({'current_id': current['id'], 'current_origin': current['origin'],
                     'target_ids': [t['id'] for t in matches],
                     'gap': 'covered' if complete else 'incomplete_contract' if matches else 'unassessed'})
    return rows


def build(out, contracts_by_path=None, target_components=None):
    """A source inventory is not a target design. Only explicit proposals enter the matrix."""
    import json
    sets = _gather(out)
    current = components(sets, contracts_by_path)
    proposal = Path(out) / 'target-design.json'
    if target_components is None and proposal.is_file():
        data = json.loads(proposal.read_text())
        if data.get('schema_version') != 1: raise ValueError('Unsupported target design')
        target_components = data.get('components')
    target_components = target_components or []
    known = {component['id'] for component in current}
    seen = set()
    for component in target_components:
        if not isinstance(component, dict) or not component.get('id') or component['id'] in seen:
            raise ValueError('Each target component needs a unique id')
        seen.add(component['id'])
        relation = component.get('relation')
        if relation not in {'retain', 'modify', 'introduce', 'retire'}: raise ValueError('Invalid target relation')
        if relation != 'introduce' and component.get('source_component_id') not in known:
            raise ValueError('Target component refers to an unknown source component')
        if not component.get('evidence_ids'): raise ValueError('Target component needs evidence')
    matrix = gap_matrix(current, target_components)
    return {'schema_version': 2, 'status': 'REVIEW_REQUIRED',
            'retained_structure': 'Source inventory is shown below. Missing target decisions remain explicit gaps.',
            'current_components': current, 'components': target_components or current,
            'target_components': target_components,
            'decisions': decisions(sets, current), 'gap_matrix': matrix,
            'limits': ' '.join(LIMITATIONS)}


# The component inventory belongs in the record; the document names the shape of the target.
SHOWN_COMPONENTS = 12
SHOWN_DECISIONS = 12


def render(out, target, language='ar'):
    """Render the target architecture as a Markdown document."""
    ar = language == 'ar'
    lines = []
    if ar:
        lines += ['# البنية المستهدفة', '',
                  '> جرد المصدر منفصل عن التصميم المستهدف؛ ما لم يُحدد ويُراجع يبقى فجوة.', '']
    else:
        lines += ['# Target architecture', '',
                  '> Source inventory and reviewed target proposals are separate. Unspecified targets remain gaps.', '']
    lines += ['## ' + ('البنية المحفوظة' if ar else 'Retained structure'), '']
    lines += [target['retained_structure']]
    lines += ['', '## ' + ('المكوّنات' if ar else 'Components')]
    by_relation = defaultdict(list)
    for component in target['components']:
        by_relation[component['relation']].append(component)
    for relation in ['unassessed', 'retain', 'modify', 'introduce', 'retire']:
        rows = by_relation.get(relation, [])
        if not rows: continue
        lines += ['', '### ' + relation.capitalize() + f' ({len(rows)})']
        for component in rows[:SHOWN_COMPONENTS]:
            lines += [f"- `{component['id']}` ← `{component['origin']}`: {component['name']}"]
        if len(rows) > SHOWN_COMPONENTS:
            lines += [('- … البقية في `target-architecture.json`' if ar
                       else '- … the rest are in `target-architecture.json`')]
    lines += ['', '## ' + ('القرارات المعمارية' if ar else 'Architectural decisions')]
    for adr in target['decisions'][:SHOWN_DECISIONS]:
        lines += ['', f"### {adr['id']}: {adr.get('problem', '')}"]
        lines += ['- ' + ('المشكلة' if ar else 'problem') + f": {adr.get('problem', '')}"]
        lines += ['- ' + ('البدائل' if ar else 'options') + ":"]
        for option in adr.get('options', []): lines += [f"  - {option}"]
        lines += ['- ' + ('المختار' if ar else 'chosen') + f": {adr.get('chosen', '')}"]
        lines += ['- ' + ('المقايضة' if ar else 'tradeoffs') + f": {adr.get('tradeoffs', '')}"]
    if len(target['decisions']) > SHOWN_DECISIONS:
        lines += ['', (f"عُرض {SHOWN_DECISIONS} قرارًا من {len(target['decisions'])}؛ البقية في "
                       '`target-architecture.json`.' if ar else
                       f"Showing {SHOWN_DECISIONS} of {len(target['decisions'])} decisions; the rest are in "
                       '`target-architecture.json`.')]
    lines += ['', '## ' + ('مصفوفة الفجوة' if ar else 'Gap matrix')]
    covered = sum(1 for row in target['gap_matrix'] if row['gap'] == 'covered')
    lines += [f"- {'مغطى' if ar else 'covered'}: {covered} / {len(target['gap_matrix'])}"]
    Path(out, 'TARGET-ARCHITECTURE.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    Path(out, 'target-architecture.json').write_text(json_dumps(target), encoding='utf-8')
    return {'markdown': str(Path(out, 'TARGET-ARCHITECTURE.md')),
            'json': str(Path(out, 'target-architecture.json'))}


def json_dumps(obj):
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2) + '\n'

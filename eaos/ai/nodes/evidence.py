"""What an AI node may cite: the cards of a report and every id a citation may resolve to (facts, claims, cards and
the rules the baseline applied)."""
import re
from pathlib import Path

from .framework import short as _short
from ...core.system.files import read_json

EVIDENCE = re.compile(r'^(FACT|CLM|TASK|RULE)-[A-Za-z0-9_.:-]+$')


def _slug(text):
    return re.sub(r'[^A-Za-z0-9_.:-]+', '-', str(text)).strip('-') or 'root'


def cards(report):
    """The report's cards, each with its id, title, kind, severity, paths, state and the fact ids it cites: studio/cards.json
    when a report has it, else the tasks of plan.json in that shape."""
    shown = (read_json(Path(report) / 'studio/cards.json', {}) or {}).get('cards')
    if isinstance(shown, list): return _with_id(shown)
    return [_card(task) for task in _with_id((read_json(Path(report) / 'plan.json', {}) or {}).get('tasks') or [])]


def _with_id(rows):
    """The rows that are objects with an id."""
    return [row for row in rows if isinstance(row, dict) and row.get('id')]


def _card(task):
    """A plan task in the shape of a card: its kind its pattern, its severity by its kind, its evidence the fact ids."""
    from ...core.contracts.card_areas import classify
    cited = (task.get('evidence') or {}).get('fact_ids') if isinstance(task.get('evidence'), dict) else task.get('evidence')
    return {**task, 'kind': task.get('pattern') or task.get('kind'), 'severity': task.get('severity') or classify(task)[1],
            'state': task.get('state') or 'open', 'evidence': [f for f in cited or [] if isinstance(f, str)]}


def _proposal(report):
    """The rules' target as the rules proposed it (target-proposal.json), before the reconcile decided it; a report from
    before that stage has only target-architecture.json."""
    report = Path(report)
    return read_json(report / 'target-proposal.json', None) or read_json(report / 'target-architecture.json', {}) or {}


def rules(report):
    """{RULE id: what it says}: the disposition rules, the reference's layers, the infrastructure baseline and the
    plan's ordering rule, as the baseline applied them to this report."""
    target = _proposal(report)
    return {**_disposition_rules(), **_layer_rules(target), **_infra_rules(target),
            'RULE-plan-order': ('The fix plan runs in milestones; a task waits for the tasks it names as prerequisites and '
                                'for the last earlier task touching the same file (eaos/analysis/planning/cards.py waves).')}


def _disposition_rules():
    """The disposition rules (eaos/analysis/target_state/projection.py RULES), in their order."""
    from ...analysis.target_state.projection import RULES as DISPOSITION
    disposition = read_json(DISPOSITION, {}) or {}
    return {f'RULE-disposition-{name}': _short((disposition.get(name) or {}).get('why'), 300) for name in disposition.get('order') or []}


def _layer_rules(target):
    """The layers of the target's reference architecture: each one's responsibility and what it may depend on."""
    try:
        from ...analysis.target_state.references import by_id
        reference = by_id(target.get('reference')) if target.get('reference') else None
    except Exception:
        reference = None
    return {f"RULE-layer-{_slug(layer['name'])}": _short(f"{layer.get('responsibility', '')}; may depend on: "
                                                         f"{', '.join(layer.get('allowed_dependencies') or []) or 'nothing'}", 300)
            for layer in (reference or {}).get('layers') or []}


def _infra_rules(target):
    """The infrastructure baseline: the decision of each area."""
    return {f"RULE-infra-{_slug(item['area'])}": _short(item.get('decision'), 300)
            for item in target.get('infrastructure') or [] if isinstance(item, dict) and item.get('area')}


def known_ids(report):
    """Every id a citation may resolve to: the report's facts (FACT-), claims (CLM-) and cards (TASK-), and the rules
    the baseline applied (RULE-)."""
    report = Path(report)
    known = set(rules(report)) | _fact_ids(report)
    known.update(c['id'] for c in (read_json(report / 'dossier.json', {}) or {}).get('claims') or [] if isinstance(c, dict) and c.get('id'))
    known.update(c['id'] for c in cards(report))
    return {i for i in known if EVIDENCE.match(i)}


def _fact_ids(report):
    """The ids of the report's facts (facts/*.json, its caches and index aside)."""
    known = set()
    for path in sorted((report / 'facts').glob('*.json')):
        if path.name in ('syntax-cache.json', 'index.json', 'run.json'): continue
        data = read_json(path, {}) or {}
        known.update(f['id'] for f in data.get('facts') or [] if isinstance(f, dict) and isinstance(f.get('id'), str))
    return known

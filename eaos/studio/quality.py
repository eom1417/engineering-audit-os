"""studio/quality.json: how good EAOS's own analysis is for this project (contract v2, docs/STUDIO.md D7).

Three parts, each from a record, none estimated here:
- the detectors: each detector's precision and recall on EAOS's labelled set and whether it meets the bar the product
  shows it at (eaos/data/engine-quality.json, packaged from docs/engine-precision.json by tools/engine_quality.py),
  with what it produced in this report (the dossier's shown and withheld claims, and the data facts it reads) and, when
  this project is one of the labelled ones, its own true and false positives there;
- the plan's capabilities that judge the analysis, and their indicators (docs/north-star.json, packaged the same way);
- nothing else: what a detector or indicator has not measured is null, with the reason in its source.
"""
import json
from pathlib import Path

from .. import indicators

PACKAGED = Path(__file__).resolve().parent.parent / 'data' / 'engine-quality.json'
SRC = 'eaos/data/engine-quality.json'


def packaged(path=None):
    try: return json.loads(Path(path or PACKAGED).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


def _ratio(value, src):
    ok = isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1
    return {'value': round(value, 4) if ok else None, 'src': src}


def outputs(report, dossier):
    """{detector: {'shown': n, 'withheld': n, 'facts': n}}: what each detector produced in this report: its findings shown,
    those held back because the detector is under its bar, and the data facts it reads (shown as data, not as findings)."""
    from ..claims import detector_of
    out = {}
    def add(detector, key, n=1):
        out.setdefault(detector, {'shown': 0, 'withheld': 0, 'facts': 0})[key] += n
    for claim in dossier.get('claims') or []:
        if isinstance(claim, dict): add(detector_of(claim), 'shown')
    for claim in dossier.get('withheld_claims') or []:
        if isinstance(claim, dict): add(detector_of(claim), 'withheld')
    # The data facts the precision set also judges: the data model read from the code and from the running app
    for name, runtime in (('domain', False), ('runtime', True)):
        facts = (indicators.load(report, f'facts/{name}.json', {}) or {}).get('facts') or []
        for fact in facts:
            kind = fact.get('kind') if isinstance(fact, dict) else None
            if kind in ('data_model', 'data_table'): add('data_model:runtime' if runtime else kind, 'facts')
    try:
        from ..facts.run import read_available
        from ..sustainability import writers
        written = writers(read_available(report))
        if written: add('data_owners', 'facts', len(written))
    except Exception:                       # a report without the domain facts: nothing to count, not an error
        pass
    return out


def _labelled(name, projects):
    name = str(name or '').lower()
    return next((p for p in projects if name and (name == p.lower() or name.startswith(p.lower()) or p.lower().startswith(name))), None)


def quality(report, dossier, name=None, lang='ar', record=None):
    """The quality section's body; None when this EAOS carries no quality record."""
    record = packaged() if record is None else record
    if not record: return None
    lang = 'ar' if lang == 'ar' else 'en'
    produced = outputs(Path(report), dossier or {})
    labelled = _labelled(name, record.get('labelled_projects') or [])
    detectors = []
    for row in record.get('detectors') or []:
        here = produced.get(row['id'], {'shown': 0, 'withheld': 0, 'facts': 0})
        judged = row.get('judged') or 0
        src = f"{SRC}#detectors[{row['id']}]"
        mine = (row.get('projects') or {}).get(labelled) if labelled else None
        detectors.append({
            'id': row['id'], 'name': (row.get('name') or {}).get(lang) or row['id'], 'engine': None,
            'applies': bool(here['shown'] or here['withheld'] or here['facts']),
            'precision': _ratio(row.get('precision') if judged else None, f'{src}.precision' if judged else 'no judged output on the labelled set yet'),
            'recall': _ratio(row.get('recall'), f'{src}.recall' if row.get('recall') is not None else 'no labelled or planted case for it yet'),
            'labelled': row.get('labelled_positives'), 'shown': bool(row.get('shown')), 'status': row.get('status') or 'not_measured',
            'why': row.get('why') or '', 'judged': judged, 'here': here,
            'project': {'tp': mine['tp'], 'fp': mine['fp'], 'unjudged': mine['unjudged']} if mine else None})
    capabilities, rows = [], []
    for capability in record.get('capabilities') or []:
        values = [row.get('value') for row in capability.get('indicators') or []]
        measured = [v for v in values if isinstance(v, (int, float))]
        capabilities.append({'id': capability['id'], 'name': capability['name'].get(lang) or capability['id'],
                             'value': _ratio(sum(measured) / len(values) if values else None,
                                             f"docs/north-star.json#capabilities[{capability['id']}]: mean of its indicators, an unmeasured one counted as 0"),
                             'measured': len(measured), 'indicators': len(values)})
        for row in capability.get('indicators') or []:
            value = row.get('value')
            rows.append({'id': row['id'], 'name': row['name'].get(lang) or row['id'], 'capability': capability['id'],
                         'value': _ratio(value, f"docs/north-star.json#{row['id']}" if value is not None else 'not measured yet'),
                         'target': row['target'] if isinstance(row.get('target'), (int, float)) and 0 <= row['target'] <= 1 else 1.0,
                         'how': 'recorded' if row.get('measured') == 'recorded' else 'automated'})
    here = [d for d in detectors if d['applies']]
    return {'detectors': detectors, 'capabilities': capabilities, 'indicators': rows,
            'bar': {k: record['bar'][k] for k in ('precision', 'recall', 'judged') if k in (record.get('bar') or {})},
            'labelled': {'items': record.get('labelled_items'), 'projects': record.get('labelled_projects') or [], 'this_project': labelled},
            'counts': {'detectors': {'value': len(detectors), 'src': f'{SRC}#detectors'},
                       'here': {'value': len(here), 'src': 'dossier.json#claims, withheld_claims by detector'},
                       'shown_here': {'value': sum(d['here']['shown'] for d in here), 'src': 'dossier.json#claims by detector'},
                       'withheld_here': {'value': sum(d['here']['withheld'] for d in here), 'src': 'dossier.json#withheld_claims by detector'}},
            'measured_at': record.get('north_star_measured_at')}

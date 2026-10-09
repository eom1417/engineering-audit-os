"""The pipeline-gap planner: how each gap of the pipeline map is closed, planned by the assistant (docs/STUDIO.md D11).

It reads the pipeline map's gap (studio/pipeline.json `views.gap`: one entry per broken pipeline rule, with its
evidence and operation) and the rules themselves (eaos/data/pipeline-rules.json), then decides for each gap: "plan"
(the step that closes it, with its operation), "ask" (closing it is a choice for the person) or "not a gap" (the rule
does not fit this pipeline: its rule is told). A planning node: a critique pass reviews the draft. A decision must cite
its gap or the gap's rule. The steps are written to nodes/pipeline_gap_planner/plan.json, where the plan orderer
reads them.
"""
import json
import sys
from pathlib import Path

from . import core
from .. import ideal

VERSION = '1'
LIMIT = {'gaps': 200}
OPERATIONS = ('retain', 'refactor', 'rebuild', 'merge', 'delete', 'new')
DETAIL = {'type': 'object', 'additionalProperties': False, 'required': ['operation', 'step'],
          'properties': {'operation': {'type': 'string', 'enum': list(OPERATIONS)}, 'step': {'type': 'string'}}}
TASK = ('You are the pipeline-gap planner of EAOS, an engineering audit. Below are the gaps of this project\'s pipeline map: '
        'each is a pipeline rule the code breaks, with where, and the rules themselves with their sources. Decide for each gap: '
        '"plan" with `detail.operation` and `detail.step` (the concrete step that closes it, in plain words), "ask" when '
        'closing it is a choice for the person (say the choice in `open_questions`), or "not a gap" when the rule does not fit '
        'this pipeline (say why). Cite in `evidence` the gap id and its rule id (RULE-pipeline-P...).')


def _gaps(report):
    report = Path(report)
    body = core.load(report / 'studio/pipeline.json')
    if body is None:
        from ..pipeline import from_report
        body = from_report(report, lang='en')
    return [g for g in ((body or {}).get('views') or {}).get('gap') or [] if isinstance(g, dict) and g.get('id')]


def inputs(report, project=None, lang='en', **_):
    gaps = _gaps(report)[:LIMIT['gaps']]
    if not gaps: return None
    try: rules_ = json.loads((Path(__file__).resolve().parents[2] / 'data/pipeline-rules.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): rules_ = []
    used = {g.get('rule') for g in gaps}
    return {'lang': lang,
            'gaps': [{'id': g['id'], 'rule': f"RULE-pipeline-{g.get('rule')}", 'subject': g.get('subject'), 'subject_kind': g.get('subject_kind'),
                      'operation': g.get('operation'), 'detail': core.short(g.get('detail'), 300), 'evidence': g.get('evidence'),
                      'card': g.get('card')} for g in gaps],
            'rules': [{'id': f"RULE-pipeline-{r['id']}", 'title': r.get('title'), 'why': core.short(r.get('why'), 300), 'source': r.get('source')}
                      for r in rules_ if isinstance(r, dict) and r.get('id') in used]}


def subjects(data):
    return [g['id'] for g in data['gaps']]


def known(report, data):
    return ideal.known_ids(report) | {g['id'] for g in data['gaps']} | {g['rule'] for g in data['gaps']}


def rules(data):
    return {g['id']: ([g['id'], g['rule']], f"The pipeline rule says: {g['detail']}", 0.6,
                      {'operation': g['operation'] if g['operation'] in OPERATIONS else 'refactor', 'step': g['detail']})
            for g in data['gaps']}


def check(data, decision):
    gap = next(g for g in data['gaps'] if g['id'] == decision['subject'])
    return None if {gap['id'], gap['rule']} & set(decision['evidence']) else 'it cites neither its gap nor its rule'


def prompt(data):
    return (TASK + '\n\n' + core.rules_of_the_answer(data['lang']) + '\n\nAnswer with the JSON object of the schema only.\n\n'
            'The bundle:\n' + json.dumps({k: v for k, v in data.items() if k != 'lang'}, ensure_ascii=False))


def finish(report, record, data):
    route = {s: r['decision'] for r in record['routes'] for s in r['subjects']}
    steps = [{'gap': d['subject'], 'decision': route[d['subject']], 'operation': (d.get('detail') or {}).get('operation'),
              'step': (d.get('detail') or {}).get('step') or d['why'], 'why': d['why'], 'evidence': d['evidence'], 'source': d['source']}
             for d in record['decisions']]
    folder = core.folder_of(report, record['node'])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'plan.json').write_text(json.dumps({'schema_version': 1, 'at': record['at'], 'method': record['method'], 'steps': steps},
                                                 ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def run(node, report, **options):
    return core.run_node(node, sys.modules[__name__], report, **options)

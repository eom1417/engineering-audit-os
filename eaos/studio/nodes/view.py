"""What the Studio reads of the AI nodes: studio/nodes.json (contract studio-nodes) and the Decisions inbox rows.

`section(report, lang)` lists every declared node (eaos/studio/nodes/__init__.py) with its router's branches and how
many subjects took each, and its last run (nodes/<node>/last.json) as it was decided: by which assistant and model, or
by the rules alone and why; a node that never ran says so. `decisions(report, lang)` turns the open questions of the
nodes' last decisions, and every subject a node routed to the inbox, into rows of studio/decisions.json.
"""
from pathlib import Path

from . import core

# Each branch's condition in Arabic, beside the English of its declaration.
WHEN_AR = {
    ('card_triage', 'confirm'): 'الدليل يثبتها: تكمل البطاقة إلى الخطة',
    ('card_triage', 'doubt'): 'الدليل لا يحسمها: فحص يحسمها قبل أن يراها الشخص',
    ('card_triage', 'reject'): 'الدليل ينقضها: تُنحّى وتُبلَّغ قاعدتها',
    ('card_triage', 'rules only'): 'ما قرر مساعد: تكمل البطاقة كما كتبتها المحركات',
    ('ideal_planner', 'accept'): 'كل عرض مخطَّط بدليل ولا سؤال باقٍ: يكمل المثالي إلى الخطة',
    ('ideal_planner', 'ask'): 'المثالي يترك أسئلة: تنتظر الشخص في صندوق القرارات',
    ('ideal_planner', 'rules only'): 'ما خُطِّط: يبقى هدف القواعد',
    ('pipeline_gap_planner', 'plan'): 'خطوة تسد الفجوة، وتكمل إلى الخطة',
    ('pipeline_gap_planner', 'ask'): 'سد الفجوة اختيار للشخص',
    ('pipeline_gap_planner', 'not a gap'): 'قاعدة خط المعالجة لا تنطبق هنا: تُبلَّغ قاعدتها',
    ('pipeline_gap_planner', 'rules only'): 'ما قرر مساعد: تبقى فجوة القواعد',
    ('plan_orderer', 'reorder'): 'ترتيب وتجميع أفضل للخطوات، وكل شرط مسبق محفوظ',
    ('plan_orderer', 'keep'): 'ترتيب القواعد صحيح أصلًا',
    ('plan_orderer', 'ask'): 'الترتيب يتوقف على اختيار للشخص',
    ('plan_orderer', 'rules only'): 'ما قرر مساعد: يبقى ترتيب القواعد',
    ('fix_reviewer', 'accept'): 'التعديل يفعل ما تطلبه البطاقة والفحوص سليمة: يُعرض على الشخص',
    ('fix_reviewer', 'retry'): 'الإصلاح خطأ أو ناقص: يُعاد',
    ('fix_reviewer', 'ask'): 'الإصلاح يحتاج اختيارًا من الشخص',
    ('fix_reviewer', 'rules only'): 'ما قرر مساعد: يبقى حكم البوابات',
}
LIMIT = {'decisions': 500, 'dropped': 200, 'log': 10}


def _log(report):
    by = {}
    for entry in core.log(report):
        by.setdefault(entry.get('node'), []).append(entry)
    return by


def section(report, lang='ar'):
    """The body of studio/nodes.json."""
    from . import NODES, SINKS, TITLES_AR
    report = Path(report)
    logs = _log(report)
    rows, questions = [], []
    for node in NODES:
        last = core.last(report, node)
        last = last if isinstance(last, dict) and last.get('node') == node.name else None
        taken = {r['decision']: len(r.get('subjects') or []) for r in (last or {}).get('routes') or []}
        decisions = list((last or {}).get('decisions') or [])
        for d in decisions:
            for q in d.get('open_questions') or []:
                questions.append({'id': f"{node.name}:{d['subject']}:{q['id']}", 'node': node.name, 'subject': d['subject'], 'question': q['question'],
                                  'options': list(q.get('options') or []), 'recommendation': q.get('recommendation')})
        rows.append({'id': node.name, 'title': {'en': node.title, 'ar': TITLES_AR.get(node.name, node.title)}, 'kind': 'ai',
                     'passes': list(node.passes), 'requires': list(node.requires),
                     'routes': [{'decision': r.decision, 'to': r.to, 'when': {'en': r.when, 'ar': WHEN_AR.get((node.name, r.decision), r.when)},
                                 'subjects': taken.get(r.decision, 0)} for r in node.routes],
                     'state': last['state'] if last else 'not_run', 'method': last['method'] if last else None,
                     'assistant': (last or {}).get('assistant'), 'model': (last or {}).get('model'), 'at': (last or {}).get('at'),
                     'cached': bool((last or {}).get('cached')), 'seconds': (last or {}).get('seconds'), 'cost_usd': (last or {}).get('cost_usd'),
                     'budget': (last or {}).get('budget') or {'seconds': float(node.budget.seconds), 'usd': node.budget.usd},
                     'why': (last or {}).get('why'), 'summary': (last or {}).get('summary') or None,
                     'decisions': decisions[:LIMIT['decisions']], 'dropped': list((last or {}).get('dropped') or [])[:LIMIT['dropped']],
                     'log': [{k: e.get(k) for k in ('at', 'state', 'assistant', 'model', 'prompt', 'inputs', 'cached', 'seconds', 'cost_usd')}
                             for e in logs.get(node.name, [])[-LIMIT['log']:]]})
    count = lambda value, what: {'value': value, 'src': f'nodes/<node>/last.json: {what}', 'unit': 'count'}
    ran = [r for r in rows if r['state'] != 'not_run']
    return {'nodes': rows, 'sinks': [{'id': key, 'title': {'en': en, 'ar': ar}} for key, (en, ar) in SINKS.items()],
            'questions': questions,
            'counts': {'nodes': count(len(rows), 'declared nodes'), 'ran': count(len(ran), 'nodes with a last run'),
                       'by_model': count(sum(r['method'] == 'model' for r in ran), "nodes the person's assistant decided"),
                       'decisions': count(sum(len(r['decisions']) for r in rows), 'decisions'),
                       'dropped': count(sum(len(r['dropped']) for r in rows), 'decisions dropped by the evidence check')}}


def decisions(report, lang='ar'):
    """Rows of studio/decisions.json: each open question of the nodes' last decisions, waiting for the person (the ideal
    planner's own questions reach the inbox through eaos/studio/ideal.py `decisions`)."""
    body = section(report, lang)
    asked = {row['id']: row['at'] or '' for row in body['nodes']}
    return [{'id': f"node-{core.short(q['id'], 120)}", 'question': q['question'], 'recommendation': q.get('recommendation') or '',
             'options': [{'id': f'o{i + 1}', 'label': str(o)} for i, o in enumerate(q['options'])], 'blocks': [], 'state': 'waiting',
             'answer': None, 'plan': None, 'asked': asked.get(q['node'], ''), 'tool': 'run_nodes'}
            for q in body['questions'] if q['node'] != 'ideal_planner']

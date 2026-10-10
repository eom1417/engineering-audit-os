"""The AI nodes of EAOS's pipeline, declared as data (docs/STUDIO.md D11).

Each node takes a deterministic output, analyses it, plans and decides, and writes one structured decision per subject
(eaos/studio/nodes/core.py, contract `ai-node`). After each node a router of declared branches (`routes`) sends every
subject on by its decision, to the next node or out of the pipeline (`SINKS`); each node has exactly one route
"rules only", the one every subject takes when the rules decide alone. `requires` names the nodes whose result a node
reads, so EAOS's own pipeline map draws them in this order, from the code (eaos/facts/pipeline_code.py).

    run(report, names=None, launcher=None, adapters=None, project=None, lang='en', fresh=False, **inputs)
        runs the named nodes (all by default) whose inputs exist, in order, and returns {name: record}.
"""
from typing import NamedTuple

from .fix_reviewer import run as review_fix
from .ideal_planner import run as plan_ideal
from .pipeline_gap_planner import run as plan_pipeline_gaps
from .plan_orderer import run as order_plan
from .triage import run as triage_cards


class Route(NamedTuple):
    decision: str
    to: str
    when: str


class Node(NamedTuple):
    name: str
    title: str
    passes: tuple = ('decide',)
    requires: tuple = ()
    consumes: tuple = ()
    produces: tuple = ()
    routes: tuple = ()
    kind: str = 'ai'
    version: str = '1'


NODES = (
    Node('card_triage', 'Card triage', consumes=('studio/cards.json', 'studio/evidence.json'), produces=('nodes/card_triage/verdicts.json',),
         routes=(Route('confirm', 'plan_orderer', 'the evidence holds: the card goes on to the plan'),
                 Route('doubt', 'probe', 'the evidence does not settle it: a probe does, before the person sees the card'),
                 Route('reject', 'library_feedback', 'the evidence contradicts the card: it is set aside and its rule is told'),
                 Route('rules only', 'plan_orderer', 'no assistant decided: the card goes on as the engines wrote it'))),
    Node('ideal_planner', 'Ideal planner', passes=('plan', 'critique'), consumes=('target-architecture.json', 'plan.json', 'studio/'),
         produces=('ideal/plan.json',),
         routes=(Route('accept', 'plan_orderer', 'every view planned on evidence, no question left: the ideal goes on to the plan'),
                 Route('ask', 'inbox', 'the ideal leaves questions: they wait for the person in the Decisions inbox'),
                 Route('rules only', 'plan_orderer', "not planned: the rules' target stands"))),
    Node('pipeline_gap_planner', 'Pipeline gap planner', passes=('plan', 'critique'), consumes=('studio/pipeline.json',),
         produces=('nodes/pipeline_gap_planner/plan.json',),
         routes=(Route('plan', 'plan_orderer', 'the gap is closed by a step, which goes on to the plan'),
                 Route('ask', 'inbox', 'closing the gap is a choice for the person'),
                 Route('not a gap', 'library_feedback', 'the pipeline rule does not fit here: its rule is told'),
                 Route('rules only', 'plan_orderer', "no assistant decided: the rules' gap stands"))),
    Node('plan_orderer', 'Plan orderer', passes=('plan', 'critique'), requires=('card_triage', 'ideal_planner', 'pipeline_gap_planner'),
         consumes=('plan.json',), produces=('nodes/plan_orderer/order.json',),
         routes=(Route('reorder', 'plan', 'a better order and grouping of the steps, every prerequisite kept'),
                 Route('keep', 'plan', "the rules' order is already right"),
                 Route('ask', 'inbox', 'the order depends on a choice for the person'),
                 Route('rules only', 'plan', "no assistant decided: the rules' order stands"))),
    Node('fix_reviewer', 'Fix reviewer', requires=('plan_orderer',), consumes=('waves/wave-N/wave.json', 'waves/wave-N/*.patch'),
         produces=('nodes/fix_reviewer/review.json',),
         routes=(Route('accept', 'handover', 'the diff does what the card asks and the checks hold: offered to the person'),
                 Route('retry', 'fix', 'the fix is wrong or incomplete: it is made again'),
                 Route('ask', 'inbox', 'the fix needs a choice from the person'),
                 Route('rules only', 'gates', "no assistant decided: the gates' verdict stands"))),
)

NODE_RUNNERS = {'card_triage': triage_cards, 'ideal_planner': plan_ideal, 'pipeline_gap_planner': plan_pipeline_gaps,
                'plan_orderer': order_plan, 'fix_reviewer': review_fix}

# Where the work leaves the AI nodes, in the person's language.
SINKS = {'plan': ('The plan', 'الخطة'), 'probe': ('A probe', 'فحص يحسمها'), 'library_feedback': ("The library's feedback", 'ملاحظات للمكتبة'),
         'inbox': ('The Decisions inbox', 'صندوق القرارات'), 'handover': ('Offered to the person', 'تُعرض على الشخص'),
         'fix': ('Fixed again', 'يُصلَح من جديد'), 'gates': ("The gates' verdict", 'حكم البوابات')}
TITLES_AR = {'card_triage': 'فرز البطاقات', 'ideal_planner': 'مخطِّط المثالي', 'pipeline_gap_planner': 'مخطِّط فجوات خط المعالجة',
             'plan_orderer': 'مرتّب الخطة', 'fix_reviewer': 'مراجع الإصلاح'}


BY_NAME = {each.name: each for each in NODES}


def node(name):
    return BY_NAME[name]


def run(report, names=None, launcher=None, adapters=None, project=None, lang='en', fresh=False, say=None, **inputs):
    """Run the named AI nodes (all by default) in order; a node with nothing to read is left out of the result."""
    records = {}
    for each in NODES:
        if names and each.name not in names: continue
        runner = NODE_RUNNERS.get(each.name)
        if runner is None: continue
        result = runner(each, report, launcher=launcher, adapters=adapters, project=project, lang=lang, fresh=fresh, say=say,
                        **inputs)
        if result is not None: records[each.name] = result
    return records

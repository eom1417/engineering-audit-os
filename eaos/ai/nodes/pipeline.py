"""The AI nodes declared in their order, each with its router's branches, and the run of the named ones."""
from typing import NamedTuple

from . import fix_reviewer, pipeline_gap_planner, plan_orderer, visual_reviewer
from .ideal_planner import run as plan_ideal
from .runner import by_rules_and_answer
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
    Node('visual_reviewer', 'Visual reviewer', consumes=('live/screens.json', 'live/screens/screenshots/*.png'),
         produces=('nodes/visual_reviewer/findings.json',),
         routes=(Route('cards', 'plan', 'the picture shows what a person would notice: each finding becomes a design card'),
                 Route('clean', 'plan', 'the picture shows nothing to change'),
                 Route('rules only', 'plan', "no assistant looked: only the axe and Lighthouse numbers stand"))),
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

NODE_RUNNERS = {'card_triage': triage_cards, 'ideal_planner': plan_ideal,
                **{module.__name__.rsplit('.', 1)[-1]: by_rules_and_answer(module)
                   for module in (visual_reviewer, pipeline_gap_planner, plan_orderer, fix_reviewer)}}

# Where the work leaves the AI nodes, in the person's language.
SINKS = {'plan': ('The plan', 'الخطة'), 'probe': ('A probe', 'فحص يحسمها'), 'library_feedback': ("The library's feedback", 'ملاحظات للمكتبة'),
         'inbox': ('The Decisions inbox', 'صندوق القرارات'), 'handover': ('Offered to the person', 'تُعرض على الشخص'),
         'fix': ('Fixed again', 'يُصلَح من جديد'), 'gates': ("The gates' verdict", 'حكم البوابات')}
TITLES_AR = {'card_triage': 'فرز البطاقات', 'visual_reviewer': 'المراجع البصري', 'ideal_planner': 'مخطِّط المثالي', 'pipeline_gap_planner': 'مخطِّط فجوات خط المعالجة',
             'plan_orderer': 'مرتّب الخطة', 'fix_reviewer': 'مراجع الإصلاح'}


BY_NAME = {each.name: each for each in NODES}


def run(report, names=None, **options):
    """Run the named AI nodes (all by default) in order; a node with nothing to read is left out of the result. The
    options go to each node as they are: its settings (runner.RUN_OPTIONS) and its inputs."""
    records = {}
    for each in NODES:
        if names and each.name not in names: continue
        runner = NODE_RUNNERS.get(each.name)
        if runner is None: continue
        result = runner(each, report, **options)
        if result is not None: records[each.name] = result
    return records


def summary(records):
    """{node: what it decided}: its state, how (the assistant or the rules), its routes and what it dropped."""
    return {name: {'state': r['state'], 'method': r['method'], 'model': r['model'], 'cached': r['cached'],
                   'routes': {x['decision']: len(x['subjects']) for x in r['routes']}, 'dropped': len(r['dropped'])}
            for name, r in records.items()}

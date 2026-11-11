"""The AI nodes declared in their order, each with its router's branches, and the run of the named ones."""
from typing import NamedTuple

from . import fix_reviewer, plan_orderer
from ...assistant.analysis.runner import by_rules_and_answer
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
    Node('card_triage', 'Card triage', consumes=('plan.json',), produces=('nodes/card_triage/verdicts.json',),
         routes=(Route('confirm', 'plan_orderer', 'the evidence holds: the card goes on to the plan'),
                 Route('doubt', 'probe',
                       'the evidence does not settle it: a probe does, before the person sees the card'),
                 Route('reject', 'library_feedback',
                       'the evidence contradicts the card: it is set aside and its rule is told'),
                 Route('rules only', 'plan_orderer',
                       'no assistant decided: the card goes on as the engines wrote it'))),
    Node('plan_orderer', 'Plan orderer', passes=('plan', 'critique'), requires=('card_triage',),
         consumes=('plan.json',), produces=('nodes/plan_orderer/order.json',),
         routes=(Route('reorder', 'plan', 'a better order and grouping of the steps, every prerequisite kept'),
                 Route('keep', 'plan', "the rules' order is already right"),
                 Route('ask', 'inbox', 'the order depends on a choice for the person'),
                 Route('rules only', 'plan', "no assistant decided: the rules' order stands"))),
    Node('fix_reviewer', 'Fix reviewer', requires=('plan_orderer',),
         consumes=('waves/wave-N/wave.json', 'waves/wave-N/*.patch'),
         produces=('nodes/fix_reviewer/review.json',),
         routes=(Route('accept', 'handover',
                       'the diff does what the card asks and the checks hold: offered to the person'),
                 Route('retry', 'fix', 'the fix is wrong or incomplete: it is made again'),
                 Route('ask', 'inbox', 'the fix needs a choice from the person'),
                 Route('rules only', 'gates', "no assistant decided: the gates' verdict stands"))),
)

NODE_RUNNERS = {'card_triage': triage_cards,
                **{module.__name__.rsplit('.', 1)[-1]: by_rules_and_answer(module)
                   for module in (plan_orderer, fix_reviewer)}}

# Where the work leaves the AI nodes, in the person's language.
SINKS = {'plan': ('The plan', 'الخطة'), 'probe': ('A probe', 'فحص يحسمها'),
         'library_feedback': ("The library's feedback", 'ملاحظات للمكتبة'),
         'inbox': ('The Decisions inbox', 'صندوق القرارات'), 'handover': ('Offered to the person', 'تُعرض على الشخص'),
         'fix': ('Fixed again', 'يُصلَح من جديد'), 'gates': ("The gates' verdict", 'حكم البوابات')}
TITLES_AR = {'card_triage': 'فرز البطاقات',
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

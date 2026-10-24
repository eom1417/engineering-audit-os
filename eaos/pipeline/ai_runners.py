"""The runners of the stages an assistant does (eaos/pipeline/runners.py has the others): the kinds of users, the
semantic reading, the AI nodes (the ideal plan, the triage, the plan's order, the pictures' review, the pipeline's gaps),
the Studio's proposals and the translation. Without its assistant, or with one lost midway, a stage is a recorded
absence (SkipStage) and the rules' result stands."""
from .stages import SkipStage


NO_ASSISTANT = 'no assistant was installed or allowed for this check, so the rules stand alone'


def _absent(provider):
    """SkipStage for an AI stage without its assistant: the reason the provider carries (eaos/ai/readiness.py
    NoAssistant: the person said no, the assistant is not signed in, ...), else nobody allowed one."""
    code = getattr(provider, 'code', None)
    return SkipStage(provider.reason, code=code) if code else SkipStage(NO_ASSISTANT, code='no_provider')


def _lost(context, problem, code):
    """SkipStage for an AI stage whose assistant failed midway: asked for one word again, an assistant that is no
    longer ready gives its own reason (signed out during the check, its limit reached); else `problem` and `code`."""
    name = (getattr(context.provider, 'config', None) or {}).get('assistant')
    if name:
        from ..ai import readiness
        try: found = readiness.probe(name, fresh=True)
        except Exception: found = {'ready': True}
        if not found['ready']:
            return SkipStage(f"during the check {found['name']} stopped answering ({found['code']}): {problem}"[:300], code=found['code'],
                             lost={'assistant': name, 'resets': found.get('resets'), 'code': found['code']})
    return SkipStage(problem, code=code)


def roles(context):
    """The kinds of users the app has, read from its code by the assistant (eaos/live/roles.py): the app is opened as each."""
    if not context.provider: raise _absent(context.provider)
    from ..core.process import Stuck
    from ..live.roles import find
    try: kinds = find(context.target, context.out, context.provider)
    except Stuck as problem: raise _lost(context, str(problem), 'ai_stuck') from None
    except Exception as problem:                       # the assistant never decides the fate of the check
        raise _lost(context, f"the kinds of users could not be read ({type(problem).__name__}: {problem})"[:300], 'ai_failed') from None
    return {'kinds': len(kinds)}


def semantic(context):
    if not context.provider:
        raise _absent(context.provider)
    from ..core.process import Stuck
    from ..ai.semantic import run
    from ..report.views import refresh
    try: result = run(context.target, context.out, context.provider, language=context.language)
    except Stuck as problem:
        raise _lost(context, str(problem), 'ai_stuck') from None
    except Exception as problem:                       # the assistant never decides the fate of the check
        raise _lost(context, f'the assistant\'s reading could not be used ({type(problem).__name__}: {problem})'[:300],
                    'ai_failed') from None
    refresh(context.out, context.language)
    return {'hypotheses': result['claims'], 'questions': result['questions'], 'calls': result['calls']}


def _node(context, name):
    """Run one AI node of eaos/ai/nodes inside the check, with its cache and evidence check, as long as the assistant
    works; return its record and what the live map reports. Without an assistant, stuck or on a failure the rules'
    result stands."""
    if not context.provider:
        raise _absent(context.provider)
    from ..ai.nodes import core, run
    record = run(context.out, names=[name], project=str(context.target), lang=context.language,
                 adapters=_adapters_of(context), assistants=context.get('assistants')).get(name)
    if record is None:
        raise SkipStage('there was nothing for the assistant to decide', code='not_applicable')
    if record['method'] != 'model':
        raise _lost(context, record['why'], 'ai_stuck' if record['why'] == core.WORDS['stuck'] else 'ai_failed')
    return record, {'dropped': len(record['dropped']), 'calls': 0 if record['cached'] else record['calls'],
                    'assistant': record['assistant'], 'model': record['model'], **_partly(context, record.get('batches'))}


def _partly(context, batches):
    """A node whose assistant answered only some of its batches (its limit reached midway, a batch that failed): the
    rules decided the rest, so the stage says so and the check is PARTIAL; running the stage again asks only those."""
    if not batches: return {}
    answered = batches['asked'] - batches['failed']
    lost = _lost(context, f"the assistant answered {answered} of {batches['asked']} batches; the rules decided the rest "
                          f"({batches['why']})", 'ai_partial')
    who = (getattr(context.provider, 'config', None) or {}).get('assistant')
    return {'assistant_lost': {**(lost.lost or {'assistant': who, 'resets': None}), 'why': str(lost)[:300],
                               'answered': answered, 'asked': batches['asked']}}


def _adapters_of(context):
    """Only the assistant the person chose for the check, when they chose one; else None (any installed)."""
    chosen = (getattr(context.provider, 'config', None) or {}).get('assistant')
    if not chosen: return None
    from ..ai.headless import installed
    return {key: adapter for key, adapter in installed().items() if key == chosen}


def ideal(context):
    """The ideal planner node (eaos/ai/nodes/ideal_planner.py) before the target is final: plan, critique and the
    evidence check; the reconcile stage turns its decisions into the target, and the rules' target stands without it."""
    record, detail = _node(context, 'ideal_planner')
    return {'elements': record['decisions'][0]['detail']['elements'], **detail}


def triage(context):
    """The card triage node (eaos/ai/nodes/triage.py): each open card confirmed, doubted or rejected on its own
    evidence, a doubted one judged again on all its facts, with why in the person's words; the cards stage then applies
    the verdicts once (eaos/analysis/card_review.py apply_verdicts) before anything ranks, plans or reports."""
    record, detail = _node(context, 'card_triage')
    return {**{row['decision']: len(row['subjects']) for row in record['routes']}, **detail}


def order(context):
    """The plan orderer node (eaos/ai/nodes/plan_orderer.py): the order and grouping of the plan's cards, every
    prerequisite kept; the steps stage writes it into the plan."""
    record, detail = _node(context, 'plan_orderer')
    return {'decision': record['decisions'][0]['decision'], **detail}


def visual(context):
    """The visual reviewer node (eaos/ai/nodes/visual_reviewer.py): the assistant opens each picture of the app's
    screens, and only those, and names what a person would notice there; the cards stage makes each a design card."""
    record, detail = _node(context, 'visual_reviewer')
    return {**{row['decision']: len(row['subjects']) for row in record['routes']}, **detail}


def pipeline_gaps(context):
    """The pipeline-gap planner node (eaos/ai/nodes/pipeline_gap_planner.py): how each broken pipeline rule is
    closed; the plan orderer reads its steps."""
    record, detail = _node(context, 'pipeline_gap_planner')
    return {**{row['decision']: len(row['subjects']) for row in record['routes']}, **detail}


def proposals(context):
    """The Studio's records of this check so far: what the triage, the ideal and the pipeline-gap planner read."""
    if not context.provider:
        raise _absent(context.provider)
    from ..core.workspace import write
    from .live_app import studio
    result = studio(context)
    write(context.out / 'proposals.json', result)
    return {'sections': len(result['written']), 'errors': len(result['errors'])}


def translate(context):
    """Every document in both languages (eaos/core/bilingual.py)."""
    if not context.provider: raise _absent(context.provider)
    from ..core.bilingual import translate as both
    return both(context.out, context.provider)

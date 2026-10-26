"""The runs that ask the person's assistant themselves rather than handing it EAOS's tools (eaos/interfaces/studio_actions/runs.py
PLANNERS): the planner of the ideal (eaos/ai/ideal/planner.py) and the AI nodes (eaos/ai/nodes/). Their steps are
the run's events, stop cancels them, and the Studio's data is published again when they end."""
import threading

from ...core.project.runs import TERMINAL
from ...core.project import state as project_state


def plan_ideal(manager, run):
    """Re-plan the ideal of the latest check with the run's assistant (or the first one available): its steps are the
    run's events, stop kills it, and a failure leaves the rules' target in place. The Studio's data is published again
    from the ledger, so every page shows the new ideal."""
    from ...journeys import guided
    from ...ai.ideal import planner as ideal
    from ...journeys.fix.selection import studio_folder
    studio = studio_folder(manager.project)
    report = studio.parent if studio else None
    if report is None or not (report / 'target-architecture.json').is_file():
        return manager._fail(run, 'there is no check to plan from yet', {'en': 'Run the check first, then re-plan the ideal.',
                                                                         'ar': 'شغّل الفحص أولًا، ثم أعد تخطيط المثالي.'})
    wanted = manager.store.load(run).get('assistant')
    adapters = {wanted: manager.adapters[wanted]} if wanted in manager.adapters else manager.adapters
    cancel = manager.cancels[run] = threading.Event()
    say = lambda en, ar: manager.store.append(run, 'step', {'en': en, 'ar': ar}, {'tool': 'replan_ideal'})
    try:
        result = ideal.plan(report, project=manager.project, lang=manager.lang, adapters=adapters, cancel=cancel,
                            started=lambda pid: manager.store.update(run, pid=pid), say=say)
    finally:
        manager.cancels.pop(run, None)
        manager.store.update(run, pid=None)
    if manager.store.load(run).get('state') in TERMINAL: return
    words = result['message']
    if result['state'] != 'planned':
        return manager._fail(run, words['ar' if manager.lang == 'ar' else 'en'],
                             {'en': 'The rules\' target stays in place. Press Retry, or log in to Claude Code or Codex first.',
                              'ar': 'يبقى هدف القواعد مكانه. اضغط «أعد»، أو سجّل الدخول في Claude Code أو Codex أولًا.'})
    try: guided.publish(project_state.load(manager.project), manager.lang)
    except Exception as problem:
        say(f'The Studio data could not be refreshed: {type(problem).__name__}', f'ما قدرت أحدّث بيانات الاستوديو: {type(problem).__name__}')
    payload = {**manager._outcome(run, answer=words['ar' if manager.lang == 'ar' else 'en']),
               'ideal': {'elements': result['elements'], 'dropped': len(result['dropped']), 'share': result['share'],
                         'departures': len(result['departures']), 'questions': len(result['open_questions']),
                         'assistant': result['assistant'], 'model': result['model']}}
    manager.store.append(run, 'result', {'en': f"The ideal is planned: {result['elements']} elements, each with its evidence",
                                         'ar': f"تم تخطيط المثالي: {result['elements']} عنصرًا، كل واحد بدليله"}, payload)
    manager.set_state(run, 'done', result=payload)

def run_nodes(manager, run):
    """Run the AI nodes on the latest check with the run's assistant: each node's steps are the
    run's events, the last batch of fixes is the fix reviewer's input, and the Studio's data is published again so the
    pipeline map, the cards and the inbox show the decisions. Without an assistant every node decides by the rules."""
    from ...journeys import guided
    from ...ai import nodes
    from ...journeys.fix.selection import studio_folder
    studio = studio_folder(manager.project)
    report = studio.parent if studio else None
    if report is None or not (report / 'plan.json').is_file():
        return manager._fail(run, 'there is no check for the AI nodes to read yet', {'en': 'Run the check first, then the AI nodes.',
                                                                                     'ar': 'شغّل الفحص أولًا، ثم عُقد الذكاء.'})
    record = manager.store.load(run)
    inputs = record.get('inputs') or {}
    names = _node_names(inputs)
    wanted = record.get('assistant')
    adapters = {wanted: manager.adapters[wanted]} if wanted in manager.adapters else manager.adapters
    wave = _last_wave(manager.project)
    cancel = manager.cancels[run] = threading.Event()
    say = lambda en, ar: manager.store.append(run, 'step', {'en': en, 'ar': ar}, {'tool': 'run_nodes'})
    try:
        records = nodes.run(report, names=names, adapters=adapters, project=manager.project, lang=manager.lang, fresh=bool(inputs.get('fresh')),
                            say=say, cancel=cancel, started=lambda pid: manager.store.update(run, pid=pid), wave=wave)
    finally:
        manager.cancels.pop(run, None)
        manager.store.update(run, pid=None)
    if manager.store.load(run).get('state') in TERMINAL: return
    try: guided.publish(project_state.load(manager.project), manager.lang)
    except Exception as problem:
        say(f'The Studio data could not be refreshed: {type(problem).__name__}', f'ما قدرت أحدّث بيانات الاستوديو: {type(problem).__name__}')
    summary = nodes.summary(records)
    by_model = sum(r['method'] == 'model' for r in records.values())
    payload = {**manager._outcome(run, answer=None), 'nodes': summary}
    manager.store.append(run, 'result', {'en': f'{len(records)} AI nodes decided ({by_model} by your assistant, the rest by the rules only)',
                                         'ar': f'قرّرت {len(records)} عُقد ذكاء ({by_model} بمساعدك، والباقي بالقواعد فقط)'}, payload)
    manager.set_state(run, 'done', result=payload)


def _node_names(inputs):
    """The AI nodes a run asks for, else every one but the ideal planner (a run of its own)."""
    from ...ai import nodes
    return inputs.get('nodes') or [n.name for n in nodes.NODES if n.name != 'ideal_planner']


def _last_wave(project):
    """The folder of the last batch of fixes, the fix reviewer's input; None when there is none."""
    try:
        state = project_state.load(project)
        return project_state.runtime_of(state) / 'waves' / f"wave-{len(state['waves'])}" if state.get('waves') else None
    except Exception:
        return None

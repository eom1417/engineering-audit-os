"""The run that asks the person's assistant itself rather than handing it EAOS's tools: the AI nodes (eaos/ai/nodes/).
Their steps are the run's events, stop cancels them, and the check's data is published again when they end."""
import threading

from ...core.project.runs import TERMINAL
from ...core.project import state as project_state


def run_nodes(manager, run):
    """Run the AI nodes on the latest check with the run's assistant: each node's steps are the
    run's events, the last batch of fixes is the fix reviewer's input, and the Studio's data is published again so the
    pipeline map, the cards and the inbox show the decisions. Without an assistant every node decides by the rules."""
    from ...ai import nodes
    from ...journeys.fix.selection import studio_folder
    studio = studio_folder(manager.project)
    report = studio.parent if studio else None
    if report is None or not (report / 'plan.json').is_file():
        return manager._fail(run, 'there is no check for the AI nodes to read yet',
                             {'en': 'Run the check first, then the AI nodes.',
                              'ar': 'شغّل الفحص أولًا، ثم عُقد الذكاء.'})
    record = manager.store.load(run)
    inputs = record.get('inputs') or {}
    names = _node_names(inputs)
    wave = _last_wave(manager.project)
    records, say = _working(manager, run, 'run_nodes', lambda adapters, cancel, say, started: nodes.run(
        report, names=names, adapters=adapters, project=manager.project, lang=manager.lang,
        fresh=bool(inputs.get('fresh')), say=say, cancel=cancel, started=started, wave=wave))
    if records is None: return
    _publish(manager, say)
    summary = nodes.summary(records)
    by_model = sum(r['method'] == 'model' for r in records.values())
    payload = {**manager._outcome(run, answer=None), 'nodes': summary}
    manager.store.append(run, 'result',
                         {'en': f'{len(records)} AI nodes decided ({by_model} by your assistant, '
                                'the rest by the rules only)',
                          'ar': f'قرّرت {len(records)} عُقد ذكاء '
                                f'({by_model} بمساعدك، والباقي بالقواعد فقط)'}, payload)
    manager.set_state(run, 'done', result=payload)


def _working(manager, run, tool, work):
    """(what `work(adapters, cancel, say, started)` gave, say), the run's assistant (or every one) asked, its stop and
    its process kept while it works; (None, say) when the run ended meanwhile (stopped)."""
    wanted = manager.store.load(run).get('assistant')
    adapters = {wanted: manager.adapters[wanted]} if wanted in manager.adapters else manager.adapters
    cancel = manager.cancels[run] = threading.Event()
    say = lambda en, ar: manager.store.append(run, 'step', {'en': en, 'ar': ar}, {'tool': tool})
    try: result = work(adapters, cancel, say, lambda pid: manager.store.update(run, pid=pid))
    finally:
        manager.cancels.pop(run, None)
        manager.store.update(run, pid=None)
    return (None if manager.store.load(run).get('state') in TERMINAL else result), say


def _publish(manager, say):
    """The Studio's data published again; said, never raised, when it cannot be."""
    from ...journeys import guided
    try: guided.publish(project_state.load(manager.project), manager.lang)
    except Exception as problem:
        say(f'The Studio data could not be refreshed: {type(problem).__name__}',
            f'ما قدرت أحدّث بيانات الاستوديو: {type(problem).__name__}')


def _node_names(inputs):
    """The AI nodes a run asks for, else every one."""
    from ...ai import nodes
    return inputs.get('nodes') or [n.name for n in nodes.NODES]


def _last_wave(project):
    """The folder of the last batch of fixes, the fix reviewer's input; None when there is none."""
    try:
        state = project_state.load(project)
        return project_state.runtime_of(state) / 'waves' / f"wave-{len(state['waves'])}" if state.get('waves') else None
    except Exception:
        return None

"""The assistants a Fix run starts beside its own in speed mode, one run each for a lane of its batch (eaos/journeys/lanes.py).

When the run's assistant opens its batch for several assistants, fix_start answers the lanes it leaves to others
(`helpers`), and the run manager (runs.py) starts a Fix run for each at once, beside the first one: the same assistant,
the cards of its lane, the prompt that fixes them and hands nothing over (prompts.LANE). The rest is a run's like any
other: its live words, its stop, going on with another assistant when it stops midway. When a helper run ends, whatever
the way, its lane is released: the cards it did not try go to the first assistant, at the end. When the first run ends
before them (stopped, failed), its helpers are stopped.
"""
import threading

from ...journeys import check_choices, guided, lanes
from ...pipeline.schedule import assistants
from ...journeys.waves import plan
from ...core.store import TERMINAL, now


def speed(project, cards):
    """A Fix preview's speed mode: {on: kept for this project, as the check's; assistants: as many as this computer holds
    now; lanes: how many the selected cards split into, the cards that share a file together}."""
    state = guided.load(project) or {}
    most = assistants('speed').count
    try: tasks = {task['id']: task for task in plan(guided.report_of(state))['tasks']}
    except (KeyError, OSError, ValueError): tasks = {}
    chosen = [tasks[card['id']] for card in cards if card['id'] in tasks]
    return {'on': check_choices.kept(state)['mode'] == 'speed', 'assistants': most, 'lanes': len(lanes.deal(chosen, most)) if chosen else 1}


def speed_of(project, body):
    """{assistants} a new Fix run fixes its batch with, in speed mode as its preview set it (`body` inputs.speed), as
    many as this computer holds now; {} for one. The person's choice is kept for the project, as the check's speed mode."""
    chosen, state = (body.get('inputs') or {}).get('speed'), guided.load(project)
    if isinstance(chosen, bool) and state and check_choices.keep(state, mode='speed' if chosen else 'normal'): guided.save(state)
    most = assistants('speed').count if chosen else 1
    return {'assistants': most} if most > 1 else {}


def after(manager, run, state):
    """Start the helpers of `run` once fix_start answered lanes for them (`state`: its assistant's stream read so far;
    the answer comes from fix_start, or from `wait` on its job), once."""
    seen, state['looked'] = state.get('looked', 0), len(state['eaos_results'])      # each answer looked at once
    payload = next((payload for _, payload in state['eaos_results'][seen:] if isinstance(payload, dict) and payload.get('helpers')), None)
    if not payload: return
    record = manager.store.load(run)
    if record.get('helpers') is not None: return              # a turn after the one that started them
    asked = payload['helpers']
    made = {f'{run}-{lane}': lane for lane in range(1, len(asked) + 1)}
    manager.store.update(run, helpers=sorted(made))
    with lanes.changing(manager.project) as project: project['open_wave']['helpers'].update(made)
    details = {card['id']: card for card in record.get('cards_detail') or []}
    for child, lane in made.items():
        cards = asked[lane - 1]
        label = {'en': f"{record['label']['en']}: assistant {lane + 1}", 'ar': f"{record['label']['ar']}: المساعد {lane + 1}"}
        manager.store.save({**{key: record.get(key) for key in ('action', 'verb', 'assistant', 'owner_answers', 'context')},
                            'id': child, 'label': label, 'cards': cards, 'cards_detail': [details.get(card, {'id': card}) for card in cards],
                            'mode': 'assistant', 'lane': lane, 'parent': run, 'state': 'running', 'attempt': 1, 'created': now(),
                            'queued_at': now(), 'started': now(), 'read': False}, new=True)
        manager.store.append(child, 'action', label, {'action': 'fix', 'by': 'person', 'arguments': {'cards': cards, 'lane': lane}})
        threading.Thread(target=manager._start, args=(child,), daemon=True).start()
    manager.store.append(run, 'step', {'en': f'{len(made)} more assistants fix the other cards at the same time, each its own files',
                                       'ar': f'{len(made)} مساعدين ثانيين يصلحون باقي البطاقات بنفس الوقت، كل واحد ملفاته'},
                         {'tool': None, 'helpers': sorted(made)})


def ended(manager, record):
    """A run ended: a helper's lane is released (what it did not try goes to the first assistant), and a first run ending
    stops the helpers still at work."""
    if record.get('lane'):
        with lanes.changing(manager.project) as project:
            wave = project.get('open_wave') or {}
            if record['id'] in (wave.get('helpers') or {}): lanes.release(wave, record['lane'])
    for child in record.get('helpers') or []:
        if manager.store.load(child).get('state') not in TERMINAL: manager.stop(child)

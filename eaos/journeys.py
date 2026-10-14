"""The journeys of one engine, declared as data (eaos/data/journeys.json): check and fix, build from a plan, extend the
project. Each is the same machinery in another order. This module picks the person's journey from their state, judges
each of its steps (done, and the state of the flow that draws it on the live map, eaos/progress), and draws a build's
own flow from the state, so the journey strip, the live map and the stage panel show a build as they show a check.
"""
import json
import time
from datetime import datetime
from pathlib import Path

from . import progress
from .progress.flow import Stage

DATA = Path(__file__).resolve().parent / 'data' / 'journeys.json'
BUILD = 'build'                 # the flow a build draws (draw_build)


def declared():
    return json.loads(DATA.read_text(encoding='utf-8'))['journeys']


def steps(name):
    return declared()[name]['steps']


def which(state):
    """The journey of this state: a build until its acceptance check is done, an extension until the check after it,
    else check and fix."""
    from . import guided
    if state.get('mode') == 'build' and not (_built(state) and guided.scan_done(state)): return 'build'
    return 'extend' if state.get('extend') and not _rechecked(state) else 'check'


def flows(state):
    """The flows the journey of this state draws, the check first."""
    return list(dict.fromkeys(['check'] + [s['flow'] for s in steps(which(state)) if s['flow']]))


def folder(state, flow):
    """The folder a flow writes its progress under: the report for the check, the runtime for the others."""
    from . import guided
    return guided.report_of(state) if flow == 'check' else guided.runtime_of(state)


def journey(state, now=None):
    """The journey's steps for the live map: [{id, title, later, flow, page, essential, journey, done, state}], `state` being
    the judged state of the step's flow (none, running, stalled, interrupted, done; eaos/progress/liveness.py). A step
    is done by its own check, and only once every earlier essential step is done and not running again; a step whose
    check cannot be read is not done."""
    name, rows, clear = which(state), [], True
    for step in steps(name):
        judged = _judged(state, step['flow'], now) if step['flow'] else 'none'
        try: finished = clear and bool(DONE[name][step['id']](state))
        except Exception: finished = False
        if step['essential']: clear = finished and judged not in ('running', 'stalled')
        rows.append({**step, 'journey': {'id': name, 'title': declared()[name]['title']}, 'done': finished, 'state': judged})
    return rows


def _judged(state, flow, now):
    where = folder(state, flow)
    folded = progress.fold(progress.read(where, flow))
    return progress.judge(folded, progress.heard_at(progress.path_for(where, flow)), time.time() if now is None else now,
                          progress.alive(folded))


# ---------------------------------------------------------------- whether each step is done

def _blueprint(state):
    from . import guided
    return guided.outputs(state) / 'blueprint'


def _read(path):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


def _built(state):
    """Every milestone of the blueprint is delivered."""
    plan = _read(_blueprint(state) / 'plan.json')
    return bool(plan) and {m['id'] for m in plan['milestones']} <= {r['milestone'] for r in state.get('built') or []}


def _extension(state):
    """{card key: the commit that holds it in the branch EAOS works on, or None} of the extension's cards."""
    from . import branches
    from .ledger import walk
    held = walk(state['project'], branches.ref(state))[0]
    return {k: held.get(k) for k in state['extend'].get('keys') or []}


def _feature_built(state):
    cards = _extension(state)
    return bool(cards) and all(cards.values())


def _rechecked(state):
    """The extension is in the branch, and a check began after its last commit."""
    from . import guided
    cards = _extension(state)
    if not cards or not all(cards.values()): return False
    landed = max(int(guided._git(state['project'], 'show', '-s', '--format=%ct', sha).stdout.strip() or 0) for sha in cards.values())
    began = (_read(guided.report_of(state) / 'run-manifest.json') or {}).get('started_at')
    return bool(began) and datetime.fromisoformat(began).timestamp() >= landed


def _check(name):
    from . import guided
    return lambda state: getattr(guided, f'{name}_done')(state)


DONE = {'check': {step: _check(step) for step in ('scan', 'ready', 'safety', 'fix')},
        'build': {'plan': lambda s: (_blueprint(s) / 'SOURCE.md').is_file(),
                  'spec': lambda s: (s.get('blueprint') or {}).get('spec_ok'),
                  'blueprint': lambda s: (s.get('blueprint') or {}).get('designed'),
                  'build': _built, 'accept': _check('scan')},
        'extend': {'feature': lambda s: bool(s.get('extend')), 'ready': _check('ready'), 'safety': _check('safety'),
                   'build': _feature_built, 'recheck': _rechecked}}


# ---------------------------------------------------------------- the build, on the live map

def draw_build(state):
    """The build's progress as the flow `build`, drawn again from the state after each of its steps: a stage per
    milestone, a step per card (kept, or set aside with why). A build lives across many calls of the assistant, so no
    process holds it: it reads as running until its last milestone is delivered, then it ends."""
    from . import guided
    plan = _read(_blueprint(state) / 'plan.json')
    if not plan: return None
    runtime = guided.runtime_of(state)
    progress.path_for(runtime, BUILD).unlink(missing_ok=True)     # a drawing, not a run: none of them goes to the history
    log = progress.ProgressLog(runtime, BUILD, pulse=False, sampler=None, alive_every=None)
    stages = [Stage(m['id'], requires=(previous['id'],) if previous else (),
                    title={'ar': m.get('name_ar') or m['name'], 'en': m['name']})
              for previous, m in zip([None] + plan['milestones'], plan['milestones'])]
    records = {r['milestone']: r for r in state.get('built') or []}
    if state.get('open_build'): records.setdefault(state['open_build']['milestone'], state['open_build'])
    began = min((r['began'] for r in records.values() if r.get('began')), default=None)
    log.started(stages, [s.name for s in stages], {}, steps={}, process=False, at=began)
    for milestone in plan['milestones']:
        if milestone['id'] in records: _draw_milestone(log, milestone, records[milestone['id']])
    if _built(state): log.finish('COMPLETE')
    else: log.close()
    return progress.path_for(runtime, BUILD)


def _draw_milestone(log, milestone, record):
    log.stage_started(milestone['id'], at=record.get('began'))
    step, cards = log.stepper(milestone['id']), milestone['tasks']
    for done, card in enumerate(cards, 1):
        if card in record['kept']: step(card, done, len(cards), 'ok', seconds=0)
        elif card in record['skipped']: step(card, done, len(cards), 'skipped', reason=record['skipped'][card])
    if record.get('branch'):
        log.ended({'stage': milestone['id'], 'status': 'ok', 'reason': f"delivered as {record['branch']}", 'seconds': None,
                   'necessity': 'required', 'artifacts': [record['branch']]}, **({'at': record['ended']} if record.get('ended') else {}))

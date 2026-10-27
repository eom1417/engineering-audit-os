"""The one model of the experience report (M10.8): EXPERIENCE.md, the Studio and the MCP tool all read `story(report)`.

It reads the records the experience run wrote under <report>/experience/ (NOTES: scenario.json, data.json,
journeys/<persona>--<goal>.json (a retry after support, <stem>--again.json, is the goal's kept journey), run.json, replays.json, tickets.json, difficulties.json) and only arranges them:

    story(report)     {version, ran, personas: [{id, name, role, about, goals: [goal in run order]}], difficulties:
                      {ranked, rejected}, time: [{goal, persona, status, seconds, calls}], seconds, calls, tickets,
                      replays: {summary, red}, not_covered, missing: [the record files that are not there]}
    summary(story)    the same without the steps, for an assistant to read in one answer

A goal: {name, persona, wanted, status: reached|stuck|stopped|blocked|not_run, why, seconds, calls, steps: [{action,
target (the control's name), value, why, landed, picture (relative to the report, or None), error}], friction}. A file
that is missing or unreadable is named in `missing`; the story is still told from the rest.
"""
import json
from pathlib import Path

FOLDER = 'experience'
RECORDS = ('scenario.json', 'data.json', 'run.json', 'replays.json', 'tickets.json', 'difficulties.json')
JOURNEYS = 'journeys'
VERDICTS = {'confirm': 0, 'doubt': 1}
SEVERITY = {'high': 0, 'medium': 1, 'low': 2}


def _load(path):
    try: body = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None
    return body if isinstance(body, dict) else None


def _journeys(folder):
    """{goal: (stem, journey)}: each goal's kept journey, its retry after support over its first try; the judge's
    second attempt is evidence, not the goal's journey."""
    journeys = {}
    for path in sorted(folder.glob('*.json')):
        body = _load(path)
        if not body or not body.get('goal') or body.get('attempt') == 'second': continue
        if body.get('attempt') == 'again' or body['goal'] not in journeys: journeys[body['goal']] = (path.stem, body)
    return journeys


def _records(folder):
    """({file name: its record}, [the files missing]); journeys/ counts as missing when it holds no journey."""
    found = {name: _load(folder / name) for name in RECORDS}
    journeys = _journeys(folder / JOURNEYS)
    missing = [name for name, body in found.items() if body is None] + ([JOURNEYS + '/'] if not journeys else [])
    return found, journeys, missing


def _picture(stem, name, journey=None):
    """The picture of a step, relative to the report: experience/journeys/<the journey's pictures_dir, else stem>/<file>."""
    if not name: return None
    return str(name) if '/' in str(name) else f"{FOLDER}/{JOURNEYS}/{(journey or {}).get('pictures_dir') or stem}/{name}"


def _target(target):
    if isinstance(target, dict): return target.get('name') or target.get('role')
    return target


def _step(stem, step, journey=None):
    return {'action': step.get('action'), 'target': _target(step.get('target')), 'value': step.get('value'),
            'why': step.get('why'), 'landed': step.get('landed'), 'picture': _picture(stem, step.get('picture'), journey),
            'error': step.get('error')}


def _status(ran, journey):
    if ran.get('status'): return ran['status']
    if not journey: return 'not_run'
    return 'reached' if journey.get('reached') else 'stopped' if journey.get('stopped') else 'stuck'


def _why(ran, journey):
    return ran.get('why') or (None if journey.get('reached') else journey.get('stuck'))


def _goal(name, ran, journeys):
    """One goal from its row of run.json (`ran`, may be {}) and its journey (may be missing)."""
    stem, journey = journeys.get(name, (None, None))
    status, journey = _status(ran, journey), journey or {}
    return {'name': name, 'persona': ran.get('persona') or journey.get('persona') or name.split('.', 1)[0],
            'wanted': journey.get('wanted'), 'status': status, 'why': _why(ran, journey),
            'seconds': ran.get('seconds', journey.get('seconds')), 'calls': ran.get('calls', journey.get('calls')),
            'steps': [_step(stem, s, journey) for s in journey.get('steps') or []],
            'friction': journey.get('friction') or ran.get('friction') or []}


def _goals(run, journeys):
    """Every goal in run order (run.json), then the journeys run.json does not name, by name."""
    rows = [g for g in (run or {}).get('goals') or [] if isinstance(g, dict) and g.get('name')]
    named = {g['name'] for g in rows}
    return [_goal(g['name'], g, journeys) for g in rows] + [_goal(n, {}, journeys) for n in sorted(journeys) if n not in named]


def _cast(scenario, goals):
    """The scenario's personas in its order; a persona only the run names is added after."""
    cast = [p for p in (scenario or {}).get('personas') or [] if isinstance(p, dict) and p.get('id')]
    known = {p['id'] for p in cast}
    return cast + [{'id': pid} for pid in dict.fromkeys(g['persona'] for g in goals) if pid not in known]


def _personas(scenario, goals):
    """Each persona of the cast with its goals."""
    return [{'id': p['id'], 'name': p.get('name') or p['id'], 'role': p.get('role'), 'about': p.get('about'),
             'goals': [g for g in goals if g['persona'] == p['id']]} for p in _cast(scenario, goals)]


def _rank(difficulty):
    return (VERDICTS.get(difficulty.get('verdict'), 2), SEVERITY.get(difficulty.get('severity'), 3), str(difficulty.get('id')))


def _difficulties(record):
    """{ranked: confirmed first, then by severity high to low, then the doubts; rejected: listed apart}."""
    rows = [d for d in (record or {}).get('difficulties') or [] if isinstance(d, dict)]
    return {'ranked': sorted((d for d in rows if d.get('verdict') != 'reject'), key=_rank),
            'rejected': [d for d in rows if d.get('verdict') == 'reject']}


def _replays(record):
    rows = (record or {}).get('replays') or []
    return {'summary': (record or {}).get('summary') or {}, 'red': [r for r in rows if isinstance(r, dict) and r.get('status') == 'red']}


def story(report):
    """The users' story of this report's experience run (module docstring); every part empty when it did not run."""
    found, journeys, missing = _records(Path(report) / FOLDER)
    run = found['run.json'] or {}
    goals = _goals(run, journeys)
    return {'version': 1, 'ran': bool(goals), 'personas': _personas(found['scenario.json'], goals),
            'difficulties': _difficulties(found['difficulties.json']),
            'time': [{k: g[k] for k in ('name', 'persona', 'status', 'seconds', 'calls')} for g in goals],
            'seconds': run.get('seconds'), 'calls': run.get('calls'),
            'tickets': [t for t in (found['tickets.json'] or {}).get('tickets') or [] if isinstance(t, dict)],
            'replays': _replays(found['replays.json']),
            'not_covered': (found['data.json'] or {}).get('not_covered') or [], 'missing': missing}


def summary(told):
    """The story without the steps and friction notes: what an assistant reads in one answer."""
    personas = [{**p, 'goals': [{k: v for k, v in g.items() if k not in ('steps', 'friction')} | {'steps': len(g['steps']),
                                 'friction': len(g['friction'])} for g in p['goals']]} for p in told['personas']]
    return {**told, 'personas': personas}

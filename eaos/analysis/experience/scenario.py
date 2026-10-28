"""The scenario planner (M10.1): who uses the app and for what, written as data before any simulated user acts.

From what the check already knows (the features of features.json, the kinds of users of roles.json, the pages of
live/screens.json and how they were opened, live/sign-in.json), the assistant names the personas, each one's goals and
the hand-offs between them (the user asks, the admin approves, the user goes on). Its answer is never trusted as it
comes: `checked` repairs it by rules (ids, references, roles, cycles, counts) and says in `dropped` what it set aside and
why, so the actors (eaos/live/experience/cast.py) can play the goals in `order`. Without an assistant, or when its answer
holds nothing usable, the plan is made by rules alone: one persona per kind of user, one goal per main feature.

    <report>/experience/scenario.json   {"version": 1, "personas": [...], "handoffs": [...], "dropped": [...], "source"}
"""
import json
import re
from pathlib import Path
from ...core.system.files import read_json

VERSION = 1
LIMIT = {'personas': 6, 'goals': 5, 'features': 30, 'roles': 10, 'pages': 40, 'surfaces': 6, 'text': 300}
VISITOR = 'visitor'
SLUG = re.compile(r'[^a-z0-9]+')
_TEXT = {'type': 'string'}
GOAL = {'type': 'object', 'required': ['id', 'goal', 'start', 'done_when', 'waits_for'],
        'properties': {'id': _TEXT, 'goal': _TEXT, 'start': _TEXT, 'done_when': _TEXT,
                       'waits_for': {'type': 'array', 'items': _TEXT}, 'makes': {'type': ['string', 'null']}}}
PERSONA = {'type': 'object', 'required': ['id', 'role', 'name', 'about', 'goals'],
           'properties': {'id': _TEXT, 'role': _TEXT, 'name': _TEXT, 'about': _TEXT,
                          'goals': {'type': 'array', 'maxItems': LIMIT['goals'], 'items': GOAL}}}
HANDOFF = {'type': 'object', 'required': ['from', 'event', 'to'], 'properties': {'from': _TEXT, 'event': _TEXT, 'to': _TEXT}}
SCHEMA = {'type': 'object', 'required': ['personas', 'handoffs'],
          'properties': {'personas': {'type': 'array', 'minItems': 1, 'maxItems': LIMIT['personas'], 'items': PERSONA},
                         'handoffs': {'type': 'array', 'items': HANDOFF}}}
TASK = '''GOAL
You are the scenario planner of EAOS, an engineering audit. Simulated users will soon use this running app the way its
real users would. Plan who they are and what each one comes to do, so that together they walk through the app's main
work, including the moments where one person's step waits on another's.

WHAT YOU ARE GIVEN
`features`: the app's features read from its code, each with its name, a description, the pages or addresses that
expose it (`surfaces`), the tables it writes and whether it is critical. `roles`: the kinds of users the code has, each
with its id and its own pages. `pages`: the pages the check opened on the running app. `sign_in`: whether a sign-in was
needed and how the pages were opened.

WHAT TO RETURN
One JSON object with `personas` and `handoffs`, following the schema below.
A persona is one person: `id` a short lowercase word (buyer, admin), `role` the id of one of `roles` or "visitor" for
someone not signed in, `name` a plain first name, `about` one sentence on who they are and why they use the app.
Each persona has one to five `goals`: `id` a short lowercase word, `goal` what the person wants in one plain sentence,
`start` the page they begin on (one of `pages` or a feature's surface, else "/"), `done_when` what they see on the
screen when it worked, `waits_for` the goals (written "<persona>.<goal>") that must be done first, and `makes` a short
name of what finishing it makes happen for someone else (order-placed), or null.
A persona with a role starts signed in as that role (the check's own user): never make its goals wait for a visitor's
sign-up, and wait on a goal of its own only when it needs what that goal made.
A hand-off is one person's finished goal that lets another go on: `from` and `to` are goals written "<persona>.<goal>",
`event` is the `makes` of the `from` goal. The user asks, the admin approves, the user goes on: that is two hand-offs.

A GOOD ANSWER
Two to six personas covering the roles that matter and the critical features first. Goals a real person would have, in
their words, each reachable from the given pages. A hand-off only where the app really makes one person wait on
another (an approval, an assignment, a reply), never a circle.

DO NOT
Invent a role, a page or a feature that is not given. Make a goal wait on itself, or plan a step that needs real money,
a real message sent to a real person, or anything outside the app.'''


def _short(text, limit=LIMIT['text']):
    return str(text or '').strip()[:limit]


def _name(value):
    """A role's name in English: roles.json may give {"en", "ar"}."""
    return _short(value.get('en') if isinstance(value, dict) else value, 80)


def _slug(text):
    return SLUG.sub('-', str(text or '').lower()).strip('-')[:40]


def _roles(report):
    """The kinds of users of roles.json, each {id, name, pages}."""
    rows = (read_json(Path(report) / 'roles.json', {}) or {}).get('roles') or []
    return [{'id': row['id'], 'name': _name(row.get('name')) or row['id'], 'pages': (row.get('pages') or [])[:LIMIT['pages']]}
            for row in rows[:LIMIT['roles']] if isinstance(row, dict) and row.get('id')]


def _features(report):
    """The features of features.json, the critical ones first, each cut short."""
    rows = [f for f in (read_json(Path(report) / 'features.json', {}) or {}).get('features') or [] if isinstance(f, dict) and f.get('name')]
    rows.sort(key=lambda f: not f.get('critical'))
    return [{'name': f['name'], 'description': _short(f.get('description')), 'surfaces': (f.get('surfaces') or [])[:LIMIT['surfaces']],
             'writes': (f.get('writes') or [])[:LIMIT['surfaces']], 'critical': bool(f.get('critical'))}
            for f in rows[:LIMIT['features']]]


def _pages(report):
    """The page addresses live/screens.json holds, each once."""
    screens = read_json(Path(report) / 'live/screens.json', {}) or {}
    paths = [row.get('path') for row in screens.get('pages') or [] if isinstance(row, dict)]
    return list(dict.fromkeys(p for p in paths if isinstance(p, str)))[:LIMIT['pages']]


def brief(report):
    """What the planner reads, bounded: the features, the kinds of users, the pages and how they were opened."""
    sign_in = read_json(Path(report) / 'live/sign-in.json', {}) or {}
    return {'features': _features(report), 'roles': _roles(report), 'pages': _pages(report),
            'sign_in': {key: sign_in[key] for key in ('needed', 'how') if key in sign_in}}


def plan(report, provider=None):
    """Ask the assistant once (deep) for the scenario, repair it (checked) and write <report>/experience/scenario.json;
    by rules alone (rules) without an assistant or when its answer holds no persona. The scenario."""
    given = brief(report)
    roles = [role['id'] for role in given['roles']]
    scenario = checked(_asked(report, provider, given), roles) if provider else {'personas': []}
    if scenario['personas']: scenario['source'] = 'assistant'
    else:
        refused = scenario.get('dropped') or []
        scenario = checked(rules(given), roles)
        scenario.update(dropped=refused + scenario['dropped'], source='rules')
    out = Path(report) / 'experience'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'scenario.json').write_text(json.dumps(scenario, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return scenario


def _asked(report, provider, given):
    """The assistant's answer to TASK over the brief, as the adapters return it or wrapped in `result`."""
    messages = [{'role': 'system', 'content': TASK + '\n\nSCHEMA\n' + json.dumps(SCHEMA)},
                {'role': 'user', 'content': json.dumps(given, ensure_ascii=False)}]
    answer = provider.complete(messages, deep=True, stage='experience_scenario', reads=str(report))[0]
    return (answer.get('result') or answer) if isinstance(answer, dict) else {}


def rules(given):
    """The scenario by rules alone: one persona per kind of user (or one visitor), and each main feature a goal of the
    kind of user whose pages expose it, else of the first persona; a persona with no feature looks around its pages."""
    people = given['roles'] or [{'id': VISITOR, 'name': 'Visitor', 'pages': []}]
    personas = [{'id': role['id'], 'role': role['id'] if given['roles'] else VISITOR, 'name': role['name'],
                 'about': f"Uses the app as {role['name']}.", 'goals': []} for role in people[:LIMIT['personas']]]
    for feature in _main(given['features']):
        owner = next((p for p, role in zip(personas, people) if set(role['pages']) & set(feature['surfaces'])), personas[0])
        owner['goals'].append(_goal(feature['name'], f"Use {feature['name']}: {feature['description']}", _start(feature['surfaces'])))
    for persona, role in zip(personas, people):
        if not persona['goals']: persona['goals'].append(_goal('look-around', 'Open my pages and see that they work.', _start(role['pages'])))
    return {'personas': personas, 'handoffs': []}


def _main(features):
    """The critical features, else the first ones, LIMIT goals at most."""
    return ([f for f in features if f['critical']] or features)[:LIMIT['goals']]


def _goal(name, goal, start):
    return {'id': name, 'goal': goal, 'start': start, 'done_when': 'The page shows the result without an error.', 'waits_for': [], 'makes': None}


def _start(paths):
    """The first address among `paths`, else the home page."""
    return next((p for p in paths if isinstance(p, str) and p.startswith('/')), '/')


def _rows(value, kind=dict):
    """The items of `value` of type `kind`; none when it is not a list."""
    return [item for item in value if isinstance(item, kind)] if isinstance(value, list) else []


def checked(scenario, roles):
    """The scenario repaired by rules: slug ids each once, roles known (else 'visitor'), at most LIMIT personas and goals,
    every reference to an existing goal, each hand-off also a wait, no cycle; what was set aside in `dropped`, each
    {what, why}. `roles`: the role ids of roles.json."""
    scenario, dropped = scenario if isinstance(scenario, dict) else {}, []
    personas = _personas(_rows(scenario.get('personas')), set(roles), dropped)
    goals = {f"{p['id']}.{g['id']}": g for p in personas for g in p['goals']}
    for name, goal in goals.items(): goal['waits_for'] = _references(name, goal['waits_for'], goals, dropped)
    handoffs = _handoffs(_rows(scenario.get('handoffs')), goals, dropped)
    _signed_in_first(personas, goals, dropped)
    _acyclic(goals, dropped)
    handoffs = [h for h in handoffs if h['from'] in goals[h['to']]['waits_for']]
    return {'version': VERSION, 'personas': personas, 'handoffs': handoffs, 'dropped': dropped}


def _personas(rows, roles, dropped):
    """The personas repaired (_persona), LIMIT at most; the ones over it noted."""
    if len(rows) > LIMIT['personas']: dropped.append({'what': f"{len(rows) - LIMIT['personas']} personas", 'why': 'more than the limit'})
    taken = set()
    found = [_persona(row, roles, taken, dropped) for row in rows[:LIMIT['personas']]]
    return [persona for persona in found if persona]


def _unique(text, taken):
    """`text` as a slug not yet in `taken` (a number added when it is), now taken; None when no slug remains."""
    found = base = _slug(text)
    if not base: return None
    number = 1
    while found in taken:
        number += 1
        found = f'{base}-{number}'
    taken.add(found)
    return found


def _persona(row, roles, taken, dropped):
    """One persona repaired: its id, a known role, at most LIMIT goals; None (and why) when it has no id or no goal."""
    pid = _unique(row.get('id') or row.get('name'), taken)
    if not pid:
        dropped.append({'what': 'a persona', 'why': 'it has no id or name'})
        return None
    role = row.get('role')
    if role not in roles and role != VISITOR:
        dropped.append({'what': f'{pid}: role {role!r}', 'why': 'not a role of the app, played as a visitor'})
        role = VISITOR
    goals = _goals(pid, _rows(row.get('goals')), dropped)
    if not goals:
        dropped.append({'what': f'persona {pid}', 'why': 'it has no goal'})
        return None
    return {'id': pid, 'role': role, 'name': _short(row.get('name'), 80) or pid, 'about': _short(row.get('about')), 'goals': goals}


def _goals(pid, items, dropped):
    """The goals of persona `pid` repaired (_goal_of), LIMIT at most; the others noted."""
    goals, own = [], set()
    for item in items:
        goal = _goal_of(item, own) if len(goals) < LIMIT['goals'] else None
        if goal: goals.append(goal)
        else: dropped.append({'what': f"{pid}: goal {item.get('id')!r}", 'why': 'no id or more than the limit'})
    return goals


def _goal_of(item, own):
    """One goal repaired: a slug id unique in its persona, its start an address, its waits a list of names."""
    gid = _unique(item.get('id') or item.get('goal'), own)
    if not gid: return None
    return {'id': gid, 'goal': _short(item.get('goal')) or gid, 'start': _start([item.get('start')]),
            'done_when': _short(item.get('done_when')), 'waits_for': _rows(item.get('waits_for'), str),
            'makes': _slug(item.get('makes')) or None}


def _references(name, waits, goals, dropped):
    """The goals `name` waits for that exist, each once, never itself; why the others were set aside."""
    kept = []
    for wait in waits:
        if wait in goals and wait != name and wait not in kept: kept.append(wait)
        else: dropped.append({'what': f'{name} waits for {wait}', 'why': 'not another goal of the scenario'})
    return kept


def _handoffs(rows, goals, dropped):
    """The hand-offs between two existing goals, each once, the receiving goal made to wait for the giving one."""
    kept, seen = [], set()
    for row in rows:
        giver, taker = row.get('from'), row.get('to')
        if {giver, taker} - set(goals) or giver == taker or (giver, taker) in seen:
            dropped.append({'what': f'hand-off {giver} -> {taker}', 'why': 'not between two other goals of the scenario, or twice'})
            continue
        seen.add((giver, taker))
        kept.append({'from': giver, 'event': _slug(row.get('event')) or goals[giver]['makes'] or giver.split('.', 1)[1], 'to': taker})
        if giver not in goals[taker]['waits_for']: goals[taker]['waits_for'].append(giver)
    return kept


def _signed_in_first(personas, goals, dropped):
    """No goal of a signed-in persona waits for a visitor's goal: it starts signed in as its role (the check's own
    user), so a stranger's sign-up gates nothing (flask-microblog, M10.10: one failed sign-up left 9 of 11 goals
    blocked)."""
    visitors = {p['id'] for p in personas if p.get('role') == 'visitor'}
    for name, goal in goals.items():
        if name.split('.', 1)[0] in visitors: continue
        for wait in [w for w in goal['waits_for'] if w.split('.', 1)[0] in visitors]:
            goal['waits_for'].remove(wait)
            dropped.append({'what': f'{name} waits for {wait}', 'why': 'a signed-in persona starts signed in: a visitor gates nothing'})


def _acyclic(goals, dropped):
    """Every wait that closes a circle removed (the edge found last in a depth-first walk), and noted."""
    state = {}

    def visit(name):
        state[name] = 'open'
        for wait in list(goals[name]['waits_for']):
            if state.get(wait) == 'open':
                goals[name]['waits_for'].remove(wait)
                dropped.append({'what': f'{name} waits for {wait}', 'why': 'it closes a circle of waits'})
            elif wait not in state: visit(wait)
        state[name] = 'done'
    for name in goals:
        if name not in state: visit(name)


def order(scenario):
    """The goals' names ("<persona>.<goal>") in an order where each comes after every goal it waits for, otherwise in
    the scenario's own order (the order M10.5 plays them in)."""
    waits = {f"{p['id']}.{g['id']}": g.get('waits_for') or [] for p in scenario.get('personas') or [] for g in p['goals']}
    out, seen = [], set()

    def visit(name):
        seen.add(name)
        for wait in waits[name]:
            if wait in waits and wait not in seen: visit(wait)
        out.append(name)
    for name in waits:
        if name not in seen: visit(name)
    return out

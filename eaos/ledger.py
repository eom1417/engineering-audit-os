"""The record of the work (ledger.json beside state.json): every card of the plan, by a key that survives a new check,
and what happened to it. The report for people reads its progress from here, and only from here.

Why a key: a check numbers its cards TASK-001, TASK-002… in its own order, so after the next check TASK-008 is another
problem. A card's key is its observation's uid (decision.observation_uid, OBS-…: what was observed and where, not how
the title words it, so a reworded title or another list of tools keeps the key); a card without one (a design card)
is keyed by its kind, its files and its words with the numbers taken out. Two cards alike are told apart by their order. Every commit EAOS makes carries its card's key as a trailer
(`EAOS-Card: <key>`), so what is in the person's branch is read from git itself, whoever merged it and however.

A card's state:
    open        in the plan, not tried yet (or tried and brought back by a later check)
    in_batch    in the batch open now
    on_branch   fixed on a branch that waits for the person's decision: not done yet
    done        in the person's current branch (merged), through an EAOS fix
    skipped     tried and not kept, with the reason: it needs a person's decision
A problem a later check no longer finds, without an EAOS fix, leaves the ledger: it is neither progress nor a card.
A card fixed and merged stays (done), with its commit, after a later check no longer finds it.
`new` marks a card a later check found that the first one did not: the scope grows, and the page says so.
closed = done; total = the cards of the current plan + the done ones it no longer has; percent = closed / total.
"""
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import branches

TRAILER = 'EAOS-Card'
NUMBERS = re.compile(r'\d+')
CLOSED = ('done',)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _git(project, *args):
    return subprocess.run(['git', '-C', str(project), *args], capture_output=True, text=True)


def key(card, ordinal=0):
    uid = (card.get('decision') or {}).get('observation_uid')
    if uid: text = '|'.join([uid] + ([str(ordinal)] if ordinal else []))
    else:
        words = NUMBERS.sub('#', ' '.join((card.get('title') or '').split()).lower())
        text = '|'.join([card.get('pattern') or 'generic', *sorted(card.get('paths') or []), words] + ([str(ordinal)] if ordinal else []))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]


def keys(cards):
    """{card id: key} for a whole plan: alike cards get their order in the plan as part of the key."""
    seen, out = {}, {}
    for card in cards:
        plain = key(card)
        seen[plain] = seen.get(plain, -1) + 1
        out[card['id']] = key(card, seen[plain])
    return out


def path(state):
    return Path(state['workspace']) / f'ledger{branches.suffix(state)}.json'


def load(state):
    try: return json.loads(path(state).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


def _save(state, ledger):
    target = path(state)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(ledger, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    temporary.replace(target)


def _walk(project, ref):
    done = _git(project, 'log', '--format=%H%x00%ae%x00%B%x1e', ref)
    by_key, legacy, reverted, undone = {}, {}, set(), set()
    if done.returncode: return by_key, legacy, undone
    for sha, email, body in _commits(done.stdout):     # newest first: a revert is met before what it reverts
        found = re.findall(rf'^{TRAILER}: ([0-9a-f]{{12}})$', body, re.M)
        if sha in reverted:
            undone.update(found)
            continue
        undoes = re.findall(r'This reverts commit ([0-9a-f]{40})', body)
        if undoes:
            reverted.update(undoes)
            continue
        _record_commit(sha, email, body, found, by_key, legacy)
    return by_key, legacy, undone - set(by_key)


def _commits(log):
    for entry in log.split('\x1e'):
        parts = entry.strip('\n').split('\x00')
        if len(parts) == 3: yield parts


def _record_commit(sha, email, body, found, by_key, legacy):
    for k in found: by_key.setdefault(k, sha)
    if not found and email == 'eaos@localhost' and re.match(r'TASK-\d+: ', body):
        legacy[body.split('\n', 1)[0]] = sha


def _plan(state, report=None):
    """The plan of the check on record: `report`/plan.json (eaos/guided.report_of), by default in the branch's part of
    the outputs folder."""
    if report is None and not state.get('outputs'): return None
    try: return json.loads((Path(report or branches.home(state) / 'technical') / 'plan.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


def _older_keys(project, wave, tasks, ids):
    """{card id: key} for a batch from before keys were kept, read from its commits' subjects ("TASK-008: <words>"): the
    card of this plan with those words (after a new check, TASK-008 may be another problem)."""
    out = {}
    for old_id, title in _batch_subjects(project, wave).items():
        chosen = _card_for(old_id, title, tasks)
        if chosen: out[old_id] = ids[chosen]
    return out


def _batch_subjects(project, wave):
    """{old card id: its title} from the subjects of a batch's commits."""
    tip = wave.get('tip') or wave.get('branch')
    if not (tip and wave.get('base')): return {}
    log = _git(project, 'log', '--format=%s', f"{wave.get('base')}..{tip}")
    if log.returncode: return {}
    return dict(line.split(': ', 1) for line in log.stdout.splitlines() if re.match(r'TASK-\d+: ', line))


def _card_for(old_id, title, tasks):
    alike = [c['id'] for c in tasks if (c.get('title') or '')[:70] == title]
    if old_id in alike: return old_id
    return alike[0] if len(alike) == 1 else None


def _entry(card, k, milestone):
    return {'key': k, 'id': card['id'], 'title': card.get('title') or '', 'pattern': card.get('pattern') or 'generic',
            'milestone': milestone, 'paths': list(card.get('paths') or []), 'state': 'open', 'new': False,
            'batch': None, 'at': None, 'why': '', 'commit': None}


def sync(state, event=None, report=None):
    """The ledger brought up to date with the plan, the batches in the state and the project's git history; saved and
    returned. None while the project has no plan yet. A point is added to the history when what is closed changes,
    or on `event`."""
    plan = _plan(state, report)
    if not plan or not isinstance(plan.get('tasks'), list): return load(state)
    ledger = load(state)
    stamp = f"{state.get('scanned_commit')}@{state.get('scanned')}"
    milestone = {i: m['id'] for m in plan.get('milestones') or [] for i in m.get('tasks') or []}
    ids = keys(plan['tasks'])
    first = ledger is None
    if first:
        ledger = {'schema_version': 1, 'started': _now(), 'plan_stamp': stamp, 'cards': {}, 'history': []}
    cards = ledger['cards']
    _merge_plan(cards, plan['tasks'], ids, milestone, first)
    if ledger.get('plan_stamp') != stamp:
        ledger['plan_stamp'] = stamp
        event = event or 'recheck'
    project = state['project']
    in_branch, legacy, undone = _walk(project, branches.ref(state))
    by_id = {c['id']: c for c in cards.values() if c['id']}
    for wave in state.get('waves') or []:                                    # what each batch did, by key
        _apply_wave(wave, cards, wave.get('keys') or _older_keys(project, wave, plan['tasks'], ids))
    _apply_history(cards, in_branch, undone)
    _apply_legacy(cards, legacy)
    _apply_open_batch(cards, by_id, state.get('open_wave') or {})
    totals = _record_history(ledger, first, event, project, state)
    ledger.update(updated=_now(), commit=_git(project, 'rev-parse', branches.ref(state)).stdout.strip() or None, totals=totals)
    _save(state, ledger)
    return ledger


def _merge_plan(cards, tasks, ids, milestone, first):
    """Every card of the plan into the ledger by its key; a card no longer found and not fixed by EAOS leaves it."""
    for card in cards.values(): card['id'] = None
    for card in tasks:
        k = ids[card['id']]
        if k in cards: _refresh(cards[k], card, milestone)
        else:
            cards[k] = _entry(card, k, milestone.get(card['id']))
            cards[k]['new'] = not first
    for k in [k for k, card in cards.items() if card['id'] is None and card['state'] != 'done']:
        del cards[k]                                                         # no longer found, not fixed by EAOS: gone


def _refresh(entry, card, milestone):
    entry.update(id=card['id'], title=card.get('title') or entry['title'], milestone=milestone.get(card['id']))
    if entry['state'] not in ('done', 'on_branch', 'in_batch', 'skipped', 'open'): entry['state'] = 'open'


def _apply_kept(wave, card):
    if not card or card['state'] in CLOSED: return
    status = wave.get('status')
    if status == 'applied':
        card.update(state='on_branch', batch=wave.get('number'), why='')
    elif status == 'accepted':
        card.update(state='done', batch=wave.get('number'), at=wave.get('merged_at') or card['at'], why='')
    elif card['state'] == 'on_branch' and status in ('undone', 'empty'):
        card.update(state='open', batch=None)


def _apply_wave(wave, cards, known):
    """What a batch did to its cards. One closed without handing anything over (abandoned, superseded) changed nothing:
    its cards stay open, whatever it failed on, and the next batch can pick them (EAOS on itself, 2026-10-13: the 7 module
    splits a gate bug had refused stayed "skipped" after their batch was abandoned, out of every later batch)."""
    if wave.get('status') in CLOSED_UNUSED:
        for card in cards.values():                                       # skipped by it before this rule: open again
            if card['state'] == 'skipped' and card.get('batch') == wave.get('number'): card.update(state='open', batch=None, why='')
        return
    for card_id, reason in (wave.get('failed') or {}).items():
        card = cards.get(known.get(card_id))
        if card and card['state'] in ('open', 'in_batch'):
            card.update(state='skipped', why=str(reason)[:300], batch=wave.get('number'))
    for card_id in wave.get('kept') or []: _apply_kept(wave, cards.get(known.get(card_id)))


CLOSED_UNUSED = ('abandoned', 'superseded')


def _apply_history(cards, in_branch, undone):
    for card in cards.values():
        if card['key'] in undone and card['state'] == 'done':                # its fix was reverted on the branch
            card.update(state='open', commit=None, batch=None, why='its fix was reverted on the branch')
        if card['key'] in in_branch and card['state'] != 'done':
            card.update(state='done', commit=in_branch[card['key']], at=_now(), why='')


def _apply_legacy(cards, legacy):
    for subject, sha in legacy.items():                                     # merged before keys: its old card, by its words
        title = subject.split(': ', 1)[1] if ': ' in subject else subject
        match = next((c for c in cards.values() if c['state'] != 'done' and c['title'][:70] == title and c['id'] is None), None)
        if match: match.update(state='done', commit=sha, at=match['at'] or _now(), why='')
        elif not any(c.get('commit') == sha for c in cards.values()):
            k = 'legacy-' + sha[:6]
            cards[k] = {'key': k, 'id': None, 'title': title, 'pattern': 'generic', 'milestone': None, 'paths': [], 'state': 'done',
                        'new': False, 'batch': None, 'at': _now(), 'why': '', 'commit': sha}


def _apply_open_batch(cards, by_id, open_wave):
    in_batch = open_wave.get('cards') or []
    for card_id in in_batch:
        card = by_id.get(card_id)
        if card and card['state'] in ('open', 'skipped'): card.update(state='in_batch', batch=open_wave.get('number'), why='')
    for card in cards.values():                                              # a batch that closed without it
        if card['state'] == 'in_batch' and card['id'] not in in_batch: card['state'] = 'open'


def _record_history(ledger, first, event, project, state):
    """The totals; a point added to the history when they moved, on the first sync, or on an event."""
    totals = count(ledger)
    history = ledger['history']
    last = history[-1] if history else None
    moved = not last or last['closed'] != totals['closed'] or last['total'] != totals['total']
    if first or event or moved:
        history.append({'at': _now(), 'event': 'baseline' if first else event or 'merged', 'closed': totals['closed'],
                        'total': totals['total'], 'percent': totals['percent'], 'commit': _git(project, 'rev-parse', branches.ref(state)).stdout.strip() or None})
        del history[:-200]
    return totals


def count(ledger):
    cards = list(ledger['cards'].values())
    tally = {s: sum(c['state'] == s for c in cards) for s in ('done', 'resolved', 'on_branch', 'in_batch', 'open', 'skipped')}
    total = len(cards)
    closed = tally['done']
    return {'total': total, 'closed': closed, **tally, 'new': sum(c['new'] for c in cards),
            'percent': round(100 * closed / total, 1) if total else 0.0}


def for_report(ledger):
    """The ledger as the report for people reads it: cards as a list."""
    if not ledger: return None
    return {**{k: v for k, v in ledger.items() if k != 'cards'}, 'cards': list(ledger['cards'].values())}

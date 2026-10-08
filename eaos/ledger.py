"""The record of the work (ledger.json beside state.json): every card of the plan, by a key that survives a new check,
and what happened to it. The report for people reads its progress from here, and only from here.

Why a key: a check numbers its cards TASK-001, TASK-002… in its own order, so after the next check TASK-008 is another
problem. A card's key is its kind, its files and its words with the numbers taken out (line numbers and counts move);
two cards alike in all three are told apart by their order. Every commit EAOS makes carries its card's key as a trailer
(`EAOS-Card: <key>`), so what is in the person's branch is read from git itself, whoever merged it and however.

A card's state:
    open        in the plan, not tried yet (or tried and brought back by a later check)
    in_batch    in the batch open now
    on_branch   fixed on a branch that waits for the person's decision: not done yet
    done        in the person's current branch (merged), through an EAOS fix
    resolved    no longer found by a later check, without an EAOS fix: closed as well
    skipped     tried and not kept, with the reason: it needs a person's decision
`new` marks a card a later check found that the first one did not: the scope grows, and the page says so.
closed = done + resolved; percent = closed / every card ever in scope.
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
CLOSED = ('done', 'resolved')


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _git(project, *args):
    return subprocess.run(['git', '-C', str(project), *args], capture_output=True, text=True)


def key(card, ordinal=0):
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


def merged_keys(project, ref='HEAD'):
    """{key: commit} for every EAOS card commit in the branch `ref`; {subject: commit} for older ones. A commit reverted
    later in the branch (`git revert`, "This reverts commit <sha>") is not there any more, unless its revert was itself
    reverted."""
    return _walk(project, ref)[:2]


def reverted_keys(project, ref='HEAD'):
    """The keys whose EAOS commit is in the branch `ref` but was reverted there, and not fixed again after."""
    return _walk(project, ref)[2]


def _walk(project, ref):
    done = _git(project, 'log', '--format=%H%x00%ae%x00%B%x1e', ref)
    by_key, legacy, reverted, undone = {}, {}, set(), set()
    if done.returncode: return by_key, legacy, undone
    for entry in done.stdout.split('\x1e'):            # newest first: a revert is met before what it reverts
        parts = entry.strip('\n').split('\x00')
        if len(parts) != 3: continue
        sha, email, body = parts
        found = re.findall(rf'^{TRAILER}: ([0-9a-f]{{12}})$', body, re.M)
        if sha in reverted:
            undone.update(found)
            continue
        undoes = re.findall(r'This reverts commit ([0-9a-f]{40})', body)
        if undoes:
            reverted.update(undoes)
            continue
        for k in found: by_key.setdefault(k, sha)
        if not found and email == 'eaos@localhost' and re.match(r'TASK-\d+: ', body):
            legacy[body.split('\n', 1)[0]] = sha
    return by_key, legacy, undone - set(by_key)


def _plan(state, report=None):
    """The plan of the check on record: `report`/plan.json (eaos/guided.report_of), by default in the branch's part of
    the outputs folder."""
    if report is None and not state.get('outputs'): return None
    try: return json.loads((Path(report or branches.home(state) / 'technical') / 'plan.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


def _older_keys(project, wave, tasks, ids):
    """{card id: key} for a batch from before keys were kept, read from its commits' subjects ("TASK-008: <words>"): the
    card of this plan with those words (after a new check, TASK-008 may be another problem)."""
    tip = wave.get('tip') or wave.get('branch')
    log = _git(project, 'log', '--format=%s', f"{wave.get('base')}..{tip}") if tip and wave.get('base') else None
    if not log or log.returncode: return {}
    said = dict(line.split(': ', 1) for line in log.stdout.splitlines() if re.match(r'TASK-\d+: ', line))
    out = {}
    for old_id, title in said.items():
        alike = [c['id'] for c in tasks if (c.get('title') or '')[:70] == title]
        chosen = old_id if old_id in alike else alike[0] if len(alike) == 1 else None
        if chosen: out[old_id] = ids[chosen]
    return out


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
    for card in cards.values(): card['id'] = None
    fresh = ledger.get('plan_stamp') != stamp
    for card in plan['tasks']:
        k = ids[card['id']]
        if k in cards:
            cards[k].update(id=card['id'], title=card.get('title') or cards[k]['title'], milestone=milestone.get(card['id']))
            if fresh and cards[k]['state'] == 'resolved': cards[k]['state'] = 'open'     # it came back
        else:
            cards[k] = _entry(card, k, milestone.get(card['id']))
            cards[k]['new'] = not first
    if fresh:                                                                # a new check: what it no longer finds is closed
        for card in cards.values():
            if card['id'] is None and card['state'] not in CLOSED:
                card.update(state='resolved', at=_now())
        ledger['plan_stamp'] = stamp
        event = event or 'recheck'
    project = state['project']
    in_branch, legacy, undone = _walk(project, branches.ref(state))
    by_id = {c['id']: c for c in cards.values() if c['id']}
    waves = state.get('waves') or []
    for wave in waves:                                                       # what each batch did, by key
        known = wave.get('keys') or _older_keys(project, wave, plan['tasks'], ids)
        for card_id, reason in (wave.get('failed') or {}).items():
            card = cards.get(known.get(card_id))
            if card and card['state'] in ('open', 'in_batch'):
                card.update(state='skipped', why=str(reason)[:300], batch=wave.get('number'))
        for card_id in wave.get('kept') or []:
            card = cards.get(known.get(card_id))
            if not card or card['state'] in CLOSED: continue
            if wave.get('status') == 'applied':
                card.update(state='on_branch', batch=wave.get('number'), why='')
            elif wave.get('status') == 'accepted':
                card.update(state='done', batch=wave.get('number'), at=wave.get('merged_at') or card['at'], why='')
            elif card['state'] == 'on_branch' and wave.get('status') in ('undone', 'empty'):
                card.update(state='open', batch=None)
    for card in cards.values():
        if card['key'] in undone and card['state'] == 'done':                # its fix was reverted on the branch
            card.update(state='open', commit=None, batch=None, why='its fix was reverted on the branch')
        if card['key'] in in_branch and card['state'] != 'done':
            card.update(state='done', commit=in_branch[card['key']], at=_now(), why='')
    for subject, sha in legacy.items():                                     # merged before keys: its old card, by its words
        title = subject.split(': ', 1)[1] if ': ' in subject else subject
        match = next((c for c in cards.values() if c['state'] != 'done' and c['title'][:70] == title and c['id'] is None), None)
        if match: match.update(state='done', commit=sha, at=match['at'] or _now(), why='')
        elif not any(c.get('commit') == sha for c in cards.values()):
            k = 'legacy-' + sha[:6]
            cards[k] = {'key': k, 'id': None, 'title': title, 'pattern': 'generic', 'milestone': None, 'paths': [], 'state': 'done',
                        'new': False, 'batch': None, 'at': _now(), 'why': '', 'commit': sha}
    open_wave = state.get('open_wave') or {}
    for card_id in open_wave.get('cards') or []:
        card = by_id.get(card_id)
        if card and card['state'] in ('open', 'skipped'): card.update(state='in_batch', batch=open_wave.get('number'), why='')
    for card in cards.values():                                              # a batch that closed without it
        if card['state'] == 'in_batch' and card['id'] not in (open_wave.get('cards') or []): card['state'] = 'open'
    totals = count(ledger)
    history = ledger['history']
    last = history[-1] if history else None
    if first or event or not last or last['closed'] != totals['closed'] or last['total'] != totals['total']:
        history.append({'at': _now(), 'event': 'baseline' if first else event or 'merged', 'closed': totals['closed'],
                        'total': totals['total'], 'percent': totals['percent'], 'commit': _git(project, 'rev-parse', branches.ref(state)).stdout.strip() or None})
        del history[:-200]
    ledger.update(updated=_now(), commit=_git(project, 'rev-parse', branches.ref(state)).stdout.strip() or None, totals=totals)
    _save(state, ledger)
    return ledger


def count(ledger):
    cards = list(ledger['cards'].values())
    tally = {s: sum(c['state'] == s for c in cards) for s in ('done', 'resolved', 'on_branch', 'in_batch', 'open', 'skipped')}
    total = len(cards)
    closed = tally['done'] + tally['resolved']
    return {'total': total, 'closed': closed, **tally, 'new': sum(c['new'] for c in cards),
            'percent': round(100 * closed / total, 1) if total else 0.0}


def for_report(ledger):
    """The ledger as the report for people reads it: cards as a list."""
    if not ledger: return None
    return {**{k: v for k, v in ledger.items() if k != 'cards'}, 'cards': list(ledger['cards'].values())}

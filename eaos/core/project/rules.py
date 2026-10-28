"""The person's own rules (M16): every requirement they state, kept in their words with where and when it was said and
its scope, in one record per project (<workspace>/rules.json, eaos/core/project/places.py), never inside the project.

A rule is not forever by default: it holds for the work it was said for (its scope: a card, or a batch of fixes) and
becomes a standing rule of the project only when the person pins it; they unpin or change it at any time. Every change
is in its history (who, when, through which door, why, and what it was). Its guard (eaos/analysis/rules/guards.py)
checks it without an AI remembering it; each break and each hold is counted, so a rule that comes back says so, and the
same requirement said again is the same rule said again, never a second one.

    {'id': 'R1', 'words': ..., 'lang': 'ar', 'said': [{at, door, by, where}], 'scope': {'kind': 'pinned'|'card'|'batch',
     'ref': ...}, 'state': 'active'|'ended', 'guard': None|{...}, 'breaks': [{at, where, places, commit}],
     'held': {at, where}, 'broken': n, 'returns': n, 'history': [{at, what, by, door, why, was}]}
"""
import contextlib
import fcntl
import json
import os
import re
import unicodedata
from pathlib import Path

from .places import workspace
from ..system.clock import now
from ..system.files import read_json

FILE = 'rules.json'
DOORS = ('chat', 'card', 'studio', 'mcp', 'terminal', 'eaos')
SCOPES = ('pinned', 'card', 'batch')
ENDED = ('accepted', 'undone', 'superseded', 'abandoned', 'empty')     # a batch's statuses once its work is over
SAME = 0.75                 # the share of words two sayings have in common to be one requirement said again
MAX_WORDS = 2000            # characters of a rule's words kept
MAX_BREAKS = 50             # breaks kept per rule (the count goes on)


class Kept(str):
    """A project given by its EAOS workspace folder (a check knows that, not the project's own folder)."""


def folder_of(project):
    return Path(project) if isinstance(project, Kept) else workspace(project)


def path(project):
    return folder_of(project) / FILE


def load(project):
    """The project's rules record: {'rules': [...], 'next': the next number, 'context': the files EAOS made for the
    pinned rules, 'hook': {'made': whether EAOS made the hook file}}."""
    record = read_json(path(project)) or {}
    return {**record, 'rules': record.get('rules') or [], 'next': record.get('next') or len(record.get('rules') or []) + 1}


@contextlib.contextmanager
def changing(project):
    """The record, read and written whole under the project's lock: two doors never lose each other's change."""
    folder = folder_of(project)
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / 'rules.lock', 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        record = load(project)
        yield record
        new = folder / f'.rules-{os.urandom(4).hex()}.json'
        new.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        new.replace(folder / FILE)


def find(record, ident):
    rule = next((r for r in record['rules'] if r['id'] == str(ident).upper()), None)
    if rule is None: raise LookupError(f'no rule {ident} here: eaos rules lists them')
    return rule


# ---------------------------------------------------------------- the person's words

def language(text):
    return 'ar' if re.search(r'[؀-ۿ]', text or '') else 'en'


def _plain(text):
    """The words of a saying, compared: case, marks, the forms of one Arabic letter and punctuation aside."""
    text = unicodedata.normalize('NFKD', str(text or '').casefold())
    text = ''.join(ch for ch in text if not unicodedata.combining(ch) and ch != 'ـ')
    for forms, letter in (('أإآ', 'ا'), ('ى', 'ي'), ('ة', 'ه'), ('ؤ', 'و'), ('ئ', 'ي')):
        text = re.sub(f'[{forms}]', letter, text)
    return {word for word in re.findall(r'\w+', text) if len(word) > 1}


def alike(first, second):
    """Whether two sayings are one requirement: SAME or more of their words shared."""
    a, b = _plain(first), _plain(second)
    return bool(a and b) and len(a & b) / len(a | b) >= SAME


def _history(rule, what, by, door, why=None, was=None):  # limits: parameters -- a history entry's own fields, each kept as given
    rule['history'].append({'at': now(), 'what': what, 'by': by, 'door': door,
                            **({'why': str(why)[:500]} if why else {}), **({'was': was} if was is not None else {})})


def _checked(words, door, scope):
    words = ' '.join(str(words or '').split())
    if not words: raise ValueError('the rule has no words: say what must always hold')
    if door not in DOORS: raise ValueError(f'unknown door {door}: one of {", ".join(DOORS)}')
    if scope['kind'] not in SCOPES: raise ValueError(f"unknown scope {scope['kind']}: one of {', '.join(SCOPES)}")
    return words[:MAX_WORDS]


def add(project, words, door, by='person', where=None, scope=None):  # limits: parameters -- a saying's own fields (its words, door, who, where, scope), as every door gives them
    """A rule said: kept in the person's words, with when, where and through which door; its scope the card or batch
    it was said for (`scope`), else pinned when asked. The same requirement said again is the rule it already is: said
    once more, back in scope, never a second rule. (rule, said before: the times it was said before, 0 for a new one)."""
    scope = dict(scope or {'kind': 'batch', 'ref': None})
    words = _checked(words, door, scope)
    saying = {'at': now(), 'door': door, 'by': by, **({'where': str(where)[:200]} if where else {})}
    with changing(project) as record:
        rule = next((r for r in record['rules'] if alike(r['words'], words)), None)
        if rule:
            rule['said'].append(saying)
            if rule['state'] == 'ended' or (scope['kind'] == 'pinned' and rule['scope']['kind'] != 'pinned'):
                was = {'scope': rule['scope'], 'state': rule['state']}
                rule.update(scope=scope, state='active')
                _history(rule, 'said again', by, door, was=was)
            return rule, len(rule['said']) - 1
        rule = {'id': f"R{record['next']}", 'words': words, 'lang': language(words), 'said': [saying], 'scope': scope,
                'state': 'active', 'guard': None, 'breaks': [], 'broken': 0, 'returns': 0, 'held': None, 'history': []}
        _history(rule, 'said', by, door)
        record['next'] += 1
        record['rules'].append(rule)
        return rule, 0


def change(project, ident, by='person', door='terminal', why=None, words=None, scope=None):  # limits: parameters -- what a person changes of a rule, each a keyword of the four doors
    """A rule changed in its words or scope (pinned, unpinned to the work in hand), its history keeping what it was."""
    with changing(project) as record:
        rule = find(record, ident)
        was = {key: rule[key] for key in ('words', 'scope', 'state')}
        if words is not None:
            rule['words'] = _checked(words, door, rule['scope'])
            rule['lang'] = language(rule['words'])
        if scope is not None:
            if scope['kind'] not in SCOPES: raise ValueError(f"unknown scope {scope['kind']}")
            rule['scope'], rule['state'] = dict(scope), 'active'
        what = 'pinned' if scope and scope['kind'] == 'pinned' else 'unpinned' if scope and was['scope']['kind'] == 'pinned' else 'changed'
        _history(rule, what, by, door, why, was)
        return rule


def end(project, ident, by='person', door='terminal', why=None):
    """A rule no longer held: unpinned to nothing, or its work over. Its record and history stay."""
    with changing(project) as record:
        rule = find(record, ident)
        if rule['state'] == 'ended': return rule
        was = {'scope': rule['scope'], 'state': rule['state']}
        rule['state'] = 'ended'
        _history(rule, 'unpinned' if was['scope']['kind'] == 'pinned' else 'ended', by, door, why, was)
        return rule


def guard(project, ident, written, by, door):
    """The rule's guard set (eaos/analysis/rules/guards.py checked it on its examples first), what it was kept."""
    with changing(project) as record:
        rule = find(record, ident)
        was = rule.get('guard')
        rule['guard'] = written
        _history(rule, 'guarded' if written.get('kind') != 'none' else 'unguarded', by, door, written.get('why'), was)
        return rule


# ---------------------------------------------------------------- held or broken

def broke(project, ident, where, places, commit=None):
    """A break recorded (a check, a fix's gate, the hook): its places, and the commit that brought it when known. The
    rule's break count, this one included."""
    with changing(project) as record:
        rule = find(record, ident)
        if rule['breaks'] and rule['breaks'][-1]['where'] == where and rule['breaks'][-1]['places'] == list(places)[:40]:
            return rule['broken']                    # the same check read again (a stage run once more)
        rule['broken'] = rule.get('broken', 0) + 1
        if (rule.get('held') or {}).get('after_break'): rule['returns'] = rule.get('returns', 0) + 1     # it held, and broke again
        if rule.get('held'): rule['held']['after_break'] = False
        rule['breaks'] = (rule['breaks'] + [{'at': now(), 'where': where, 'places': list(places)[:40],
                                             **({'commit': commit} if commit else {})}])[-MAX_BREAKS:]
        return rule['broken']


def held(project, ident, where):
    with changing(project) as record:
        rule = find(record, ident)
        rule['held'] = {'at': now(), 'where': where, 'after_break': bool(rule['breaks'])}


def came_back(rule):
    """The times the rule was broken again after it had held (M16.5: "it came back <n> times")."""
    return rule.get('returns', 0)


# ---------------------------------------------------------------- the scope

def in_scope(rule, state, card=None, batch=None):
    """Whether the rule holds now: pinned, or its card still to land, or its batch not over; with `card` or `batch`,
    whether it holds for that work (a pinned rule holds for all of it)."""
    if rule['state'] != 'active': return False
    kind, ref = rule['scope']['kind'], rule['scope'].get('ref')
    if kind == 'pinned': return True
    if kind == 'card': return _card_open(state, ref) and (card is None or card == ref or _in_batch(state, ref, batch))
    return _batch_open(state, ref) and (batch is None or ref is None or int(ref) == int(batch))


def _waves(state):
    open_wave = (state or {}).get('open_wave')
    return [*((state or {}).get('waves') or []), *([dict(open_wave, status='open')] if open_wave else [])]


def _batch_open(state, number):
    if number is None: return True
    wave = next((w for w in _waves(state) if int(w.get('number') or 0) == int(number)), None)
    return wave is None or wave.get('status') not in ENDED


def _card_open(state, card):
    return not any(w.get('status') == 'accepted' and card in (w.get('kept') or {}) for w in _waves(state))


def _in_batch(state, card, batch):
    return batch is not None and any(int(w.get('number') or 0) == int(batch) and card in (w.get('cards') or []) for w in _waves(state))


def settle(project, state):
    """The rules whose work is over, ended with the reason (a rule left unpinned stops at its scope's end); and the
    rules said for the next batch tied to the batch that opened. The rules ended."""
    ended = []
    with changing(project) as record:
        for rule in record['rules']:
            scope = rule['scope']
            if rule['state'] == 'active' and scope['kind'] == 'batch' and scope.get('ref') is None and (state or {}).get('open_wave'):
                scope['ref'] = state['open_wave']['number']
            if rule['state'] == 'active' and not in_scope(rule, state):
                rule['state'] = 'ended'
                why = f"its card {scope['ref']} landed" if scope['kind'] == 'card' else f"its batch {scope['ref']} is over"
                _history(rule, 'ended', 'eaos', 'eaos', why, {'scope': scope, 'state': 'active'})
                ended.append(rule)
    return ended


def holding(project, state, card=None, batch=None):
    """The rules that hold for this work (all that hold now, without `card` or `batch`)."""
    return [rule for rule in load(project)['rules'] if in_scope(rule, state, card, batch)]


def keep(project, **values):
    """Values of the record itself (where its pinned rules are written), set."""
    with changing(project) as record:
        record.update(values)


def said_on(rule):
    """The day the rule was first said, as the person reads it."""
    return rule['said'][0]['at'][:10]

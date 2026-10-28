"""The person's rules held (M16.3, M16.4): on a whole check every place each rule is broken; on a change only what the
change brought (a match it added, a test it made fail), so a rule already broken elsewhere never refuses a sound
change, and the card that names every place is what fixes the rest.
"""
import contextlib
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from . import guards
from ...core.project import rules as registry
from ...core.system.files import read_json

RECORD = 'rules.json'          # a check's rules, beside its report (the rules stage writes it)


def read(out):
    return read_json(Path(out) / RECORD) or {}


def row(rule, result):
    """One rule's result as the check, the gate and the views read it."""
    return {'id': rule['id'], 'words': rule['words'], 'lang': rule['lang'], 'scope': rule['scope'], 'said_on': registry.said_on(rule),
            'said': len(rule['said']), 'kind': (rule.get('guard') or {}).get('kind'), 'guard': guards.said(rule.get('guard')),
            'status': result['status'], 'places': result['places'], 'found': result['said'], 'seconds': result['seconds'],
            'broken_before': rule.get('broken', 0), 'returns': registry.came_back(rule)}


def in_check(rules, root, found=None):
    """Every rule that holds now, its guard run on the whole code at `root` (a detector's on `found`, when given)."""
    return [row(rule, guards.run(rule.get('guard'), root, None, found)) for rule in rules]


@contextlib.contextmanager
def at_commit(repo, commit):
    """A function giving the code of `repo` at `commit`, checked out apart the first time it is asked for (a guard that
    held needs no past to compare with), and removed at the end."""
    made = {}
    with tempfile.TemporaryDirectory(prefix='eaos-rule-before-') as folder:
        def code():
            if 'where' not in made:
                where = Path(folder) / 'code'
                done = subprocess.run(['git', '-C', str(repo), 'worktree', 'add', '--detach', '--quiet', str(where), commit], capture_output=True, text=True)
                made['where'] = where if not done.returncode else None
            return made['where']
        try:
            yield code
        finally:
            if made.get('where'): subprocess.run(['git', '-C', str(repo), 'worktree', 'remove', '--force', str(made['where'])], capture_output=True)


def _new_places(after, before):
    """The places of `after` that are new: per file, the matches past the count `before` had there (a match moved
    within its file is not new)."""
    had = Counter(place.split(':')[0] for place in before)
    seen, new = Counter(), []
    for place in sorted(after):
        path = place.split(':')[0]
        seen[path] += 1
        if seen[path] > had[path]: new.append(place)
    return new


def _brought(rule, result, paths, before, found):
    """A guard's break kept only for what the change brought: a pattern's matches past those the code had before it, a
    test that passed before it. `before`: the code before the change (a folder, or a callable giving one)."""
    kind = rule['guard']['kind']
    earlier = (before() if callable(before) else before) if kind in ('pattern', 'test') else None
    if earlier is not None:
        was = guards.run(rule['guard'], earlier, paths, found)
        if kind == 'test' and was['status'] == 'broken': result['status'] = 'held'        # it failed before the change too
        if kind == 'pattern': result['places'] = _new_places(result['places'], was['places'])
    if not result['places'] and kind != 'test': result['status'] = 'held'
    return result


def on_change(rules, root, paths, before=None, found=None):  # limits: parameters -- a change's copy, its files, the code before it and the gate's own findings
    """Each rule's result on a change: its guard on the changed `paths` at `root`, against the same guard on the code
    before the change (read only when a guard fails); `found`, the gate's findings for a detector guard (already only
    what the change added). Broken only by what the change brought."""
    results = []
    for rule in rules:
        result = guards.run(rule.get('guard'), root, paths, found)
        if result['status'] == 'broken': result = _brought(rule, result, paths, before, found)
        results.append(row(rule, result))
    return results


def broken(results):
    return [item for item in results if item['status'] == 'broken']


def brief(project, state, card=None, batch=None):
    """The rules that hold for this work, as its assistant reads them: [{id, words, said_on, guard}]."""
    return [{'id': r['id'], 'words': r['words'], 'said_on': registry.said_on(r), 'guard': guards.said(r.get('guard'))}
            for r in registry.holding(project, state, card, batch)]


SAID = {'en': ('it breaks your rule {id}, said on {said_on}: "{words}" at {where}', '; this change brought it back ({returns} time(s) '
              'it came back)', '; pin it so it holds for every change (eaos rules pin {id})'),
        'ar': ('يكسر قاعدتك {id} اللي قلتها في {said_on}: «{words}» عند {where}', '؛ هذا التعديل رجّعها (رجعت تنكسر {returns} مرة)',
               '؛ ثبّتها عشان تنطبق على كل تعديل (eaos rules pin {id})')}


def refusal(broken, lang='en'):
    """The sentence a refused change gives for each rule it breaks: the person's words, when they said them, where, how
    often it came back (this change brought it back once more), and pinning offered when it is not pinned (M16.5)."""
    first, back, pin = SAID['ar' if lang == 'ar' else 'en']
    said = []
    for item in broken:
        values = {**item, 'where': ', '.join(item['places'][:4]), 'returns': item['returns'] + 1}
        text = first.format(**values) + (back.format(**values) if item['broken_before'] else '')
        text += pin.format(**values) if item['scope']['kind'] != 'pinned' else ''
        said.append(text + (f" ({item['found'][:200]})" if item['kind'] == 'test' and lang != 'ar' else ''))
    return said


def record(project, results, where):
    """Each result into the rule's record: a break with its places, a hold; the same break of the same check counted once."""
    for item in results:
        try:
            if item['status'] == 'broken': registry.broke(project, item['id'], where, item['places'])
            elif item['status'] == 'held': registry.held(project, item['id'], where)
        except LookupError:
            continue                     # a rule removed while the check ran


def gate(owner, rules, root, changed, laws):
    """A fix's gate (eaos/journeys/fix/waves/batch.py edit_gates): the person's rules this change breaks, only what it
    brought against the copy just before it (the gate's commit is made), each recorded on its rule, as the refusal's
    sentences. `laws`: what the code laws' gates found the change added, for a detector guard."""
    with at_commit(root, 'HEAD~1') as before:
        results = on_change(rules, root, changed, before, found_of(laws))
    record(owner, results, 'gate')
    return refusal(broken(results))


def as_gate(state, card, root, changed, laws):
    """The gate's problems ({gate, where, what}) of the person's rules that hold for this card (a build's, M16.4)."""
    rules = registry.holding(state['project'], state, card)
    return [{'gate': 'rules', 'where': card or '', 'what': said} for said in gate(state['project'], rules, root, changed, laws)] if rules else []


def found_of(problems):
    """The gates' problems as a detector guard reads them."""
    return [{'detector': p['gate'], 'places': [part.strip() for part in p['where'].split(',') if part.strip()], 'said': p['what']}
            for p in problems]

"""The finish line of a card on what engines report about code: the exact findings it must clear, fixed when the card is
made, each judged by one ruler. On EAOS itself (2026-10-15) one "complexity" card mixed seven kinds of finding, judged
the whole file by whichever engine spoke, and six cards of a batch could not pass whatever the assistant did:
- a branching score (reforge complex_function, lizard ccn, enola) is judged by EAOS's own count
  (facts/code/metrics.py, the one the gates and the code laws use): engines disagree (one function scored 15, 40 and 49), so a
  function EAOS counts within MAX_COMPLEXITY is no target, whatever an engine said; one EAOS does not count (a language
  it does not read) is judged by the engine that reported it;
- a count an engine states exactly (too many parameters, nesting too deep, a function too long) is judged by that engine;
- the size of a file or a class is a split's work (eaos/analysis/planning/cards.py _split_last), never a simplification's target.
A target is followed by its function's name, so moving the function to another file does not clear it: to a file where no
function of that name was reported when the card was made (`also_in`), never to one that had one already. A function with
no name (an arrow function, a lambda: engines call it <anonymous>) is judged in its own file only. A target was judged by
its name across the whole project, and every anonymous function anywhere kept a card standing that no fix of its file
could finish (TASK-131 of a React project, 2026-10-24).
"""
import re

from ...core.contracts.code_laws import MAX_COMPLEXITY

EXACT = {'reforge.codebase.many_parameters': 'too many parameters', 'reforge.codebase.deep_nesting': 'nesting too deep',
         'reforge.codebase.long_function': 'too long'}
SIZE = {'reforge.codebase.large_type', 'reforge.codebase.large_file', 'reforge.codebase.function_proliferation'}
SUFFIX = re.compile(r':(?:arity:\d+|declaration)$')
NAMELESS = ('', 'anonymous', 'lambda', 'default')


def name(symbol):
    """A function's own name, however an engine writes it (path::Class::method:arity:2, Class.method, pkg/mod.func)."""
    return SUFFIX.sub('', symbol or '').split('::')[-1].split('.')[-1]


def nameless(function):
    """A function with no name of its own: an engine's <anonymous> or <lambda>, a default export."""
    return function.strip('<>').lower() in NAMELESS


def targets(facts, sets):
    """What a card on these engine findings must clear: [{'rule', 'path', 'name', 'also_in'|'line'}], one ruler each
    (module docstring): a named function with the other files it was reported in then, a nameless one with its line."""
    counted, places, out = _counted(sets), _reported(sets), {}
    for fact in facts:
        value, where = fact.get('value') or {}, fact.get('location') or {}
        key = (where.get('path'), name(where.get('symbol')))
        if value.get('kind') != 'complexity' or value.get('rule') in SIZE or not key[1]: continue
        branches = counted.get(key)
        rule = _ruler(value, branches)
        if rule != 'branches' or branches > MAX_COMPLEXITY: out[(rule, *key)] = _target(rule, key, where, counted, places)
    return [out[k] for k in sorted(out)]


def _ruler(value, branches):
    """The rule a finding is judged by: its engine's for an exact count or a function EAOS does not count, else EAOS's
    branch count."""
    return _rule(value) if value.get('rule') in EXACT or branches is None else 'branches'


def _target(rule, key, where, counted, places):
    """One target: a nameless function with its line, a named one with the other files it was reported in then."""
    target = {'rule': rule, 'path': key[0], 'name': key[1]}
    if nameless(key[1]): target['line'] = where.get('line') or where.get('start_line')
    elif also := sorted(_files(rule, key[1], counted, places) - {key[0]}): target['also_in'] = also
    return target


def judges(wanted, facts):
    """The engines that state the targets: a card is rechecked by the engine that found it, and a branch count, EAOS's
    own (facts/code/metrics.py), needs none."""
    return sorted({f['value']['engine'] for f in facts for t in wanted if t['rule'] != 'branches' and _rule(f['value']) == t['rule']})


def left(wanted, sets):
    """The targets still standing on the code `sets` were collected from."""
    counted, places = _counted(sets), _reported(sets)
    return [t for t in wanted if _standing(t, counted, places)]


def _standing(target, counted, places):
    """Whether the target is still there: in its own file; a named function moved, in a file it was not in when the card
    was made (a card made before `also_in`: in any file)."""
    rule, path, function = target['rule'], target['path'], target['name']
    over = lambda file: (counted.get((file, function)) or 0) > MAX_COMPLEXITY if rule == 'branches' else (rule, file, function) in places
    if over(path) or nameless(function): return over(path)
    elsewhere = _files(rule, function, counted, places) - {path} - set(target.get('also_in') or ())
    return any(over(file) for file in elsewhere)


def said(target):
    """One target in words: `decide` in eaos/x.py: more than 15 branches."""
    why = (f'more than {MAX_COMPLEXITY} branches' if target['rule'] == 'branches' else
           EXACT.get(target['rule'], f"still reported by {target['rule']}"))
    what = (f"the function with no name at line {target['line']}" if target.get('line') else
            'a function with no name' if nameless(target['name']) else f"`{target['name']}`")
    return f"{what} in {target['path']}: {why}"


def proof(claim):
    """How a card with a finish line is proven done, for the assistant before it starts; None without one."""
    wanted = ((claim.get('probe_spec') or {}).get('specification') or {}).get('targets')
    if not wanted: return None
    return 'Clear exactly these and nothing else in the file counts: ' + '; '.join(map(said, wanted))


def _rule(value):
    """The rule an engine reported under, or the engine when it names none."""
    return value.get('rule') or value.get('engine')


def _counted(sets):
    """EAOS's branch count per (path, function name), the larger of two same-named functions."""
    out = {}
    for fact in (sets.get('metrics') or {}).get('facts') or []:
        value, where = fact.get('value') or {}, fact.get('location') or {}
        if value.get('scope') in ('function', 'method'):
            key = (where.get('path'), name(where.get('symbol')))
            out[key] = max(out.get(key, 0), value.get('branches') or 0)
    return out


def _reported(sets):
    """(rule, path, function name) of every complexity finding an engine reported."""
    return {(_rule(f['value']), (f.get('location') or {}).get('path'), name((f.get('location') or {}).get('symbol')))
            for f in (sets.get('external') or {}).get('facts') or [] if (f.get('value') or {}).get('kind') == 'complexity'}


def _files(rule, function, counted, places):
    """The files where a function of that name is counted (a branch count) or reported by that rule."""
    if rule == 'branches': return {path for path, f in counted if f == function}
    return {path for r, path, f in places if r == rule and f == function}

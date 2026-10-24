"""The finish line of a card on what engines report about code: the exact findings it must clear, fixed when the card is
made, each judged by one ruler. On EAOS itself (2026-10-15) one "complexity" card mixed seven kinds of finding, judged
the whole file by whichever engine spoke, and six cards of a batch could not pass whatever the assistant did:
- a branching score (reforge complex_function, lizard ccn, enola) is judged by EAOS's own count
  (facts/metrics.py, the one the gates and the code laws use): engines disagree (one function scored 15, 40 and 49), so a
  function EAOS counts within MAX_COMPLEXITY is no target, whatever an engine said; one EAOS does not count (a language
  it does not read) is judged by the engine that reported it;
- a count an engine states exactly (too many parameters, nesting too deep, a function too long) is judged by that engine;
- the size of a file or a class is a split's work (eaos/plan.py _split_last), never a simplification's target.
A target is followed by its function's name, so moving the function to another file does not clear it.
"""
import re

from .code_laws import MAX_COMPLEXITY

EXACT = {'reforge.codebase.many_parameters': 'too many parameters', 'reforge.codebase.deep_nesting': 'nesting too deep',
         'reforge.codebase.long_function': 'too long'}
SIZE = {'reforge.codebase.large_type', 'reforge.codebase.large_file', 'reforge.codebase.function_proliferation'}
SUFFIX = re.compile(r':(?:arity:\d+|declaration)$')


def name(symbol):
    """A function's own name, however an engine writes it (path::Class::method:arity:2, Class.method, pkg/mod.func)."""
    return SUFFIX.sub('', symbol or '').split('::')[-1].split('.')[-1]


def targets(facts, sets):
    """What a card on these engine findings must clear: [{'rule', 'path', 'name'}], one ruler each (module docstring)."""
    counted, out = _counted(sets), {}
    for fact in facts:
        value, where = fact.get('value') or {}, fact.get('location') or {}
        key = (where.get('path'), name(where.get('symbol')))
        if value.get('kind') != 'complexity' or value.get('rule') in SIZE or not key[1]: continue
        branches = _branches(counted, *key)
        rule = _rule(value) if value.get('rule') in EXACT or branches is None else 'branches'
        if rule != 'branches' or branches > MAX_COMPLEXITY:
            out[(rule, *key)] = {'rule': rule, 'path': key[0], 'name': key[1]}
    return [out[k] for k in sorted(out)]


def judges(wanted, facts):
    """The engines that state the targets: a card is rechecked by the engine that found it, and a branch count, EAOS's
    own (facts/metrics.py), needs none."""
    return sorted({f['value']['engine'] for f in facts for t in wanted if t['rule'] != 'branches' and _rule(f['value']) == t['rule']})


def left(wanted, sets):
    """The targets still standing on the code `sets` were collected from."""
    counted = _counted(sets)
    reported = {(_rule(f['value']), name((f.get('location') or {}).get('symbol')))
                for f in (sets.get('external') or {}).get('facts') or [] if (f.get('value') or {}).get('kind') == 'complexity'}
    return [t for t in wanted if ((_branches(counted, t['path'], t['name']) or 0) > MAX_COMPLEXITY if t['rule'] == 'branches'
                                  else (t['rule'], t['name']) in reported)]


def said(target):
    """One target in words: `decide` in eaos/x.py: more than 15 branches."""
    why = (f'more than {MAX_COMPLEXITY} branches' if target['rule'] == 'branches' else
           EXACT.get(target['rule'], f"still reported by {target['rule']}"))
    return f"`{target['name']}` in {target['path']}: {why}"


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


def _branches(counted, path, function):
    """A function's count at its path, or, moved, wherever a function of that name is now; None when EAOS counts none."""
    return counted.get((path, function), max((n for (_, f), n in counted.items() if f == function), default=None))

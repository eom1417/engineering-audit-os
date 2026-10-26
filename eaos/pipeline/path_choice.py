"""The paths of a check, declared once: what each looks at, and the stages, engines and cards a choice of them runs.

A check follows one path or several together. Every path runs the spine (the required stages, which are cheap and make
the report, and the assistant's review of the cards); each adds the optional stages it needs, the engines whose
capabilities it looks at (a new engine joins its path by what it finds, not by its name), and keeps the card patterns
it is about. `complete` is all of them.

    resolve(['security', 'look'])  {'paths', 'stages', 'engines', 'patterns'}: the union, closed over what they require

How scalability splits: how easily the code grows is in `code`, how the app holds under load is in `speed`.
"""
from ..core.contracts.check_paths import COMPLETE, PATHS, SPINE
from .loops import switches
from .stages import BY_NAME, ORDER, REQUIRED, STAGES


def _closed(names):
    """`names` and every stage they require, in the declared order."""
    wanted, frontier = set(), list(names)
    while frontier:
        name = frontier.pop()
        if name in wanted: continue
        wanted.add(name)
        frontier += BY_NAME[name].requires
    return [name for name in ORDER if name in wanted]


def resolve(paths):
    """What a check following `paths` runs: {'paths', 'stages' (None: all), 'engines' (None: every installed one, []:
    none asked), 'patterns' (None: all)}. Unknown paths are refused."""
    paths = sorted(set(paths or [COMPLETE]))
    unknown = [p for p in paths if p not in PATHS]
    if unknown: raise ValueError(f"unknown check path: {', '.join(unknown)} (one of {', '.join(PATHS)})")
    # beside `complete`, a path that switches an optional loop on (eaos/pipeline/loops.py) is an option of the full check
    if COMPLETE in paths: return {'paths': [COMPLETE, *_switching(paths)], 'stages': None, 'engines': None, 'patterns': None}
    chosen = [PATHS[p] for p in paths]
    joined = lambda key: sorted({value for path in chosen for value in path.get(key, ())})
    spine = [stage.name for stage in STAGES if stage.necessity == REQUIRED] + list(SPINE)
    return {'paths': paths, 'stages': _closed(spine + joined('stages')), 'engines': _engines(joined('kinds'), joined('engines')),
            'patterns': joined('patterns')}


def _engines(kinds, named):
    """The engines that find any of `kinds`, and those `named`."""
    from ..engines import ADAPTERS
    return sorted({name for name, adapter in ADAPTERS.items() if set(kinds) & {c.kind for c in adapter.capabilities()}} | set(named))


def _switching(paths):
    """The paths of `paths` that switch an optional loop on (eaos/pipeline/loops.py)."""
    return [path for path in paths if path in switches()]

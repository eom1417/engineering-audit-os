"""A size or complexity measure becomes work only with a sign of harm.

A size or branch count is true but rarely worth a fix on its own: a flat switch over three drivers, a protocol
endpoint kept in one file, a constructor of independent `isset` lines. The count is real, the harm is not. So a
function past the limit is a card when it nests deep or its file keeps being fixed; a module past the line limit when
its file keeps being fixed. Otherwise the claim is retained, with the measure and the reason, never a card a batch
spends a fix on.
"""
DEEP = 6            # blocks open at the deepest line, the body counted: five inside, past ESLint's max-depth of four
FIXED_OFTEN = 3     # commits named as fixes that changed the file
HISTORY_ENOUGH = 10  # commits read before a file's fixes say anything (eaos/features/claims/analysis/from_facts.py cochanges)
OWNER = 'eaos'
REASON = ('Measured only: past the size or complexity limit, but no function in it nests {deep} deep and its file was '
          'not fixed {fixed} times in the history read. Kept as a measure, not a fix.')


def _measure(claim):
    """(kind, path, symbol) of a size claim, or None for another claim."""
    render = claim.get('render') or {}
    key, params = render.get('key'), render.get('params') or {}
    if key == 'hotspot': return key, params.get('path'), params.get('symbol')
    if key == 'large_module': return key, params.get('path'), None
    if key == 'engine_cluster' and params.get('kind') == 'complexity': return key, params.get('place'), None
    return None


def _signs(sets):
    """(deepest nesting by (path, symbol) and by path, fix commits by path or None when the history is too short)."""
    by_symbol, by_path = {}, {}
    for fact in (sets.get('metrics') or {}).get('facts') or []:
        value, location = fact.get('value') or {}, fact.get('location') or {}
        if value.get('scope') not in ('function', 'method'): continue
        path, depth = location.get('path'), value.get('max_nesting') or 0
        by_symbol[(path, location.get('symbol'))] = depth
        by_path[path] = max(depth, by_path.get(path, 0))
    return by_symbol, by_path, _fixes(sets.get('history') or {})


def _fixes(history):
    if (history.get('summary') or {}).get('commits_analysed', 0) < HISTORY_ENOUGH: return None
    return {f['location']['path']: f['value'].get('fix_commits', 0) for f in history.get('facts') or []
            if f.get('kind') == 'history_churn'}


def harmed(measure, signs):
    """Whether a size claim's place shows harm: its file fixed often, or (a function's claim) a deep function there.
    A module's split is earned by its history alone: a cohesive long file is no harm."""
    (key, path, symbol), (by_symbol, by_path, fixes) = measure, signs
    if fixes is not None and fixes.get(path, 0) >= FIXED_OFTEN: return True
    if key == 'large_module': return False
    return (by_symbol.get((path, symbol), 0) if symbol else by_path.get(path, 0)) >= DEEP


def mark(rows, sets):
    """Each size claim with no sign of harm retained with its reason (eaos/kernel/contracts/decisions.py, accepted)."""
    signs = _signs(sets)
    for row in rows:
        measure = _measure(row)
        if not measure or not measure[1] or row.get('confidence') == 'REFUTED' or harmed(measure, signs): continue
        row['disposition'] = {'kind': 'accepted', 'owner': OWNER, 'reason': REASON.format(deep=DEEP, fixed=FIXED_OFTEN)}

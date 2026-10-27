"""Old engines still wired in (M13.1, M13.3): code another part replaced that is still called, or that sits behind a
switch fixed to one value, so the dead-code check sees it reached and says nothing.

Switches: ast-grep's records (eaos/rules/ast-grep/rules/flags.yml) of a name fixed to true or false at a module's top
and of every `if` that reads one, alone or negated, read with EAOS's own symbols and call graph (the `syntax` facts).
A switch counts when nothing changes it: no other assignment to it in its file, no module state the domain facts saw
change, and a branch that reads it in its own file or one that imports it by name. The branch it closes is the `if`'s
body (true when the switch reads false) or what follows it (the else, or the rest of its function). A function is
an old engine when every call to it is in a branch a switch closes and no other line of the project names it.

Two engines doing one job: two functions, or two modules, whose names are one name with a marker apart (old, new,
legacy, v1, v2, ...), both in the product, with the same parameters; the old one is the one its marker calls old
(or the one the other calls new, or the lower version), and it is a finding only while something still calls or
imports it. Its history says when it stopped changing and when the other began, when the repository has one.
"""
import re
from pathlib import Path, PurePosixPath

from ...core.contracts.vocabulary import classify
from ...facts.engine_findings import engine_records

# A name says old only by these words; `new`, `next` or `previous` alone are a name's meaning (new_token, previous_seconds),
# so a pair needs one of its names marked old, or both marked by a version (v1 and v2).
OLD = {'old', 'legacy', 'deprecated', 'obsolete', 'classic', 'bak', 'backup'}
NEW = {'new', 'next', 'modern'}
VERSION = re.compile(r'^v(\d+)$')
WORDS = re.compile(r'[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+')
LEAVES = re.compile(r'(?<![\w.])(return|throw|raise)(?!\w)')
EXPORTS = re.compile(r'module\.exports|^\s*export\s*\{|__all__')


def _of(sets, kind, name='syntax'):
    return [f for f in (sets.get(name) or {}).get('facts', []) if f['kind'] == kind]


def _text(root, path, cache):
    if path not in cache:
        try: cache[path] = (Path(root) / path).read_text(encoding='utf-8', errors='replace').split('\n') if root else []
        except OSError: cache[path] = []
    return cache[path]


def _changed(name, path, line, lines):
    """Whether a line of the file other than its declaration assigns the name again."""
    again = re.compile(rf'(?<![\w.]){re.escape(name)}\s*(?:[-+*/|&]?=)(?!=)')
    return any(again.search(text) for number, text in enumerate(lines, 1) if number != line)


def switches(sets, root, cache):
    """{(path, name): {'value', 'line'}}: the switches fixed at a module's top that nothing changes."""
    moving = {(f['location']['path'], f['value'].get('name')) for f in _of(sets, 'mutable_global', 'domain')}
    out = {}
    for fact in engine_records(sets, 'flag_constant'):
        path, captures = fact['location']['path'], fact['value'].get('captures') or {}
        name, line = captures.get('F'), fact['location'].get('line')
        if not name or (path, name) in moving or _changed(name, path, line, _text(root, path, cache)): continue
        out[(path, name)] = {'value': captures.get('V', '').lower() == 'true', 'line': line}
    return out


def _imports(sets):
    """{(importing file, name)}: the names each file imports by name."""
    return {(f['location']['path'], name) for f in _of(sets, 'import_edge') for name in f['value'].get('names') or ()}


def _switch_of(path, name, fixed, imported):
    """(the switch's file, its record) a branch of `path` reads, or (None, None)."""
    if (path, name) in fixed: return path, fixed[(path, name)]
    if (path, name) not in imported: return None, None
    return next(((where, row) for (where, flag), row in fixed.items() if flag == name), (None, None))


def _enclosing_end(sets, path, line):
    """The last line of the innermost function around `line`."""
    around = [f for f in _of(sets, 'symbol') if f['location']['path'] == path and f['location']['start_line'] <= line <= (f['location'].get('end_line') or 0)]
    return min((f['location']['end_line'] for f in around), default=line)


def _sides(fact, switch, sets, lines):
    """(dead lines, live lines) of one branch a switch reads, or None when what it closes is nothing: the body when it
    reads off; else what follows it (its else, or the rest of its function when the body leaves it)."""
    value, line = fact['value'], fact['location']['line']
    body, end = (value.get('spans') or {}).get('BODY') or [line, line], value.get('end_line') or line
    after = [body[1] + 1, end if end > body[1] else _enclosing_end(sets, fact['location']['path'], end)]
    if switch['value'] == (value.get('form') == 'negated'): return body, after          # the body never runs
    if end <= body[1] and not _leaves(lines, body): return None                       # it runs, and what follows too
    return (after, body) if after[0] <= after[1] else None


def closed(sets, root, cache):
    """[{path, switch, switch_path, switch_line, value, dead: [first, last], live: [first, last], line}]: each branch
    a switch closes, and the code that runs in its place."""
    fixed, imported, out = switches(sets, root, cache), _imports(sets), []
    for fact in engine_records(sets, 'flag_branch'):
        path, name = fact['location']['path'], (fact['value'].get('captures') or {}).get('F')
        where, switch = _switch_of(path, name, fixed, imported)
        sides = switch and _sides(fact, switch, sets, _text(root, path, cache))
        if not sides: continue
        out.append({'path': path, 'line': fact['location']['line'], 'switch': name, 'switch_path': where,
                    'switch_line': switch['line'], 'value': switch['value'], 'dead': sides[0], 'live': sides[1],
                    'fact_ids': [fact['id']]})
    return out


def _leaves(lines, body):
    """Whether a branch's body leaves its function (returns or raises), so the code after it does not run."""
    return any(LEAVES.search(text) for text in lines[body[0] - 1:body[1]])


def _inside(path, line, spans):
    return any(path == where and first <= line <= last for where, (first, last) in spans)


def _named_elsewhere(name, definition, spans, root, cache):
    """Whether a line of the project names the function outside its own body, the closed branches and the lists that
    export it."""
    word = re.compile(rf'(?<![\w.]){re.escape(name)}(?!\w)')
    for path in sorted({p for p, _ in spans} | {definition['path']}):
        for number, text in enumerate(_text(root, path, cache), 1):
            if not word.search(text) or EXPORTS.search(text) or _inside(path, number, spans): continue
            if path == definition['path'] and definition['line'] <= number <= definition['end_line']: continue
            return True
    return False


def _definitions(sets):
    """{name: its definition} of the project's own functions (a name defined twice is left out: it cannot be told)."""
    seen, out = set(), {}
    for fact in _of(sets, 'symbol'):
        if fact['value'].get('kind') not in ('function', 'method') or classify(fact['location']['path']) != 'source': continue
        name = fact['value']['name']
        if name in seen: out.pop(name, None); continue
        seen.add(name)
        out[name] = {'path': fact['location']['path'], 'line': fact['location']['start_line'],
                     'end_line': fact['location'].get('end_line') or fact['location']['start_line'], 'fact_id': fact['id'],
                     'parameters': len(((fact['value'].get('signature') or {}).get('parameters')) or [])}
    return out


def _callees(sets, path, span, defined):
    return sorted({f['value']['callee'] for f in _of(sets, 'call_edge') if f['location']['path'] == path
                   and span[0] <= (f['location'].get('start_line') or 0) <= span[1] and f['value']['callee'] in defined
                   and not f['value'].get('attribute')})      # console.log is no call of the project's own log


def _calls(sets):
    calls = {}
    for fact in _of(sets, 'call_edge'): calls.setdefault(fact['value']['callee'], []).append(fact)
    return calls


def _only_there(name, calls, spans):
    """Whether every call to the name is in a closed branch."""
    return all(_inside(c['location']['path'], c['location'].get('start_line') or 0, spans) for c in calls.get(name, []))


def switched_off(sets, root=None):
    """Each closed branch with the old engines only it calls and what runs in its place (the live branch's own
    functions): [{..., 'engines': [{name, path, line}], 'replaced_by': [names]}]."""
    cache, defined, calls = {}, _definitions(sets), _calls(sets)
    branches = closed(sets, root, cache)
    spans = [(row['path'], tuple(row['dead'])) for row in branches]
    out = []
    for row in branches:
        engines = [name for name in _callees(sets, row['path'], row['dead'], defined)
                   if _only_there(name, calls, spans) and not _named_elsewhere(name, defined[name], spans, root, cache)]
        out.append({**row, 'engines': [{'name': n, 'path': defined[n]['path'], 'line': defined[n]['line']} for n in engines],
                    'fact_ids': row['fact_ids'] + [defined[n]['fact_id'] for n in engines],
                    'replaced_by': [n for n in _callees(sets, row['path'], row['live'], defined) if n not in engines]})
    return out


def words(name):
    """The lower-case words of a name: legacyGenerate, old_export, exportV2 -> [legacy, generate], [old, export], [export, v2]."""
    found = [w.lower() for w in WORDS.findall(name)]
    merged = []
    for word in found:
        if word.isdigit() and merged and merged[-1] == 'v': merged[-1] = 'v' + word
        else: merged.append(word)
    return merged


def _marker(word): return word in OLD | NEW or bool(VERSION.match(word))


def _stem(name):
    parts = words(name)
    return '_'.join(w for w in parts if not _marker(w)), [w for w in parts if _marker(w)]


def _version(marks):
    return next((int(VERSION.match(w).group(1)) for w in marks if VERSION.match(w)), None)


def _older(one, other):
    """The older of two marked names: the one marked old, or the lower version; None when their markers do not say."""
    (_, a), (_, b) = _stem(one), _stem(other)
    if bool(set(a) & OLD) != bool(set(b) & OLD): return one if set(a) & OLD else other
    va, vb = _version(a), _version(b)
    if va is not None and vb is not None and va != vb: return one if va < vb else other
    return None


def _history(sets):
    return {f['location']['path']: f['value'] for f in _of(sets, 'history_churn', 'history')}


def _pairs(groups, older):
    """(old, new) of every two members of a group whose names say which is older (`older(a, b)`)."""
    for group in groups:
        for index, one in enumerate(group):
            for other in group[index + 1:]:
                old = older(one, other)
                if old is not None: yield (one, other) if old == one else (other, one)


def _row(kind, old, new, line, history, fact_ids):  # limits: parameters -- a finding's fields, each its own
    return {'kind': kind, 'old': old[0], 'new': new[0], 'path_old': old[1], 'path_new': new[1], 'line': line,
            'stopped': (history.get(old[1]) or {}).get('last_change'), 'began': (history.get(new[1]) or {}).get('first_change'),
            'fact_ids': fact_ids}


def two_engines(sets):
    """[{kind, old, new, path_old, path_new, line, stopped, began, fact_ids}]: two functions or modules doing one job."""
    by_stem, defined, history, calls = {}, _definitions(sets), _history(sets), _calls(sets)
    for name, definition in defined.items():
        stem, path = _stem(name)[0], PurePosixPath(definition['path'])
        if stem: by_stem.setdefault((stem, definition['parameters'], path.parent.as_posix(), path.suffix), []).append(name)
    out = [_row('function', (old, defined[old]['path']), (new, defined[new]['path']), defined[old]['line'], history,
                [defined[old]['fact_id'], defined[new]['fact_id']])
           for old, new in _pairs(by_stem.values(), _older) if old in calls]      # nothing calls it: dead code, said elsewhere
    return out + two_modules(sets, history)


def two_modules(sets, history):
    """Two modules a marker apart (engine.js and engine_v2.js, legacy/report.py and report.py), the old one still
    imported by the product."""
    nodes = {f['location']['path']: f for f in _of(sets, 'graph_node', 'graph') if classify(f['location']['path']) == 'source'}
    imported = {target for f in nodes.values() for target in f['value'].get('depends_on') or []}
    by_stem = {}
    for path in nodes: by_stem.setdefault((_stem(PurePosixPath(path).stem)[0], PurePosixPath(path).suffix), []).append(path)
    by_name = lambda one, other: {_module_name(one): one, _module_name(other): other}.get(_older(_module_name(one), _module_name(other)))
    return [_row('module', (old, old), (new, new), 1, history, [nodes[old]['id'], nodes[new]['id']])
            for old, new in _pairs(by_stem.values(), by_name) if old in imported]


def _module_name(path):
    """A module's name with its folder: legacy/report.py reads legacy_report, so the folder's marker counts."""
    parts = PurePosixPath(path)
    return '_'.join([*parts.parent.parts[-1:], parts.stem])

"""A machine guard per rule (M16.2): what checks a rule without an AI remembering it. Written once (by the person's
assistant through `rule_guard`, or by EAOS's own ask, eaos/ai/rule_guard.py), proved on its own examples before it is
kept, then run free on every check, change and commit:

    pattern    an ast-grep rule over the code (`rule`, ast-grep's own rule object, in `language`), with the code it must
               find (`examples.broken`) and the code it must leave (`examples.kept`); a match is a place the rule breaks
    test       a command of the project's own (its tests, a lint), run in its folder: broken when it fails, the places
               the `path:line` its output names. Always the project's own test: unpinning a rule never removes it
    detector   EAOS's own detectors and gates (`detectors`: a gate of eaos/analysis/repair/gates.py, `copy`, `complex`,
               `size`, `security`, `dead`, `tidy`, or a detector of the claims ledger, `real_data`, `data_keeping`,
               `one_source:near_copy`...): broken where they find something
    none       EAOS cannot guard this rule (`why`): said so in every view, never pretended

`files` (globs) bounds where a guard applies: a change touching none of them runs nothing of it (the smallest check
that suffices, M16.7).
"""
import fnmatch
import json
import os
import re
import tempfile
import time
from pathlib import Path

KINDS = ('pattern', 'test', 'detector', 'none')
GATES = ('copy', 'complex', 'size', 'security', 'dead', 'tidy', 'layers', 'structure', 'vendor', 'cycle', 'broken')
EXTENSIONS = {'python': '.py', 'javascript': '.js', 'typescript': '.ts', 'tsx': '.tsx', 'jsx': '.jsx', 'html': '.html',
              'css': '.css', 'go': '.go', 'rust': '.rs', 'java': '.java', 'kotlin': '.kt', 'ruby': '.rb', 'php': '.php',
              'c': '.c', 'cpp': '.cpp', 'csharp': '.cs', 'swift': '.swift', 'bash': '.sh', 'json': '.json', 'yaml': '.yml'}
TEST_SECONDS = 600
PLACE = re.compile(r'([\w./-]+\.\w+):(\d+|:\w+)')       # path:line, or path::function as a code law names one


def _need(condition, why):
    if not condition: raise ValueError(why)


def _none(guard, files):
    _need(str(guard.get('why') or '').strip(), 'say why EAOS cannot guard this rule')
    return {'kind': 'none', 'why': str(guard['why'])[:500]}


def _test(guard, files):
    command = guard.get('command')
    _need(isinstance(command, list) and command and all(isinstance(p, str) for p in command), 'a test guard is its command as a list of words')
    return {'kind': 'test', 'command': command, 'env': {str(k): str(v) for k, v in (guard.get('env') or {}).items()}, 'files': files,
            'tests': [str(t) for t in guard.get('tests') or []]}


def _detector(guard, files):
    detectors = [str(d) for d in guard.get('detectors') or []]
    _need(detectors, 'name the detectors that guard it')
    return {'kind': 'detector', 'detectors': detectors, 'files': files}


def checked(guard):
    """The guard as kept, or ValueError with what is wrong; a pattern is proved on its examples (ast-grep)."""
    _need(isinstance(guard, dict) and guard.get('kind') in KINDS, f'a guard is one of {", ".join(KINDS)}')
    makers = {'none': _none, 'test': _test, 'detector': _detector, 'pattern': _pattern}
    return makers[guard['kind']](guard, [str(f) for f in guard.get('files') or []])


def _pattern(guard, files):
    language = str(guard.get('language') or '').lower()
    _need(language in EXTENSIONS, f'the language of a pattern is one of {", ".join(EXTENSIONS)}')
    _need(isinstance(guard.get('rule'), dict) and guard['rule'], "a pattern guard's rule is an ast-grep rule object ({'pattern': ...})")
    examples = guard.get('examples') or {}
    broken, kept = list(examples.get('broken') or []), list(examples.get('kept') or [])
    _need(broken, 'a pattern guard needs at least one example of the code that breaks the rule')
    written = {'kind': 'pattern', 'language': language, 'rule': guard['rule'], 'message': str(guard.get('message') or '')[:300],
               'files': files, 'examples': {'broken': broken, 'kept': kept}}
    proved(written)
    return written


def proved(guard):
    """ValueError unless the pattern finds every broken example and none of the kept ones."""
    with tempfile.TemporaryDirectory(prefix='eaos-rule-examples-') as folder:
        names = {}
        for side in ('broken', 'kept'):
            for number, code in enumerate(guard['examples'][side], 1):
                name = f"{side}-{number}{EXTENSIONS[guard['language']]}"
                (Path(folder) / name).write_text(code, encoding='utf-8')
                names[name] = (side, number)
        found, error = _matches(guard, folder, list(names))
        _need(error is None, f'ast-grep refused the rule: {error}')
        hit = {names[Path(place['path']).name] for place in found if Path(place['path']).name in names}
        missed = [n for n in range(1, len(guard['examples']['broken']) + 1) if ('broken', n) not in hit]
        wrong = sorted(n for side, n in hit if side == 'kept')
        _need(not missed, f"the rule does not find broken example {', '.join(map(str, missed))}")
        _need(not wrong, f"the rule finds kept example {', '.join(map(str, wrong))}: it would refuse sound code")


def _inline(guard):
    """The guard as ast-grep's inline rule (JSON is YAML)."""
    return json.dumps({'id': 'eaos-person-rule', 'language': guard['language'], 'severity': 'error',
                       'message': guard.get('message') or 'a rule of the person is broken', 'rule': guard['rule']})


def _matches(guard, root, files=None):
    """([{path, line, code}], None) of the pattern's matches under `root` (only `files` when given), or ([], why)."""
    from ...engines.code.ast_grep import BINARY, EXCLUDED
    from ...engines.process import run, which
    binary = which(BINARY)
    if not binary: return [], 'ast-grep is not installed (eaos tools install)'
    globs = [part for name in EXCLUDED for part in ('--globs', f'!**/{name}/**')]
    code, out, error, _ = run([binary, 'scan', '--inline-rules', _inline(guard), '--json=stream', '--color', 'never',
                               *globs, *(files or ['.'])], cwd=root, timeout=120)
    if code and not out.strip(): return [], (error or f'exit {code}').strip()[-300:]
    return [_match(json.loads(line)) for line in out.splitlines() if line.strip()], None


def _match(row):
    return {'path': row['file'], 'line': row['range']['start']['line'] + 1, 'code': str(row.get('lines') or row.get('text') or '')[:200]}


def _within(path, globs):
    return not globs or any(fnmatch.fnmatch(path, g) for g in globs)


def applies(guard, paths):
    """Whether a change to `paths` reaches the guard: it names no files, or one of the paths is among them."""
    globs = (guard or {}).get('files') or []
    return paths is None or any(_within(p, globs) for p in paths) or not globs


def run(guard, root, paths=None, found=None):
    """{'status': held | broken | unguarded | not_run, 'places', 'said', 'seconds'}: the guard on the code at `root`, on
    `paths` only when given (a pattern reads only them; a test or detector runs when they reach it). `found`: the
    detectors' findings [{detector, places}] of the check or the gate, for a detector guard."""
    started = time.monotonic()
    if not guard or guard['kind'] == 'none':
        return {'status': 'unguarded', 'places': [], 'said': (guard or {}).get('why') or 'no guard written yet', 'seconds': 0}
    if not applies(guard, paths):
        return {'status': 'not_run', 'places': [], 'said': 'the change reaches none of its files', 'seconds': 0}
    if guard['kind'] == 'pattern': status, places, said = _run_pattern(guard, root, paths)
    elif guard['kind'] == 'test': status, places, said = _run_test(guard, root)
    else: status, places, said = _run_detectors(guard, found, paths)
    return {'status': status, 'places': places[:40], 'said': said, 'seconds': round(time.monotonic() - started, 2)}


def _files_of(root, paths, globs):
    return [p for p in paths if (Path(root) / p).is_file() and _within(p, globs)]


def _run_pattern(guard, root, paths):
    globs = guard.get('files') or []
    files = None if paths is None else _files_of(root, paths, globs)
    if files == []: return 'held', [], 'none of the changed files is of its kind'
    found, error = _matches(guard, root, files)
    if error: return 'not_run', [], error
    places = sorted({f"{f['path']}:{f['line']}" for f in found if _within(f['path'], globs)})
    return ('broken', places, f'{len(places)} places') if places else ('held', [], 'nowhere')


def _run_test(guard, root):
    from ...core.system.process import run_command
    try: done = run_command(guard['command'], TEST_SECONDS, cwd=str(root), env={**os.environ, **guard.get('env', {})})
    except OSError as problem: return 'not_run', [], f'{guard["command"][0]}: {problem}'
    except Exception as problem:            # a timeout: the guard said nothing either way
        return 'not_run', [], f'{type(problem).__name__}: {problem}'[:300]
    if done.returncode == 0: return 'held', [], 'its test passed'
    output = (done.stdout or '') + (done.stderr or '')
    places = sorted({f'{_inside(root, p)}:{n.lstrip(":")}' for p, n in PLACE.findall(output) if (Path(root) / p).is_file()})
    return 'broken', places or [' '.join(guard['command'])], output.strip()[-600:]


def _inside(root, path):
    """A place a test named, as the project reads it: relative to its folder (a runner may print absolute paths)."""
    try: return str(Path(path).resolve().relative_to(Path(root).resolve())) if Path(path).is_absolute() else path
    except ValueError: return path


def _run_detectors(guard, found, paths):
    if found is None: return 'not_run', [], 'its detectors did not run here'
    mine = [row for row in found if _among(row['detector'], guard['detectors'])]
    if not mine: return 'held', [], 'nothing found'
    places = sorted({place for row in mine for place in row['places']})       # on a change, the gates found what it added
    return 'broken', places, '; '.join(sorted({row.get('said') or row['detector'] for row in mine}))[:600]


def _among(detector, names):
    return any(_named(detector, name) for name in names)


def _named(detector, name):
    """Whether `detector` is `name` or one of its kinds (`real_data` names `real_data:iban`)."""
    return detector == name or detector.startswith(name + ':')


def said(guard):
    """What the guard is, in a line both the person's assistant and a person read."""
    if not guard: return 'no guard yet'
    if guard['kind'] == 'pattern': return f"the code pattern {json.dumps(guard['rule'], ensure_ascii=False)[:160]} ({guard['language']})"
    if guard['kind'] == 'test': return 'the test ' + ' '.join(guard['command'])[:160]
    if guard['kind'] == 'detector': return "EAOS's detectors " + ', '.join(guard['detectors'])
    return 'not guarded: ' + guard['why']

"""The record of a logic-flaw hunt (logic-flaws.json) and its `logic_flaws` fact set, which the claims make cards of
(eaos/analysis/claims/from_logic_flaws.py). A candidate is kept only when it points at a real line of a source file of
the project, says what a layer finding does not already say, and the second reading did not refute it; every candidate
set aside is kept with its reason. The record names the code it read (`source`, the files' contents): read again on
other code, it says nothing.

    run(target, out, provider)    the hunt, its checks and its record: {flaws, holds, dropped, reviewed}
"""
import json
from pathlib import Path

from ...core.contracts.vocabulary import SOURCE
from ...core.project.workspace import inventory
from ...facts import digest, make
from ...facts.run import add_to_index
from ...facts.store import read_set, write_set
from . import hunt

NAME = 'logic_flaws'
VERSION = '2'
RECORD = 'logic-flaws.json'
LIMITATIONS = ['Found by the assistant reading the code (an optional deep check), each candidate read again to disprove it; '
               'a flaw neither reading could settle is kept as unsure for the triage and a person to judge.']
REQUIRED = ('title', 'invariant', 'principal', 'impact', 'fix')


def source_of(root):
    """The fingerprint of the code a hunt read: every file's path, size and content, never its time."""
    files = inventory(root)['files']
    return digest(json.dumps(sorted([f['path'], f['size'], f.get('sha256')] for f in files)).encode('utf-8'))


def _place(root, flaw):
    """(path, lines) when the flaw names a source file inside the project, else (None, reason). ValueError or OSError
    when the path cannot be read at all (a NUL byte)."""
    path = str(flaw.get('path') or '').removeprefix('./')
    file = (root / path).resolve()
    if not path or not file.is_relative_to(root) or not file.is_file(): return None, f'no file {path or "named"} in the project'
    if file.suffix.lower() not in SOURCE: return None, f'{path} is not source code'
    return path, file.read_text(encoding='utf-8', errors='replace').split('\n')


def grounded(root, flaw, known=frozenset()):
    """The flaw with its excerpt when it is whole, points at a real line of a source file and is not a layer finding
    already (`known`: their (path, line)); else the reason it is not."""
    missing = [k for k in REQUIRED if not str(flaw.get(k) or '').strip()]
    if missing: return None, f"it says no {', '.join(missing)}"
    if flaw.get('class') not in hunt.CLASSES or flaw.get('severity') not in hunt.SEVERITIES: return None, 'its class or severity is unknown'
    path, lines = _place(root, flaw)
    if path is None: return None, lines
    line, why = _line(path, lines, flaw.get('line'), known)
    if why: return None, why
    return {**flaw, 'path': path, 'excerpt': '\n'.join(lines[max(0, line - 3):line + 2])[:800], 'cited': lines[line - 1].strip()[:400]}, None


def _line(path, lines, line, known):
    """(line, None) when `line` is a real line of the file (an int, never True) no layer finding names; else (None, why)."""
    if type(line) is not int or not 1 <= line <= len(lines): return None, f'{path} has no line {line}'
    if (path, line) in known: return None, f'a layer finding already says {path}:{line}'
    return line, None


def _layer_places(out):
    """(path, line) of every layer finding of the check (the `boundaries` set), which the hunt must not repeat."""
    try: facts = read_set(out, 'boundaries').get('facts') or []
    except (OSError, ValueError): return frozenset()
    return frozenset((f['location'].get('path'), f['location'].get('start_line')) for f in facts if f.get('kind') == 'boundary_finding')


def _sorted_out(root, flaws, known):
    """(kept, dropped): the grounded candidates, one per place and class, and the rest with their reason."""
    kept, dropped, seen = [], [], set()
    for flaw in flaws:
        try: checked, why = grounded(root, flaw, known)
        except (ValueError, OSError): checked, why = None, 'its path cannot be read'
        key = checked and (checked['path'], checked['line'], checked['class'])
        if checked and key in seen: why = 'the same flaw twice'
        if why: dropped.append({'title': str(flaw.get('title') or '')[:200], 'why': why})
        else: seen.add(key); kept.append(checked)
    return kept, dropped


def _judged(kept, verdicts, dropped):
    """The candidates the second reading did not refute, each with its verdict (holds / unsure)."""
    flaws = []
    for number, flaw in enumerate(kept, 1):
        verdict, why = verdicts.get(number, ('unsure', 'the second reading gave no verdict'))
        if verdict == 'refuted': dropped.append({'title': flaw['title'][:200], 'why': f'refuted: {why}'[:400]})
        else: flaws.append({**flaw, 'verdict': 'holds' if verdict == 'holds' else 'unsure', 'critic': why[:400]})
    order = {s: n for n, s in enumerate(reversed(hunt.SEVERITIES))}
    flaws.sort(key=lambda f: (f['verdict'] != 'holds', order[f['severity']], f['path'], f['line']))
    return flaws


def _critique(provider, kept, root):
    """The critic's verdicts; when its call fails, none (every candidate stays unsure) and why."""
    try: return hunt.critique(provider, kept, root), None
    except (ValueError, OSError, hunt.Unfinished) as failed: return {}, f'the second reading did not finish: {failed}'


def run(target, out, provider, minutes=hunt.MINUTES):
    """The hunt, its grounding and its critic, within `minutes` of wall clock (hunt.Unfinished past them). The grounded
    candidates are saved, unsure, before the critic reads them, so a critic that fails or runs out of time loses nothing:
    they stay unsure for the triage. Returns the record's summary."""
    root = Path(target).resolve()
    with hunt.deadline(minutes):
        return _hunted(root, out, provider)


def _hunted(root, out, provider):
    found = hunt.candidates(provider, out, root)
    kept, dropped = _sorted_out(root, found['flaws'], _layer_places(out))
    head = {'schema_version': 2, 'source': source_of(root), 'reviewed': found['reviewed']}
    write(out, {**head, 'flaws': _judged(kept, {}, []), 'dropped': dropped, 'critic': 'not read yet'}, root)
    verdicts, failed = _critique(provider, kept, root)
    return write(out, {**head, 'flaws': _judged(kept, verdicts, dropped), 'dropped': dropped, 'critic': failed or 'read'}, root)


def facts_of(record):
    keys = ('title', 'title_ar', 'class', 'severity', 'verdict', 'principal', 'invariant', 'steps', 'impact', 'fix', 'fix_ar', 'test',
            'critic', 'cited')
    return [make('logic_flaw', NAME, VERSION, record['source'], {'path': f['path'], 'start_line': f['line']}, {k: f.get(k) for k in keys},
                 limitations=LIMITATIONS) for f in record['flaws']]


def write(out, record, target):
    """logic-flaws.json and the `logic_flaws` fact set (its input_sha the code it read), listed in the facts' index."""
    out = Path(out)
    (out / RECORD).write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    summary = {'flaws': len(record['flaws']), 'holds': sum(f['verdict'] == 'holds' for f in record['flaws']),
               'dropped': len(record['dropped']), 'reviewed': len(record['reviewed']), 'critic': record.get('critic')}
    entry = write_set(out, NAME, NAME, VERSION, LIMITATIONS, {'facts': facts_of(record), 'input_sha': record['source'], 'summary': summary})
    add_to_index(out, target, entry)
    return summary


def current(fact_set, target):
    """The facts of a `logic_flaws` set when they were found on the code at `target` (or no target is named), else none."""
    facts = (fact_set or {}).get('facts') or []
    if not facts or target is None: return facts
    try: return facts if fact_set.get('input_sha') == source_of(target) else []
    except (OSError, ValueError): return []

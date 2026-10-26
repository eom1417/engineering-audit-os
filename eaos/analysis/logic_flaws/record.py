"""The record of a logic-flaw hunt (logic-flaws.json) and its `logic_flaws` fact set, which the claims make cards of
(eaos/analysis/claims/from_logic_flaws.py). A candidate is kept only when it points at a real line of the project and
the second reading did not refute it; every candidate set aside is kept with its reason.

    run(target, out, provider)    the hunt, its checks and its record: {flaws, dropped, reviewed}
"""
import json
from pathlib import Path

from ...facts import digest, make
from ...facts.store import write_set
from . import hunt

NAME = 'logic_flaws'
VERSION = '1'
RECORD = 'logic-flaws.json'
LIMITATIONS = ['Found by the assistant reading the code (an optional deep check), each candidate read again to disprove it; '
               'a flaw neither reading could settle is kept as unsure for the triage and a person to judge.']
REQUIRED = ('title', 'invariant', 'principal', 'impact', 'fix')


def _place(root, flaw):
    """(path, lines) when the flaw names a file inside the project, else (None, reason)."""
    path = str(flaw.get('path') or '').removeprefix('./')
    file = (root / path).resolve()
    if not path or not file.is_relative_to(root) or not file.is_file(): return None, f'no file {path or "named"} in the project'
    return path, file.read_text(encoding='utf-8', errors='replace').split('\n')


def grounded(root, flaw):
    """The flaw with its excerpt when it is whole and points at a real line; else the reason it is not."""
    missing = [k for k in REQUIRED if not str(flaw.get(k) or '').strip()]
    if missing: return None, f"it says no {', '.join(missing)}"
    if flaw.get('class') not in hunt.CLASSES or flaw.get('severity') not in hunt.SEVERITIES: return None, 'its class or severity is unknown'
    path, lines = _place(root, flaw)
    if path is None: return None, lines
    line = flaw.get('line')
    if not isinstance(line, int) or not 1 <= line <= len(lines): return None, f'{path} has no line {line}'
    return {**flaw, 'path': path, 'excerpt': '\n'.join(lines[max(0, line - 3):line + 2])[:800]}, None


def _sorted_out(root, flaws):
    """(kept, dropped): the grounded candidates, one per place and class, and the rest with their reason."""
    kept, dropped, seen = [], [], set()
    for flaw in flaws:
        checked, why = grounded(root, flaw)
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
    return flaws


def check(target, out, provider):
    """{flaws, dropped, reviewed}: the hunt and its two checks, no file written."""
    root = Path(target).resolve()
    found = hunt.candidates(provider, out, root)
    kept, dropped = _sorted_out(root, found['flaws'])
    flaws = _judged(kept, hunt.critique(provider, kept, root), dropped)
    order = {s: n for n, s in enumerate(reversed(hunt.SEVERITIES))}
    flaws.sort(key=lambda f: (f['verdict'] != 'holds', order[f['severity']], f['path'], f['line']))
    return {'schema_version': 1, 'flaws': flaws, 'dropped': dropped, 'reviewed': found['reviewed']}


def facts_of(record):
    sha = digest(json.dumps([[f['path'], f['line'], f['class']] for f in record['flaws']]).encode('utf-8'))
    keys = ('title', 'title_ar', 'class', 'severity', 'verdict', 'principal', 'invariant', 'steps', 'impact', 'fix', 'fix_ar', 'test', 'critic')
    return sha, [make('logic_flaw', NAME, VERSION, sha, {'path': f['path'], 'start_line': f['line']}, {k: f.get(k) for k in keys},
                      limitations=LIMITATIONS) for f in record['flaws']]


def write(out, record):
    out = Path(out)
    (out / RECORD).write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    sha, facts = facts_of(record)
    summary = {'flaws': len(record['flaws']), 'holds': sum(f['verdict'] == 'holds' for f in record['flaws']),
               'dropped': len(record['dropped']), 'reviewed': len(record['reviewed'])}
    write_set(out, NAME, NAME, VERSION, LIMITATIONS, {'facts': facts, 'input_sha': sha, 'summary': summary})
    return summary


def run(target, out, provider):
    return write(out, check(target, out, provider))

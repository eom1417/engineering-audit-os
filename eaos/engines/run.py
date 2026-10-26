"""Every engine of the registry run on a target, as many at once as the computer has room for, into one manifest."""
import contextvars
import json
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from . import (ast_grep, bandit, checkov, codegraph, codeql, dependency_cruiser, enola, gitleaks, gitnexus, jscpd, knip,
               lizard, oasdiff, osv_scanner, react_docgen, reforge, sarif, scc, semgrep, spectral, sqlfluff, syft,
               trivy)
from .contract import NOT_APPLICABLE, OBSERVED, UNAVAILABLE
from .process import state_digest
from ..core import progress
from ..core.system import resources
from ..core.toolchain import registry

# The engines are the registry's (eaos/data/toolchain.json): every tool the engines stage runs (`check: engines`) with a
# command of its own has its adapter here, by its NAME; an added tool that declares an `engine` runs through sarif.py.
# Install, run and display read the one list; an entry without its adapter fails here, at import.
_BY_NAME = {module.NAME: module for module in (ast_grep, bandit, checkov, codegraph, codeql, dependency_cruiser, enola, gitleaks,
                                                gitnexus, jscpd, knip, lizard, oasdiff, osv_scanner, react_docgen, reforge, scc,
                                                semgrep, spectral, sqlfluff, syft, trivy)}
ADAPTERS = {tool['name']: _BY_NAME[tool['name']] for tool in registry()['tools']
            if tool.get('check') == 'engines' and tool.get('binary') and not tool.get('engine')} | sarif.declared()
# What an engine may take while it runs; an adapter that takes more says so (CodeQL's database: codeql.MEMORY).
ENGINE_MB = 1024


def health():
    """What is installed, at what version, and whether it matches the pin. Runs no analysis."""
    report = {}
    for name, adapter in sorted(ADAPTERS.items()):
        found = adapter.version()
        report[name] = {'installed': found is not None, 'version': found, 'pinned': adapter.PINNED,
                        'version_matches_pin': found == adapter.PINNED,
                        'capabilities': [{'kind': c.kind, 'rule': c.rule, 'method': c.method}
                                         for c in adapter.capabilities()]}
    return report


def ordered(names):
    """Engines in name order, except that an engine runs after the ones it reads (its AFTER)."""
    names, done = sorted(names), []
    while names:
        ready = next(name for name in names if not set(getattr(ADAPTERS[name], 'AFTER', ())) & set(names) - {name})
        names.remove(ready); done.append(ready)
    return done


def _report(name, target, workdir, exclude, formats):
    try:
        return ADAPTERS[name].analyze(target, workdir, exclude, formats).as_dict()
    except Exception as problem:                           # an engine must never take the run down with it
        return {'engine': name, 'status': 'error', 'reason': f'{type(problem).__name__}: {problem}'[:300],
                'findings': [], 'coverage': {}, 'version': None, 'pinned_version': ADAPTERS[name].PINNED}


class _Job(NamedTuple):
    """What every engine of one run is asked to read: the target, its scratch folder, the excluded paths, the formats."""
    target: Path
    workdir: Path
    exclude: tuple
    formats: object


def _run_one(name, selected, reports, job):
    progress.step(name, len(reports), len(selected), 'running')
    began = time.monotonic()
    reports[name] = _report(name, *job)
    status = reports[name].get('status') or 'error'
    progress.step(name, len(reports), len(selected), status, time.monotonic() - began,
                  reason=reports[name].get('reason') or '', reason_code='' if status == 'observed' else f'engine_{status}')


def _need(name):
    return getattr(ADAPTERS[name], 'MEMORY', ENGINE_MB)


def _run_all(selected, target, workdir, exclude, formats):
    """Each selected engine's report, in order, each one a step of the running stage from waiting to its own status. An
    engine starts once the engines it reads have ended, beside the others only while this computer has room for it
    (resources.room): a strong computer runs many at once, a small one one at a time, never none."""
    reports, left, running, began = {}, list(selected), {}, {}
    args = (selected, reports, _Job(target, workdir, exclude, formats))
    for name in selected: progress.step(name, 0, len(selected), 'waiting')
    with ThreadPoolExecutor(resources.capacity()[0], thread_name_prefix='eaos-engine') as pool:
        while left or running:
            waiting = False
            for name in _startable(left, running):
                waiting = _no_room(name, running, began)
                if waiting: break
                left.remove(name)
                began[name] = time.monotonic()
                running[pool.submit(contextvars.copy_context().run, _run_one, name, *args)] = name
            done, _ = wait(running, timeout=resources.WAIT if waiting else None, return_when=FIRST_COMPLETED)
            for future in done:
                running.pop(future)
                future.result()
    return {name: reports[name] for name in selected}


def _startable(left, running):
    """The engines left that read (AFTER) none of the engines left or running."""
    return [n for n in left if not set(getattr(ADAPTERS[n], 'AFTER', ())) & (set(left) | set(running.values())) - {n}]


def _no_room(name, running, began):
    """Whether `name` waits: others run, and the computer has no room for it beside them and what they are starting."""
    starting = sum(_need(n) for n in running.values() if time.monotonic() - began[n] < resources.STARTING)
    return bool(running) and not resources.room(_need(name) + starting)


def analyze(target, workdir, exclude=(), only=None, formats=None, keep=False):
    """Run every requested engine and return one manifest. The target is proven unchanged afterwards.

    Each engine of the registry is reported as a step of the running stage (eaos/core/progress/context.py), from waiting
    to its own status (observed, not applicable, unavailable, error): the live map shows each tool as it runs. `keep`:
    the engines named in `only` are run again within the same check (one that failed), beside the others' results kept
    from it."""
    target, workdir = Path(target).resolve(), Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    selected = _selected(only)
    unknown = sorted(set(only or ()) - set(ADAPTERS))
    before = state_digest(target)
    reports = _run_all(selected, target, workdir, exclude, formats)
    after = state_digest(target)
    if keep: selected, reports = _with_kept(workdir, selected, reports)
    manifest = {
        'contract_version': 1,
        'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'target': str(target), 'exclude': sorted(exclude), 'formats': sorted(formats) if formats else None,
        'requested': selected, 'unknown_engines': unknown,
        'target_unchanged': before == after, 'target_digest': before,
        'engines': reports,
        'findings': sorted((item for name in selected for item in reports[name].get('findings', [])),
                     key=lambda row: (row['engine'], row['id'])),
        'coverage': {name: {'status': reports[name]['status'], 'reason': reports[name].get('reason', ''),
                            'version': reports[name].get('version'),
                            'evaluated_kinds': reports[name].get('evaluated_kinds', []),
                            'detail': reports[name].get('coverage', {})}
                     for name in selected},
        'limits': 'External engines are recorded, never trusted: we did not implement their rules, so every '
                  'finding enters as heuristic evidence and needs corroboration or a probe to rise above it.'}
    # On disk each finding once, under its engine (the list above repeats them for the caller): compact, read back
    # by _with_kept; the facts carry them on (facts/external.json).
    on_disk = {key: value for key, value in manifest.items() if key != 'findings'}
    (workdir / 'engines.json').write_text(json.dumps(on_disk, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    return manifest


def _selected(only):
    """The engines asked for (`only`, by default all), each after the ones it reads."""
    return ordered(ADAPTERS if not only else [name for name in ADAPTERS if name in set(only)])


def _with_kept(workdir, selected, reports):
    """(every engine, every report): the ones run now and the others of the check's last engines.json."""
    try: previous = json.loads((workdir / 'engines.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return selected, reports
    kept = {name: row for name, row in (previous.get('engines') or {}).items() if name in ADAPTERS and name not in reports}
    return ordered([*kept, *selected]), {**kept, **reports}


def observed(manifest):
    """The engines that actually produced evidence in this run."""
    return sorted(name for name, detail in manifest.get('coverage', {}).items() if detail['status'] == OBSERVED)


def missing(manifest):
    return sorted(name for name, detail in manifest.get('coverage', {}).items() if detail['status'] == UNAVAILABLE)


def not_applicable(manifest):
    """Engines with nothing to read in this project: neither absent nor a clean result."""
    return sorted(name for name, detail in manifest.get('coverage', {}).items() if detail['status'] == NOT_APPLICABLE)

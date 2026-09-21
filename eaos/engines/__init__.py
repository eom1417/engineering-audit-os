"""External analysis engines, behind one contract.

A missing engine reduces coverage; it never fails the run. Every engine's version is discovered by
running it, never assumed, and a version that does not match its pin is reported as such and still
recorded — so a reader can tell "we did not look" apart from "we looked and found nothing".
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from . import codegraph, enola, jscpd, reforge
from .contract import OBSERVED, UNAVAILABLE
from .process import state_digest

ADAPTERS = {module.NAME: module for module in (enola, codegraph, reforge, jscpd)}


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


def analyze(target, workdir, exclude=(), only=None, formats=None):
    """Run every requested engine and return one manifest. The target is proven unchanged afterwards."""
    target, workdir = Path(target).resolve(), Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    selected = sorted(ADAPTERS) if not only else [name for name in sorted(ADAPTERS) if name in set(only)]
    unknown = sorted(set(only or ()) - set(ADAPTERS))
    before = state_digest(target)
    reports = {}
    for name in selected:
        try:
            reports[name] = ADAPTERS[name].analyze(target, workdir, exclude, formats).as_dict()
        except Exception as problem:                       # an engine must never take the run down with it
            reports[name] = {'engine': name, 'status': 'error', 'reason': f'{type(problem).__name__}: {problem}'[:300],
                             'findings': [], 'coverage': {}, 'version': None, 'pinned_version': ADAPTERS[name].PINNED}
    after = state_digest(target)
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
    (workdir / 'engines.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    return manifest


def observed(manifest):
    """The engines that actually produced evidence in this run."""
    return sorted(name for name, detail in manifest.get('coverage', {}).items() if detail['status'] == OBSERVED)


def missing(manifest):
    return sorted(name for name, detail in manifest.get('coverage', {}).items() if detail['status'] == UNAVAILABLE)

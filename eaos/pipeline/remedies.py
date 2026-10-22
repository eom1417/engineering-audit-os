"""What EAOS does by itself about a stage that did not run, after a check (docs/GUIDE.md): the catalog names a remedy
for a reason code (eaos/data/errors.json reasons[code].remedy); the ones that need no person are applied, rules first,
and the stage runs again, up to ROUNDS times, only after a change was proven (a tool installed, the assistant answering,
a stage it needs now ok). A reason tried once is not tried again; a person's consent is never given here. The manifest
keeps what was done (`remedies`), for the report and the Studio to say plainly."""
from pathlib import Path

from ..progress.reasons import reasons
from .run import MANIFEST, _write

ROUNDS = 3


def remedy_of(row):
    """The catalog's remedy for a stage row's reason code, or None."""
    return (reasons().get(str(row.get('reason_code') or '')) or {}).get('remedy')


def apply(manifest, redo, out, progress=None, assistant=None):
    """The manifest after the remedies that need no person were applied and their stages run again (`redo(stages)`
    returns the new manifest); `remedies` lists each try: {stage, code, remedy, round, outcome, after}."""
    tried, record = set(), []
    for round_ in range(1, ROUNDS + 1):
        todo = [(name, row, remedy) for name, row in manifest['stages'].items() if row.get('status') != 'ok'
                and (remedy := remedy_of(row)) and (name, row.get('reason_code')) not in tried]
        if not todo: break
        stages = []
        for name, row, remedy in todo:
            tried.add((name, row.get('reason_code')))
            outcome = _try(remedy, manifest, assistant)
            record.append({'stage': name, 'code': row.get('reason_code'), 'remedy': remedy, 'round': round_, 'outcome': outcome})
            if outcome == 'fixed' and remedy.get('then') == 'again_from': stages.append(name)
        if not stages: break
        if progress: progress(round_, ROUNDS, 'remedies')
        manifest = redo(stages)
    for row in record: row['after'] = manifest['stages'].get(row['stage'], {}).get('status')
    manifest['remedies'] = record
    _write(Path(out) / MANIFEST, manifest)
    return manifest


def _try(remedy, manifest, assistant):
    """'fixed' once the remedy's change is proven, 'failed' when it is not, 'needs_person' when only the person can."""
    if remedy.get('needs') == 'person' or remedy.get('consent'): return 'needs_person'
    if any(manifest['stages'].get(s, {}).get('status') != 'ok' for s in remedy.get('requires_ok') or []): return 'failed'
    tool = remedy.get('tool')
    if tool == 'tools_check':
        from ..toolchain import install
        return 'failed' if install(names=remedy.get('only'), echo=lambda *_: None) else 'fixed'
    if tool == 'assistant_check':
        from ..assistants.readiness import probe
        return 'fixed' if assistant and probe(assistant, fresh=True).get('ready') else 'failed'
    return 'fixed'                       # the stage alone runs again (tools_failed: the engines stage, its tools again)

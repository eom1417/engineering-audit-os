"""What EAOS does by itself about a stage that did not run, after a check (docs/GUIDE.md): the catalog names a remedy
for a reason code (eaos/data/errors.json reasons[code].remedy); the ones that need no person are applied, rules first,
and the stage runs again, up to ROUNDS times, only after a change was proven (a tool installed, the assistant answering,
a stage it needs now ok). A reason tried once is not tried again; a person's consent is never given here. The manifest
keeps what was done (`remedies`), for the report and the Studio to say plainly."""
import json
from pathlib import Path

from ..progress.reasons import reasons
from .run import MANIFEST, _write

ROUNDS = 3


def remedy_of(row):
    """The catalog's remedy for a stage row's reason code, or None."""
    return (reasons().get(str(row.get('reason_code') or '')) or {}).get('remedy')


def apply(manifest, redo, out, progress=None, assistant=None, provider=None):
    """The manifest after the remedies that need no person were applied and their stages run again (`redo(stages)`
    returns the new manifest); `remedies` lists each try: {stage, code, remedy, round, outcome, after}. A failed stage
    the catalog knows no remedy for is put to the person's assistant once (`provider`), its answer one allowed action."""
    tried, record = set(), []
    for round_ in range(1, ROUNDS + 1):
        todo = [(name, row, remedy) for name, row in manifest['stages'].items() if row.get('status') != 'ok'
                and (remedy := remedy_of(row)) and (name, row.get('reason_code')) not in tried]
        if not todo: break
        stages = []
        for name, row, remedy in todo:
            tried.add((name, row.get('reason_code')))
            outcome = _try(remedy, manifest, assistant)
            record.append({'stage': name, 'code': row.get('reason_code'), 'remedy': remedy, 'round': round_, 'outcome': outcome,
                           **({'next': 'tools_find'} if outcome == 'failed' and remedy.get('tool') == 'tools_check' else {})})
            if outcome == 'fixed' and remedy.get('then') == 'again_from': stages.append(name)
        if not stages: break
        if progress: progress(round_, ROUNDS, 'remedies')
        manifest = redo(stages)
    manifest = _ask_once(manifest, redo, record, provider)
    for row in record: row['after'] = manifest['stages'].get(row['stage'], {}).get('status')
    manifest['remedies'] = record
    _write(Path(out) / MANIFEST, manifest)
    return manifest


def _ask_once(manifest, redo, record, provider):
    """The assistant, once in the whole check, on the failed stages no remedy is known for: run one again (an error it
    reads as passing, a timeout) or say what the person should do. Rules first: it is asked only here."""
    unknown = {name: row.get('reason') for name, row in manifest['stages'].items() if row.get('status') == 'failed' and not remedy_of(row)}
    if not (provider and unknown): return manifest
    ask = ('These stages of an EAOS check failed, each with its reason: ' + json.dumps(unknown, ensure_ascii=False)[:4000] + '. Answer one '
           'JSON object: {"action": "again_from" or "none", "stage": "<one of them, for again_from>", "advice": "<what the person should do, '
           'one sentence>"}. again_from only when running it again may pass (a timeout, a passing hiccup); otherwise none.')
    try: answer = (provider.complete([{'role': 'user', 'content': ask}], small=True, stage='remedies')[0] or {}).get('result') or {}
    except Exception: return manifest            # the rules' record stands; the assistant is a help, never a failure
    stage = answer.get('stage') if answer.get('action') == 'again_from' and answer.get('stage') in unknown else None
    record.append({'stage': stage or next(iter(unknown)), 'code': 'stage_error', 'remedy': {'assistant': answer.get('advice') or ''},
                   'round': ROUNDS + 1, 'outcome': 'fixed' if stage else 'needs_person'})
    return redo([stage]) if stage else manifest


def consent(manifest, question):
    """`question` for the person when a remedy needs their agreement (running the app), else {}: their yes runs the
    check again from setup (audit person_agreed)."""
    if not any(r.get('remedy', {}).get('consent') == 'run' and r['outcome'] == 'needs_person' for r in manifest.get('remedies') or []): return {}
    return {'status': 'needs_agreement', 'ask_the_person': question,
            'what_now': 'Ask the person this. Only if they say yes, call audit with person_agreed=true: the app runs and the stages that need it run again.'}


def pending(report):
    """The first stage of the last check whose reason has a remedy needing no person, never tried (a check made before
    the remedies, or a tool installed since), else None."""
    try: manifest = json.loads((Path(report) / MANIFEST).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None
    tried = {r['stage'] for r in manifest.get('remedies') or []}
    return next((name for name, row in (manifest.get('stages') or {}).items() if row.get('status') != 'ok' and name not in tried
                 and (r := remedy_of(row)) and not (r.get('needs') or r.get('consent'))), None)


def agreed(run_app, again_from, person_agreed):
    """(run_app, again_from) of a check the person agreed to after `consent`: the app runs, from setup on."""
    return (True, again_from or 'setup') if person_agreed else (run_app, again_from)


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

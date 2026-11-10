"""<report>/studio/: cards.json, evidence.json, decisions.json, history.json and manifest.json, written after every
check and every batch from the report and the ledger.

Each file is written to a temporary name and renamed; manifest.json goes last, with the fingerprint of every file, so
a reader never sees a half-written set. A file that cannot be built is left out and its error returned; the rest is
still written, and nothing here stops the step that called it. Paths are relative to the project; an absolute path, a
home directory or `..` is never written.
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path

from ...core.system import version_info as build_info
from ...core.system.clock import now
from . import model as M
from .cards import cards
from .decisions import decision_rows
from .evidence import evidence, sources
from .history import history

CONTRACT = 1
REVISION = 2
# The key each file's body is under; history's body is the file itself.
KEY = {'cards': 'cards', 'evidence': 'facts', 'decisions': 'decisions'}


def _git(project, *args):
    if not project: return None
    done = subprocess.run(['git', '-C', str(project), *args], capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else None


def scan_of(project, state=None):
    """{commit, branch, at, recorded, detached, dirty} of the check. `recorded` is true when the scan itself wrote down
    the branch (or a detached HEAD), the full commit and whether the checkout had unsaved changes
    (eaos/core/project/branches.py scan_provenance); otherwise commit and branch are what git says now, and detached and
    dirty are None."""
    state = state or {}
    if state.get('scanned_commit') and ('scanned_branch' in state or 'scanned_detached' in state):
        return {'commit': state['scanned_commit'], 'branch': state.get('scanned_branch'), 'at': state.get('scanned') or '',
                'recorded': True, 'detached': state.get('scanned_detached'), 'dirty': state.get('scanned_dirty')}
    commit = state.get('scanned_commit') or _git(project, 'rev-parse', 'HEAD')
    branch = state.get('branch') or _git(project, 'rev-parse', '--abbrev-ref', 'HEAD')
    return {'commit': commit, 'branch': None if branch == 'HEAD' else branch, 'at': state.get('scanned') or '',
            'recorded': False, 'detached': None, 'dirty': None}


def _write(folder, name, data):
    """name.json, written whole and renamed into place; returns its bytes."""
    blob = json.dumps(data, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8')
    target = folder / f'{name}.json'
    temporary = target.with_name(f'.{target.name}.tmp')
    temporary.write_bytes(blob)
    os.replace(temporary, target)
    return blob


def _attempt(built, errors, name, make):
    """Build one file's body; one that cannot be built is named in `errors`, and the others go on."""
    try: built[name] = make()
    except Exception as error: errors.append({'section': name, 'error': f'{type(error).__name__}: {error}'[:300]})


def _build(report, m, lang, project, scan):
    """({file: body}, errors) of the files built from the records `m`."""
    built, errors = {}, []
    claims = {c.get('id'): c for c in m['dossier'].get('claims') or [] if isinstance(c, dict)}
    _attempt(built, errors, 'cards', lambda: cards(m, claims, lang, M.task_cards(m)))
    card_rows = built.get('cards') or []
    cited = {i for c in card_rows for i in c['evidence']}
    _attempt(built, errors, 'evidence', lambda: evidence(report, cited, sources(project, scan['commit'])))
    _attempt(built, errors, 'decisions', lambda: decision_rows(report, card_rows, lang))
    progress = m['progress']
    _attempt(built, errors, 'history', lambda: history(scan, m['score'], card_rows, progress.get('ledger'), progress.get('waves') or ()))
    return built, errors


def _publish(folder, built):
    """Write every built file; returns the manifest's entries, each with its fingerprint."""
    entries = []
    for section in (s for s in ('cards', 'evidence', 'decisions', 'history') if s in built):
        blob = _write(folder, section, _body(section, built[section]))
        entries.append({'name': section, 'file': f'{section}.json', 'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob)})
    return entries


def _body(name, body):
    head = {'schema_version': 1, 'contract': CONTRACT}
    return {**head, KEY[name]: body} if name in KEY else {**head, 'revision': REVISION, **body}


def write(report, lang='ar', project=None, progress=None, state=None):
    """Write <report>/studio/ and return {'written': [files], 'errors': [{section, error}]}; the project's name is its
    folder's."""
    report = Path(report)
    folder = report / 'studio'
    folder.mkdir(parents=True, exist_ok=True)
    lang = 'ar' if lang == 'ar' else 'en'
    try: m = M.records(report, progress)
    except Exception as error:              # no record to build from: say so, and leave no stale manifest behind
        (folder / 'manifest.json').unlink(missing_ok=True)
        return {'written': [], 'errors': [{'section': 'records', 'error': f'{type(error).__name__}: {error}'[:300]}]}
    scan = scan_of(project, state)
    if not scan['at']: scan['at'] = str(m['manifest'].get('started_at') or '')
    built, errors = _build(report, m, lang, project, scan)
    entries = _publish(folder, built)
    manifest = {'schema_version': 1, 'language': lang, 'contract': CONTRACT, 'revision': REVISION, 'built': build_info.stamp(now()),
                'project': {'name': Path(str(project or report)).name}, 'scanned': scan, 'sections': entries}
    if entries: _write(folder, 'manifest', manifest)
    return {'written': [e['name'] for e in entries], 'errors': errors}

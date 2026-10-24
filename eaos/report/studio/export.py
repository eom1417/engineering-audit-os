"""studio/: the data the Studio reads, written from the one model after every check and every batch (docs/STUDIO.md).

One JSON file per section, each checked against its contract (schemas/artifacts/studio-<section>.schema.json) before it
is written, and a .js twin of each so the Studio opens from a file, where a browser refuses to fetch JSON. Every file
is written to a temporary name and renamed; manifest.json goes last, with the fingerprint of every section, so a reader
never sees a half-written set. A section that cannot be built or breaks its contract is left out and named in
studio/errors.json; the rest is still written, and nothing here stops the step that called it.

Every number the Studio shows is a measure {value, src}; what was not measured is null, never 0. Paths are relative to
the project; an absolute path, a home directory or `..` is never written.
"""
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ...core import artifact_contracts, build_info
from . import change as change_map
from . import coverage as coverage_section
from . import history as history_section
from . import library as library_section
from . import hidden as hidden_map
from . import journeys as journeys_map
from . import data_paths as data_map
from . import functions as function_explorer
from .evidence import evidence, sources
from . import infra as infra_map
from ...ai import ideal as planned_ideal
from ...ai.nodes import view as ai_nodes
from ...analysis import model as M
from . import paths as code_paths
from ...analysis import pipeline_map
from . import screens as screens_gallery
from . import system as system_map
from .export_sections import TASK_STATE, cards, decision_rows, decisions, head, health, meta, plans, story, why_of  # noqa: F401  (TASK_STATE, decisions, why_of: read here by the tests and tools/studio_synthetic.py)

CONTRACT = 1
REVISION = 2           # contract v2: sections added without breaking a v1 reader (docs/STUDIO.md)
SECTIONS = ('meta', 'head', 'health', 'cards', 'evidence', 'story', 'docs', 'plans', 'decisions', 'media', 'system')
SECTIONS_V2 = ('functions', 'screens', 'history', 'paths', 'journeys', 'hidden', 'data_paths', 'infra', 'pipeline', 'ideal', 'nodes', 'gaps', 'operations', 'library')   # contract v2 sections written here (coverage is written last, apart)


def _git(project, *args):
    if not project: return None
    done = subprocess.run(['git', '-C', str(project), *args], capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else None


def scan_of(project, state=None):
    """{commit, branch, at, recorded, detached, dirty} of the check. `recorded` is true when the scan itself wrote down
    the branch (or a detached HEAD), the full commit and whether the checkout had unsaved changes (eaos/core/branches.py
    scan_provenance); otherwise commit and branch are what git says at export time, and detached and dirty are None."""
    state = state or {}
    if state.get('scanned_commit') and ('scanned_branch' in state or 'scanned_detached' in state):
        return {'commit': state['scanned_commit'], 'branch': state.get('scanned_branch'), 'at': state.get('scanned') or '',
                'recorded': True, 'detached': state.get('scanned_detached'), 'dirty': state.get('scanned_dirty')}
    commit = state.get('scanned_commit') or _git(project, 'rev-parse', 'HEAD')
    branch = state.get('branch') or _git(project, 'rev-parse', '--abbrev-ref', 'HEAD')
    return {'commit': commit, 'branch': None if branch == 'HEAD' else branch, 'at': state.get('scanned') or '',
            'recorded': False, 'detached': None, 'dirty': None}


# ---------------------------------------------------------------- writing

def _published(built, stamps):
    """(section, body) of every built section, the contract v1 sections first."""
    key = {'cards': 'cards', 'evidence': 'facts', 'docs': 'docs', 'plans': 'plans', 'decisions': 'decisions', 'media': 'images'}
    for section in (s for s in SECTIONS if s in built):
        body = built[section]
        made = {'provenance': stamps[section]} if section in stamps else {}
        yield section, {'schema_version': 1, 'contract': CONTRACT, **({key[section]: body} if section in key else body), **made}
    for section in (s for s in SECTIONS_V2 if s in built):
        made = {'provenance': stamps[section]} if section in stamps else {}
        yield section, {'schema_version': 1, 'contract': CONTRACT, 'revision': REVISION, **built[section], **made}


def _write(folder, name, data):
    """name.json, written whole and renamed into place; returns its bytes. (Its .js twin, for a page opened from a file,
    went in 0.0.73: nothing made such a page, and the twin doubled every section.)"""
    blob = json.dumps(data, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8')
    target = folder / f'{name}.json'
    temporary = target.with_name(f'.{target.name}.tmp')
    temporary.write_bytes(blob)
    os.replace(temporary, target)
    return blob


def export(report, lang='ar', name=None, project=None, progress=None, state=None, build=None):
    """Write <report>/studio/ and return {'written': [sections], 'errors': [{section, error}]}; `build`: a project still built
    from its plan (build_tools.studio_build), its plan, questions and next step in place of a check's."""
    report = Path(report)
    folder = report / 'studio'
    folder.mkdir(parents=True, exist_ok=True)
    lang = 'ar' if lang == 'ar' else 'en'
    try: m = M.records(report, progress)
    except Exception as error:              # no record to build from: say so, and leave no stale manifest behind
        errors = [{'section': 'records', 'error': f'{type(error).__name__}: {error}'[:300]}]
        (folder / 'manifest.json').unlink(missing_ok=True)
        (folder / 'errors.json').write_text(json.dumps(errors, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        return {'written': [], 'errors': errors}
    m['build'] = build
    stamp = {**build_info.stamp(datetime.now(timezone.utc).isoformat(timespec='seconds')), 'studio_digest': build_info.studio_digest()}
    scan = scan_of(project, state)
    if not scan['at']: scan['at'] = str((m['manifest'] or {}).get('started_at') or '')
    built, errors = {}, []
    card_rows = _build_core(report, m, lang, project, progress, state, scan, stamp, built, errors)
    _build_maps(report, m, lang, project, progress, scan, card_rows, built, errors)
    entries = _publish_all(folder, report, built, errors, lang, name, project, scan, stamp)
    return {'written': [e['name'] for e in entries], 'errors': errors}


def _attempt(built, errors, section, make):
    """Build one section; one that cannot be built is named in `errors`, and the others go on."""
    try: built[section] = make()
    except Exception as error: errors.append({'section': section, 'error': f'{type(error).__name__}: {error}'[:300]})


def _build_core(report, m, lang, project, progress, state, scan, stamp, built, errors):
    """The contract v1 sections, into `built`; returns the cards every later section reads."""
    attempt = lambda section, make: _attempt(built, errors, section, make)
    claims = {c.get('id'): c for c in m['dossier'].get('claims') or [] if isinstance(c, dict)}
    attempt('cards', lambda: cards(m, claims, lang))
    card_rows = built.get('cards') or []
    history = (((progress or {}).get('ledger') or {}).get('scores') or
               [{'at': scan['at'], 'commit': scan['commit'], 'score': None if m['score']['score'] is None else m['score']['score'] / 100}])
    attempt('meta', lambda: meta(report, m))
    attempt('head', lambda: head(m, scan, lang, stamp, freshness(project, state)))
    attempt('health', lambda: health(m, history))
    attempt('evidence', lambda: evidence(report, {i for c in card_rows for i in c['evidence']}, sources(project, scan['commit'])))
    attempt('story', lambda: story(report, m, card_rows))
    attempt('docs', lambda: library_section.docs(report))
    attempt('plans', lambda: plans(m, card_rows, lang))
    attempt('decisions', lambda: decision_rows(report, m, card_rows, lang))
    attempt('media', lambda: library_section.media(report, lang))
    attempt('system', lambda: system_map.system(report, card_rows))
    return card_rows


def _build_maps(report, m, lang, project, progress, scan, card_rows, built, errors):
    """The contract v2 sections, into `built`: the maps, the history, the library, the ideal and the change."""
    attempt = lambda section, make: _attempt(built, errors, section, make)
    attempt('paths', lambda: code_paths.paths(report, card_rows, m['plan'], lang))
    attempt('journeys', lambda: journeys_map.journeys(report, built.get('media')))
    if 'journeys' in built: attempt('hidden', lambda: hidden_map.hidden(report, built['journeys'], card_rows))
    attempt('data_paths', lambda: data_map.data_paths(report, lang))
    attempt('infra', lambda: infra_map.infra(report, lang))
    attempt('pipeline', lambda: pipeline_map.from_report(report, card_rows, m['plan'], lang))
    attempt('history', lambda: history_section.history(scan, m['score']['score'], card_rows, (progress or {}).get('ledger'),
                                                       (progress or {}).get('waves') or ()))
    if 'docs' in built and 'media' in built:
        attempt('library', lambda: library_section.library(report, built['docs'], built['media'], project))
    if built.get('pipeline', False) is None: built.pop('pipeline')   # the check wrote no facts/pipeline.json
    attempt('ideal', lambda: planned_ideal.section(report, lang))
    attempt('nodes', lambda: ai_nodes.section(report, lang))
    attempt('change', lambda: change_map.change(m, card_rows, lang))
    for section, body in zip(('gaps', 'operations'), built.pop('change', None) or (None, None)):
        if body is not None: built[section] = body                    # no target: coverage says why
    attempt('functions', lambda: function_explorer.functions(report, card_rows, built.get('evidence') or ()))
    attempt('screens', lambda: screens_gallery.screens(built.get('journeys'), built.get('media'), (report / 'facts/entrypoints.json').is_file(), report))
    for section in ('functions', 'screens'):                         # nothing was read to build it from
        if built.get(section, False) is None: built.pop(section)


def _publish_all(folder, report, built, errors, lang, name, project, scan, stamp):
    """Write every section that keeps its contract, then coverage, the locales, errors.json and the manifest last;
    returns the manifest's entries."""
    contracts, entries = artifact_contracts.contracts(), []

    def publish(section, data):
        problems = artifact_contracts.validate(data, contracts[f'studio-{section}'])
        if problems:
            errors.append({'section': section, 'error': '; '.join(problems[:5])[:300]})
            return
        blob = _write(folder, section, data)
        entries.append({'name': section, 'file': f'{section}.json', 'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob)})

    # Every section that draws a target says how its ideal was made: the rules only, or planned with a model (D10).
    for section, body in _published(built, planned_ideal.provenance_of(built.get('ideal'))): publish(section, body)
    # Last of the sections: it says which of the others were written, and what is not measured yet.
    _attempt(built, errors, 'coverage', lambda: coverage_section.coverage(report, built, [e['name'] for e in entries], list(errors), lang))
    if 'coverage' in built: publish('coverage', {'schema_version': 1, 'contract': CONTRACT, 'revision': REVISION, **built['coverage']})
    from .localization import publish as publish_locales
    locales = None
    try:
        locales = publish_locales(report, lang)
    except (OSError, ValueError, TypeError) as error:
        errors.append({'section': 'locales', 'error': str(error)[:300]})
    (folder / 'errors.json').write_text(json.dumps(errors, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    manifest = {'schema_version': 1, 'language': lang, 'contract': CONTRACT, 'revision': REVISION, 'built': stamp,
                'project': {'name': name or Path(str(project or report)).name}, 'scanned': scan, 'sections': entries}
    if locales:
        manifest['locales'] = locales
    if entries and not artifact_contracts.validate(manifest, contracts['studio-manifest']): _write(folder, 'manifest', manifest)
    return entries


def freshness(project, state):
    """(freshness, detail) at export time, from eaos/core/branches.py freshness: fresh, behind, rewritten, dirty, other_branch or
    unknown with its reason; eaos_updated when the scan was made by another EAOS. The live Studio asks the server again
    (GET /api/freshness) instead of trusting this snapshot."""
    from ...core import branches
    if not project or not (state or {}).get('scanned'): return 'unknown', {'state': 'unknown', 'reason': 'not_scanned', 'behind': None, 'eaos_updated': False}
    found = branches.freshness({**(state or {}), 'project': str(project)})
    updated = bool((state or {}).get('scanned_with')) and state.get('scanned_with') != build_info.digest()
    detail = {'state': found['state'], 'reason': found['reason'], 'behind': found['behind'], 'eaos_updated': updated}
    if found['state'] == 'fresh' and updated: return 'eaos_updated', detail
    return found['state'], detail

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
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .. import artifact_contracts, build_info, indicators
from ..compose.labels import impact_of
from . import coverage as coverage_section
from . import hidden as hidden_map
from . import journeys as journeys_map
from . import data_paths as data_map
from . import infra as infra_map
from . import model as M
from . import paths as code_paths
from . import pipeline as pipeline_map
from . import system as system_map

CONTRACT = 1
REVISION = 2           # contract v2: sections added without breaking a v1 reader (docs/STUDIO.md)
SECTIONS = ('meta', 'head', 'health', 'cards', 'evidence', 'story', 'docs', 'plans', 'decisions', 'media', 'system')
SECTIONS_V2 = ('paths', 'journeys', 'hidden', 'data_paths', 'infra', 'pipeline')   # contract v2 sections written here (coverage is written last, apart)
SAFE = re.compile(r'^(?![/\\~])(?![A-Za-z]:)(?!(.*/)?\.\.(/|$)).+')
LANGUAGES = M.LANGUAGES
LANGUAGES_SHOWN = ('ar', 'en')     # the Studio's two languages: a sentence written for both, shown in the person's
SEVERITY_OF_CONFIDENCE = {'CONFIRMED': 1.0, 'LIKELY': 0.7, 'HYPOTHESIS': 0.4}
TASK_STATE = {'done': 'done', 'resolved': 'done', 'on_branch': 'active', 'in_batch': 'active', 'open': 'todo',
              'skipped': 'blocked'}
RELATION = {'retain': 'retain', 'modify': 'modify', 'rebuild': 'rebuild', 'delete': 'delete', 'retire': 'delete',
            'introduce': 'missing'}
STAGE_STATE = {'ok': 'done', 'skipped': 'skipped', 'unavailable': 'partial', 'failed': 'failed', 'not_reached': 'skipped'}
DOC_GROUPS = (('START-HERE.md', 'start'), ('README.md', 'start'), ('EXECUTIVE.md', 'start'), ('CURRENT-STATE.md', 'story'),
              ('TARGET-STATE.md', 'story'), ('GAP-AND-STRATEGY.md', 'story'), ('EXECUTION-PLAN.md', 'plan'))


def rel(path):
    """A path the Studio may show: relative to the project, else None."""
    path = str(path or '').replace('\\', '/')
    return path if path and SAFE.match(path) else None


def measure(value, src, unit=None):
    out = {'value': value if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else None, 'src': src}
    if unit: out['unit'] = unit
    return out


def ratio(value, src):
    ok = isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1
    return {'value': round(value, 4) if ok else None, 'src': src}


def _git(project, *args):
    if not project: return None
    done = subprocess.run(['git', '-C', str(project), *args], capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else None


def scan_of(project, state=None):
    """{commit, branch, at} of the check: the state's when a guided session made it, else the project's git now."""
    state = state or {}
    commit = state.get('scanned_commit') or _git(project, 'rev-parse', 'HEAD')
    branch = state.get('branch') or _git(project, 'rev-parse', '--abbrev-ref', 'HEAD')
    return {'commit': commit, 'branch': None if branch == 'HEAD' else branch, 'at': state.get('scanned') or ''}


# ---------------------------------------------------------------- the sections

def meta(report, m):
    nodes = indicators.facts(report, 'graph_node')
    counts = {}
    for row in nodes:
        name = LANGUAGES.get(Path(str((row.get('location') or {}).get('path') or '')).suffix.lower())
        if name: counts[name] = counts.get(name, 0) + 1
    total = sum(counts.values())
    stages = [{'id': name, 'title': name, 'state': STAGE_STATE.get((row or {}).get('status'), 'partial')}
              for name, row in (m['manifest'].get('stages') or {}).items()]
    lines = sum((row.get('value') or {}).get('lines') or 0 for row in indicators.facts(report, 'metric')
                if (row.get('value') or {}).get('scope') == 'file') or None
    return {'languages': [{'name': name, 'files': count, 'share': round(count / total, 4)}
                          for name, count in sorted(counts.items(), key=lambda item: -item[1])],
            'files': measure(m['coverage'].get('source_files'), 'dossier.json#coverage.source_files', 'count'),
            'lines': measure(lines, 'facts/metrics.json#metric[scope=file].value.lines', 'lines'),
            'stages': stages}


def head(m, scan, lang, stamp, freshness):
    s = m['score']
    fixable = sum(1 for r in m['rows'] if r['auto'])
    if s['score'] is None:
        verdict = ('لم تُحسب درجة لهذا الفحص.' if lang == 'ar' else 'This check has no score.')
    else:
        verdict = (f"{len(m['rows'])} مشكلة، منها {fixable} يصلحها EAOS وحده." if lang == 'ar' else
                   f"{len(m['rows'])} problems; EAOS fixes {fixable} of them by itself.")
    if fixable:
        # A numeral never sits glued to a one-letter prefix (لـ165): it stands alone after a word, and the noun agrees with it.
        cards = ('بطاقة واحدة' if fixable == 1 else 'بطاقتين' if fixable == 2 else
                 f"{fixable} {'بطاقات' if fixable <= 10 else 'بطاقة'}")
        step = {'action': (f'ابدأ دفعة إصلاح تشمل {cards}' if lang == 'ar' else f'Start a fix batch for {fixable} cards'),
                'tool': 'fix_start'}
    elif m['rows']:
        step = {'action': ('راجع البطاقات التي تحتاج قرارًا' if lang == 'ar' else 'Review the cards that need a decision'), 'tool': 'findings'}
    else:
        step = {'action': ('لا شيء ينتظر: افحص بعد التغيير التالي' if lang == 'ar' else 'Nothing waits: check again after the next change'), 'tool': 'audit'}
    return {'scanned': scan, 'eaos': {k: stamp[k] for k in ('version', 'commit', 'digest')}, 'freshness': freshness,
            'verdict': verdict, 'next': step}


def health(m, history):
    s = m['score']
    domains = [{'id': area, 'name': area,
                'score': ratio(None if a['score'] is None else a['score'] / 100, f'model.score areas.{area}'),
                'cards': a['total']} for area, a in s['areas'].items()]
    return {'score': ratio(None if s['score'] is None else s['score'] / 100, 'model.score: mean of measured areas, capped at 39 by a confirmed critical problem'),
            'formula': f'area = 100 x {M.HALF_POINT} / ({M.HALF_POINT} + weighted points per 100 files); score = mean of measured areas',
            'domains': domains, 'history': history}


def cards(m, claims):
    rows = {r['id']: r for r in m['rows']}
    plan = {t.get('id'): t for t in m['plan'].get('tasks') or [] if isinstance(t, dict)}
    out = []
    for card in M.task_cards(m):
        row, task = rows.get(card['id']) or {}, plan.get(card['id']) or {}
        claim = claims.get(task.get('claim_id')) or {}
        params = (claim.get('render') or task.get('render') or {}).get('params') or {}
        place = rel(params.get('place'))
        evidence = list((task.get('evidence') or {}).get('fact_ids') or claim.get('fact_ids') or [])
        out.append({'id': card['id'], 'key': card['key'], 'title': card['title'], 'kind': card['pattern'],
                    'category': row.get('area') or M.classify({'pattern': card['pattern']})[0], 'severity': card['severity'],
                    'fixable': bool(row.get('auto')), 'needs_decision': task.get('kind') == 'investigate' or card['state'] == 'skipped',
                    'scope': 'group' if str(params.get('place') or '').startswith('group:') else 'place',
                    'place': place, 'paths': [p for p in map(rel, card['paths']) if p], 'evidence': evidence,
                    'state': card['state'], 'milestone': card.get('milestone'),
                    'confidence': SEVERITY_OF_CONFIDENCE.get(row.get('confidence')), **why_of(task)})
    return out


def why_of(task):
    """{'why': {ar, en}}: why the card matters, in the person's two languages (the report's impact sentence, translated
    by its render key where the catalogue has it); nothing when the plan gives no impact."""
    if not task.get('impact') and not task.get('impact_render'): return {}
    claim = {'impact': {'scenario': task.get('impact') or ''}, 'render': task.get('impact_render')}
    words = {lang: impact_of(claim, lang) for lang in LANGUAGES_SHOWN}
    return {'why': words} if all(w and w != '—' for w in words.values()) else {}


CODE_CONTEXT = 2           # lines shown before and after a fact's line
CODE_WIDTH = 240           # a longer line is cut: a minified file never fills the page
SECRET_KINDS = {'secret', 'credential', 'hardcoded_secret'}


def code_excerpt(source, path, line, kind, secrets=frozenset()):
    """{start, line, lines, hidden}: the lines around `line` of `path` as the check read them, or None: no line, a
    secret (its value is never written), or a file that cannot be read as text. A line where any fact found a secret
    (`secrets`: {(path, line)}) is written empty and named in `hidden`. `source(path)` returns the file's text or None."""
    if not path or not isinstance(line, int) or line < 1 or kind in SECRET_KINDS: return None
    text = source(path)
    if text is None or '\0' in text[:4096]: return None
    rows = text.splitlines()
    if line > len(rows): return None
    start = max(1, line - CODE_CONTEXT)
    shown = range(start, min(len(rows), line + CODE_CONTEXT) + 1)
    hidden = [n for n in shown if (path, n) in secrets]
    return {'start': start, 'line': line, 'lines': ['' if n in hidden else rows[n - 1][:CODE_WIDTH] for n in shown], 'hidden': hidden}


def sources(project, commit):
    """path -> text: the file at the scanned commit (git show), else the project's working copy; never a path
    outside the project. Cached, so each file is read once."""
    root = Path(project).resolve() if project else None
    cache = {}

    def read(path):
        if path in cache: return cache[path]
        text = None
        if root and commit:
            done = subprocess.run(['git', '-C', str(root), 'show', f'{commit}:{path}'], capture_output=True)
            if done.returncode == 0 and len(done.stdout) <= 2_000_000: text = done.stdout.decode('utf-8', 'replace')
        if text is None and root:
            file = (root / path).resolve()
            if file.is_relative_to(root) and file.is_file() and file.stat().st_size <= 2_000_000:
                text = file.read_text(encoding='utf-8', errors='replace')
        cache[path] = text
        return text
    return read


def evidence(report, cited, source=None):
    source = source or (lambda path: None)
    rows = indicators.facts(report)
    secrets = set()
    for row in rows:
        value, where = row.get('value') or {}, row.get('location') or {}
        if (value.get('kind') or row.get('kind')) not in SECRET_KINDS: continue
        for site in [where, *(s for s in value.get('sites') or [] if isinstance(s, dict))]:
            for n in (site.get('start_line'), site.get('line')):
                if isinstance(n, int) and rel(site.get('path')): secrets.add((rel(site.get('path')), n))
    out = []
    for row in rows:
        if row.get('id') not in cited: continue
        value, where = row.get('value') or {}, row.get('location') or {}
        sites = [{'path': rel(s.get('path')), 'line': s.get('line') if isinstance(s.get('line'), int) else None}
                 for s in value.get('sites') or [] if isinstance(s, dict) and rel(s.get('path'))]
        out.append({'id': row['id'], 'kind': value.get('kind') or row.get('kind') or '', 'engine': value.get('engine'),
                    'path': rel(where.get('path')), 'line': next((n for n in (where.get('start_line'), where.get('line')) if isinstance(n, int)), None),
                    'summary': str(value.get('message') or value.get('rule') or row.get('kind') or '')[:400], 'sites': sites[:20]})
        fact = out[-1]
        # the code around the fact's line, else around its first site in the same file
        line = fact['line'] or next((site['line'] for site in sites if site['path'] == fact['path'] and site['line']), None)
        fact['code'] = code_excerpt(source, fact['path'], line, fact['kind'], secrets)
    return out


def story(report, m, card_rows):
    target = m['target']
    closed = {c['id'] for c in card_rows if c['state'] in M.CLOSED}
    current = {c.get('id'): c for c in target.get('current_components') or [] if isinstance(c, dict)}
    gap = []
    for row in m['gap_matrix'].get('rows') or target.get('gap_matrix') or []:
        comp = current.get(row.get('current_id')) or {}
        relation = 'missing' if row.get('gap') == 'missing' and not comp else RELATION.get(comp.get('relation'), 'modify')
        tasks = [t for t in row.get('blocking_tasks') or [] if isinstance(t, str)]
        gap.append({'component': comp.get('name') or row.get('current_origin') or row.get('component') or '', 'relation': relation,
                    'to': row.get('target_component'), 'files': comp.get('files') or 0, 'cards': tasks,
                    'closed': sum(t in closed for t in tasks)})
    sustain = M._load(Path(report) / 'sustainability.json', {}) or {}
    predicted = (M._load(Path(report) / 'predictions.json', {}) or {}).get('predictions') or []
    after = ((predicted[-1].get('prediction') or {}).get('after') or {}) if predicted else {}
    rows = [{'id': r['indicator'], 'name': r['indicator'],
             'today': measure(r.get('value') if r.get('measured') else None, f"sustainability.json#rows[{r['indicator']}].value"),
             'expected': measure(after.get(r['indicator']), f"predictions.json#predictions[-1].prediction.after.{r['indicator']}"),
             'target': measure(r.get('target'), f"sustainability.json#rows[{r['indicator']}].target")}
            for r in sustain.get('rows') or [] if isinstance(r, dict) and r.get('indicator')]
    return {'current': {'summary': str(target.get('retained_structure') or '')[:600],
                        'components': [{'name': c.get('name') or c.get('id') or '', 'layer': c.get('kind'), 'files': c.get('files') or 0}
                                       for c in current.values()]},
            'target': {'summary': str(target.get('limits') or '')[:600],
                       'components': [{'name': c.get('name') or '', 'responsibility': c.get('responsibility') or '', 'layer': c.get('layer')}
                                      for c in target.get('target_components') or [] if isinstance(c, dict)]},
            'gap': gap, 'indicators': rows}


def docs(report):
    report, order = Path(report), {name: i for i, (name, _) in enumerate(DOC_GROUPS)}
    groups = dict(DOC_GROUPS)
    out = []
    for path in sorted(report.rglob('*.md')):
        name = path.relative_to(report).as_posix()
        if name.startswith(('handover/site/', 'studio/', 'bundles/')): continue
        first = path.read_text(encoding='utf-8', errors='replace').lstrip().split('\n', 1)[0]
        title = first.lstrip('#').strip() if first.startswith('#') else path.stem
        group = groups.get(name) or (name.split('/', 1)[0] if '/' in name else 'technical')
        out.append({'id': name, 'title': title[:200] or path.stem, 'path': name, 'group': group,
                    'bytes': path.stat().st_size, 'order': order.get(name)})
    return out


def plans(m, card_rows, lang):
    by_id = {c['id']: c for c in card_rows}
    steps = []
    for stone in m['plan'].get('milestones') or []:
        if not isinstance(stone, dict): continue
        tasks = [{'id': t, 'title': by_id[t]['title'], 'state': TASK_STATE[by_id[t]['state']], 'acceptance': None, 'depends_on': []}
                 for t in stone.get('tasks') or [] if t in by_id]
        states = {t['state'] for t in tasks}
        state = ('done' if tasks and states == {'done'} else 'active' if states & {'active', 'done'} else
                 'blocked' if tasks and states == {'blocked'} else 'todo')
        steps.append({'id': stone.get('id') or '', 'title': stone.get('goal_ar' if lang == 'ar' else 'goal') or stone.get('name') or '',
                      'state': state, 'weight': len(tasks), 'gate': stone.get('exit_ar' if lang == 'ar' else 'exit'),
                      'depends_on': [], 'sub_plan': None, 'tasks': tasks})
    total, closed = len(card_rows), sum(c['state'] in M.CLOSED for c in card_rows)
    touched = any(c['state'] not in ('open',) for c in card_rows)
    state = 'closed' if total and closed == total else 'active' if touched else 'registered'
    return [{'id': 'fix', 'title': 'خطة الإصلاح' if lang == 'ar' else 'Fix plan', 'kind': 'fix', 'parent': None, 'state': state,
             'goal': '', 'indicators': [], 'steps': steps,
             'progress': ratio(closed / total if total else None, 'ledger: (done + resolved) / every card in scope')}]


def decisions(m, card_rows, lang):
    out = []
    review = [c for c in card_rows if c['needs_decision'] and c['state'] not in M.CLOSED]
    if review:
        out.append({'id': 'investigations',
                    'question': (f'{len(review)} بطاقة تحتاج تحققًا قبل أي تغيير. هل يتولاها المساعد؟' if lang == 'ar' else
                                 f'{len(review)} cards need checking before any change. Should the assistant take them on?'),
                    'recommendation': ('نعم: يتحقق المساعد من كل بطاقة بدليلها ويعرض عليك ما يحتاج قرارك فقط.' if lang == 'ar' else
                                       'Yes: the assistant checks each card against its evidence and brings you only what needs you.'),
                    'options': [{'id': 'yes', 'label': 'نعم' if lang == 'ar' else 'Yes'}, {'id': 'later', 'label': 'لاحقًا' if lang == 'ar' else 'Later'}],
                    'blocks': [c['id'] for c in review][:200], 'state': 'waiting', 'answer': None, 'plan': 'fix',
                    'asked': '', 'tool': 'findings'})
    target = m['target']
    if target.get('status') == 'REVIEW_REQUIRED':
        out.append({'id': 'target-architecture',
                    'question': ('هل تعتمد البنية المستهدفة؟' if lang == 'ar' else 'Do you approve the target structure?'),
                    'recommendation': ('راجع قرارات البنية في القصة، ثم اعتمدها أو اطلب تعديلها.' if lang == 'ar' else
                                       'Review the structure decisions in the story, then approve them or ask for changes.'),
                    'options': [{'id': d.get('id') or '', 'label': str(d.get('chosen') or '')[:200]}
                                for d in target.get('decisions') or [] if isinstance(d, dict)],
                    'blocks': ['S06'], 'state': 'waiting', 'answer': None, 'plan': None, 'asked': '', 'tool': None})
    return out


def media(report):
    report, out = Path(report), []
    for path in sorted([*report.rglob('*.mmd'), *report.rglob('*.svg'), *report.rglob('*.png')]):
        name = path.relative_to(report).as_posix()
        if name.startswith(('handover/site/', 'studio/', 'bundles/')): continue
        out.append({'id': name, 'path': name, 'title': name.rsplit('/', 2)[-2] if '/' in name else path.stem,
                    'kind': 'diagram' if path.suffix in ('.mmd', '.svg') else 'screen', 'batch': None, 'phase': None,
                    'route': None, 'viewport': None, 'pair': None})
    return out


# ---------------------------------------------------------------- writing

def _write(folder, name, data):
    """name.json and its .js twin, each written whole and renamed into place; returns the JSON bytes."""
    text = json.dumps(data, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    blob = text.encode('utf-8')
    for target, body in ((folder / f'{name}.json', blob),
                         (folder / f'{name}.js', f'(window.EAOS_STUDIO=window.EAOS_STUDIO||{{}})[{json.dumps(name)}]={text};\n'.encode('utf-8'))):
        temporary = target.with_name(f'.{target.name}.tmp')
        temporary.write_bytes(body)
        os.replace(temporary, target)
    return blob


def export(report, lang='ar', name=None, project=None, progress=None, state=None):
    """Write <report>/studio/ and return {'written': [sections], 'errors': [{section, error}]}."""
    report = Path(report)
    folder = report / 'studio'
    folder.mkdir(parents=True, exist_ok=True)
    lang = 'ar' if lang == 'ar' else 'en'
    contracts = artifact_contracts.contracts()
    try: m = M.records(report, progress)
    except Exception as error:              # no record to build from: say so, and leave no stale manifest behind
        errors = [{'section': 'records', 'error': f'{type(error).__name__}: {error}'[:300]}]
        (folder / 'manifest.json').unlink(missing_ok=True)
        (folder / 'errors.json').write_text(json.dumps(errors, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        return {'written': [], 'errors': errors}
    stamp = {**build_info.stamp(datetime.now(timezone.utc).isoformat(timespec='seconds')), 'studio_digest': build_info.studio_digest()}
    scan = scan_of(project, state)
    if not scan['at']: scan['at'] = str((m['manifest'] or {}).get('started_at') or '')
    claims = {c.get('id'): c for c in m['dossier'].get('claims') or [] if isinstance(c, dict)}
    built, errors, entries = {}, [], []

    def attempt(section, make):
        try: built[section] = make()
        except Exception as error: errors.append({'section': section, 'error': f'{type(error).__name__}: {error}'[:300]})

    attempt('cards', lambda: cards(m, claims))
    card_rows = built.get('cards') or []
    history = (((progress or {}).get('ledger') or {}).get('scores') or
               [{'at': scan['at'], 'commit': scan['commit'], 'score': None if m['score']['score'] is None else m['score']['score'] / 100}])
    attempt('meta', lambda: meta(report, m))
    attempt('head', lambda: head(m, scan, lang, stamp, freshness(project, state)))
    attempt('health', lambda: health(m, history))
    attempt('evidence', lambda: evidence(report, {i for c in card_rows for i in c['evidence']}, sources(project, scan['commit'])))
    attempt('story', lambda: story(report, m, card_rows))
    attempt('docs', lambda: docs(report))
    attempt('plans', lambda: plans(m, card_rows, lang))
    attempt('decisions', lambda: decisions(m, card_rows, lang))
    attempt('media', lambda: media(report))
    attempt('system', lambda: system_map.system(report, card_rows))
    attempt('paths', lambda: code_paths.paths(report, card_rows, m['plan'], lang))
    attempt('journeys', lambda: journeys_map.journeys(report, built.get('media')))
    if 'journeys' in built: attempt('hidden', lambda: hidden_map.hidden(report, built['journeys'], card_rows))
    attempt('data_paths', lambda: data_map.data_paths(report, lang))
    attempt('infra', lambda: infra_map.infra(report, lang))
    attempt('pipeline', lambda: pipeline_map.from_report(report, card_rows, m['plan'], lang))
    if built.get('pipeline', False) is None: built.pop('pipeline')   # the check wrote no facts/pipeline.json
    key = {'cards': 'cards', 'evidence': 'facts', 'docs': 'docs', 'plans': 'plans', 'decisions': 'decisions', 'media': 'images'}
    def publish(section, data):
        problems = artifact_contracts.validate(data, contracts[f'studio-{section}'])
        if problems:
            errors.append({'section': section, 'error': '; '.join(problems[:5])[:300]})
            return
        blob = _write(folder, section, data)
        entries.append({'name': section, 'file': f'{section}.json', 'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob)})

    for section in SECTIONS:
        if section not in built: continue
        body = built[section]
        publish(section, {'schema_version': 1, 'contract': CONTRACT, **({key[section]: body} if section in key else body)})
    for section in SECTIONS_V2:
        if section in built: publish(section, {'schema_version': 1, 'contract': CONTRACT, 'revision': REVISION, **built[section]})
    # Last of the sections: it says which of the others were written, and what is not measured yet.
    attempt('coverage', lambda: coverage_section.coverage(report, built, [e['name'] for e in entries], list(errors), lang))
    if 'coverage' in built: publish('coverage', {'schema_version': 1, 'contract': CONTRACT, 'revision': REVISION, **built['coverage']})
    (folder / 'errors.json').write_text(json.dumps(errors, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    manifest = {'schema_version': 1, 'contract': CONTRACT, 'revision': REVISION, 'built': stamp,
                'project': {'name': name or Path(str(project or report)).name}, 'scanned': scan, 'sections': entries}
    if entries and not artifact_contracts.validate(manifest, contracts['studio-manifest']): _write(folder, 'manifest', manifest)
    return {'written': [e['name'] for e in entries], 'errors': errors}


def freshness(project, state):
    """fresh when the project's branch is still at the scanned commit; branch_moved when it is not; unknown when either
    is not known. A report made by another EAOS is rebuilt by guided.publish before it is read."""
    scanned = (state or {}).get('scanned_commit')
    now = _git(project, 'rev-parse', 'HEAD')
    if not scanned or not now: return 'unknown'
    return 'fresh' if now.startswith(scanned) or scanned.startswith(now) else 'branch_moved'

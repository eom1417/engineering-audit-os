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

from .. import artifact_contracts, build_info, indicators, owner_share
from ..compose.labels import impact_of
from ..plan import title_of
from . import change as change_map
from . import coverage as coverage_section
from . import history as history_section
from . import library as library_section
from . import hidden as hidden_map
from . import journeys as journeys_map
from . import data_paths as data_map
from . import functions as function_explorer
from .evidence import evidence, rel, sources
from . import infra as infra_map
from . import ideal as planned_ideal
from .nodes import view as ai_nodes
from . import model as M
from . import paths as code_paths
from . import pipeline as pipeline_map
from . import screens as screens_gallery
from . import system as system_map

CONTRACT = 1
REVISION = 2           # contract v2: sections added without breaking a v1 reader (docs/STUDIO.md)
SECTIONS = ('meta', 'head', 'health', 'cards', 'evidence', 'story', 'docs', 'plans', 'decisions', 'media', 'system')
SECTIONS_V2 = ('functions', 'screens', 'history', 'paths', 'journeys', 'hidden', 'data_paths', 'infra', 'pipeline', 'ideal', 'nodes', 'gaps', 'operations', 'library')   # contract v2 sections written here (coverage is written last, apart)
LANGUAGES = M.LANGUAGES
LANGUAGES_SHOWN = ('ar', 'en')     # the Studio's two languages: a sentence written for both, shown in the person's
SEVERITY_OF_CONFIDENCE = {'CONFIRMED': 1.0, 'LIKELY': 0.7, 'HYPOTHESIS': 0.4}
TASK_STATE = {'done': 'done', 'resolved': 'done', 'on_branch': 'active', 'in_batch': 'active', 'open': 'todo',
              'skipped': 'blocked'}
RELATION = {'retain': 'retain', 'modify': 'modify', 'rebuild': 'rebuild', 'delete': 'delete', 'retire': 'delete',
            'introduce': 'missing'}
STAGE_STATE = {'ok': 'done', 'skipped': 'skipped', 'unavailable': 'partial', 'failed': 'failed', 'not_reached': 'skipped'}


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
    """{commit, branch, at, recorded, detached, dirty} of the check. `recorded` is true when the scan itself wrote down
    the branch (or a detached HEAD), the full commit and whether the checkout had unsaved changes (eaos/branches.py
    scan_provenance); otherwise commit and branch are what git says at export time, and detached and dirty are None."""
    state = state or {}
    if state.get('scanned_commit') and ('scanned_branch' in state or 'scanned_detached' in state):
        return {'commit': state['scanned_commit'], 'branch': state.get('scanned_branch'), 'at': state.get('scanned') or '',
                'recorded': True, 'detached': state.get('scanned_detached'), 'dirty': state.get('scanned_dirty')}
    commit = state.get('scanned_commit') or _git(project, 'rev-parse', 'HEAD')
    branch = state.get('branch') or _git(project, 'rev-parse', '--abbrev-ref', 'HEAD')
    return {'commit': commit, 'branch': None if branch == 'HEAD' else branch, 'at': state.get('scanned') or '',
            'recorded': False, 'detached': None, 'dirty': None}


# ---------------------------------------------------------------- the sections

def _in(lang, ar, en):
    """The Arabic words for an Arabic page, else the English."""
    return ar if lang == 'ar' else en


def _language_counts(nodes):
    counts = {}
    for row in nodes:
        name = LANGUAGES.get(Path(str((row.get('location') or {}).get('path') or '')).suffix.lower())
        if name: counts[name] = counts.get(name, 0) + 1
    return counts


def meta(report, m):
    counts = _language_counts(indicators.facts(report, 'graph_node'))
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


def head(m, scan, lang, stamp, fresh):
    freshness, detail = fresh
    counted = M.problem_counts(m)
    return {'scanned': scan, 'eaos': {k: stamp[k] for k in ('version', 'commit', 'digest')}, 'freshness': freshness, 'freshness_detail': detail,
            'verdict': _verdict(m['score'], counted, lang), 'next': _next_step(counted['fixable'], m['rows'], lang)}


def _verdict(s, counted, lang):
    if s['score'] is None: return _in(lang, 'لم تُحسب درجة لهذا الفحص.', 'This check has no score.')
    fixable = counted['fixable']
    return _in(lang, f"{counted['problems']} مشكلة، منها {fixable} يصلحها EAOS وحده.",
               f"{counted['problems']} problems; EAOS fixes {fixable} of them by itself.")


def _cards_ar(count):
    # A numeral never sits glued to a one-letter prefix (لـ165): it stands alone after a word, and the noun agrees with it.
    if count == 1: return 'بطاقة واحدة'
    if count == 2: return 'بطاقتين'
    return f"{count} {'بطاقات' if count <= 10 else 'بطاقة'}"


def _next_step(fixable, rows, lang):
    if fixable:
        return {'action': _in(lang, f'ابدأ دفعة إصلاح تشمل {_cards_ar(fixable)}', f'Start a fix batch for {fixable} cards'),
                'tool': 'fix_start'}
    if rows:
        return {'action': _in(lang, 'راجع البطاقات التي تحتاج قرارًا', 'Review the cards that need a decision'), 'tool': 'findings'}
    return {'action': _in(lang, 'لا شيء ينتظر: افحص بعد التغيير التالي', 'Nothing waits: check again after the next change'), 'tool': 'audit'}


def health(m, history):
    s = m['score']
    domains = [{'id': area, 'name': area,
                'score': ratio(None if a['score'] is None else a['score'] / 100, f'model.score areas.{area}'),
                'cards': a['total']} for area, a in s['areas'].items()]
    return {'score': ratio(None if s['score'] is None else s['score'] / 100, 'model.score: mean of measured areas, capped at 39 by a confirmed critical problem'),
            'formula': f'area = 100 x {M.HALF_POINT} / ({M.HALF_POINT} + weighted points per 100 files); score = mean of measured areas',
            'domains': domains, 'history': history}


def cards(m, claims, lang):
    rows = {r['id']: r for r in m['rows']}
    plan = {t.get('id'): t for t in m['plan'].get('tasks') or [] if isinstance(t, dict)}
    tasks = [(card, plan.get(card['id']) or {}) for card in M.task_cards(m)]
    return [_card(card, rows.get(card['id']) or {}, task, claims.get(task.get('claim_id')) or {}, lang) for card, task in tasks]


def _needs_decision(task, card):
    """The owner's to decide (or, before cards were resolved, an investigation), or a card a batch could not fix."""
    owner = task['resolution']['resolution'] == 'owner' if task.get('resolution') else task.get('kind') == 'investigate'
    return owner or card['state'] == 'skipped'


def _card(card, row, task, claim, lang):
    params = (claim.get('render') or task.get('render') or {}).get('params') or {}
    place = rel(params.get('place'))
    evidence = list((task.get('evidence') or {}).get('fact_ids') or claim.get('fact_ids') or [])
    title = title_of(task, lang) if task.get('render') else card['title']     # in the Studio's language when it has words for it
    return {'id': card['id'], 'key': card['key'], 'title': title, 'kind': card['pattern'],
            'category': row.get('area') or M.classify({'pattern': card['pattern']})[0], 'severity': card['severity'],
            'fixable': bool(row.get('auto')),
            'needs_decision': _needs_decision(task, card),
            **({'resolution': resolution_of(task['resolution'])} if task.get('resolution') else {}),
            'scope': 'group' if str(params.get('place') or '').startswith('group:') else 'place',
            'place': place, 'paths': [p for p in map(rel, card['paths']) if p], 'evidence': evidence,
            'state': card['state'], 'milestone': card.get('milestone'),
            'confidence': SEVERITY_OF_CONFIDENCE.get(row.get('confidence')), **why_of(task)}


def resolution_of(row):
    """What the assistant decided for a card (eaos/plan.py resolve): {kind: fix | owner, by, words, and the change of a
    fix or the question, options and recommendation of an owner's choice; capped when it was the owner's but turned
    into the assistant's recommendation}. A fixable card with `by: assistant` is in the Studio's "fix with the
    assistant's recommendations" selection."""
    out = {'kind': row.get('resolution'), 'by': row.get('by') or 'assistant', 'words': row.get('words') or '', 'why': row.get('why') or ''}
    if out['kind'] == 'fix': out.update(change=row.get('change') or '', capped=bool(row.get('capped')))
    if out['kind'] == 'owner': out.update(question=row.get('question') or '', options=list(row.get('options') or []),
                                          recommendation=row.get('recommendation') or '')
    return out


def why_of(task):
    """{'why': {ar, en}}: why the card matters, in the person's two languages (the report's impact sentence, translated
    by its render key where the catalogue has it); nothing when the plan gives no impact."""
    if not task.get('impact') and not task.get('impact_render'): return {}
    claim = {'impact': {'scenario': task.get('impact') or ''}, 'render': task.get('impact_render')}
    words = {lang: impact_of(claim, lang) for lang in LANGUAGES_SHOWN}
    return {'why': words} if all(w and w != '—' for w in words.values()) else {}


def story(report, m, card_rows):
    target = m['target']
    closed = {c['id'] for c in card_rows if c['state'] in M.CLOSED}
    current = {c.get('id'): c for c in target.get('current_components') or [] if isinstance(c, dict)}
    gap = [_gap_row(row, current, closed) for row in m['gap_matrix'].get('rows') or target.get('gap_matrix') or []]
    return {'current': {'summary': str(target.get('retained_structure') or '')[:600],
                        'components': [{'name': c.get('name') or c.get('id') or '', 'layer': c.get('kind'), 'files': c.get('files') or 0}
                                       for c in current.values()]},
            'target': {'summary': str(target.get('limits') or '')[:600],
                       'components': [{'name': c.get('name') or '', 'responsibility': c.get('responsibility') or '', 'layer': c.get('layer')}
                                      for c in target.get('target_components') or [] if isinstance(c, dict)]},
            'gap': gap, 'indicators': []}


def _gap_row(row, current, closed):
    comp = current.get(row.get('current_id')) or {}
    relation = 'missing' if row.get('gap') == 'missing' and not comp else RELATION.get(comp.get('relation'), 'modify')
    tasks = [t for t in row.get('blocking_tasks') or [] if isinstance(t, str)]
    return {'component': comp.get('name') or row.get('current_origin') or row.get('component') or '', 'relation': relation,
            'to': row.get('target_component'), 'files': comp.get('files') or 0, 'cards': tasks,
            'closed': sum(t in closed for t in tasks)}


def _milestone_state(tasks):
    states = {t['state'] for t in tasks}
    if tasks and states == {'done'}: return 'done'
    if states & {'active', 'done'}: return 'active'
    return 'blocked' if tasks and states == {'blocked'} else 'todo'


def _milestone(stone, by_id, lang):
    tasks = [{'id': t, 'title': by_id[t]['title'], 'state': TASK_STATE[by_id[t]['state']], 'acceptance': None, 'depends_on': []}
             for t in stone.get('tasks') or [] if t in by_id]
    return {'id': stone.get('id') or '', 'title': stone.get(_in(lang, 'goal_ar', 'goal')) or stone.get('name') or '',
            'state': _milestone_state(tasks), 'weight': len(tasks), 'gate': stone.get(_in(lang, 'exit_ar', 'exit')),
            'depends_on': [], 'sub_plan': None, 'tasks': tasks}


def plans(m, card_rows, lang):
    by_id = {c['id']: c for c in card_rows}
    steps = [_milestone(stone, by_id, lang) for stone in m['plan'].get('milestones') or [] if isinstance(stone, dict)]
    total, closed = len(card_rows), sum(c['state'] in M.CLOSED for c in card_rows)
    touched = any(c['state'] not in ('open',) for c in card_rows)
    state = 'closed' if total and closed == total else 'active' if touched else 'registered'
    return [{'id': 'fix', 'title': 'خطة الإصلاح' if lang == 'ar' else 'Fix plan', 'kind': 'fix', 'parent': None, 'state': state,
             'goal': '', 'indicators': [], 'steps': steps,
             'progress': ratio(closed / total if total else None, 'ledger: (done + resolved) / every card in scope')}]


def _owner_question(card):
    """A real product choice the assistant left to the person on one card; None for any other resolution."""
    asked = card.get('resolution') or {}
    if asked.get('kind') != 'owner': return None
    options = [{'id': f'o{i + 1}', 'label': text} for i, text in enumerate(asked['options'])]
    return {'id': f"card:{card['id']}", 'question': asked['question'], 'recommendation': asked['recommendation'],
            'options': options, 'recommended_option': next((o['id'] for o in options if o['label'] == asked['recommendation']), None),
            'blocks': [card['id']], 'state': 'waiting', 'answer': None, 'plan': 'fix', 'asked': '', 'tool': 'findings'}


def _investigations(review, lang):
    return {'id': 'investigations',
            'question': _in(lang, f'{len(review)} بطاقة تحتاج تحققًا قبل أي تغيير. هل يتولاها المساعد؟',
                            f'{len(review)} cards need checking before any change. Should the assistant take them on?'),
            'recommendation': _in(lang, 'نعم: يتحقق المساعد من كل بطاقة بدليلها ويعرض عليك ما يحتاج قرارك فقط.',
                                  'Yes: the assistant checks each card against its evidence and brings you only what needs you.'),
            'options': [{'id': 'yes', 'label': _in(lang, 'نعم', 'Yes')}, {'id': 'later', 'label': _in(lang, 'لاحقًا', 'Later')}],
            'blocks': [c['id'] for c in review][:200], 'state': 'waiting', 'answer': None, 'plan': 'fix',
            'asked': '', 'tool': 'findings'}


def _target_question(target, lang):
    return {'id': 'target-architecture',
            'question': _in(lang, 'هل تعتمد البنية المستهدفة؟', 'Do you approve the target structure?'),
            'recommendation': _in(lang, 'راجع قرارات البنية في القصة، ثم اعتمدها أو اطلب تعديلها.',
                                  'Review the structure decisions in the story, then approve them or ask for changes.'),
            # one approval, never one option per structure decision (the incident: 51 English ADR sentences)
            'options': [{'id': 'approve', 'label': _in(lang, 'اعتمدها', 'Approve')},
                        {'id': 'changes', 'label': _in(lang, 'اطلب تعديلًا', 'Ask for changes')},
                        {'id': 'review', 'label': _in(lang, 'أراجعها أولًا', 'Review them first')}],
            'recommended_option': 'review', 'decisions_count': len([d for d in target.get('decisions') or [] if isinstance(d, dict)]),
            'blocks': ['S06'], 'state': 'waiting', 'answer': None, 'plan': None, 'asked': '', 'tool': None}


def decisions(m, card_rows, lang):
    review = [c for c in card_rows if c['needs_decision'] and c['state'] not in M.CLOSED]
    resolved = any(c.get('resolution') for c in card_rows)
    # The assistant resolved the cards: only a real product choice it left to the person is asked, one card each.
    out = [q for q in map(_owner_question, review) if q] if resolved else []
    if review and not resolved: out.append(_investigations(review, lang))
    if m['target'].get('status') == 'REVIEW_REQUIRED': out.append(_target_question(m['target'], lang))
    return out


STOP = frozenset('هل في وفي فيه اذا إذا اللي عليه كل شي من على إلى الى او أو أم و ما ماذا كيف وين أين لما لها له لهم هذا هذه نفس نفسه the a an of in on to is are do does or and what which how where should we it'.split())


def _words(text):
    """The content words of a question, for telling two askings of one topic apart: Arabic's article and its letter
    variants folded, short and common words left out."""
    text = re.sub('[\u064b-\u0652]', '', str(text or '').lower()).translate(str.maketrans('أإآةى', 'اااهي'))
    words = set()
    for word in re.findall(r'[\w./-]+', text):
        for prefix in ('وال', 'بال', 'لل', 'ال'):
            if word.startswith(prefix) and len(word) > len(prefix) + 2: word = word[len(prefix):]; break
        if len(word) > 2 and word not in STOP: words.add(word)
    return words


def tidy_decisions(rows):
    """The inbox asks each thing once and only what the person decides: a card_triage question is a fact about the
    code the assistant checks itself (the `investigations` row already offers that), so it never reaches the person;
    two questions on one topic (the same key, or most of the same words, as the planner and a screen reviewer ask
    about the phone's tab bar) become one, the first kept with the others' ids in `merged`."""
    kept = []
    for row in rows:
        if str(row.get('id', '')).startswith('node-card_triage:'): continue
        if row.get('state') == 'waiting': row = _first_asking(row, kept)
        if row is not None: kept.append(row)
    return [{k: v for k, v in row.items() if k != '_words'} for row in kept]


def _topic_key(row):
    return str(row.get('id', '')).rsplit(':', 1)[-1].removeprefix('ideal-')


def _same_topic(kept, key, words):
    """A waiting question already kept with the same key, or most of the same words."""
    if kept.get('state') != 'waiting': return False
    if key and _topic_key(kept) == key: return True
    mine = kept['_words']
    return len(words) >= 3 and len(mine) >= 3 and len(words & mine) / min(len(words), len(mine)) >= 0.5


def _first_asking(row, kept):
    """The row with its words, when it is the first asking of its topic; None when an earlier one takes it in."""
    key, words = _topic_key(row), _words(row.get('question'))
    same = next((k for k in kept if _same_topic(k, key, words)), None)
    if same is None: return {**row, '_words': words}
    same.setdefault('merged', []).append(row['id'])
    return None


# ---------------------------------------------------------------- writing

def _asked(report, m, card_rows, lang):
    """Every question of the inbox in one language, each asked once."""
    return tidy_decisions(decisions(m, card_rows, lang) + planned_ideal.decisions(report, lang) + ai_nodes.decisions(report, lang)
                          + planned_ideal.disagreements(report, lang))


def _recommends(recommendation, label):
    """Whether a recommendation opens with an option's label, as a whole word."""
    if not label or not recommendation.startswith(label): return False
    rest = recommendation[len(label):]
    return not rest or rest[0] in ' :،,.-–'


def _recommended(source):
    """The option a question recommends: the one it names, else the only option its recommendation opens with."""
    options = source.get('options', [])
    explicit = source.get('recommended_option')
    if explicit in {o['id'] for o in options}: return explicit
    recommendation = str(source.get('recommendation') or '').strip()
    matches = [o['id'] for o in options if _recommends(recommendation, str(o.get('label') or '').strip())]
    return matches[0] if len(matches) == 1 else None


def _decision_rows(report, m, card_rows, lang):
    """The inbox in the page's language, each row with the revision and recommended option of its English asking."""
    rows = _asked(report, m, card_rows, lang)
    by_id = {row['id']: row for row in _asked(report, m, card_rows, 'en')}
    for row in rows:
        source = by_id.get(row['id'], row)
        identity = {k: source.get(k) for k in ('id', 'question', 'options', 'blocks', 'asked', 'tool')}
        row['revision'] = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        row['recommended_option'] = _recommended(source)
    return owner_share.capped(rows, len(card_rows))


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


def _js_string(text):
    """A JavaScript single-quoted string literal holding `text` exactly."""
    return "'" + text.replace('\\', '\\\\').replace("'", "\\'").replace('\u2028', '\\u2028').replace('\u2029', '\\u2029') + "'"


def _write(folder, name, data):
    """name.json and its .js twin, each written whole and renamed into place; returns the JSON bytes. The twin, for a
    page opened from a file, hands the same JSON text to JSON.parse: a browser parses a large section that way much
    faster than the same data written as a JavaScript object literal."""
    text = json.dumps(data, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    blob = text.encode('utf-8')
    twin = f'(window.EAOS_STUDIO=window.EAOS_STUDIO||{{}})[{json.dumps(name)}]=JSON.parse({_js_string(text)});\n'
    for target, body in ((folder / f'{name}.json', blob), (folder / f'{name}.js', twin.encode('utf-8'))):
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
    attempt('decisions', lambda: _decision_rows(report, m, card_rows, lang))
    attempt('media', lambda: library_section.media(report, lang))
    attempt('system', lambda: system_map.system(report, card_rows))
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
    # Every section that draws a target says how its ideal was made: the rules only, or planned with a model (D10).
    stamps = planned_ideal.provenance_of(built.get('ideal'))
    attempt('change', lambda: change_map.change(m, card_rows, lang))
    for section, body in zip(('gaps', 'operations'), built.pop('change', None) or (None, None)):
        if body is not None: built[section] = body                    # no target: coverage says why
    attempt('functions', lambda: function_explorer.functions(report, card_rows, built.get('evidence') or ()))
    attempt('screens', lambda: screens_gallery.screens(built.get('journeys'), built.get('media'), (report / 'facts/entrypoints.json').is_file(), report))
    for section in ('functions', 'screens'):                         # nothing was read to build it from
        if built.get(section, False) is None: built.pop(section)
    def publish(section, data):
        problems = artifact_contracts.validate(data, contracts[f'studio-{section}'])
        if problems:
            errors.append({'section': section, 'error': '; '.join(problems[:5])[:300]})
            return
        blob = _write(folder, section, data)
        entries.append({'name': section, 'file': f'{section}.json', 'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob)})

    for section, body in _published(built, stamps): publish(section, body)
    # Last of the sections: it says which of the others were written, and what is not measured yet.
    attempt('coverage', lambda: coverage_section.coverage(report, built, [e['name'] for e in entries], list(errors), lang))
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
    return {'written': [e['name'] for e in entries], 'errors': errors}


def freshness(project, state):
    """(freshness, detail) at export time, from eaos/branches.py freshness: fresh, behind, rewritten, dirty, other_branch or
    unknown with its reason; eaos_updated when the scan was made by another EAOS. The live Studio asks the server again
    (GET /api/freshness) instead of trusting this snapshot."""
    from .. import branches
    if not project or not (state or {}).get('scanned'): return 'unknown', {'state': 'unknown', 'reason': 'not_scanned', 'behind': None, 'eaos_updated': False}
    found = branches.freshness({**(state or {}), 'project': str(project)})
    updated = bool((state or {}).get('scanned_with')) and state.get('scanned_with') != build_info.digest()
    detail = {'state': found['state'], 'reason': found['reason'], 'behind': found['behind'], 'eaos_updated': updated}
    if found['state'] == 'fresh' and updated: return 'eaos_updated', detail
    return found['state'], detail

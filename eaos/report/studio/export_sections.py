"""The Studio's contract v1 sections (eaos/report/studio/export.py writes them): meta, head, health, cards, story, plans
and the inbox (decisions), each built from the one model (eaos/analysis/presentation/model.py); a number is a measure {value, src},
and what was not measured is null, never 0."""
import hashlib
import json
from pathlib import Path

from ...core.contracts import owner_share
from ...facts.store import facts as facts_of
from ...core.language.words import impact_of
from ..documents.run import absences
from ...analysis.planning.cards import title_of
from . import blueprint_plan as build_plan
from .evidence import rel
from ...ai.ideal import planner as planned_ideal
from . import inbox
from ...ai.nodes import view as ai_nodes
from ...analysis.presentation import model as M

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
    counts = _language_counts(facts_of(report, 'graph_node'))
    total = sum(counts.values())
    stages = [{'id': name, 'title': name, 'state': STAGE_STATE.get((row or {}).get('status'), 'partial')}
              for name, row in (m['manifest'].get('stages') or {}).items()]
    lines = _source_lines(report)
    return {'languages': [{'name': name, 'files': count, 'share': round(count / total, 4)}
                          for name, count in sorted(counts.items(), key=lambda item: -item[1])],
            'files': measure(m['coverage'].get('source_files'), 'dossier.json#coverage.source_files', 'count'),
            'lines': measure(lines, 'facts/metrics.json#metric[scope=file].value.lines', 'lines'),
            'stages': stages}


def _source_lines(report):
    """The lines of every source file the check measured; None when it measured none."""
    return sum((row.get('value') or {}).get('lines') or 0 for row in facts_of(report, 'metric')
               if (row.get('value') or {}).get('scope') == 'file') or None


def head(m, scan, lang, stamp, fresh):
    freshness, detail = fresh
    counted, build = M.problem_counts(m), m.get('build')
    return {'scanned': scan, 'eaos': {k: stamp[k] for k in ('version', 'commit', 'digest')}, 'freshness': freshness, 'freshness_detail': detail,
            'verdict': build_plan.verdict(build, lang) if build else _verdict(m['score'], counted, lang),
            'next': build_plan.next_step(build, lang) if build else _next_step(counted['fixable'], m['rows'], lang),
            'not_run': [{'stage': r['stage'], 'status': r['status'], 'reason': r['reason'][lang], 'did': r['did']} for r in absences(m['manifest'])]}


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
                'cards': a['total'], 'accepted': a['accepted']} for area, a in s['areas'].items()]
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
    params = _params(claim, task)
    place = rel(params.get('place'))
    evidence = _fact_ids(task, claim)
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


def _params(claim, task):
    """The render parameters of a card's words: its claim's, else its task's."""
    return (claim.get('render') or task.get('render') or {}).get('params') or {}


def _fact_ids(task, claim):
    """The facts a card cites: its task's evidence, else its claim's."""
    return list((task.get('evidence') or {}).get('fact_ids') or claim.get('fact_ids') or [])


def resolution_of(row):
    """What the assistant decided for a card (eaos/analysis/planning/cards.py resolve): {kind: fix | owner, by, words, and the change of a
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
    return {'current': _story_current(target, current), 'target': _story_target(target), 'gap': gap, 'indicators': []}


def _story_current(target, current):
    """The story's today: the structure kept, and each component with its kind and files."""
    return {'summary': str(target.get('retained_structure') or '')[:600],
            'components': [{'name': c.get('name') or c.get('id') or '', 'layer': c.get('kind'), 'files': c.get('files') or 0}
                           for c in current.values()]}


def _story_target(target):
    """The story's target: its limits, and each component with its responsibility and layer."""
    return {'summary': str(target.get('limits') or '')[:600],
            'components': [{'name': c.get('name') or '', 'responsibility': c.get('responsibility') or '', 'layer': c.get('layer')}
                           for c in target.get('target_components') or [] if isinstance(c, dict)]}


def _gap_relation(row, comp):
    """What happens to a component of today: missing when the target adds what nothing of today is."""
    return 'missing' if row.get('gap') == 'missing' and not comp else RELATION.get(comp.get('relation'), 'modify')


def _gap_row(row, current, closed):
    comp = current.get(row.get('current_id')) or {}
    relation = _gap_relation(row, comp)
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
    state = _fix_state(card_rows, closed)
    fix = {'id': 'fix', 'title': 'خطة الإصلاح' if lang == 'ar' else 'Fix plan', 'kind': 'fix', 'parent': None, 'state': state,
           'goal': '', 'indicators': [], 'steps': steps,
           'progress': ratio(closed / total if total else None, 'ledger: (done + resolved) / every card in scope')}
    return [fix] + list(filter(None, [build_plan.plan(m.get('build'), lang)]))


def _fix_state(card_rows, closed):
    """The fix plan's state: closed when every card is, active once a card moved, else registered."""
    touched = any(c['state'] not in ('open',) for c in card_rows)
    return 'closed' if card_rows and closed == len(card_rows) else 'active' if touched else 'registered'


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
    review = _open_decisions(card_rows)
    resolved = any(c.get('resolution') for c in card_rows)
    # The assistant resolved the cards: only a real product choice it left to the person is asked, one card each.
    out = [q for q in map(_owner_question, review) if q] if resolved else []
    if review and not resolved: out.append(_investigations(review, lang))
    if m['target'].get('status') == 'REVIEW_REQUIRED': out.append(_target_question(m['target'], lang))
    return out


def _open_decisions(card_rows):
    """The cards not closed that need a decision."""
    return [c for c in card_rows if c['needs_decision'] and c['state'] not in M.CLOSED]


def _asked(report, m, card_rows, lang):
    """Every question of the inbox in one language, each asked once."""
    return inbox.tidy(decisions(m, card_rows, lang) + build_plan.questions(m.get('build'), lang) + planned_ideal.decisions(report, lang)
                      + ai_nodes.decisions(report, lang) + planned_ideal.disagreements(report, lang))


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


def decision_rows(report, m, card_rows, lang):
    """The inbox in the page's language, each row with the revision and recommended option of its English asking."""
    rows = _asked(report, m, card_rows, lang)
    by_id = {row['id']: row for row in _asked(report, m, card_rows, 'en')}
    for row in rows:
        source = by_id.get(row['id'], row)
        identity = {k: source.get(k) for k in ('id', 'question', 'options', 'blocks', 'asked', 'tool')}
        row['revision'] = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        row['recommended_option'] = _recommended(source)
    # the share caps what a check asks per problem; a blueprint's questions are the product's own, each asked
    owner_share.capped([row for row in rows if row.get('tool') != 'blueprint'], len(card_rows))
    return rows

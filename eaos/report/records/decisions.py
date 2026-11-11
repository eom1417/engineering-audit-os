"""studio/decisions.json: what waits for the person, each thing asked once (`eaos waiting`, `eaos answer`).

The rows: a real product choice the assistant left to the person on one card, else one question offering the
investigations; every open question of the AI nodes' last decisions; and, answered already, every card the rules
wrote and the assistant took out. Two askers' questions on one topic are one row (`tidy`).
"""
import hashlib
import json
import re
from pathlib import Path

from ...ai.nodes import framework as nodes_core
from ...ai.nodes.pipeline import NODES
from ...core.contracts import owner_share
from ...core.system.files import read_json
from .model import CLOSED

STOP = frozenset('هل في وفي فيه اذا إذا اللي عليه كل شي من على إلى الى او أو أم و ما ماذا كيف وين أين لما لها له '
                 'لهم هذا هذه نفس نفسه the a an of in on to is are do does or and what which how where should '
                 'we it'.split())
QUOTED = re.compile(r'[«“"]([^»”"]{2,60})[»”"]')
# What the assistant did to a card the rules wrote ({ar, en}) and where that left it: rejected, out of the plan; doubted
# and closed as not proven (eaos/analysis/repair/review.py).
REJECTED = ({'ar': 'رفضها', 'en': 'rejected it'}, {'ar': 'خارج الخطة', 'en': 'out of the plan'})
NOT_PROVEN = ({'ar': 'أغلقها لأنها ما ثبتت', 'en': 'closed it as not proven'},
              {'ar': 'مغلقة، ما ثبتت', 'en': 'closed, not proven'})


def _in(lang, ar, en):
    """The Arabic words for Arabic, else the English."""
    return ar if lang == 'ar' else en


def _slug(text):
    return re.sub(r'[^A-Za-z0-9_.:-]+', '-', str(text)).strip('-') or 'root'


# ---------------------------------------------------------------- the cards' questions

def _owner_question(card):
    """A real product choice the assistant left to the person on one card; None for any other resolution."""
    asked = card.get('resolution') or {}
    if asked.get('kind') != 'owner': return None
    options = [{'id': f'o{i + 1}', 'label': text} for i, text in enumerate(asked['options'])]
    return {'id': f"card:{card['id']}", 'question': asked['question'], 'recommendation': asked['recommendation'],
            'options': options,
            'recommended_option': next((o['id'] for o in options if o['label'] == asked['recommendation']), None),
            'blocks': [card['id']], 'state': 'waiting', 'answer': None, 'plan': 'fix', 'asked': '', 'tool': 'findings'}


def _investigations(review, lang):
    return {'id': 'investigations',
            'question': _in(lang, f'{len(review)} بطاقة تحتاج تحققًا قبل أي تغيير. هل يتولاها المساعد؟',
                            f'{len(review)} cards need checking before any change. Should the assistant take them on?'),
            'recommendation': _in(lang, 'نعم: يتحقق المساعد من كل بطاقة بدليلها ويعرض عليك ما يحتاج قرارك فقط.',
                                  'Yes: the assistant checks each card against its evidence and brings you only '
                                  'what needs you.'),
            'options': [{'id': 'yes', 'label': _in(lang, 'نعم', 'Yes')},
                        {'id': 'later', 'label': _in(lang, 'لاحقًا', 'Later')}],
            'blocks': [c['id'] for c in review][:200], 'state': 'waiting', 'answer': None, 'plan': 'fix',
            'asked': '', 'tool': 'findings'}


def _card_questions(card_rows, lang):
    review = [c for c in card_rows if c['needs_decision'] and c['state'] not in CLOSED]
    resolved = any(c.get('resolution') for c in card_rows)
    # The assistant resolved the cards: only a real product choice it left to the person is asked, one card each.
    out = [q for q in map(_owner_question, review) if q] if resolved else []
    if review and not resolved: out.append(_investigations(review, lang))
    return out


# ---------------------------------------------------------------- the AI nodes' questions and the cards set aside

def _node_questions(report):
    """Each open question of the AI nodes' last decisions, waiting for the person."""
    rows = []
    for node in NODES:
        last = nodes_core.last(report, node)
        if isinstance(last, dict) and last.get('node') == node.name: rows += _open_questions(node.name, last)
    return rows


def _open_questions(name, last):
    """The rows of the open questions of one node's last run."""
    return [{'id': 'node-' + nodes_core.short(f"{name}:{d['subject']}:{q['id']}", 120), 'question': q['question'],
             'recommendation': q.get('recommendation') or '',
             'options': [{'id': f'o{i + 1}', 'label': str(o)} for i, o in enumerate(q.get('options') or [])],
             'blocks': [], 'state': 'waiting', 'answer': None, 'plan': None, 'asked': last.get('at') or '',
             'tool': 'run_nodes'}
            for d in last.get('decisions') or [] for q in d.get('open_questions') or []]


def _set_aside(row, ar, done=REJECTED):
    """The answered row of one card the rules wrote and the assistant took out: rejected, or doubted and closed."""
    did, left = (words['ar' if ar else 'en'] for words in done)
    short = nodes_core.short
    question = (f"{row['card']}: القواعد كتبت البطاقة «{short(row.get('title'), 160)}» ومساعدك {did}. "
                f"{row.get('why') or ''}" if ar else
                f"{row['card']}: the rules wrote the card \"{short(row.get('title'), 160)}\" and your assistant "
                f"{did}. {row.get('why') or ''}")
    return {'id': f"disagree-{_slug(row['card'])}", 'question': short(question, 600),
            'recommendation': f'رأي مساعدك: البطاقة {left}' if ar else f"your assistant's view: the card is {left}",
            'options': [{'id': 'assistant', 'label': left},
                        {'id': 'rule', 'label': 'في الخطة' if ar else 'in the plan'}],
            'blocks': [], 'state': 'answered', 'answer': 'assistant', 'plan': None, 'asked': '', 'tool': None}


def _disagreements(report, lang):
    """The cards the assistant took out of the rules' plan (cards.json `set_aside`, and `doubted` that it closed)."""
    ar = lang == 'ar'
    cards = read_json(Path(report) / 'cards.json', {}) or {}
    return ([_set_aside(row, ar) for row in cards.get('set_aside') or []]
            + [_set_aside(row, ar, NOT_PROVEN) for row in cards.get('doubted') or [] if row.get('closed')])


# ---------------------------------------------------------------- each thing asked once

def _words(text):
    """The content words of a question, for telling two askings of one topic apart: Arabic's article and its letter
    variants folded, short and common words left out."""
    text = re.sub('[ً-ْ]', '', str(text or '').lower()).translate(str.maketrans('أإآةى', 'اااهي'))
    words = set()
    for word in re.findall(r'[\w./-]+', text):
        for prefix in ('وال', 'بال', 'لل', 'ال'):
            if word.startswith(prefix) and len(word) > len(prefix) + 2: word = word[len(prefix):]; break
        if len(word) > 2 and word not in STOP: words.add(word)
    return words


def tidy(rows):
    """Each thing asked once and only what the person decides: a card_triage question is a fact about the code the
    assistant checks itself (the `investigations` row already offers that), so it never reaches the person; two
    questions on one topic (_same_topic) become one, the first kept with the others' ids in `merged`."""
    kept = []
    for row in rows:
        if str(row.get('id', '')).startswith('node-card_triage:'): continue
        if row.get('state') == 'waiting': row = _first_asking(row, kept)
        if row is not None: kept.append(row)
    return [{k: v for k, v in row.items() if k != '_words'} for row in kept]


def _topic_key(row):
    return str(row.get('id', '')).rsplit(':', 1)[-1].removeprefix('ideal-')


def _source(row):
    """Who asks: the id's first part (node, disagree...). Each asker numbers its own topics."""
    return re.split(r'[-:]', str(row.get('id', '')), maxsplit=1)[0]


def _same_topic(kept, row, words):
    """Whether a waiting question already kept asks what `row` asks: the same key; or, from another asker, the same
    thing named in quotes («اقرأ أولًا»), or half the words of the shorter question. Two questions of one asker with
    different keys are two topics, however alike they read."""
    if kept.get('state') != 'waiting': return False
    if _topic_key(kept) == _topic_key(row): return True
    if _source(kept) == _source(row): return False
    if set(QUOTED.findall(kept.get('question') or '')) & set(QUOTED.findall(row.get('question') or '')): return True
    mine = kept['_words']
    shorter = min(len(words), len(mine))
    return shorter >= 3 and len(words & mine) >= shorter / 2


def _first_asking(row, kept):
    """The row with its words, when it is the first asking of its topic; None when an earlier one takes it in."""
    words = _words(row.get('question'))
    same = next((k for k in kept if _same_topic(k, row, words)), None)
    if same is None: return {**row, '_words': words}
    same.setdefault('merged', []).append(row['id'])
    return None


def _asked(report, card_rows, lang):
    """Every question in one language, each asked once."""
    return tidy(_card_questions(card_rows, lang) + _node_questions(report) + _disagreements(report, lang))


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


def decision_rows(report, card_rows, lang):
    """The rows in the check's language, each with the revision and recommended option of its English asking."""
    rows = _asked(report, card_rows, lang)
    by_id = {row['id']: row for row in _asked(report, card_rows, 'en')}
    for row in rows:
        source = by_id.get(row['id'], row)
        identity = {k: source.get(k) for k in ('id', 'question', 'options', 'blocks', 'asked', 'tool')}
        row['revision'] = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        row['recommended_option'] = _recommended(source)
    owner_share.capped(rows, len(card_rows))       # the share caps what a check asks per problem
    return rows

"""The person's inbox asks each thing once (eaos/studio/export.py writes it): two askers' questions on one topic are
one row, and a fact the assistant checks itself is never asked of the person."""
import re

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


def tidy(rows):
    """The inbox asks each thing once and only what the person decides: a card_triage question is a fact about the
    code the assistant checks itself (the `investigations` row already offers that), so it never reaches the person;
    two questions on one topic (_same_topic: as the planner and a screen reviewer ask about the phone's tab bar) become
    one, the first kept with the others' ids in `merged`."""
    kept = []
    for row in rows:
        if str(row.get('id', '')).startswith('node-card_triage:'): continue
        if row.get('state') == 'waiting': row = _first_asking(row, kept)
        if row is not None: kept.append(row)
    return [{k: v for k, v in row.items() if k != '_words'} for row in kept]


QUOTED = re.compile(r'[«“"]([^»”"]{2,60})[»”"]')


def _topic_key(row):
    return str(row.get('id', '')).rsplit(':', 1)[-1].removeprefix('ideal-')


def _source(row):
    """Who asks: the id's first part (ideal, node, disagree...). Each asker numbers its own topics."""
    return re.split(r'[-:]', str(row.get('id', '')), maxsplit=1)[0]


def _same_topic(kept, row, words):
    """Whether a waiting question already kept asks what `row` asks: the same key; or, from another asker, the same
    thing named in quotes («اقرأ أولًا»), or half the words of the shorter question. Two questions of one asker with
    different keys are two topics, however alike they read (EAOS, 2026-10-14: two of the planner's questions ending in
    one sentence about the intake were read as one)."""
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

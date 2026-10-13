"""The owner's share: at most one decision in ten cards is the person's (AGENTS.md "Few cards, the assistant decides").
Anything simple or technical the assistant decides itself; past the share, its own recommendation is taken.
"""
OWNER_SHARE = 0.10          # at most this share of the cards asks the person (at least one)
CARD_SEVERITY = {'critical': 5, 'high': 4, 'medium': 2, 'low': 1, 'info': 0.5}


def cap_owner(resolved, cards):
    """At most OWNER_SHARE of the `cards` ask the person: the questions that matter most (severity x reach) stay
    `owner`; the others become `fix` with the assistant's own recommendation, saying so. Changes `resolved`; returns
    the cards it turned."""
    asked = [card for card, r in resolved.items() if r['resolution'] == 'owner']
    room = max(1, int(cards * OWNER_SHARE))
    if len(asked) <= room: return []
    weight = lambda card: (-CARD_SEVERITY.get(resolved[card].get('severity'), 1) * (1 + (resolved[card].get('reach') or 0)), card)
    turned = sorted(asked, key=weight)[room:]
    for card in turned:
        row = resolved[card]
        row.update(resolution='fix', change=row['recommendation'], capped=True,
                   note=(f'it would have asked you about "{row["question"]}"; with more questions than one in ten cards, '
                         f'this one mattered less (severity x reach), so its own recommendation is taken'))
    return turned


def capped(rows, cards):
    """At most one waiting question in ten cards , from every source: the ones only the person can
    answer (no recommendation) and the target's approval stay; past the cap the rest take their recommended option,
    answered by the assistant, as triage does for cards (cap_owner)."""
    waiting = [row for row in rows if row.get('state') == 'waiting']
    room = max(1, int(cards * OWNER_SHARE))
    ranked = sorted(waiting, key=lambda row: (row.get('recommended_option') is not None, row.get('id') != 'target-architecture'))
    for row in ranked[room:]:
        if row.get('recommended_option'): row.update(state='answered', answer=row['recommended_option'])
    return rows

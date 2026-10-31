"""What each kind of card is (a claim's `render.key`), said once; the ledger, the remediation, the debt register and the words
read it, and a key not here is refused when a claim is built (eaos/analysis/claims/ledger.py errors).

A kind's subtypes (an engine cluster's kind, a layer finding's rule) are not kinds: they vary inside one, in the card's params.
What a kind's detector, fix or words do with them stays with their owner; this says only which of them the kind has.
"""
from typing import NamedTuple


class CardKind(NamedTuple):
    detector: tuple = None       # (the detector's prefix, the param that names it): judged per subtype, else by the key alone
    own_pattern: bool = False    # its remediation pattern is its key, with or without a probe
    own_fix: bool = False        # the card carries its own fix, in its params
    own_text: bool = False       # the card carries its own words in both languages, in its params
    debt_category: str = None    # the debt category of a kind that carries its own severity


_SAYS_ITSELF = {'own_fix': True, 'own_text': True}
KINDS = {
    **{key: CardKind() for key in (
        'broken_code', 'cochange', 'cycle', 'dead_code', 'dead_code_review', 'duplicated_rule', 'external_write', 'hotspot',
        'large_module', 'load_blocker', 'mutable_global', 'policy', 'redundant_work', 'security_weakness', 'trace_gap', 'untested',
        'vulnerable_dependency')},
    'engine_cluster': CardKind(detector=('engine_cluster', 'kind')),
    'layer_finding': CardKind(detector=('layer', 'rule'), **_SAYS_ITSELF),
    'repository_finding': CardKind(detector=('repository', 'rule'), **_SAYS_ITSELF),
    'logic_flaw': CardKind(detector=('logic', 'class'), **_SAYS_ITSELF),
    'experience_difficulty': CardKind(detector=('experience', 'kind'), **_SAYS_ITSELF),
    'real_data': CardKind(detector=('real_data', 'kind'), **_SAYS_ITSELF),
    'old_engine': CardKind(detector=('old_engine', 'kind'), own_pattern=True, debt_category='dead_code', **_SAYS_ITSELF),
    'data_keeping': CardKind(detector=('data_keeping', 'kind'), own_pattern=True, debt_category='data', **_SAYS_ITSELF),
    'one_source': CardKind(detector=('one_source', 'kind'), own_pattern=True, debt_category='maintainability', **_SAYS_ITSELF),
    'person_rule': CardKind(own_pattern=True, debt_category='reliability', **_SAYS_ITSELF),
}
_NOT_REGISTERED = CardKind()


def card_kind(key):
    """What a kind is. A key not registered reads as a plain card, so a project saved by an older EAOS still reads."""
    return KINDS.get(key, _NOT_REGISTERED)

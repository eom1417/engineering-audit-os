"""The whole system in layers (M6): a check reads every project as the layers a professional firm reads, by default.

    run(target, out)          the static part: the layer map, the boundaries, what ships to the browser, every endpoint
                              and its guard, the data layer's rules, where the business rules live, operations and tests;
                              writes <out>/layers.json (what people and the Studio read) and the `boundaries` fact set
                              (what the claims make cards of: eaos/analysis/claims/from_layers.py)
    amend(out, live)          the live part's findings (the data rules tried, the API tried, the built output of the
                              isolated copy: eaos/pipeline/runners/layers_live.py) joined to the same two

The record and its fact set: layers/record.py. Nothing is written into the project; a placement EAOS is unsure of becomes
a question, never a finding.
"""
from .record import RECORD, amend, check, depcruise_rules, facts_of, introduced, read, run  # noqa: F401

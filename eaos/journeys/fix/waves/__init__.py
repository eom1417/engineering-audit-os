"""Fix a batch of plan cards at once, and hand the result over as a branch (NS9.T4).

One card at a time behind every gate costs about twelve minutes a card; the first milestone of a real project
holds more than a hundred. So a batch (a wave) is executed together, and the expensive gates run once:

  1. The candidate: a clone of the authorised commit (eaos/journeys/fix/execute.candidate); its branch is handed over as
     eaos/<branch>/wave-<n>, or the name the person gave in the fix preview.
  2. Each card: its codemod, or the assistant's edit (eaos/journeys/execute), committed alone, then the quick gate: no
     new broken code. A card that breaks something is taken back at once (its commit is dropped).
  3. The acceptance of every card from one collection of facts (batch_acceptance, waves/acceptance.py); a card whose
     problem is still there is dropped the same way.
  4. The project's own checks and the behaviour lock, once for the whole batch. When they fail, the batch is
     split in half until the card responsible is found (culprits), and only the cards that pass together stay.
  5. runtime/execution.json gets one row per card; the kept commits are the branch.

apply() fetches that branch into the person's project without touching their current branch or files;
undo() deletes it again while it is not merged. Nothing else in the project is written.

A wave is the flow `fix` of the live map (FLOW), drawn from the state at each save (draw, called by guided.save) to
<runtime>/progress/fix.jsonl: each card a step of `change`, then the end checks as they are reached, then the handover
(waves/live_map.py). The cards a batch takes: waves/cards.py; the batch itself, its gates and its branch: waves/batch.py.
"""
from .batch import (BATCH_ENGINES, GatesFailed, apply, change, commit, culprits, declared_screens, drop_last,  # noqa: F401
                    edit_gates, failing_output, finish_batch, gates, merged, open_batch, rebuild, undo, without)
from .cards import SIZE, next_batch, plan, ready_cards, too_early, with_prerequisites  # noqa: F401
from .live_map import FLOW, publish, saved  # noqa: F401

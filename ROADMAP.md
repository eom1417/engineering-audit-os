# EAOS roadmap

The only plan of EAOS. A finished item leaves this page and goes to `CHANGELOG.md` with the test that proves it.
Each fix starts with one small test that reproduces the real incident; one fast journey test (fixture repository,
fake assistant: check → change → check again → fix three cards with one failing → accept) runs after each group.

## Now

- **The final proof**: one full check of EAOS from the Studio with the assistant, and one real fix batch of 5–10 ready
  cards on the trial project; then the owner's review.

## Known imperfections (from the fifteen fixes, 0.0.8)

- A fix run that kept nothing ends as `failed` with the reason; there is no separate "nothing changed" state.
- Decisions are merged by a word-overlap heuristic; it is not exact.
- On EAOS's first check its Studio has no report data yet, so live setup refuses the empty page (later checks use the
  previous report); no English screen pictures are taken yet.
- Batches and merged commits made before 0.0.8 carry title keys and do not match the new uid keys.

## Then

- A second slimming pass inside the largest kept modules (`human_report.py`, `guided.py`, `dossier.py`): the CLI
  journey and the MCP journey share one implementation.
- `1.0.0` only when the owner declares it.

# Executive summary

> One page: status, the three biggest risks with impact, the investment, and what happens if we do nothing.

## Status
- REVIEW_REQUIRED · 573 live claims · 308 task cards · 530 proposed moves
- ✗ single source: current 0.111, target 0.0, gap 0.111
- — minimal path: not measured (target 0.0, — gap)
- ✓ honest boundaries: current 0, target 0, gap 0
- ✓ data owners: current 0, target 0, gap 0
- ✗ verifiable paths: current 0.08, target 0.0, gap 0.08
- ✗ understandable units: current 242, target 0, gap 242

## Top three risks
1. **CLM-271** (CONFIRMED) — 2 symbols share the same structure up to identifier names (internal/facts/accessors.go:81 .method_declaration, internal/facts/accessors.go:98 .method_declaration)
   - impact: Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.
   - falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.
   - detail: DECISION-BRIEF.md
2. **CLM-012** (CONFIRMED) — 16 symbols share the same structure up to identifier names (internal/explainers/deadmethods/deadmethods.go:349 .function_declaration…
   - impact: Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.
   - falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.
   - detail: DECISION-BRIEF.md
3. **CLM-569** (CONFIRMED) — 328 functions perform the same ordered sequence of calls (internal/clientspec/clientspec.go:None, internal/conformance/conformance.go:None…
   - impact: The same orchestration is maintained in several places at once.
   - falsifier: Evidence that the shared order is coincidental rather than one orchestration copied.
   - detail: DECISION-BRIEF.md

## Investment
- 308 task cards in the plan · 530 transform stages
- 530 canonicalize, 0 eliminate_redundancy

## What if we do nothing
Every indicator gap stays as-is, and 573 live claims and 530 pending moves wait for a decision. Nothing changes automatically.

## Limits
- The executive page is a single screen; it cites the underlying artifacts, not their detail.
- Risks are the claim ledger's top-ranked live claims, in the ledger's own order; where the ledger is empty the page falls back to the largest duplication moves and says so.
- The "what if nothing" cost is the predicted delta × a stated engineering rate, not a quote.
- The page is regenerated whenever the underlying artifacts change; it is never the source of truth.

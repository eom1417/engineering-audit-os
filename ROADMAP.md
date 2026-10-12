# EAOS roadmap

The only plan of EAOS. A finished item leaves this page and goes to `CHANGELOG.md` with the test that proves it.
Each fix starts with one small test that reproduces the real incident; one fast journey test (fixture repository,
fake assistant: check → change → check again → fix three cards with one failing → accept) runs after each group.

## Now: fifteen fixes

### A. State that tells the truth
1. **A stale fix batch.** A batch whose base is not the current code is retired by one helper, called by `status`,
   `fix_start` and after a check. A failed `fix_finish` leaves the batch as it was; `tried` stores stable keys.
2. **Cards keyed by title.** Cards are keyed on the observation uid. A problem no longer found is deleted, never
   "resolved"; progress is cards fixed and merged; one count on every page.

### B. Fixing from the Studio
3. The fix verb's tools include `fix_abandon`, `findings` and `plan`.
4. The person's answer acts; a direct action is not blocked by a run waiting for the person.
5. A batch skips a failing card with its reason and finishes the rest; a run that changed nothing says so.
6. The branch in the fix preview: build on the analysis branch, deliver as `eaos/<branch>/wave-N`, merge into the
   branch open in the project folder, all editable; the base commit pinned in the confirm token.

### C. A true report
7. The assistant's verdicts applied once, right after triage and before ranking, readiness, plan, report and ledger:
   rejected removed with its reason; doubted re-judged with the measurement facts and never auto-fixed; only real
   human decisions reach the person; the ideal planner's decisions feed the target and the gaps.
8. Complexity: no codegraph metric as a finding; corroboration needs a value over a threshold; severity in ranking;
   per-function hotspots, one card per hotspot.
9. Dead code: files named by a path literal, and package data, are reachable.
10. Target: complexity alone means modify, not rebuild; CLI features grouped by subcommand; `tools/` is dev tooling.
11. Plain labels and areas, real sections and sizes, design cards deduplicated, C4 before the reports,
    minified and generated files excluded in any project.

### D. The Studio
12. Markdown and tables rendered in run results and the assistant's messages (the docs reader's renderer).
13. Branches: only the person's work branches and the one they work on, grouped "this computer" / "GitHub", plain
    words, cleanup in a sheet (merged branches and stale worktrees deleted; unmerged work kept as `archive/<name>`).
14. Decisions: no duplicates, no question the machine can answer, one waiting count.

### E. Real screen pictures
15. Live setup refuses an empty "no data" page as success; EAOS's own Studio served with its data; dark pictures
    taken; names from the `#/route`; the re-scan sheet follows the scan run.

## Then

- The final proof: one full check of EAOS from the Studio with the assistant, and one real fix batch of 5–10 ready
  cards on the trial project.
- A second slimming pass inside the largest kept modules (`human_report.py`, `guided.py`, `dossier.py`): the CLI
  journey and the MCP journey share one implementation.
- `1.0.0` only when the owner declares it.

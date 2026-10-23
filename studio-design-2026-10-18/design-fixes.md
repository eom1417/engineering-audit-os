# Design fixes after Gate D (lead, 2026-10-18)

All five required items from Abdullah's review (`gate-design.md`) are closed, plus the quick minor notes. I re-ran every
check on the final files.

## 1. Never four
- **Redo from a stage (CHK-10) now takes 3 presses when idle.** Status's "About this check" fold lists the stages that
  did not plainly finish (four partial, one skipped).
  - Path: fold (1) → a stage (2) → "Redo from here…" (3).
  - "One stage in detail" (CHK-09) now takes 2.
- **Expert batch tools (FIX-16) take 3 presses.**
  - Path: More work… on Status (1) → the Expert group (2) → a tool (3).
  - The launcher's search also finds them: typing "batch" lists every batch tool, so More work… (1) → the tool (2).
- **Other shortcuts added:**
  - "Close this batch…" in Where things stand (FIX-14: 2 presses).
  - A "Questions from runs" row on Waiting that opens the run-question examples (DEC-02 to DEC-05, FIX-08: 2).
- **Claims corrected:** every claim the measurement disproved was corrected; 22 designed counts differed (see item 2).

## 2. A measured press table
- **`prototype/tools/presses.cjs`** has a recipe for each of the 198 IDs.
  - It presses from Status at 390 and 1440, in Arabic and English, counts the presses and asserts the end state.
  - State-dependent features start on Status with their `?state=`: `running`, `fixing`, `resume`, `signin`, `offline`,
    `reconnecting`, `newcheck`, `empty`, `loading`.
  - Pages that open instead of Status (folder chooser, export chooser, no key, read-only) start there.
  - Counting rule D46: the press that opens a preview counts; the governance tick and act are not pressed (+c).
  - It writes `tools/presses-results.json`, including the labels actually pressed.
- **`tools/clicks.py`** now generates the IA §10 table from those results, with a "Measured presses" column.
  - It fails on any missing feature, failed run, or count above 3.
- **Result:** 198 of 198 pass in all four runs. None is above 3. Worst case: 0 presses → 19 features, 1 → 36, 2 → 89,
  3 → 54.

## 3. 44 px targets on the phone
- Under 1024 px, these grow to 44 px: `.btn--sm`, segmented controls, filter and operation chips, summaries (including
  the run timeline folds), inputs, document contents links and the banner actions.
- Small stand-alone links keep their look and get an invisible 44 px hit area: section links, timeline times, "Open the
  stage", "Ask again", run ids, health area names, card titles.
- Map nodes carry a 22 px transparent ring.
- New audit `tools/targets.cjs`: 0 controls under 44 px at 390, in Arabic and in English.

## 4. axe at zero
- Code blocks and wide tables are keyboard-focusable named regions. The core sets this after every render.
- The run page's progress bar has a name.
- `aria-pressed` was removed from view-switching links (Components, Code paths, Unseen, run filters); they use
  `aria-current` instead.
- Search results are labelled `role=group` blocks, with no headings inside a list role.
- New `tools/axe.cjs`: 248 screen and sheet combinations, 0 violations.

## 5. A light global search (D48)
- **What the box searches:** only small indexes.
  - Places: every screen title, in both languages.
  - Decisions, problems, actions, runs, branches, plan steps.
  - Your app's screens, code paths, gaps, components.
  - Documents by title, path and headings.
- **What it never loads:** the functions section, or the library text.
- **"Search deeper" rows:**
  - "Search functions for '…'" opens Functions with the query.
  - "Search the check's records for '…'" covers full text.
  - "Ask your assistant".
- The scope is written in IA §5 and DESIGN-SYSTEM (the Search or ask component).

## Minor notes
- **Live strip:** hidden on a page that already shows the same run (its run page, Activity's Now, the sign-in pages).
- **Branch page:** one "Merge into develop…" only.
- **Direct control:** its "never" list now names every owner-only act.
- **Accept:**
  - It offers only the batch's own branch, locked, with the reason (G8).
  - Its "From the terminal" fold shows `eaos accept --into develop`.
- **Reject:** its "From the terminal" fold shows `eaos undo` (D49).
- **Dark mode:** the risk tag in dark mode uses a lighter step.
- **Project menu:** lists other projects (PJS-02).
- **Carried into the build, not done in the prototype:** splitting code per place and dictionaries per language within
  the first-page budget.

## Checks re-run on the final files
- `tools/sweep.cjs`: 984 pages, 0 issues.
- `tools/sheets-sweep.cjs`: 836 sheets, 0 issues.
- `tools/targets.cjs`: 0 controls under 44 px.
- `tools/axe.cjs`: 0 violations.
- `tools/presses.cjs` with `tools/clicks.py`: 198 of 198 measured, none above 3.
- `shots/final/` refreshed: 20 screens at 390 and 1440, in Arabic light and Arabic dark, 80 pictures.
- IA.md, DESIGN-SYSTEM.md, `prototype/README.md` and SCREENS.md are updated.

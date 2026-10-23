# Gate D: the committee's design (Abdullah, 2026-10-18)

## Verdict: CHANGES REQUIRED (5 items, quick re-check)
**Not a redo.** The design is independent, governance-safe, feasible and professional. Five concrete gaps must close
before the owner sees it.

## What I verified myself
- **The committee's own tools:**
  - `sweep.cjs`: 984 pages, 0 issues.
  - `sheets-sweep.cjs`: 824 sheets, 0 issues.
  - `clicks.py`: 198/198, none above 3. But `clicks.py` is a hand-written table, not a measurement.
- **Real presses in a headless browser at 390 and 1440:**
  - About 65 features pressed from Status by their visible labels, with the end state checked.
  - An address-level walk from Status to depth 3: 1,838 addresses at 390, 2,627 at 1440, mapped against every
    `SCREENS.md` row.
  - Found: **CHK-10 "Redo from a stage" takes 4 presses** when nothing runs (Activity → the last check → Open the stage
    → Redo from here…). **FIX-16 Expert batch tools takes 4** (the launcher's Expert group is a fold). CHK-09 is 3,
    not 2.
- **Accessibility:**
  - axe-core over 27 screens and sheets × 390/1440 × Arabic/English × light/dark: **no contrast violation**, 4 rule
    failures (item 4).
  - Keyboard focus is visible everywhere; the confirm sheet traps Tab; the act button stays locked until the tick.
  - A touch-target audit at 390 found many controls under 44 px (item 3).
- **Governance (read from the live DOM): never weakened.**
  - Owner band on every owner-only act.
  - Free preview band on every preview.
  - The tick and the named act button sit together, with focus on Cancel.
  - Protected branches are listed, locked, with the reason (accept, merge, fix delivery).
  - "Accept it by itself" is owner-only, never into a protected branch, and previews again when changed.
  - Merging without recorded checks needs an explicit acknowledgement (G11); a recovery point is kept on delete
    (G10).
  - Free text never counts as consent; saving an answer changes nothing.
  - Direct control lists its scope and what it never does.
- **Independence from the old Studio:**
  - A grep of every committee file for old Studio paths, page and component names, addresses and screenshots found
    nothing except `studio/src/...` file paths inside the sample data.
  - The structure differs from the old Studio (Status / Waiting / Problems / Activity / Understand).
- **Feasibility:** the back end provides every promise except a global search over functions and document text
  (item 5). Checked in the code:
  - "fetched N ago": `BranchControl.last_fetch`;
  - "answers at once": `Actions.create`'s reading path;
  - cost shown only at the end, and no money estimate before a run;
  - no push notifications;
  - the library read per document.
- **Quality (as the owner will feel it):** calm, finished and consistent in Arabic and English, light and dark, phone
  and desktop.
  - One accent for "your move"; the sentence comes before the numbers; folds are closed by default.
  - The governance moments are explicit and quiet.
  - Professional, not a wireframe.

## Items (re-checked with the same tools)
1. **Never four.**
   - Make Redo from a stage reachable in 3 presses or fewer when idle, for example by listing the last check's stages
     on Activity or in Status's "About this check".
   - Make the Expert batch tools reachable in 3 or fewer: an open section, or found by the launcher's search.
   - Correct every claim the measured run disproves.
   - Counting rule (D46): from Status; the press that opens a preview counts; the governance tick and act do not.
2. **A measured press table.** A recipe that presses from Status for all 198 IDs at 390 and 1440 and asserts each end
   state (state-dependent ones from their `?state=`). It writes results, and the IA table is generated from them.
3. **44 px targets on the phone** for every control outside running text:
   - `.btn--sm` (36 px): row Fix…, Pause/Stop, Open the fact/step, Remove from the line, Fix them all…/Select them/
     Select a group, Ask's Send/Preview…, the sign-in keys;
   - segmented controls (40 px);
   - stand-alone links of 20–27 px: "Open the list", "All runs (10)", "Open the stage", "Refresh", "Ask again",
     timeline times, Waiting's section links.
4. **axe at zero.**
   - Make `.code` and `.ac-table-wrap` scrollable regions keyboard-focusable and labelled.
   - Give the run page's `.ac-bar` progressbar a name.
   - Remove `aria-pressed` from the plain button in Components (use a real toggle, or `aria-current`).
   - Search results: groups with `role=group` and a label, not h3 headings inside a list role.
5. **A light global search (D48).**
   - Never load the 4.6 MB functions section or the library text from the global box.
   - Add a "Search functions for '…'" row that opens Functions.
   - Find documents by title, path and headings; full text goes through "Search the check's records".
   - Write the scope in IA §5 and DESIGN-SYSTEM.

## Minor notes (pass; carried into the build)
- Hide the live strip on a page that already shows the same run.
- Show one "Merge into develop…" on a branch page, not two.
- Direct control's "never" names every owner-only act.
- "From the terminal" shows `eaos undo` for Reject (D49).
- Accept offers only the batch's own branch (G8).
- The build splits code per place and dictionaries per language, with the first page inside the Studio budget
  (≤240 KB gz, target 200).
- Nit: the dark-mode risk tag in the check preview.

Decisions D46–D49 and the full evidence are in
`/workspace/eaos-work/studio-governance/dossier/ledger.md` (job 2). My scripts are in
`/workspace/eaos-work/studio-governance/abdullah/design/`.

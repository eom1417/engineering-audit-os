# Gate D re-check: the committee's design (Abdullah, 2026-10-18)

## Verdict: APPROVED. The design may go to the owner.

All five Gate D items are closed. I verified each one with my own tools on the final files.

| Item | What I checked myself | Result |
|---|---|---|
| 1. Never four | My press walk at 390 and 1440 (`abdullah/design/paths.cjs`, `p4.json`) | Closed. CHK-09 is 2 presses (About this check → a stage). CHK-10 is 3 (→ Redo from here…, preview open). FIX-16 is 3 (More work… → Expert → a batch tool), or 2 through the launcher's search. FIX-14, DEC-02 and PJS-02 are 2 each. |
| 2. Measured table | Ran `tools/presses.cjs` myself on a scratch copy, 4 runs (390 and 1440, Arabic and English) | Closed. It clicks visible elements and asserts end states. Result: 198 of 198 passed, none above 3. The IA §10 table is generated from these results. |
| 3. 44 px on the phone | My hit-area test: 4 points 21 px from each control's centre, over 31 screens and sheets at 390, Arabic and English | Closed. Every control outside running text passes, except the branch and freshness chips: the next line overlaps their extended area at the bottom, leaving about 41 px. Carried as a note. |
| 4. axe at zero | My `axe.cjs`: 27 screens and sheets × 2 widths × 2 languages × 2 themes | Closed: 0 violations (Gate D had 4 failing rules). |
| 5. Light search | Read the global index in `app.js`, then pressed through it | Closed. The index never touches functions or library text. "Search functions for '…'" opens `#/understand/functions?q=…`; "Search the check's records" and "Ask your assistant" are offered. The scope is written in IA §5 and DESIGN-SYSTEM. |

I also spot-checked the minor notes:
- one "Merge into develop…" on a branch page;
- the live strip hidden on the page of the same run;
- the full "never" list for direct control;
- Accept locked to the batch's own branch, with `eaos accept --into develop`;
- Reject shows `eaos undo`.

Fresh phone screenshots show no regression.

The quick redo lists only the stages that did not plainly finish. Redoing a stage that finished normally still takes
4 presses through "Show the stages". I accept this: redo is for partial, failed or skipped stages.

## Carried into the build gate
1. The chips' 44 px hit area must not be overlapped by the line below.
2. Split code per place and dictionaries per language, with the first page inside the Studio budget (≤240 KB gzipped,
   target 200).
3. Run the prototype's own measured recipes against the real Studio, as gates: `presses.cjs` (198 of 198, never four),
   `axe.cjs` (0 violations), `targets.cjs` / hit area (44 px).

## Next, by the owner's word only
1. The owner reviews the design.
2. The build starts only after the owner approves it: a new Studio implementing this design, wired to the existing
   back end.
3. The old Studio is deleted at the owner's word, after the new one has been tried.

The full record is in `/workspace/eaos-work/studio-governance/dossier/ledger.md` (job 2, "Gate D re-check").

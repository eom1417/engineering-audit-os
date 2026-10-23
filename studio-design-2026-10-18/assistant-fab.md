# Floating assistant (the owner's request, 18 Oct)

## What it is
- **The button:**
  - On every screen, except the full Ask view and the opening pages; on those, Ctrl/Cmd+I does nothing.
  - Phone: a 52 px circle at the end corner above the tab bar. It rises above the live strip and the selection bar.
  - Desktop: a labelled pill at the end corner of the content area.
  - Keyboard: Ctrl/Cmd+I opens and closes it; Esc closes it.
- **The panel opens in place:**
  - Desktop: a 400 px side panel. From 1280 px the page reflows beside it and stays usable; split views fold to one
    column. Below 1280 px it overlays the end side.
  - Phone: a bottom sheet. Tab stays inside it, and the keyboard does not pop up on open.
- **One conversation:** `assets/assist.js` shows the same conversation as `#/ask` (shared through `EAOS.askAPI` from
  `ask.js`). That includes:
  - what it read, and the answer as it is written;
  - proposals that open their normal previews;
  - depth per turn;
  - the cost footer;
  - the owner-only "Let it act for an hour".
- **Getting there:**
  - "Open the full view" goes to `#/ask`; Search or ask still lists the full view.
  - The box's "Ask your assistant: …" opens the panel and asks the question.
- **Context:** the page it was opened from is a removable chip (a problem, a run, a branch, a map node, a document, a
  place), with three suggested questions for that page. Answers use the context; for example, on TASK-006 or R-12 they
  speak about that item.
- **States:**
  - ready;
  - thinking (the answer streams; Send waits);
  - failed (Retry);
  - no ready assistant (why, `claude login` with Copy, Assistants and cost);
  - offline copy (explains, offers "How to open it live").
- **Address:** `?ask=1` opens it on any screen.

## Check durations corrected
The sample's "last check took 81 minutes" was an invented example. It is replaced everywhere (`data.js` through
`build-data.py`, the run R-11 and its timeline, the estimate basis, Status's More work, IA) with the measured facts:
- A complete check of this project without the assistant took 13 minutes; stages run side by side as the machine allows.
- The security path alone takes 3 minutes; the code path 12.
- With the assistant it takes longer: its stages run one at a time in normal mode, while speed mode runs several
  assistants at once.

The last check shows 13 minutes, and the check preview estimates 11 to 15 minutes for a complete check (security 3–4,
code 10–14).

## Docs
Updated:
- IA §5, §6 and §7, and the CHT rows (now 1 press to open);
- DESIGN-SYSTEM (the component);
- SCREENS.md (C-08);
- README.

## Checks (all re-run)
- `tools/presses.cjs` with `tools/clicks.py`: 198 of 198 measured at 390 and 1440 in Arabic and English, none above 3.
  CHT-01, -02, -03 and -07 take 1 press.
- `tools/sweep.cjs`: 1,048 pages, 0 issues.
- `tools/sheets-sweep.cjs`: 880 sheets, 0 issues.
- `tools/targets.cjs`: 0 controls under 44 px in Arabic and English; the button never overlaps a primary action, a bar
  or the live strip (checked at the top and bottom of every screen, 390 and 1440).
- `tools/axe.cjs`: 288 combinations, 0 violations.
- `shots/final/`: `21-assistant-status-*` and `22-assistant-problem-*` at 390 and 1440, Arabic light and dark. The
  status, Activity and check preview shots were refreshed for the new durations.
- R-11 made consistent: a complete check WITHOUT the assistant (13 min, no tokens or cost, its seven assistant stages skipped "without the assistant" and redoable with it; Assistants and cost says so; estimates unchanged); sweep 1,048 pages 0 issues, presses 198/198 none above 3.

# Decisions: the archive

The reasoning behind choices of done milestones, moved from `docs/DECISIONS.md` as it was written, with its date. Not
read at the start of a session; what still binds is in `docs/DECISIONS.md`.

## 2026-10-25
- **M5 (assistant's decisions)**:
  - The browser agent is EAOS's own (`live/agent.py`): `browser-use` and `Stagehand` need a model key of their own,
    which EAOS never holds (it works through the person's assistant), so they cannot be measured here; the Playwright
    MCP's steps are references that live one page only, not replayable without the assistant. A step names a control by
    its role and name, so a replay finds it again; a step that deletes, pays, sends or signs out is refused in the
    browser. Explored once with the assistant's smallest model (15 steps, 8 minutes at most), replayed free after.
  - Screens are found in layers before any assistant: the pages a framework's files make, the code's hash routes and
    menus, a server's GET routes (kept only when they answer with a page), Django's URL configuration with its
    includes; a page the code names is a page of its own, never folded into a "template" with its siblings.
  - Sign-in by rules first: the app's own sign-in page, after its own sign-up page, with the run's own account (`demo`,
    a password the run chooses); Django's account by its own command. The assistant comes after, for a test user per
    kind; the person last, told what EAOS tried.
  - The lock and the walk-through run once with the run's one session over every page, then as each kind of user over
    that kind's own pages (its recording beside the others', `__screenshots__/@<kind>`).
  - The corpus' CoreUI expected `/#/login` and `/#/404`; its pinned commit names them `/#/authentication/login` and
    `/#/error-pages/404`: the expectation was corrected, not the check.
  - M5.1-M5.3 were built as one branch (`dev/m5-seeing`, a commit per card): the complexity law's split of M5.1's
    functions came with M5.2's, and each card's proof is the same corpus run.
- **One plan (owner)**: `ROADMAP.md` is the only place that holds a plan, a backlog or a status; it runs M-1 to M10,
  numbered in the order the milestones run (M-1 to M4 done; M5 seeing any app, M6 the whole system in layers, M7
  reliable fixes, M8 interfaces and EAOS clean, M9 intelligence and the final proof, M10 simulated users). It replaces
  the numbering of 2026-10-23 (old M6-M9 are now M7-M10, the layers planned as M10 this morning are M6); the entries
  below were renumbered with it. Merged into it and then deleted: the six plans left in assistants' accounts
  (2026-09-29 to 2026-10-23), the open items of `/workspace/HANDOFF.md`, and `/workspace/eaos-hub` (the old tracking
  page, frozen since 2026-10-08 at version 0.0.2, its own plan of 187 cards and steps NS1-NS35). Of the hub's ideas
  never carried over: verification after a change became M7.5, production readiness M6.9, "who reads this data" M6.5,
  independent proof M9.3, the project's laws as gates M6.2; dropped: chaos testing (the k6 baseline and M6.9 cover
  what a person can act on), an archive before delete (the fix branch and git keep everything), protecting official
  outputs as files (a feature of one project, not of EAOS), the "initiative engine" (no definition left to build).

- **M4.6 (assistant's decision)**: a split of the Studio's code is proved by drawing: `console/tools/same.cjs` crawls
  every screen and sheet of the working Studio, draws each with the code before and after (the code swapped in the
  browser, the server and its data the same) and refuses any difference; with it the 48 functions were split, not
  listed.

## 2026-10-24
- **M4 (assistant's decisions, the owner may change them)**: a gap the person chose (no consent to run the app, a path
  not followed, sign-in declined) is said but never a big red gap; repair or rebuild is decided by the target (rebuild
  when it rebuilds or deletes half of today's files), the hours shown beside it by a rough rule said as such; the
  Studio's 48 complex functions are listed under the laws (may only shrink) rather than split blind, since no test
  checks the screens.

# Decisions: the archive

The reasoning behind choices of done milestones, moved from `docs/DECISIONS.md` as it was written, with its date. Not
read at the start of a session; what still binds is in `docs/DECISIONS.md`.

## 2026-10-25
- **M6 (assistant's decisions, the owner may change them)**:
  - The layers are one package, `analysis/layers/`, writing `layers.json` and the `boundaries` fact set; its findings
    become cards through `analysis/layer_claims.py` (pattern `layer_boundary`, the card naming its boundary and the
    reference's fix). The access gaps (a table without row-level security, a write policy open to everyone) moved into
    it as the data layer's rules: one source, and their old detector was hidden (one judged output).
  - Each reference type's layer carries a `role` (screen, endpoint, logic, data, client, shared, entry): a file its path
    does not place is placed by what it imports; a file neither places is a listed gap, never a guess. Beside its layer
    each file has a side (browser, server, shared, database, test, build), read from its directives, imports and markup
    and from what imports it (Next.js renders a component on the server unless it says 'use client').
  - The browser rules are EAOS's own Python over the side of each file, not Semgrep or ast-grep patterns: each needs to
    know where a file runs, which a pattern cannot. Their examples are the planted app and its clean twin
    (`tests/test_layers.py`). The same holds for the business calculation inside a screen (M6.8).
  - Boundaries: EAOS's own resolved graph checks the rules generated from the reference for every language, type-only
    imports left out; dependency-cruiser gets the same rules plus "browser code reaches no server code through any chain
    of files" (`reachable`), and a chain only it sees is a card of its own. import-linter and go-arch-lint were not added:
    they would check the same rules again on the same graph (M2's rule: an engine stays only for what no other finds),
    and no corpus app is in Go to prove one. Said here so the owner can ask for them.
  - The live part is the `layers` path: beside `complete` an option (loop `try_layers`, switch `layers`), its time
    said in its words (up to 15 minutes; Schemathesis has 240 seconds). The Supabase CLI's advisors run with `--db-url`
    against the run's own PostgreSQL, the migrations applied over small stand-ins of Supabase's `auth` and `storage`
    schemas (no Docker, no Supabase project); pgTAP is loaded as SQL from its pinned source; every test runs in a
    transaction rolled back and the database is dropped after. A write policy is tried as a blind change of every row
    (`update t set owner = <other>` without a condition): one with a condition also needs the read policy.
  - The second test account (for one user reaching another's object) is made by the same sign-up rules as the first
    (`demo2`); Schemathesis gets both as peers of a Web Fuzzing Commons file, deleted after the run with its report.
  - The corpus' Node REST API is `davidtiger3622/crud-api-sqlite` (an Express API with SQLite, Supabase sign-in and an
    `openapi.json`), not the express-openapi-validator example first picked: that example imports packages it does not
    declare and never starts. An install held to a lockfile older than its package.json (`npm ci`, `--frozen-lockfile`)
    is tried once more without holding to it, in the run's own copy; pnpm installs with `--config.strict-dep-builds=false`
    (pnpm 10 and later refuse packages whose build scripts nobody approved).
  - A missing item of operations is a finding of the layers, never a card: the target's infrastructure rows already plan
    it (one source). The target projection keeps its own placement (the layer map uses the same path rule); placing its
    unplaced files by the map changed the gaps of other components and was left out.
  - A handler that answers 401 checks who is signed in, one that answers 403 checks a right, whatever their checks are
    called; a route of any method is called with a GET by the behaviour lock, as a browser does.
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

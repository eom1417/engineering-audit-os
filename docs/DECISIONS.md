# Decisions of the owner

Newest first. Each decision binds every assistant, in any chat, until the owner changes it here.

## 2026-10-25
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
- **M6, the whole system in layers (owner)**: EAOS checks a project as layers (browser, endpoints, business rules,
  data) and their boundaries by default, not only when the project declares a policy; planned as M6, run right
  after M5 (`ROADMAP.md`). From the review of the tools (2026-10-25, over 40 checked for licence, 2026 activity, use
  without changing the project, machine-readable and repeatable output):
  - adopted: `dependency-cruiser` used fully (reachability, type-only imports), `import-linter` and `go-arch-lint`
    with rules generated from the reference catalogue; `gitleaks` over the built output; `Schemathesis` (MIT) for
    the running API (ignored authentication, one user reaching another's object, bad input); the Supabase CLI's
    security advisors (MIT) and pgTAP for row-level security;
  - built by EAOS (no tool does it): the layer map without a declared policy, the endpoint-and-guard table, the
    browser-boundary rules, row-level security read from the migrations, browser-server rule consistency;
  - rejected: Dredd and Optic (archived), RESTler, madge and ts-arch (stale), Sheriff and jMolecules (they need the
    project changed), ZAP and Nuclei (noise for this purpose), splinter's SQL taken directly (no licence; its checks
    come through the MIT Supabase CLI), AI pentest agents such as Strix and Shannon (not repeatable).
- **Open, the owner's to decide**: the official Semgrep rules EAOS fetches are under the Semgrep Rules License
  (internal use; not offered to others as a service). Fine while each person runs EAOS on their own code; if EAOS is
  ever offered as a service, the rules it relies on are rewritten as EAOS's own first.

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
- **Efficiency**: the owner's time and tokens are spent only on what proves the change: the affected tests while
  working, the full verify once per batch of changes, real (not padded) estimates (`/workspace/AGENTS.md` §4).
- **EAOS holds itself to 400 lines / complexity 10** with no exception from M3 on (`tools/code_limits.py`); the laws it
  holds every project to stay 600 / 15 until the owner says otherwise.

## 2026-10-23
- **The account is only the mind.** Everything about the work lives locally with the project (this repository and
  `/workspace`): plans, decisions, progress, hand-overs. Nothing is kept in an assistant's or account's folders; any
  account, model (Claude, Codex, others) or API key continues from the files.
- **The context is always current**: context files, roadmap, decisions and metrics are updated with every finished card
  (`docs/STANDARDS.md` §8).
- **The North Star** (`docs/NORTH-STAR.md`): EAOS is a software engineering firm in one command, with three journeys
  (repair, build from an idea, add a feature).
- **The plan** is `ROADMAP.md` (M-1 to M8). "Execute Mx" means every card of Mx to the Definition of Done without
  asking again. At each milestone end `beta-trial` and the Studio are updated without asking.
- **Quality never drops in any mode**; economy modes change speed and cost only.
- **The ideal picture stays**; it is made faster (M4.4), never switched off.
- **`semgrep` noise** is silenced as the executor sees best; **complexity engines** are merged only if the check loses
  no strength.
- **The engine and the CLI with MCP are the product**, with 100% control; the Studio is optional and light, yet
  pleasant and useful.
- **Tests**: only those truly needed.
- **HungerLab** comes later as a private snapshot repository (`eom1417/hungerlab-snapshot`); its screens problem is
  solved at the root by the compatibility corpus (M0.3, M5), never project by project.
- **Cloudflare's security-audit skill**: its ideas are used (strict judge M7.4, logic hunting M9.2); the existing
  engines are not replaced by it.
- **Model tiers with escalation** come in M9.1.
- **Branches**: only `main`, `develop` and `beta-trial` stay; `update.sh` deletes merged `dev/` branches.
- **The user's full experience is simulated** (M10): AI actors try the program as its users would (a user asks, an
  admin approves, the user goes on; support tickets when stuck), with realistic dummy data, only in the isolated copy.
  Three levels: the saved journeys are **replayed without AI in every full check**; a **short simulation** is an option
  of the full check, shown with its time and cost; the **full simulation** is its own check path, runnable alone.
  Whether the short simulation joins every full check is decided from the numbers of M10.10. It is built last, on M5's
  browser-agent layer, M7.4's judge and M9.1's model tiers.

## 2026-10-17
- Every development starts on a new `dev/<topic>` branch from `develop` without asking; directly on `develop` only
  when the owner says so.
- The disk: a helping tool never weighs on the machine (`AGENTS.md`, "The disk").

## 2026-10-13
- The code laws: least code, one source of truth, clear and clean (`docs/STANDARDS.md` §1).
- EAOS develops EAOS: `beta-trial` is the working EAOS; `develop` is checked as an outside project.
- `main` is never touched; only the owner decides about it.

# Decisions of the owner

What binds every assistant, in any chat, until the owner changes it here: grouped by topic, each with its date. A new
decision goes under its topic; once its milestone is done, the reasoning behind an assistant's own choices moves to
`docs/archive/DECISIONS-DONE.md` and only what still binds stays.

## How we work
- **The account is only the mind** (2026-10-23): everything about the work lives with the project (this repository and
  `/workspace`): plans, decisions, progress, hand-overs. Nothing is kept in an assistant's or account's folders; any
  account, model (Claude, Codex, others) or API key continues from the files.
- **One plan** (2026-10-25): `ROADMAP.md` is the only place that holds a plan, a backlog or a status; it runs M-1 to
  M10 in the order the milestones run. Plans found elsewhere are merged into it and then deleted.
- **The context is always current** (2026-10-23): the context files, roadmap, decisions and metrics are updated with
  every finished card (`docs/STANDARDS.md` §8). Done cards and old reasoning move to `docs/archive/` (2026-10-25), so
  what is read at the start of a session stays short.
- **How to read the references** (2026-10-25): when two references disagree, the newer one holds; when a step of the
  plan looks wrong or weaker than another way, the assistant asks the owner before taking it.
- **"Execute Mx"** (2026-10-23) means every card of Mx to the Definition of Done without asking again; at each
  milestone end `beta-trial` and the Studio are updated without asking.
- **Efficiency** (2026-10-24): the owner's time and tokens are spent only on what proves the change: the affected
  tests while working, the full verify once per batch of changes, real (not padded) estimates (`/workspace/AGENTS.md`).
- **Tests** (2026-10-23): only those truly needed.

## Branches and safety
- **`main` is never touched** (2026-10-13); only the owner decides about it.
- **EAOS develops EAOS** (2026-10-13): `beta-trial` is the working EAOS; `develop` is checked as an outside project.
- **Every development starts on a new `dev/<topic>` branch** from `develop` without asking (2026-10-17); directly on
  `develop` only when the owner says so. Only `main`, `develop` and `beta-trial` stay (2026-10-23); `update.sh`
  deletes merged `dev/` branches.
- **The disk** (2026-10-17): a helping tool never weighs on the machine (`AGENTS.md`, "The disk").

## Code
- **The code laws** (2026-10-13): least code, one source of truth, clear and clean (`docs/STANDARDS.md` §1).
- **EAOS holds itself to 400 lines / complexity 10** with no exception from M3 on (2026-10-24, `tools/code_limits.py`);
  the laws it holds every project to stay 600 / 15 until the owner says otherwise.

## The product
- **The North Star** (2026-10-23, `docs/NORTH-STAR.md`): EAOS is a software engineering firm in one command, with three
  journeys (repair, build from an idea, add a feature).
- **The engine and the CLI with MCP are the product** (2026-10-23), with 100% control; the Studio is optional and
  light, yet pleasant and useful.
- **Quality never drops in any mode** (2026-10-23); economy modes change speed and cost only.
- **The ideal picture stays** (2026-10-23); it is made faster (M4.4), never switched off.
- **Engines** (2026-10-23): `semgrep` noise is silenced as the executor sees best; complexity engines are merged only if
  the check loses no strength.
- **The browser agent is EAOS's own** (2026-10-25, `live/agent.py`): `browser-use` and `Stagehand` need a model key of
  their own, which EAOS never holds; it is explored once with the assistant's smallest model and replayed free after
  (the reasoning: `docs/archive/DECISIONS-DONE.md`).
- **HungerLab** (2026-10-23) comes as a private snapshot repository (`eom1417/hungerlab-snapshot`); its screens problem
  is solved at the root by the compatibility corpus, never project by project.
- **Cloudflare's security-audit skill** (2026-10-23, https://github.com/cloudflare/security-audit-skill, MIT): its ideas are used (strict judge M7.4, logic hunting M9.2); the
  existing engines are not replaced by it.
- **Model tiers with escalation** come in M9.1 (2026-10-23).
- **M6, the whole system in layers** (2026-10-25, owner): EAOS checks a project as layers (browser, endpoints, business rules,
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
- **The user's full experience is simulated** (2026-10-23, M10): AI actors try the program as its users would (a user asks, an
  admin approves, the user goes on; support tickets when stuck), with realistic dummy data, only in the isolated copy.
  Three levels: the saved journeys are **replayed without AI in every full check**; a **short simulation** is an option
  of the full check, shown with its time and cost; the **full simulation** is its own check path, runnable alone.
  Whether the short simulation joins every full check is decided from the numbers of M10.10. It is built last, on M5's
  browser-agent layer, M7.4's judge and M9.1's model tiers.

## Open, the owner's to decide
- The official Semgrep rules EAOS fetches are under the Semgrep Rules License
  (internal use; not offered to others as a service). Fine while each person runs EAOS on their own code; if EAOS is
  ever offered as a service, the rules it relies on are rewritten as EAOS's own first.

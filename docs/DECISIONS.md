# Decisions of the owner

Newest first. Each decision binds every assistant, in any chat, until the owner changes it here.

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
- **Cloudflare's security-audit skill**: its ideas are used (strict judge M6.4, logic hunting M8.2); the existing
  engines are not replaced by it.
- **Model tiers with escalation** come in M8.1.
- **Branches**: only `main`, `develop` and `beta-trial` stay; `update.sh` deletes merged `dev/` branches.
- **The user's full experience is simulated** (M9): AI actors try the program as its users would (a user asks, an
  admin approves, the user goes on; support tickets when stuck), with realistic dummy data, only in the isolated copy.
  Three levels: the saved journeys are **replayed without AI in every full check**; a **short simulation** is an option
  of the full check, shown with its time and cost; the **full simulation** is its own check path, runnable alone.
  Whether the short simulation joins every full check is decided from the numbers of M9.10. It is built last, on M5's
  browser-agent layer, M6.4's judge and M8.1's model tiers.

## 2026-10-17
- Every development starts on a new `dev/<topic>` branch from `develop` without asking; directly on `develop` only
  when the owner says so.
- The disk: a helping tool never weighs on the machine (`AGENTS.md`, "The disk").

## 2026-10-13
- The code laws: least code, one source of truth, clear and clean (`docs/STANDARDS.md` §1).
- EAOS develops EAOS: `beta-trial` is the working EAOS; `develop` is checked as an outside project.
- `main` is never touched; only the owner decides about it.

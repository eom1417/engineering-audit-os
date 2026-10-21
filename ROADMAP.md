# EAOS roadmap

The only plan of EAOS. A finished item leaves this page and goes to `CHANGELOG.md` with the test that proves it.
Each fix starts with one small test that reproduces the real incident; one fast journey test (fixture repository,
fake assistant: check → change → check again → fix three cards with one failing → accept) runs after each group.

## Now

- **A complete product from a plan, from one press** (owner, 2026-10-21; the HungerLab incident: the blueprint missed
  every cross-cutting card, an assistant added about 50 by hand, and nothing proved each requirement was built). Three
  changes, in order, each with the test of its incident; the check-and-fix way is not touched:
  1. *The cards every product needs, as data* (`eaos/data/product-standard.json`, read by `blueprint.design`; ~1 h).
     Each row: `when` (a fact of the spec: `nonfunctional.languages` > 1, `data_sensitivity` personal/health/payment,
     `platforms` with mobile, `expected_users`, each `integrations` entry, always), its milestone (`M02` foundations,
     or the last one, "Ready to release"), title, paths, acceptance, tests. Rows: languages and right-to-left; privacy
     (consent, export, delete); offline; one adapter and a contract test per integration; security headers and secrets
     out of the code; accessibility (axe, 0 serious); speed budget (Lighthouse >= 90); load at the expected users (k6);
     logging of errors; CI running every gate; README to run it. `nonfunctional` becomes required by `validate_spec`.
     Test: the HungerLab-shaped spec draws those cards with no hand-added one.
  2. *Every requirement built* (`blueprint.validate_spec`, `build_tools._build_finish_job`; ~1 h). The spec lists the
     plan's requirements with their ids (`requirements: [{id, text}]`) and features and standard rows name what they
     `cover`; a requirement no card covers is a problem, so the blueprint is not drawn; the last milestone is refused
     while a requirement has only skipped cards. The blueprint and the Studio's plan show the coverage.
     Test: an uncovered requirement stops `blueprint_design`; a skipped one stops the last `build_finish`.
  3. *One press to the end* (`build_start` input `whole`, its Studio chain in `prompts.CHAINS`; ~30 min). "Build the
     whole product" builds every milestone in order, then checks the last branch (`audit` with the app run) and fixes
     its cards until no critical or high problem is left; then the person decides to take it in.
     Test: the chain names every step; the Studio offers the action once the blueprint has no open question.
  Then one real trial from the Studio on a small two-language, two-role plan, from the plan to the accepted product.
  Reused as they are: the gates of every card, the screen review against DESIGN.md, the check's speed, accessibility,
  load and security tools. Not promised by code: legal and scientific sign-off, trials with real people (drafts only).

- **The proof of 0.0.34**: one full check of EAOS from the Studio with the assistant (CodeQL on Python, the speed baseline
  on EAOS's real server, the translation memory, the screen review of the 33 design fixes), then a fix batch of the
  cards left: the five module splits after their simplifications, and the cards whose finish line is now precise.
- **The Studio lighter still**: diagrams drawn with the report instead of Mermaid in the browser, the functions section
  paged on the server, and the server start rebuilding only the sections that changed.
- **Accessibility problems measured by axe become cards without the assistant**; today the look path without AI pictures
  the screens and finds no card.
- **The load test proven on a real web app**: EAOS's own production run is not found at setup, so its speed was not
  measured; then the speed mode measured with the assistant.
- **The screen lock in a batch of code changes** names every screen that differs; the next step is to show the person
  the before and after pictures of a design change to approve, instead of trusting every design card's look.

## Then

- A second slimming pass inside the largest kept modules (`human_report.py`, `guided.py`, `dossier.py`): the CLI
  journey and the MCP journey share one implementation.
- `1.0.0` only when the owner declares it.

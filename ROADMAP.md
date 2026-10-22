# EAOS roadmap

The only plan of EAOS. A finished item leaves this page and goes to `CHANGELOG.md` with the test that proves it.
Each fix starts with one small test that reproduces the real incident; one fast journey test (fixture repository,
fake assistant: check → change → check again → fix three cards with one failing → accept) runs after each group.

## Now

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

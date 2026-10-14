# EAOS roadmap

The only plan of EAOS. A finished item leaves this page and goes to `CHANGELOG.md` with the test that proves it.
Each fix starts with one small test that reproduces the real incident; one fast journey test (fixture repository,
fake assistant: check → change → check again → fix three cards with one failing → accept) runs after each group.

## Now

- **The design library for building from a plan**: free, pinned design sources (styles and UX rules by product type,
  reference design systems, shadcn/ui components and blocks with right-to-left support, themes, the Arabic fonts of
  Google Fonts, and craft guidance for the assistant) unified by one EAOS design standard: phone first, both
  directions, one theme, readable contrast. A redesign of an existing project, offered when the screen review finds
  the look weak, is the person's choice.
- **The proof of 0.0.27 and the design library**: one full check of EAOS from the Studio with the assistant, a real fix
  batch, and a real build from a plan; then the owner's review.

## Then

- A second slimming pass inside the largest kept modules (`human_report.py`, `guided.py`, `dossier.py`): the CLI
  journey and the MCP journey share one implementation.
- `1.0.0` only when the owner declares it.

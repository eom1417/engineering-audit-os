# NS46.T11 and NS46.T17: the real command-centre trial harness

Task: NS46.T11, NS46.T17

Scouting record for `tools/studio_trial.py` and its browser half `studio/scripts/trial.mjs`: the trial that drives
the live Studio (the command-centre server and a real Chromium) with a real assistant from the check to an accepted
branch, and records the owner-control evidence (answers, guards, persistence, screens). Written 2026-10-09, before
the harness's first measured run. Versions were read on this computer from the EAOS toolchain
(`~/.eaos/tools`, `eaos/data/toolchain.json`); none was re-checked online. No new package enters EAOS or the Studio.

## Driving the browser

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| Playwright for Node, from the EAOS toolchain (`~/.eaos/tools/node/node_modules/playwright`, Chromium 1243) | Apache-2.0 | 2026-10-09, the version pinned in `eaos/data/toolchain.json` | released monthly by Microsoft | already drives the Studio in `studio/scripts/live.mjs` (F9) and the screen gate (`eaos/templates/screens/audit.mjs`); clicks, keyboard, video recording, route interception, colour schemes and phone emulation in one API |
| Playwright for Python | Apache-2.0 | not installed here | same project | the same engine, but one more package in `.venv` and a second browser install beside the toolchain's |
| Selenium WebDriver | Apache-2.0 | not re-checked | active | needs a separate driver binary; no built-in video or network interception |
| Cypress | MIT | not re-checked | active | runs inside its own runner and app; not scriptable as one phase called from Python |

**Decision**

Adopt the toolchain's Playwright for Node, as `studio/scripts/live.mjs` does: the trial adds a phase script, not a
browser stack. The Python half (`tools/studio_trial.py`) keeps the pattern of the other `tools/*_trial.py`: it
copies the project, starts the real server (`eaos studio`), runs one browser phase at a time and writes
`$EAOS_MEASURE/<kind>/<project>/trial.json`.

**Pinned**

none (the toolchain's Playwright, pinned in `eaos/data/toolchain.json`)

## Judging the screens

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| The EAOS screen gate, `eaos/screens/audit.py` (Playwright + axe-core from the toolchain) | EAOS; axe-core MPL-2.0 | 2026-10-09 | used by `tools/studio_gates.py` | already measures overflow, layout width, first scroll, axe serious/critical, 44 px targets, language, direction and theme per viewport and variant |
| Lighthouse | Apache-2.0 | toolchain | active | a score per page, not the per-variant failures the owner-control matrix needs; it stays with F14 |

**Decision**

Reuse the screen gate on the live decisions page, phone, tablet and desktop × Arabic and English × light and dark.

**Pinned**

none

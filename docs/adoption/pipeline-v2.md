# Pipeline v2: visual evidence tools (adopted 2026-10-11)

Owner request 2026-10-11 (eaos-dev/planning/ai-joint-planning/PLAN.md, addendum): journeys, crawl, page states,
architecture map and a visual reviewer in the check. Each tool is pinned in `upstreams/toolchain.json` (mirrored in
`eaos/data/toolchain.json`), installed by `eaos tools install` without root, and run as a separate process by a thin
adapter. None needs a network at check time beyond the app's own address on this computer.

| Tool | Version | Licence | Install | Adapter | Stage | Checked how |
|---|---|---|---|---|---|---|
| rrweb + rrweb-player | 2.1.7 | MIT | npm (libraries) | `eaos/behavior_lock.py` `run_journeys`, `JOURNEY_HOOKS` | `journeys` | the lock's page specs record each page when EAOS_RRWEB is set |
| Unlighthouse (`@unlighthouse/cli`) | 0.19.1 | MIT | npm, binary `unlighthouse-ci` | `eaos/screens/crawl.py` | `crawl` | drives the pinned Playwright Chromium; resolves the pinned lighthouse 13.5.0 (it asks ^13.5.0) |
| CodeCharta analysis (`codecharta-analysis`) | 2.1.0 | BSD-3-Clause | npm, binary `ccsh`, needs temurin-jre | `eaos/engines/architecture.py` `city` | `architecture` | unifiedparser + gitlogparser merged: 101 buildings on RendaPerene in 4 s |
| Emerge (`emerge-viz`) | 2.0.7 | MIT | pip, with setuptools 80.10.2 | `eaos/engines/architecture.py` `clusters` | `architecture` | 139 files, 560 imports on RendaPerene in 1.5 s; its clipboard step fails without a clipboard after its files are written, so its files decide |

Release downloads: none of the four ships a release archive EAOS downloads; npm and PyPI resolve the exact versions
above, as for the other npm and pip tools of the toolchain.

The visual reviewer (node `visual_reviewer`) uses the person's own assistant. Headless Claude Code reads a picture
when its Read tool is allowed on exactly that file (`--tools Read --allowedTools "Read(<file>)" --permission-mode
dontAsk`); a read of any other file is refused. Proven on 2026-10-11 with a test page (button text, colour and small
print read correctly; the read outside refused): eaos-dev/workers/pipeline-v2/p3/image-reading-proof.md. Codex gets
the same pictures attached with `-i`; Codex sign-in was broken on the development computer, so that path is not yet
proven.

Studied and not chosen: Midscene, Stagehand and Browser Use (they need a model key of their own); BackstopJS stays an
option for the fix loop.

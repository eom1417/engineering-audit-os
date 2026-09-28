# Trials: a real assistant drives EAOS alone (X9)

`tools/mcp_trial.py` plays the person with two messages and nothing else: «افحص مشروعي بـ EAOS وأصلح مشاكله», then
«نعم، موافق» to the one question. Between them is Claude Code with the EAOS MCP tools and its own read-only tools
(Read, Grep, Glob): no Bash, no Edit, no Write, so every change goes through EAOS's gates. Each run starts from a
fresh clone and an empty EAOS home. The record is `$EAOS_MEASURE/mcp/<project>/trial.json` with every turn.

## endomap, 2026-09-28: delivered

| | |
| --- | --- |
| The person's turns | 2 (the request, then «نعم، موافق») |
| Result | the branch `eaos/wave-1` in the project, 8 fixes kept; the project's branch untouched |
| Time | 18.7 minutes, from nothing to the delivered branch |
| Files written by hand | 0 |
| Tool calls | status 1, audit 1, wait 6, findings 2, run_setup 2, safety_net 1, fix_start 1, fix_read 1, fix_edit 1, fix_skip 1, fix_finish 1 |

What it did on its own: checked the project, chose the security upgrades (8 libraries, `hono` first with 7 known
holes), ran the app, recorded its screens, applied the upgrades, and closed the batch through the project's own checks
and the screens. It kept out what did not pass and said why: `nanoid` and `postcss` still had their hole after the
upgrade; `vitest` needed a lockfile only npm can write, so it skipped it with the one command the owner can run. It
warned, unasked, that `vite` moved from 5 to 6 and that the 3D scene was not in the recorded screens, so the owner
should look at it before taking the branch. It also judged the 47 "broken code" findings a false alarm (to verify).

## chief-ops, 2026-09-28: first run stopped by an EAOS bug, fixed

The assistant got the app running on its own in five attempts: without PostgreSQL (the app's file store), then the
local sign-in it found in the code (`CO_LOCAL_ONLY`, an owner e-mail, the one-time code shown on screen), then the
programme chooser. It recorded 28 of 28 screens and applied two security upgrades (`fast-uri`, `sharp`). The last
step, `fix_finish`, failed twice on `runtime/runtime/checks-original-log.json`: a run's record was written before its
folder existed (fixed in aee341a). With no other way to change files, the assistant stopped and said so plainly,
changing nothing. It also sampled EAOS's findings against the code and found real false positives: the server's own
entry, its security headers, the rate limit and dynamically imported routes called dead code, and a documented
`npm run deploy:<target>` template called missing. Those were fixed at their causes (ca6efe4; dead-code facts on
chief-ops 150 → 74). The second run is recorded below when it ends.

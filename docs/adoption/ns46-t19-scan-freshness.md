# NS46.T19: live scan freshness, local time and direct governance

Task: NS46.T19

Scouting record for the owner addition "Live scan freshness, local time and full governance"
(eaos-dev/planning/studio-v2/STUDIO-COMPLETE.md), written 2026-10-09 before its code. No new package enters EAOS or
the Studio for this task.

## Displaying times in the reader's zone

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| `Intl.DateTimeFormat` / `Intl.RelativeTimeFormat` (ECMA-402, in every browser and Node) | platform | 2026-10-09, Node 22 and Chromium of the pinned Playwright | the browsers | device zone from `resolvedOptions().timeZone`, any IANA zone by `timeZone`, relative phrases in Arabic and English, zero bytes added |
| date-fns + date-fns-tz | MIT | not re-checked | active | the same through Intl underneath, plus bundle weight |
| Luxon | MIT | not re-checked | active | a full date library for what four Intl calls do |
| Temporal polyfill | MIT | not re-checked | proposal stage 3 | not in every browser the person may use; a polyfill is large |

**Decision**

Use Intl directly in one shared formatter in `studio/src/i18n/prefs.tsx`: device zone by default, a remembered
Settings override, relative plus exact zoned time. Stored data stays UTC ISO-8601.

**Pinned**

none

## Knowing whether the scan is current

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| Git argv reads (`rev-parse`, `merge-base --is-ancestor`, `rev-list --count`, `diff --name-only`, `status --porcelain`) on demand from the live server | GPL-2.0 tool | 2026-10-09, git 2.43.0 | git | exact, cheap, the same reads `guided.same_code` and `export.freshness` already make |
| A filesystem watcher (watchdog / inotify) | Apache-2.0 | not re-checked | active | pushes changes, but one more dependency and platform differences; focus, a modest interval and run completion are enough |

**Decision**

A read-only `GET /api/freshness` on the existing command centre, polled on focus, every minute and after a run ends;
re-scan goes through the existing `audit` action and run queue.

**Pinned**

none

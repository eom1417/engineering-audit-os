# Studio branch control and live scan freshness (NS46.T18, NS46.T19)

Owner requests of 2026-10-09 (eaos-dev planning: BRANCH-CONTROL.md and STUDIO-COMPLETE.md, "Live scan freshness,
local time and full governance"). Adoption records: `docs/adoption/ns46-t18-branch-control.md`,
`docs/adoption/ns46-t19-scan-freshness.md`.

## Where it lives

| Part | File |
|---|---|
| Branch service inside the command centre | `eaos/studio/actions/branches.py` (`BranchControl`, mounted by `Actions`) |
| Scan provenance and freshness from git | `eaos/branches.py` (`scan_provenance`, `freshness`, `dirty`) |
| Recorded at scan time | `eaos/guided.py` `scan`, `eaos/agent_tools.py` `_audit_job` |
| Snapshot contract | `eaos/studio/export.py` (`scan_of`, `freshness`), `tools/make_contracts.py` (`scan`, `head.freshness_detail`) |
| Endpoints | `docs/studio-actions.json` `endpoints` (`/api/freshness`, `/api/context`, `/api/branches…`) |
| Front end | `studio/src/branches/` (live state, scan sheet, switcher, words), `studio/src/pages/branches/`, `studio/src/command/Direct.tsx` |
| One time formatter | `studio/src/i18n/prefs.tsx` (`timeFormatter`, `zone`, `setZone`), `studio/src/i18n/text.tsx` (`When`) |

## Rules the code enforces

- Four branches are never conflated: the checkout of the project folder, the analysis branch (`state.branch`), the
  report's branch (the manifest's `scanned`) and the base chosen for comparison. Selecting an analysis branch calls
  `guided.choose`; the checkout is compared before and after and the run fails if it moved.
- Ownership comes only from durable provenance: an EAOS wave or build in the state, or `runs/branch-provenance.json`.
  A name or prefix is never proof. A tool-owned branch with commits by any other author is `shared` and not changed.
- Every mutation passes the command centre's locks first (launch token, CSRF, Origin, Host), then a confirm token bound
  to the exact heads its preview showed, then the project's branch lock (`runs/branches.lock`), and is written to the
  run history as a run with `branch_op`. Git runs as argv; names pass `git check-ref-format --branch` and are only used
  inside full refs.
- Merge: an applied EAOS batch into its own target goes through `accept` (ledger, report and cleanup once); any other
  tool-owned branch by `merge-tree` then `update-ref <new> <expected old>`, or a merge inside the clean worktree that has
  the target checked out. Conflicts change nothing and can become a read-only assistant review run.
- Protected: the remote's default branch, `main`/`master` unless the project unprotects them, the project's own list,
  and EAOS's own `main` always. Enforced by the backend, not only by disabled buttons.
- Deletion: only tool-owned, unprotected, not checked out anywhere, not the analysis or default branch, no run using it;
  a recovery ref `refs/eaos-recovery/<id>` is written first; unmerged commits need a second confirm token; remote
  deletion is its own preview, consent and `--force-with-lease` push; local and remote never imply each other.
- In-flight runs are never retargeted: a run records `context` (analysis branch and commit, checkout) when created; the
  analysis branch cannot change while any run is queued or working (the refusal names each run and offers its stop);
  choosing the branch already analysed changes nothing, so a re-scan never waits for a run.

## Freshness

`branches.freshness(state)` compares the recorded commit with the branch head now: `fresh` (or only EAOS's own commits
since), `behind` (commits, files, the first 50 files), `rewritten` (the scanned commit is gone or not an ancestor),
`dirty` (unsaved changes in the checkout of that branch), `other_branch`, or `unknown` with `not_scanned`,
`legacy_report`, `not_git` or `branch_missing`. The live Studio asks `/api/freshness` on focus, every 60 seconds while
visible, after any run finishes and when the report reloads. Re-scan dispatches the `audit` action through the command
centre; copying an instruction is a labelled fallback, and a snapshot offers the `eaos studio` command instead.

## Time

Stored times stay UTC ISO-8601. Display uses the device zone (`Intl.DateTimeFormat().resolvedOptions().timeZone`) or the
zone chosen in Settings (remembered in `localStorage` `eaos.studio.zone`), with the relative form and the exact zoned
time on hover, tap or Enter.

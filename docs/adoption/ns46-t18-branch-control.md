# NS46.T18: Studio branch control

Task: NS46.T18

Scouting record for the owner's branch-control request (eaos-dev/planning/studio-v2/BRANCH-CONTROL.md), written
2026-10-09 before the code of `eaos/studio/actions/branches.py`. Git was read on this computer (`git --version`:
2.43.0). No new package enters EAOS or the Studio for this task.

## Reading the repository's branches

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| Git plumbing through argv: `for-each-ref`, `worktree list --porcelain`, `rev-list --left-right --count`, `status --porcelain=v2 --branch` | GPL-2.0 tool, called as a program | 2026-10-09, git 2.43.0 | git releases every few months | already how `eaos/branches.py` and `eaos/guided.py` read git; machine-readable output, NUL separators, no shell |
| GitPython | BSD-3-Clause | not re-checked | maintained, in maintenance mode | wraps the same git commands; one more dependency and its own process management for nothing new |
| pygit2 / libgit2 | GPL-2.0 with linking exception | not re-checked | active | fast in-process reads, but a compiled wheel per platform and no worktree/merge-tree parity with the git the person uses |
| dulwich | Apache-2.0 / GPL-2.0 | not re-checked | active | pure Python, but does not read every repository feature git does (worktrees, some pack formats) |

**Decision**

Adopt the git the person already has, called with argv lists only (never a shell), as `eaos/branches.py` does.
Branch names are validated with `git check-ref-format --branch` and then only ever passed as full refs
(`refs/heads/<name>`, `refs/remotes/<remote>/<name>`) after `--end-of-options` where git accepts it.

**Pinned**

none

## Merging without touching the checkout, and safe deletion

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| `git merge-tree --write-tree` + `git commit-tree` + `git update-ref <ref> <new> <old>` | GPL-2.0 tool | 2026-10-09, git 2.43.0 (merge-tree --write-tree since 2.38) | git | an isolated merge (no index, no worktree), conflicts listed without changing anything, and a compare-and-swap ref update that fails if the target moved |
| `git merge` in a temporary worktree | GPL-2.0 tool | 2026-10-09 | git | works on older git, but writes a worktree and needs cleanup; kept only for a target that is checked out (the merge must update that worktree's files) |
| The existing EAOS accept pathway (`agent_tools.accept` → `guided.merge` → `guided.reconcile`) | EAOS | 2026-10-09, in the repository | used by every accepted wave | the only path that updates the ledger, REPORT.html, counters and wave cleanup together; managed waves must go through it |
| `git branch -D` / `git push --force` | GPL-2.0 tool | 2026-10-09 | git | force forms discard work silently: not used by Studio branch control |

**Decision**

Managed EAOS waves are accepted through the existing accept pathway (the command centre's `manager.call('accept')`), so
the ledger and the report change once. Other tool-owned branches use an isolated `merge-tree` preview whose heads are
bound into the confirm token, then `commit-tree` and a compare-and-swap `update-ref` under the project lock; a target
checked out in a clean worktree is merged there instead. Deletion first writes a recovery ref
(`refs/eaos-recovery/...`), then removes the branch with `update-ref -d <ref> <expected>`; remote deletion is a
separate `git push --porcelain --force-with-lease=<ref>:<expected> <remote> :<ref>` with its own consent, never a
force push of content.

**Pinned**

none

## The Studio side

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| Existing Studio components (Sheet, Props, Chip, Button, Segmented, react-aria-components 1.22.0 already pinned) | Apache-2.0 | 2026-10-09, studio/package.json | active | sheets, menus and focus management already used by the command centre; no new package |
| A git-graph widget (e.g. @gitgraph/react) | MIT | not adopted | unmaintained since 2021 | draws ancestry, which the contract forbids inferring; only recorded parent-to-work lineage is shown |

**Decision**

Build the Branches workspace and drawer from the Studio's existing components; lineage is a compact recorded
parent-to-work list, not a drawn graph.

**Pinned**

none

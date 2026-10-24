"""Branch control from the Studio (docs/STUDIO-BRANCH-CONTROL.md, NS46.T18) and the live freshness of the scan (NS46.T19).

    control = BranchControl(actions)          # the command centre's Actions: its store, manager, locks and project
    control.inventory(base='develop')         # every local and remote branch, the checkout, worktrees and policy
    control.preview_merge({'source': 'eaos/wave-2', 'target': 'develop'})   # isolated: nothing changes
    control.merge({..., 'confirm': token})    # only with the confirm token of that preview, at the heads it showed

Reading answers at once. A change (select the analysis branch, merge, delete, restore, fetch, protect) goes through the
command centre's locks first (launch token, CSRF, Origin: security.py), then needs a confirm token bound to the exact
heads its preview showed, holds the project's branch lock, and is written to the run history as a run of its own, with
its outcome and how to recover from it.

Git is called with argv lists, never through a shell. A branch name is checked by `git check-ref-format --branch` and
then used only inside a full ref (refs/heads/<name>). Ownership comes only from durable provenance: an EAOS wave or
build in the project's state, or an entry EAOS wrote in runs/branch-provenance.json; a name or a prefix is never proof.
What git does not say stays unknown.

    runs/branch-provenance.json    {branches: {name: {created_by, kind, run, tip, base, base_commit, at, merged_into, checks}}}
    runs/branch-recovery.json      [{id, ref, branch, where, remote, tip, at, run, restored}]
    runs/branch-policy.json        {protected: [...], unprotected: [...]}: the project's own choices over the defaults
    refs/eaos-recovery/<id>        the commit of a deleted branch, kept so the deletion can be undone
"""
from .deleting import Deleting
from .guards import Guards
from .inventory import Inventory
from .merging import Merging
from .remotes import Remotes
from .state_view import StateView
from .common import Blocked, git, say, valid_name, work_of  # noqa: F401  (the package's names other modules call)


class BranchControl(Remotes, Deleting, Merging, Guards, Inventory, StateView):
    def __init__(self, actions):
        self.actions = actions
        self.project = actions.project
        self.store = actions.store
        self.manager = actions.manager
        self.locks = actions.locks

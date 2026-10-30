"""Every external tool at its pinned version, installed without root, and checked by one command.

eaos/data/toolchain.json is the only list (install, the engines stage and the pages read it). `install` puts each tool under $EAOS_ENGINE_TOOLS (default
~/.eaos/tools): a release is downloaded and accepted only if its sha256 matches the pinned one,
a Python tool goes into that directory's own virtualenv, a Node tool into its own prefix; every executable
is linked into bin/. `doctor` reports, per tool, whether the binary is there and at the pinned version.
Nothing here uses sudo or a system package manager: a tool that needs one says so and stops.

One install runs at a time on a computer (`machine_lock`), shared by every project. It installs WORKERS tools at once,
in the order the check needs them, and writes each tool as a stage of the `tools` flow (home()/progress/tools.jsonl,
eaos/core/progress/log.py), its download as a counted step: the Studio's "Preparing the tools" page reads that file, and
`readiness` tells the check which of the tools it needs on a project are ready, still coming, or failed.

- pins.py: the registry, the tools home and where each tool lives in it, which tools a project needs, a release's build;
- versions.py: the version of each tool installed now, and `doctor`;
- installers.py: one tool installed at its pinned version (a release, pip, npm, git; Playwright's browser);
- runs.py: the install runs (the lock, the tools flow, `prepare`, `readiness`) and the `eaos tools` command.
"""
# The names other modules call through the package (toolchain.home, toolchain.install ...), each kept in one module here.
from .pins import (Unavailable, applies, browsers, checkout, home, needed, node_modules, npm_prefix,  # noqa: F401
                   ordered, project_files, registry, release_spec, rule_applies, tool_env)
from .runs import FLOW, install, installing, machine_lock, main, prepare, readiness, ready, stages, stale, wait_for_check  # noqa: F401
from .versions import browser_missing, doctor, found_version, package_version, pip_version  # noqa: F401

#!/usr/bin/env bash
# Everything a new computer needs to develop EAOS, from a clone of this repository alone (Linux or a Mac).
#
#   git clone git@github.com:eom1417/engineering-audit-os.git && cd engineering-audit-os && bash tools/dev_setup.sh
#
# 1. .venv with EAOS installed from this checkout (editable) and its optional extras
# 2. every external tool EAOS runs, at its pinned version and sha256, in ~/.eaos/tools ($EAOS_ENGINE_TOOLS)
# 3. the development material under ~/.eaos/dev ($EAOS_DEV_HOME, see tools/dev_paths.py):
#    the pinned sample corpus and the engines' source checkouts
# Safe to run again: each step keeps what is already in place.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
"$PYTHON" -c 'import sys; assert sys.version_info >= (3, 10), "EAOS needs Python 3.10 or newer"'

if [ "$(uname)" = Linux ] && command -v apt-get >/dev/null; then
  SUDO=""; [ "$(id -u)" = 0 ] || SUDO="sudo"
  # venv, the Arabic and Latin fonts Typst embeds in EXECUTIVE.pdf, and git
  $SUDO apt-get install -y python3-venv fonts-noto-core git || echo "warning: apt-get could not install the system packages"
fi

[ -x .venv/bin/python ] || "$PYTHON" -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -e '.[facts,runtime,live]'

.venv/bin/python -m eaos tools install --stage assessment

.venv/bin/python tools/dev_paths.py upstreams
# The owner's live project (live_corpus) is private: without access to it the rest of the corpus is still fetched.
.venv/bin/python tools/north_star.py fetch || echo "warning: part of the corpus could not be fetched (a private project needs access to its repository)"

echo
.venv/bin/python -m eaos doctor | head -1 || true
.venv/bin/python tools/dev_paths.py
echo "ready: .venv/bin/python -m unittest discover -s tests -q   (the full suite takes about 25 minutes)"

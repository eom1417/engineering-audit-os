#!/bin/bash
# Every law of docs/STANDARDS.md §1-2 in one command; refuses a change that makes any number worse (tools/quality.py).
# --record writes the numbers after one went down. Needs the development setup (tools/dev_setup.sh).
cd "$(dirname "$0")/.." || exit 1
export EAOS_ENGINE_TOOLS="${EAOS_ENGINE_TOOLS:-$HOME/.eaos/tools}"
exec .venv/bin/python tools/quality.py "$@"

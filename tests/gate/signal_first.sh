#!/usr/bin/env bash
# N2.T4 — the fixes must work on the repository that exposed the defect, not on a fixture.
set -euo pipefail
cd "$(dirname "$0")/../.."
PYTHON="${PYTHON:-.venv/bin/python}"
EAOS="${EAOS:-.venv/bin/eaos}"
GO="${GO:-/workspace/upstream-src/enola}"
OUT="$(mktemp -d)/signal"
trap 'rm -rf "$(dirname "$OUT")"' EXIT

[ -d "$GO" ] || { echo "FAIL: enola reference absent at $GO"; exit 1; }

echo "  running the gate's reference audit"
"$EAOS" audit "$GO" --out "$OUT" --skip site >/dev/null

DOSSIER="$OUT/dossier.json"
[ -f "$DOSSIER" ] || { echo "FAIL: no dossier at $DOSSIER"; exit 1; }

TOP10=$(mktemp)
"$PYTHON" "$(dirname "$0")/signal_first_top10.py" "$DOSSIER" > "$TOP10"

VENDORED_HITS=$(grep -cE '(/testdata/|/fixtures/|/vendor/|/node_modules/|/third_party/|/generated/|/\.venv/|/dist/|/build/)' "$TOP10" || true)
if [ "$VENDORED_HITS" -gt 0 ]; then
    echo "FAIL: top 10 claims include $VENDORED_HITS vendored paths"
    grep -E '(/testdata/|/fixtures/|/vendor/|/node_modules/|/third_party/|/generated/|/\.venv/|/dist/|/build/)' "$TOP10"
    exit 1
fi
echo "  no vendored path in the top 10"

HOTSPOT_HITS=$(grep -cE '(hotspot|complexity|branching|maintain|deep|size|cycle|nesting)' "$TOP10" || true)
if [ "$HOTSPOT_HITS" -lt 1 ]; then
    echo "FAIL: top 10 has no hotspot-style claim; the gate is satisfied only because there are no real concerns"
    cat "$TOP10"
    exit 1
fi
echo "  top 10 includes at least one hotspot-style claim ($HOTSPOT_HITS hits)"

echo "PASS: the gate finds the reader's code at the top of the report, not vendored noise"

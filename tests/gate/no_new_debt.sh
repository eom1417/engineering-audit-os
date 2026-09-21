#!/usr/bin/env bash
# M7.T3 — the gate must ignore the debt a project already had and fail on what a change added.
set -euo pipefail
cd "$(dirname "$0")/../.."
EAOS="${EAOS:-.venv/bin/eaos}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
PROJECT="$WORK/project"
OUT="$WORK/report"
cp -r tests/fixtures/debt "$PROJECT"

step() { printf '  %s\n' "$1"; }

step "audit the project as it stands"
"$EAOS" audit "$PROJECT" --out "$OUT" --skip engines --skip site >/dev/null

step "pin the existing debt"
"$EAOS" baseline pin --out "$OUT" --note "gate scenario" >/dev/null
ACCEPTED=$("$EAOS" baseline show --out "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["claims"])')
if [ "$ACCEPTED" -lt 1 ]; then echo "FAIL: the fixture carries no debt, so the scenario proves nothing"; exit 1; fi
step "accepted debt: $ACCEPTED claims"

step "re-audit unchanged: the gate must pass"
"$EAOS" audit "$PROJECT" --out "$OUT" --skip engines --skip site --gate new >/dev/null
step "unchanged tree passed the gate with $ACCEPTED accepted findings"

step "add one new duplicate and re-audit: the gate must fail"
cat >> "$PROJECT/existing.py" <<'NEW'


def receipt_sum(rows, percentage):
    total = 0
    for row in rows:
        total = total + row
    return total * (1 + percentage)
NEW
set +e
"$EAOS" audit "$PROJECT" --out "$OUT" --skip engines --skip site --gate new >"$WORK/gated.json"
CODE=$?
set -e
if [ "$CODE" -ne 1 ]; then
  echo "FAIL: a new finding did not fail the gate (exit $CODE)"; python3 -m json.tool "$WORK/gated.json" | head -30; exit 1
fi
python3 - "$WORK/gated.json" <<'PY'
import json, sys
verdict = json.load(open(sys.argv[1]))['gate']
assert verdict['status'] == 'FAIL', verdict
assert verdict['failing'], 'the gate failed without naming what is new'
assert verdict['accepted_debt'] >= 1, 'the accepted debt was not carried into the verdict'
print(f"  new findings that failed the gate: {len(verdict['failing'])}, "
      f"accepted debt ignored: {verdict['accepted_debt']}")
PY

step "warn-only reports the same verdict without failing"
"$EAOS" audit "$PROJECT" --out "$OUT" --skip engines --skip site --gate new --warn-only >/dev/null

step "remove the new duplicate: the gate must pass again"
python3 - "$PROJECT/existing.py" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
path.write_text(path.read_text().split('def receipt_sum')[0].rstrip() + '\n', encoding='utf-8')
PY
"$EAOS" audit "$PROJECT" --out "$OUT" --skip engines --skip site --gate new >/dev/null
echo "PASS: existing debt does not fail the gate; one new finding does; removing it passes again"

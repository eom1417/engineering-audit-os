#!/usr/bin/env bash
# M9.T1 — a tool that claims to improve architecture has to pass its own rules.
set -euo pipefail
cd "$(dirname "$0")/../.."
EAOS="${EAOS:-.venv/bin/eaos}"
PYTHON="${PYTHON:-.venv/bin/python}"
OUT="${SELF_AUDIT_OUT:-$(mktemp -d)/self}"
mkdir -p "$OUT"

fail() { echo "FAIL: $1"; exit 1; }

echo "  auditing this repository with itself"
"$EAOS" audit . --out "$OUT" --skip site >/dev/null

VIOLATIONS=$("$PYTHON" -c "import json,sys; print(len(json.load(open('$OUT/report-result.json'))['output_spec_violations']))")
[ "$VIOLATIONS" -eq 0 ] || { "$PYTHON" -c "import json;[print(' ',v) for v in json.load(open('$OUT/report-result.json'))['output_spec_violations']]"; fail "$VIOLATIONS output-contract violations"; }
echo "  output contract: clean"

POLICY=$("$PYTHON" -c "
import json
m=json.load(open('$OUT/run-manifest.json'))['stages']['policy']
print(m['status'])")
[ "$POLICY" = "ok" ] || fail "the policy stage did not run ($POLICY)"
"$EAOS" policy check . --out "$OUT" >/dev/null || fail "this repository violates its own declared policy"
echo "  architecture policy: clean"

"$PYTHON" tools/invariants.py >/dev/null || fail "an invariant is declared with no test enforcing it"
echo "  declared invariants: all enforced"

"$PYTHON" tools/validate.py >/dev/null || fail "the framework validator reports errors"
echo "  validator: clean"

STAGES=$("$PYTHON" -c "
import json
rows=json.load(open('$OUT/run-manifest.json'))['stages']
bad={n:r['status'] for n,r in rows.items() if r['status'] in ('failed','not_reached')}
print(json.dumps(bad))")
[ "$STAGES" = "{}" ] || fail "stages did not complete: $STAGES"
echo "  every stage completed or explained itself"

if [ -f "$OUT/baseline/baseline.json" ]; then
  "$EAOS" audit . --out "$OUT" --skip site --gate new >/dev/null || fail "a new finding appeared above the pinned baseline"
  echo "  no new debt above the baseline"
else
  echo "  no baseline pinned in this report directory; skipping the debt gate"
fi

echo "PASS: the tool satisfies its own output contract, policy, invariants and validator"

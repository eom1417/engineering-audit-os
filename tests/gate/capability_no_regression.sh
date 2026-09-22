#!/usr/bin/env bash
# N1.T3 — a domain that reached its level must not quietly fall back below it.
set -euo pipefail
cd "$(dirname "$0")/../.."
PYTHON="${PYTHON:-.venv/bin/python}"
EAOS="${EAOS:-.venv/bin/eaos}"
TOLERANCE="${TOLERANCE:-0.02}"
RECORD=docs/capability-score.json
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

[ -f "$RECORD" ] || { echo "FAIL: no recorded scorecard at $RECORD"; exit 1; }

echo "  producing the two reference reports"
"$EAOS" audit . --out "$WORK/self" --skip site >/dev/null
GO=/workspace/upstream-src/enola
if [ -d "$GO" ]; then
  "$EAOS" audit "$GO" --out "$WORK/go" --skip site >/dev/null
  REPORTS=("$WORK/self" "$WORK/go")
else
  echo "  the polyglot reference repository is absent; measuring this repository alone"
  REPORTS=("$WORK/self")
fi

"$PYTHON" tools/capability_score.py "${REPORTS[@]}" > "$WORK/now.json"

"$PYTHON" - "$RECORD" "$WORK/now.json" "$TOLERANCE" <<'PY'
import json, sys
recorded = json.load(open(sys.argv[1]))
now = json.load(open(sys.argv[2]))
tolerance = float(sys.argv[3])
before = {name: row['score'] for name, row in recorded['domains'].items()}
after = now['domains']
regressions = []
for name, was in before.items():
    is_now = after.get(name)
    if was is None or is_now is None:
        continue
    if is_now < was - tolerance:
        regressions.append(f'{name}: {was} -> {is_now}')
if regressions:
    print('FAIL: a domain fell below its recorded level')
    for line in regressions:
        print('  ' + line)
    raise SystemExit(1)
improved = [f'{name}: {before[name]} -> {after[name]}' for name in before
            if before[name] is not None and after.get(name) is not None and after[name] > before[name] + 1e-9]
for line in improved:
    print('  improved ' + line)
print('PASS: no domain regressed beyond the tolerance')
PY

#!/usr/bin/env bash
# N1.T3 / N11.T9 — a domain that reached a level must not quietly fall back below it.
#
# The comparison is against docs/capability-high-water.json, not against the scorecard: the
# scorecard is rewritten by every remeasurement, so comparing a run to a record it just wrote
# passed a real fall from 0.9788 to 0.6667 without a word. The high-water file is written only
# upward, so the bar survives the run that fails to clear it.
#
# The reference reports are produced with the engines on. The product is an argument for using
# them; judging it with them switched off measures a different tool.
set -euo pipefail
cd "$(dirname "$0")/../.."
PYTHON="${PYTHON:-.venv/bin/python}"
EAOS="${EAOS:-.venv/bin/eaos}"
TOLERANCE="${TOLERANCE:-0.02}"
ENGINES="${ENGINES:-codegraph enola jscpd reforge}"
RECORD=docs/capability-high-water.json
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

[ -f "$RECORD" ] || { echo "FAIL: no high-water record at $RECORD; run tools/capability_score.py --write"; exit 1; }

echo "  producing the two reference reports with the engines on"
# shellcheck disable=SC2086
"$EAOS" audit . --out "$WORK/self" --skip site --engines $ENGINES >/dev/null
GO=/workspace/upstream-src/enola
if [ -d "$GO" ]; then
  # shellcheck disable=SC2086
  "$EAOS" audit "$GO" --out "$WORK/go" --skip site --engines $ENGINES >/dev/null
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
before = recorded['domains']
reached = recorded.get('reached_at', {})
after = now['domains']
regressions = []
for name, was in before.items():
    is_now = after.get(name)
    if was is None or is_now is None:
        continue
    if is_now < was - tolerance:
        regressions.append(f"{name}: {was} (reached at {reached.get(name, 'unknown')}) -> {is_now}")
if regressions:
    print('FAIL: a domain fell below the level it had already reached')
    for line in regressions:
        print('  ' + line)
    raise SystemExit(1)
improved = [f'{name}: {before[name]} -> {after[name]}' for name in before
            if before[name] is not None and after.get(name) is not None and after[name] > before[name] + 1e-9]
for line in improved:
    print('  improved ' + line)
print('PASS: no domain fell below its high-water mark')
PY

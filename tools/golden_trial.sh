#!/usr/bin/env bash
# The golden trial (the owner, 2026-10-22: "half the checks never run" must never reach beta-trial again): a whole check
# with the app run, without AI, on a small app whose screens are hash routes with no client router (as EAOS builds),
# copied to a scratch folder. It fails when a stage that runs the app did not end ok, or the report page is missing.
# Then the detection baseline (M0.2): the same check of tests/fixtures/baseline-app, refused when it finds any of its
# planted problems less than tests/fixtures/baseline-problems.json records (tools/detection_baseline.py). Last its clean
# twin (tests/fixtures/baseline-clean, M6.0), checked the same way: refused when the layers find anything on it.
# Usage: tools/golden_trial.sh <eaos executable>   (update.sh runs it with the beta-trial's own eaos)
set -euo pipefail
EAOS=${1:-eaos}
HERE=$(cd "$(dirname "$0")/.." && pwd)
W=$(mktemp -d /tmp/eaos-golden-XXXXXX)
trap 'rm -rf "$W"' EXIT
cp -r "$HERE/tests/fixtures/golden-app" "$W/app"
( cd "$W/app" && git init -q && git add . && git -c user.name=t -c user.email=t@t commit -qm golden )
export EAOS_HOME="$W/home" EAOS_OUTPUT="$W/output"
( cd "$W/app" && "$EAOS" check --run-app --assistant none --lang en --watch >"$W/check.log" 2>&1 ) || { tail -40 "$W/check.log"; exit 1; }
"$(dirname "$EAOS")/python" - "$W/output" "$W/app" <<'PY'
import json, sys
from pathlib import Path
manifest = json.loads(next(Path(sys.argv[1]).rglob('run-manifest.json')).read_text())
wanted = ('setup', 'crawl', 'lock', 'record', 'journeys', 'screens', 'baseline')
crawled = json.loads(next(Path(sys.argv[1]).rglob('live/crawl.json')).read_text()).get('pages')
if len(crawled or []) < 4: sys.exit(f'golden trial failed: the crawl found {crawled}, not the four pages behind the welcome and the buttons')
bad = {s: (manifest['stages'][s]['status'], manifest['stages'][s].get('reason')) for s in wanted if manifest['stages'][s]['status'] != 'ok'}
human = next(Path(sys.argv[1]).rglob('human/index.html'), None)
if not (human and (human.parent.parent / 'RUN.md').is_file()): sys.exit('golden trial failed: no RUN.md beside the report')
if bad or human is None: sys.exit(f'golden trial failed: {bad or "no report for people"}')
from starlette.testclient import TestClient
from eaos.interfaces.api import server
keys = server.Keys(port=8765)
http = TestClient(server.create_app(human.parent.parent, keys=keys, mounts=[], watch=False), base_url='http://127.0.0.1:8765')
url = http.get('/api/report-ticket', headers={'X-EAOS-Token': keys.token}).json()['url']
page = http.get(url)
if page.status_code != 200 or 'text/html' not in page.headers.get('content-type', ''): sys.exit(f'golden trial failed: the report page answered {page.status_code}')
from eaos.journeys import guided
from eaos.live import setup as live_setup
state = guided.load(Path(sys.argv[2]).resolve())
live_setup.authorize(guided.source(state), guided.runtime_of(state), 'golden')       # run_setup, as the fix flow starts
ran = live_setup.setup(guided.source(state), guided.runtime_of(state), report=guided.report_of(state), provider=None)
state['setup'] = {'commit': guided.tip(state), 'ok': ran['ok'], 'attempts': ran['attempts'], 'limitations': ran['limitations']}
safety = guided.safety_run(state)
# the random about screen, alone, is refused: the other screens are locked
if safety.get('passed') != safety.get('screens', 0) - 1 or 'about' not in str(safety.get('skipped')): sys.exit(f"golden trial failed: the safety net recorded {safety.get('screens')} screens, {safety.get('passed')} passed: {safety.get('skipped')}")
from eaos.journeys import agent_tools
if (refused := agent_tools._no_safety_net(guided.load(Path(sys.argv[2]).resolve()))): sys.exit(f'golden trial failed: no fix batch would open: {refused}')
print(f"golden trial: a fix batch opens, every stage that runs the app ended ok, the report for people opens, the safety net recorded {safety['passed']} screens")
PY
cp -r "$HERE/tests/fixtures/baseline-app" "$W/baseline"
( cd "$W/baseline" && git init -q && git add . && git -c user.name=t -c user.email=t@t commit -qm baseline )
( cd "$W/baseline" && EAOS_OUTPUT="$W/baseline-output" "$EAOS" check --run-app --assistant none --lang en --watch >"$W/baseline.log" 2>&1 ) \
  || { tail -40 "$W/baseline.log"; exit 1; }
"$(dirname "$EAOS")/python" "$HERE/tools/detection_baseline.py" "$W/baseline-output"
# The clean twin (M6.0, M6.12): the same app done right, checked the same way; any layer finding on it is refused.
cp -r "$HERE/tests/fixtures/baseline-clean" "$W/clean"
( cd "$W/clean" && git init -q && git add . && git -c user.name=t -c user.email=t@t commit -qm clean )
( cd "$W/clean" && EAOS_OUTPUT="$W/clean-output" "$EAOS" check --run-app --assistant none --lang en --watch >"$W/clean.log" 2>&1 ) \
  || { tail -40 "$W/clean.log"; exit 1; }
"$(dirname "$EAOS")/python" - "$W/clean-output" <<'PY'
import json, sys
from pathlib import Path
record = json.loads(next(Path(sys.argv[1]).rglob('layers.json')).read_text())
if record['findings']: sys.exit('golden trial failed: the clean twin has layer findings: ' + '; '.join(f['en'] for f in record['findings']))
print(f"clean twin: no layer finding on {len(record['map'])} files, {len(record['endpoints'])} endpoints, {len(record['tables'])} tables")
PY

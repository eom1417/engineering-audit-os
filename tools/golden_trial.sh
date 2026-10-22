#!/usr/bin/env bash
# The golden trial (the owner, 2026-10-22: "half the checks never run" must never reach beta-trial again): a whole check
# with the app run, without AI, on a small app whose screens are hash routes with no client router (as EAOS builds),
# copied to a scratch folder. It fails when a stage that runs the app did not end ok, or the report page is missing.
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
wanted = ('setup', 'crawl', 'lock', 'record', 'screens')
bad = {s: (manifest['stages'][s]['status'], manifest['stages'][s].get('reason')) for s in wanted if manifest['stages'][s]['status'] != 'ok'}
human = next(Path(sys.argv[1]).rglob('human/index.html'), None)
if bad or human is None: sys.exit(f'golden trial failed: {bad or "no report for people"}')
from starlette.testclient import TestClient
from eaos.api import server
keys = server.Keys(port=8765)
http = TestClient(server.create_app(human.parent.parent, keys=keys, mounts=[], watch=False), base_url='http://127.0.0.1:8765')
url = http.get('/api/report-ticket', headers={'X-EAOS-Token': keys.token}).json()['url']
page = http.get(url)
if page.status_code != 200 or 'text/html' not in page.headers.get('content-type', ''): sys.exit(f'golden trial failed: the report page answered {page.status_code}')
from eaos import guided
from eaos import live_setup
state = guided.load(Path(sys.argv[2]).resolve())
live_setup.authorize(guided.source(state), guided.runtime_of(state), 'golden')       # run_setup, as the fix flow starts
ran = live_setup.setup(guided.source(state), guided.runtime_of(state), report=guided.report_of(state), provider=None)
state['setup'] = {'commit': guided._commit(state), 'ok': ran['ok'], 'attempts': ran['attempts'], 'limitations': ran['limitations']}
safety = guided.safety_run(state)
if not safety.get('passed'): sys.exit(f"golden trial failed: the safety net recorded {safety.get('screens')} screens, {safety.get('passed')} passed: {safety.get('skipped')}")
print(f"golden trial: every stage that runs the app ended ok, the report for people opens, the safety net recorded {safety['passed']} screens")
PY

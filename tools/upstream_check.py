"""Is it safe to upgrade an engine? Answer offline first, then ask GitHub what exists.

Four upstream projects move on their own schedule. A blind upgrade changes what an adapter reads
without changing the adapter, and the failure is silent: fewer findings, not an error. This tool
runs the pinned contracts first, and only then reports which versions moved.
"""
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REPOSITORIES = {
    'enola': 'enola-labs/enola',
    'codegraph': 'codegraph-ai/CodeGraph',
    'reforge': 'LyleMi/Reforge',
    'jscpd': 'kucherenko/jscpd',
}


def pinned():
    from eaos.engines import ADAPTERS
    return {name: adapter.PINNED for name, adapter in sorted(ADAPTERS.items())}


def contracts_pass():
    """Run the offline contract suite. Nothing here touches the network or an installed binary."""
    done = subprocess.run([sys.executable, '-m', 'unittest', 'tests.test_engine_contracts', '-q'],
                          cwd=ROOT, capture_output=True, text=True)
    return done.returncode == 0, (done.stdout + done.stderr).strip().splitlines()[-1:]


def installed():
    from eaos.engines import ADAPTERS
    return {name: adapter.version() for name, adapter in sorted(ADAPTERS.items())}


def latest(repository, timeout=10):
    url = f'https://api.github.com/repos/{repository}/releases/latest'
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read()).get('tag_name')
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as problem:
        return f'unavailable: {type(problem).__name__}'


def report(online):
    pins = pinned()
    ok, tail = contracts_pass()
    rows = []
    for name in sorted(REPOSITORIES):
        row = {'engine': name, 'pinned': pins.get(name), 'installed': None, 'latest': None}
        if online:
            row['latest'] = latest(REPOSITORIES[name])
            row['moved'] = bool(row['latest'] and not str(row['latest']).startswith('unavailable')
                                and str(row['latest']).lstrip('v') != str(row['pinned']).lstrip('v'))
        rows.append(row)
    if online:
        found = installed()
        for row in rows:
            row['installed'] = found.get(row['engine'])
            row['installed_matches_pin'] = row['installed'] == row['pinned']
    return {'contracts_pass': ok, 'contract_result': tail, 'engines': rows,
            'verdict': ('contracts hold; an upgrade may proceed one engine at a time' if ok else
                        'contracts fail against the pinned samples; do not upgrade anything yet'),
            'limits': 'Passing contracts means the adapter still reads the pinned sample, not that a '
                      'new version behaves the same. Re-capture the sample after any upgrade.'}


def main(argv):
    online = '--online' in argv
    result = report(online)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['contracts_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

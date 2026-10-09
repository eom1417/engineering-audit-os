"""The Studio's speed budgets measured in a real browser on the shipped build (STUDIO-COMPLETE.md, NS46.T2).

    python tools/studio_budgets.py [--data <studio folder>] [--out <file>] [--rounds 5]

The shipped Studio (eaos/data/studio) is laid out with a report's data scripts, as tools/studio_gates.py lays it out
(default: a synthetic report of 5,000 cards and 1,000 components, tools/studio_synthetic.py), served over loopback,
and the Problems page is driven by the pinned Playwright (tools/studio_budgets.mjs): typing Arabic and Latin searches,
ticking facets, grouping and clearing, each step timed from the input event to the first frame painted after the list
changed, on a desktop and on a phone profile with the CPU slowed four times (a mid phone). `filter_5000_ms` is the
slowest step's median on the phone profile. The result goes to $EAOS_MEASURE/studio-gates/budgets.json with the
shipped build's source fingerprint, which F14 and the NS46.T2 acceptance read (tools/north_star_studio.py); a
`home_interactive_ms` measured on the same build is kept.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
from eaos import toolchain  # noqa: E402
from eaos.screens import audit  # noqa: E402

PROFILES = [{'name': 'desktop', 'width': 1440, 'height': 900, 'mobile': False, 'cpu': 1},
            {'name': 'phone-4x-cpu', 'width': 390, 'height': 844, 'mobile': True, 'cpu': 4}]
BUDGETED = 'phone-4x-cpu'


def measure(site, rounds):
    with audit.serve(site) as base, tempfile.TemporaryDirectory(prefix='eaos-budgets-') as folder:
        config = Path(folder) / 'config.json'
        config.write_text(json.dumps({'url': base + 'index.html?lang=ar&theme=light#/problems', 'rounds': rounds, 'profiles': PROFILES,
                                      'modules': {'playwright': str(toolchain.home() / 'node/node_modules')}}), encoding='utf-8')
        done = subprocess.run(['node', str(ROOT / 'tools/studio_budgets.mjs'), str(config)], capture_output=True, text=True, timeout=900,
                              env={**os.environ, 'PLAYWRIGHT_BROWSERS_PATH': str(toolchain.browsers())})
    lines = [line for line in done.stdout.splitlines() if line.startswith('{')]
    if done.returncode or not lines: raise SystemExit(f'studio_budgets.mjs exited {done.returncode}: {(done.stderr or done.stdout)[-1500:]}')
    return json.loads(lines[-1])


def main(argv=None):
    import dev_paths
    import studio_synthetic
    parser = argparse.ArgumentParser(description="The Studio's speed budgets, measured in a browser on the shipped build.")
    parser.add_argument('--data', help='a studio/ folder (default: a fresh synthetic report of 5,000 cards)')
    parser.add_argument('--out', help='default $EAOS_MEASURE/studio-gates/budgets.json')
    parser.add_argument('--rounds', type=int, default=5)
    args = parser.parse_args(argv)
    absent = audit.missing('playwright')
    if absent: print(absent); return 2
    shipped = ROOT / 'eaos/data/studio'
    source = json.loads((shipped / 'SOURCE.json').read_text(encoding='utf-8'))['source_sha256']
    out = Path(args.out or dev_paths.MEASURE / 'studio-gates/budgets.json')
    with tempfile.TemporaryDirectory(prefix='eaos-budgets-site-') as folder:
        site = Path(folder) / 'site'
        shutil.copytree(shipped, site)
        data = Path(args.data) if args.data else Path(folder) / 'data'
        if not args.data:
            problems = studio_synthetic.write(data, studio_synthetic.build())
            if problems: print(f'synthetic report breaks its contracts: {problems[:3]}'); return 2
        for script in data.glob('*.js'): shutil.copy(script, site / script.name)
        result = measure(site, args.rounds)
    phone = next(p for p in result['profiles'] if p['name'] == BUDGETED)
    errors = [e for p in result['profiles'] for e in p['errors']]
    was = json.loads(out.read_text(encoding='utf-8')) if out.is_file() else {}
    record = {'schema_version': 1, 'studio_source_sha256': source, 'measured': datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'filter_5000_ms': None if errors or phone['cards'] < 5000 else phone['worst_median_ms'],
              'filter_5000': {'cards': phone['cards'], 'data': str(args.data or 'synthetic: tools/studio_synthetic.py (5,000 cards, 1,000 components)'),
                              'method': 'Problems page of the shipped build in Chromium (pinned Playwright); each step timed from the input '
                                        'event to the first frame painted after the list changed; the value is the slowest step median on '
                                        f'the {BUDGETED} profile', 'profiles': result['profiles']},
              'home_interactive_ms': was.get('home_interactive_ms') if was.get('studio_source_sha256') == source else None}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    for profile in result['profiles']:
        print(f"{profile['name']}: {profile['cards']} cards; " + '; '.join(f"{s['name']} {s['median_ms']} ms" for s in profile['steps'])
              + f"; slowest median {profile['worst_median_ms']} ms" + (f"; errors: {profile['errors'][:2]}" if profile['errors'] else ''))
    print(f"filter_5000_ms = {record['filter_5000_ms']} (budget 100); {out}")
    return 0 if record['filter_5000_ms'] is not None and record['filter_5000_ms'] <= 100 else 1


if __name__ == '__main__':
    sys.exit(main())

"""Behavioral acceptance for the bundled synthetic pricing fixture.

Usage: python3 check_acceptance.py /absolute/path/to/coupled-billing
Imports only the caller-selected, trusted fixture. Does not mutate that source.
This script is a reference artifact for a proposed check contract, not an EAOS feature.
"""
import importlib.util
import json
from pathlib import Path
import sys


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    if len(sys.argv) != 2:
        print(json.dumps({'status': 'blocked', 'reason': 'Expected one trusted fixture directory'}))
        return 2
    target = Path(sys.argv[1]).resolve()
    if not all((target / name).is_file() for name in ['app.py', 'export.py']):
        print(json.dumps({'status': 'blocked', 'reason': 'Fixture entry files are absent'}))
        return 2
    # Permit a future candidate to share a local rule module; do not write bytecode.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(target))
    try:
        quote = load(target / 'app.py', 'example_quote').quote
        exported_total = load(target / 'export.py', 'example_export').exported_total
        observations = []
        for premium, expected in [(False, 100.0), (True, 90.0)]:
            for entry, function in [('quote', quote), ('exported_total', exported_total)]:
                actual = function(100, premium)
                observations.append({'entry': entry, 'input': {'amount': 100, 'premium': premium},
                                     'expected': expected, 'actual': actual, 'pass': actual == expected})
        passed = all(item['pass'] for item in observations)
        print(json.dumps({'status': 'pass' if passed else 'fail', 'invariant': 'EX-PRICE-01',
                          'observations': observations}, indent=2))
        return 0 if passed else 1
    except (ImportError, AttributeError, OSError) as error:
        print(json.dumps({'status': 'blocked', 'reason': type(error).__name__}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

"""Check a report's artifacts against the contracts in schemas/artifacts/.

The validator lives in eaos/artifact_contracts.py, shared with the stage gates; this is its command line.
An executor runs this on its own output before claiming a task.

Usage:  python tools/contracts.py <report-dir> [--runtime <runtime-dir>]   # exit 1 if any present artifact is invalid
        python tools/contracts.py --list                                    # every contract and its artifact
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from eaos.artifact_contracts import RUNTIME, SCHEMAS, check, contracts, load_valid, location, validate  # noqa: E402,F401


def main(argv):
    if argv == ['--list']:
        for name, schema in contracts().items():
            print(f"{name:24} {'runtime' if name in RUNTIME else 'report ':7} {schema['x-artifact']:30} {schema['x-owner']}")
        return 0
    if not argv or argv[0].startswith('--'):
        print(__doc__.strip().splitlines()[-2].strip(), file=sys.stderr)
        return 2
    runtime = argv[argv.index('--runtime') + 1] if '--runtime' in argv else None
    results = check(argv[0], runtime)
    for name, problems in results.items():
        print(f"{'OK  ' if not problems else 'FAIL'} {name}")
        for problem in problems[:20]: print(f'     {problem}')
    return 1 if any(results.values()) else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

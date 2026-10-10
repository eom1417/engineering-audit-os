"""Golden progress files: real runs kept as fixtures, and the fold each one must keep producing.

    python tools/progress_golden.py record <run-progress.jsonl> <name> --strip <folder>
        copy a real run's progress file to tests/fixtures/progress/<name>.jsonl; the host becomes `golden-host`,
        every process number a small fixed one, and every path under <folder> starts with `/golden` instead
    python tools/progress_golden.py expect
        write tests/fixtures/progress/<name>.fold.json = the Python fold (eaos/progress/fold.py) of every golden file
    python tools/progress_golden.py check
        exit 1 when a committed .fold.json differs from the fold of its golden file

The Studio's TypeScript fold is held to the same .fold.json files (plan section 4.4), so a change to either fold
that changes what the page shows shows up as a diff here.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIXTURES = ROOT / 'tests/fixtures/progress'


def _clean(value, strip):
    """`value` with every path under `strip` starting with /golden instead."""
    if isinstance(value, str): return value.replace(strip, '/golden') if strip else value
    if isinstance(value, list): return [_clean(v, strip) for v in value]
    if isinstance(value, dict): return {k: _clean(v, strip) for k, v in value.items()}
    return value


def sanitized(rows, strip):
    pids = {}
    pid = lambda value: pids.setdefault(value, 1000 + len(pids))
    out = []
    for row in rows:
        row = _clean(row, strip)
        if row.get('event') == 'run.started': row.update(host='golden-host', pid=pid(row.get('pid')))
        if row.get('event') == 'stage.activity':
            row['programs'] = [{**p, 'pid': pid(p.get('pid'))} for p in row.get('programs') or []]
        out.append(row)
    return out


def lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def folded(path):
    from eaos.progress import fold
    return json.dumps(fold(lines(path)), ensure_ascii=False, indent=1, sort_keys=True) + '\n'


def record(argv):
    strip = argv[argv.index('--strip') + 1].rstrip('/') if '--strip' in argv else ''
    rows = sanitized(lines(argv[1]), strip)
    target = FIXTURES / f'{argv[2]}.jsonl'
    target.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    print(f'{target.relative_to(ROOT)}: {len(rows)} lines')
    return 0


def expect_or_check(write):
    """Write each golden file's fold (`write`), or report the golden files whose committed fold differs."""
    differ = []
    for path in sorted(FIXTURES.glob('*.jsonl')):
        expected = path.with_suffix('.fold.json')
        text = folded(path)
        if write: expected.write_text(text, encoding='utf-8')
        elif not expected.is_file() or expected.read_text(encoding='utf-8') != text: differ.append(path.name)
    print('differ: ' + ', '.join(differ) if differ else 'all golden folds match')
    return 1 if differ else 0


def main(argv):
    if argv[:1] == ['record'] and len(argv) >= 3: return record(argv)
    if argv[:1] in (['expect'], ['check']): return expect_or_check(argv[0] == 'expect')
    print(__doc__)
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

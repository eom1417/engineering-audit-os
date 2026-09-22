"""Measure the engine's reach into each language before any change is attempted.

For every language the snapshot has files in, this tool reports:
  files           how many files the snapshot holds in that language
  hashed          how many of them are within the engine's size and capture limits
  parsed          how many of those the parser extracted from
  imports_resolved  how many of those imports resolved to another in-target file
  symbols         how many function/class symbols the parser produced

The result is the baseline every polyglot task compares itself against.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eaos.facts.source import language_of, inventory  # noqa: E402
from eaos.facts.run import collect  # noqa: E402


KNOWN_TARGETS = {
    'enola': '/workspace/upstream-src/enola',
    'codegraph': '/workspace/upstream-src/CodeGraph',
    'reforge': '/workspace/upstream-src/Reforge',
    'jscpd': '/workspace/upstream-src/jscpd',
}


def measure(target, sets_required=('syntax', 'resolve')):
    """Run the chosen extractors and return one row per language with the counts."""
    target = Path(target).resolve()
    inventory_data = inventory(target)
    out = Path('/tmp') / f'.tmp-language-depth-{Path(target).name}'
    if out.exists():
        import shutil; shutil.rmtree(out)
    collect(target, out, list(sets_required))
    by_lang = {}
    import json
    syntax_facts = json.loads((out / 'facts/syntax.json').read_text())['facts']
    for fact in syntax_facts:
        path = fact['location']['path']
        lang = language_of(path) or 'unknown'
        row = by_lang.setdefault(lang, {'files': 0, 'parsed': 0, 'symbols': 0, 'imports': 0, 'imports_resolved': 0})
        row['parsed'] += 1
        if fact['kind'] == 'symbol':
            row['symbols'] += 1
        elif fact['kind'] == 'import_edge':
            row['imports'] += 1
            if fact.get('resolution') == 'RESOLVED':
                row['imports_resolved'] += 1
    # Add file counts from inventory.
    for f in inventory_data['files']:
        lang = language_of(f['path']) or 'unknown'
        row = by_lang.setdefault(lang, {'files': 0, 'parsed': 0, 'symbols': 0, 'imports': 0, 'imports_resolved': 0})
        row['files'] += 1
    import shutil
    shutil.rmtree(out)
    return by_lang


def render(name, target_path):
    row = measure(target_path)
    lines = [f'# {name}: language depth', '']
    lines += ['| language | files | parsed | symbols | imports_resolved | resolve_rate |']
    lines += ['| --- | --- | --- | --- | --- | --- |']
    for lang in sorted(row):
        r = row[lang]
        resolve_rate = round(r['imports_resolved'] / r['imports'], 4) if r['imports'] else 0.0
        lines += [f"| {lang} | {r['files']} | {r['parsed']} | {r['symbols']} | {r['imports_resolved']} | {resolve_rate} |"]
    return '\n'.join(lines) + '\n'


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Write docs/language-depth.json')
    parser.add_argument('--target', choices=list(KNOWN_TARGETS) + ['self'], default='self')
    args = parser.parse_args(argv)

    targets = {'self': str(ROOT)}
    targets.update(KNOWN_TARGETS)
    target = targets[args.target]

    name = args.target
    data = {name: measure(target)}
    print(render(name, target))
    if args.write:
        import json
        path = ROOT / 'docs' / 'language-depth.json'
        existing = json.loads(path.read_text()) if path.is_file() else {}
        existing.update(data)
        path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + '\n')
        print(f'wrote {path}')


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

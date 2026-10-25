"""The numbers of docs/METRICS.md, measured from the repository and from a real check of EAOS (M0.4).

    python tools/metrics.py <check output> <project home> [--write "<title>"]

<check output> is the check's output folder (the one holding technical/), <project home> the project's folder in
EAOS's home (the one holding runtime/); the development container's RUNBOOK.md names them for its develop check.
It prints the table; --write puts it in docs/METRICS.md as the section "<title>", replacing one of the same title.
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / 'docs' / 'METRICS.md'
CORPUS = ROOT / 'tools' / 'corpus.json'
PROBLEMS = ROOT / 'tests' / 'fixtures' / 'baseline-problems.json'
MB = 1024 * 1024


def lines(paths):
    paths = list(paths)
    return sum(len(path.read_text(encoding='utf-8', errors='replace').splitlines()) for path in paths), len(paths)


def size(folder):
    """(MB, files) as the disk holds them: a file with two names (REPORT.html) counted once."""
    files = {(stat.st_dev, stat.st_ino): stat.st_size for path in Path(folder).rglob('*')
             if path.is_file() and not path.is_symlink() for stat in [path.stat()]}
    return sum(files.values()) // MB, len(files)


def read(path, default=None):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def code():
    python, modules = lines((ROOT / 'eaos').rglob('*.py'))
    flat = len(list((ROOT / 'eaos').glob('*.py')))
    js, scripts = lines((ROOT / 'console' / 'src').rglob('*.js'))
    words, _ = lines((ROOT / 'console' / 'src' / 'words').glob('*.js'))
    tests = sorted((ROOT / 'tests').glob('test_*.py'))
    test_lines, test_files = lines(tests)
    cases = sum(path.read_text(encoding='utf-8').count('def test_') for path in tests)
    return [('Python lines (`eaos/`)', f'{python:,} in {modules} files ({flat} flat at the package root)'),
            ('Studio UI (`console/src`)', f'{js:,} JS lines in {scripts} files (words {words:,})'),
            ('Tests', f'{test_lines:,} lines in {test_files} files, {cases} test functions')]


def engine_findings(technical):
    reports = ((read(technical / 'engines' / 'engines.json', {}) or {}).get('engines') or {}).values()
    return [row for report in reports for row in report.get('findings') or []]


def check(output, home):
    technical = Path(output) / 'technical'
    manifest = read(technical / 'run-manifest.json', {})
    stages = manifest.get('stages') or {}
    findings = engine_findings(technical)
    engines = Counter(row['engine'] for row in findings).most_common(2)
    tools = len((read(ROOT / 'eaos' / 'data' / 'toolchain.json', {}) or {}).get('tools') or [])
    out_mb, out_files = size(output)
    runtime_mb, _ = size(Path(home) / 'runtime')
    return [('Check time', _check_time(manifest, stages)),
            ('Stages / documents / engines', f"{len(stages)} / {len(list(technical.glob('*.md')))} `.md` / {tools} tools"),
            ('Output', f'{out_mb:,} MB, {out_files:,} files'),
            ('Runtime', f'{runtime_mb:,} MB'),
            ('Cards on itself', _cards_on_itself(technical)),
            ('Engine findings', f"{len(findings):,} ({', '.join(f'`{name}` {count:,}' for name, count in engines)})")]


def _check_time(manifest, stages):
    """The check's wall time and its four slowest stages."""
    slowest = sorted(stages.items(), key=lambda item: -(item[1].get('seconds') or 0))[:4]
    return f"{manifest.get('seconds', 0):,.0f} s wall (" + ' · '.join(f"{name} {row.get('seconds') or 0:,.0f}" for name, row in slowest) + ')'


def _cards_on_itself(technical):
    """The plan tasks the check made on EAOS, their three commonest patterns, and the claims they come from."""
    tasks = (read(technical / 'plan.json', {}) or {}).get('tasks') or []
    patterns = Counter(task.get('pattern') for task in tasks).most_common(3)
    return (f"{len(tasks)} plan tasks ({', '.join(f'{count} {name}' for name, count in patterns)}) "
            f"from {(read(technical / 'report-result.json', {}) or {}).get('claims', 0)} claims")


def trials():
    return [('Compatibility corpus', _corpus()), ('Detection baseline', _baseline())]


def _corpus():
    apps = (read(CORPUS, {}) or {}).get('apps') or []
    run = [app for app in apps if app.get('result')]
    passed = sum(app['result'].get('passed', False) for app in run)
    return f'{passed} of {len(run)} apps pass ({len(apps)} pinned)' if run else 'not run yet'


def _baseline():
    problems = (read(PROBLEMS, {}) or {}).get('problems') or []
    found = sum(problem.get('found', 'missed') != 'missed' for problem in problems)
    return f'{found} of {len(problems)} planted problems found' if problems else 'not built yet'


def table(output, home):
    rows = code() + check(output, home) + trials()
    return '| Measure | Value |\n|---|---|\n' + '\n'.join(f'| {name} | {value} |' for name, value in rows) + '\n'


def write(title, text):
    """docs/METRICS.md with the section `## title` holding `text`, replacing the section of that title, or added
    before the findings sections."""
    page = METRICS.read_text(encoding='utf-8')
    section = f'## {title}\n\n{text}\n'
    start = page.find(f'## {title}\n')
    if start >= 0:
        end = page.find('\n## ', start + 1)
        page = page[:start] + section + (page[end + 1:] if end >= 0 else '')
    else:
        anchor = page.find('\n## Findings')
        page = page[:anchor + 1] + section + '\n' + page[anchor + 1:] if anchor >= 0 else page.rstrip('\n') + '\n\n' + section
    METRICS.write_text(page, encoding='utf-8')


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    measured = table(sys.argv[1], sys.argv[2])
    print(measured)
    if '--write' in sys.argv: write(sys.argv[sys.argv.index('--write') + 1], measured)

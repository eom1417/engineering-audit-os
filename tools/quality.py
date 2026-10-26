"""Every law of docs/STANDARDS.md §1-2 in one command (tools/quality.sh): code limits, layers, duplication, dead code
and security, measured on EAOS's own code by the same engines EAOS runs on any project.

Code limits, written-once and layers hold as tools/code_limits.json and pyproject.toml say. Every other number is
recorded in tools/quality.json and may only go down: one that grew, or a finding of a kind not recorded, fails. After a
number went down, `tools/quality.sh --record` writes the new numbers (refused while anything is worse).
"""
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]   # this folder too: PYTHONSAFEPATH leaves it out
import code_limits  # noqa: E402  (beside this file)
from eaos import engines  # noqa: E402
from eaos.engines.process import which  # noqa: E402

BASELINE = ROOT / 'tools' / 'quality.json'
# enola is not one of them: its dead-code count moves with the words of the documents (CHANGELOG, METRICS), not the code.
ENGINES = ('jscpd', 'bandit', 'semgrep', 'gitleaks', 'osv-scanner')
# Not what EAOS ships: the tests and their fixtures, the developer tools (tools/, console/tools: the code limits still
# hold them), an assistant's worktrees (.claude), the built Studio, the examples beside EAOS's semgrep rules, and what is vendored or generated.
EXCLUDE = ('tests', 'tools', '.claude', 'node_modules', 'eaos/data/studio', 'eaos/rules', 'upstreams', 'acceptance', 'build')
CODE = ('python', 'javascript', 'css')  # what jscpd compares: the code, not data or prose


def engine_counts(workdir):
    """({'engine:rule': findings}, [engines that did not run]) over the repository."""
    manifest = engines.analyze(ROOT, workdir, exclude=EXCLUDE, only=ENGINES, formats=CODE)
    failed = [f'{name} did not run: {row["status"]} {row["reason"]}'.strip()
              for name, row in manifest['coverage'].items() if row['status'] != 'observed']
    counts = Counter(f"{row['engine']}:{row['rule']}" for row in manifest['findings'])
    return counts, failed


def dead_counts(workdir):
    """{'deadcode:rule': findings} of EAOS's own dead-code detector (eaos/facts/dead_code/detect.py) over the Python code, the one
    every check runs (vulture's were all names called by dispatch, M2.3); the Studio's is knip's below. tools/ is EAOS's
    code too: what only it reads is read (the code laws' limits were said never read)."""
    from eaos.facts.run import collect
    collect(ROOT, workdir, ['syntax', 'resolve', 'entrypoints', 'deadcode'], exclude=(*(e for e in EXCLUDE if e != 'tools'), 'console'))
    facts = json.loads((Path(workdir) / 'facts' / 'deadcode.json').read_text(encoding='utf-8'))['facts']
    return Counter(f"deadcode:{fact['value']['rule']}" for fact in facts if fact.get('kind') == 'engine_finding'
                   and fact['value']['adjudication']['verdict'] == 'confirmed')


def knip_counts():
    """{'knip:kind': items} over the Studio's source, its entries as console/knip.json declares them."""
    out = subprocess.run([which('knip'), '--reporter', 'json', '--no-exit-code', '--no-progress'], cwd=ROOT / 'console',
                         capture_output=True, text=True, check=True).stdout
    counts = Counter()
    for issue in json.loads(out)['issues']:
        counts.update({f'knip:{kind}': len(items) for kind, items in issue.items() if isinstance(items, list)})
    return counts


def studio_lint():
    """The Studio's JavaScript (console/src): each name never defined and each import or variable never used, by ESLint with
    only those two rules (console/eslint.config.js); none is allowed."""
    eslint = ROOT / 'console' / 'node_modules' / '.bin' / 'eslint'
    if not eslint.is_file(): return ['studio lint: eslint is not installed: run npm ci in console/']
    found = subprocess.run([str(eslint), '--format', 'json', 'src'], cwd=ROOT / 'console', capture_output=True, text=True)
    if found.returncode > 1: return ['studio lint: eslint failed: ' + found.stderr.strip()[-300:]]
    return [f"studio lint: {Path(row['filePath']).relative_to(ROOT).as_posix()}:{m.get('line')}: {m['message']} ({m.get('ruleId')})"
            for row in json.loads(found.stdout) for m in row['messages']]


def law_problems():
    """What breaks a law that has no recorded number: a limit passed, logic written twice, a leftover (in the Studio too), a
    layer crossed."""
    problems = [f'code limit: {breach}' for breach in code_limits.breaches(code_limits.measure(), code_limits.load())]
    problems += [f'written twice: {", ".join(group)}' for group in code_limits.duplicates()]
    problems += [f'leftover: {message}' for message in code_limits.leftovers()]
    problems += studio_lint()
    layers = subprocess.run([str(Path(sys.executable).parent / 'lint-imports')], cwd=ROOT, capture_output=True, text=True)
    problems += [f'layers: {line.strip()}' for line in layers.stdout.splitlines() if line.rstrip().endswith('BROKEN')]
    return problems + (['layers: lint-imports failed: ' + layers.stderr.strip()[-300:]] if layers.returncode > 1 else [])


def worse(now, recorded):
    """Each number above its record (a kind not recorded is recorded at 0)."""
    return [f'{key}: {count} (recorded {recorded.get(key, 0)})' for key, count in sorted(now.items())
            if count > recorded.get(key, 0)]


def measure():
    counts = Counter({f'code:{kind}': len(over) for kind, over in code_limits.measure().items()})
    with tempfile.TemporaryDirectory() as workdir:
        found, failed = engine_counts(workdir)
        dead = dead_counts(workdir)
    return +(counts + found + dead + knip_counts()), law_problems() + failed


def main(record=False):
    now, problems = measure()
    recorded = json.loads(BASELINE.read_text(encoding='utf-8')) if BASELINE.is_file() else {}
    if recorded or not record: problems += worse(now, recorded)  # the first --record writes today's numbers
    lower = sorted(key for key, count in recorded.items() if now.get(key, 0) < count)
    for key in sorted(set(now) | set(recorded)): print(f'{key:70} {now.get(key, 0):6} (recorded {recorded.get(key, 0)})')
    if problems:
        print('\nREFUSED, worse than recorded or against a law:\n  ' + '\n  '.join(problems))
        return 1
    if record:
        BASELINE.write_text(json.dumps(dict(sorted(now.items())), indent=1) + '\n', encoding='utf-8')
        print('\nrecorded')
    elif lower: print(f'\nOK; {len(lower)} numbers went down: run tools/quality.sh --record')
    else: print('\nOK')
    return 0


if __name__ == '__main__':
    sys.exit(main('--record' in sys.argv))

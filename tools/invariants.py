"""Every invariant a docstring asserts must have a test that fails when it is broken.

An invariant nobody enforces is not an invariant; it is an intention. This tool extracts each
claim, matches it against the register in docs/invariants.json, and fails when one has no
enforcing test — or when the register names a test that no longer exists.
"""
import ast
import json
import re
import subprocess
import sys
from hashlib import sha1
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / 'docs/invariants.json'
# Words that turn a description into an assertion about what the system will not do.
CLAIM = re.compile(r'\b(never|always|must not|must be|must have|must stay|cannot|may not|no \w+ (?:may|is|are))\b',
                   re.IGNORECASE)
ARABIC_CLAIM = re.compile(r'(لا يجوز|يجب ألا|يجب أن|لا يمكن|لن)')


def identity(path, symbol, sentence):
    return 'INV-' + sha1(f'{path}|{symbol}|{sentence}'.encode('utf-8')).hexdigest()[:10]


def sentences(text):
    for raw in re.split(r'(?<=[.!؟])\s+|\n\n', text):
        sentence = ' '.join(raw.split())
        if sentence and (CLAIM.search(sentence) or ARABIC_CLAIM.search(sentence)):
            yield sentence


def extract(root=None):
    """Every invariant sentence in the package, with a content-derived identity."""
    root = Path(root or ROOT / 'eaos')
    found = []
    for path in sorted(root.rglob('*.py')):
        relative = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding='utf-8'))
        targets = [(tree, '<module>')] + [(node, node.name) for node in ast.walk(tree)
                                          if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        for node, symbol in targets:
            doc = ast.get_docstring(node)
            if not doc:
                continue
            for sentence in sentences(doc):
                found.append({'id': identity(relative, symbol, sentence), 'file': relative,
                              'symbol': symbol, 'statement': sentence})
    return found


def load_register():
    if not REGISTER.is_file():
        return {'schema_version': 1, 'invariants': []}
    return json.loads(REGISTER.read_text(encoding='utf-8'))


def merge(found, register):
    """Keep what the register knows, add what is new, drop what the code no longer says."""
    known = {row['id']: row for row in register.get('invariants', [])}
    merged = []
    for row in found:
        previous = known.get(row['id'], {})
        merged.append({**row, 'kind': previous.get('kind', 'invariant'),
                       'enforced_by': previous.get('enforced_by'),
                       'note': previous.get('note', '')})
    return {'schema_version': 1, 'extracted_at_commit': commit(), 'invariants': merged,
            'limits': 'Extraction is lexical: it finds sentences that assert, not every promise a '
                      'docstring makes. A sentence it misses is still an invariant.'}


def commit():
    done = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, cwd=ROOT)
    return done.stdout.strip() or 'unknown'


def known_tests():
    """Every test id in the suite, as module::Class::method."""
    ids = set()
    for path in sorted((ROOT / 'tests').glob('test_*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        module = path.stem
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for inner in node.body:
                    if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)) and inner.name.startswith('test'):
                        ids.add(f'tests/{module}.py::{node.name}::{inner.name}')
    return ids


def check(register):
    problems = []
    tests = known_tests()
    for row in register['invariants']:
        if row.get('kind') == 'rationale':
            # Explaining why the code is shaped this way is not a promise about behaviour, but the
            # exemption has to be argued or it becomes a way to opt out of every invariant.
            if not (row.get('note') or '').strip():
                problems.append(f"{row['id']} {row['file']}:{row['symbol']} is marked rationale "
                                f"without saying why it is not an invariant")
            continue
        if row.get('kind') not in ('invariant', 'rationale'):
            problems.append(f"{row['id']} has an unknown kind {row.get('kind')!r}")
            continue
        enforcing = row.get('enforced_by')
        if not enforcing:
            problems.append(f"{row['id']} {row['file']}:{row['symbol']} has no enforcing test — "
                            f"write one or delete the sentence: {row['statement'][:90]}")
            continue
        for test in ([enforcing] if isinstance(enforcing, str) else enforcing):
            if test not in tests:
                problems.append(f"{row['id']} names a test that does not exist: {test}")
    return problems


def main(argv):
    register = merge(extract(), load_register())
    if '--list' in argv:
        REGISTER.write_text(json.dumps(register, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        unenforced = sum(1 for row in register['invariants']
                         if row.get('kind', 'invariant') == 'invariant' and not row.get('enforced_by'))
        print(f"{len(register['invariants'])} statements, {unenforced} invariants without an enforcing "
              f"test -> {REGISTER.relative_to(ROOT)}")
        return 0
    problems = check(register)
    if '--json' in argv:
        print(json.dumps({'invariants': len(register['invariants']), 'problems': problems}, ensure_ascii=False, indent=1))
    else:
        for problem in problems:
            print(problem)
        print(f"{len(register['invariants'])} invariants, {len(problems)} unenforced")
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

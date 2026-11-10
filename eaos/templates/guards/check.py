"""The guards a repository keeps: every count of a rule per file is a ceiling that may only fall, and zero is a ban.

    python check.py --config <config.json>             fails (exit 1) when any count rose above its ceiling
    python check.py --config <config.json> --tighten   lowers the ceilings to the counts of today
    python check.py --config <config.json> --record    writes the first ledger; refused when one exists

It needs only Python's standard library, so it runs in any repository without EAOS. The config names the folders read,
the folders left out, the line length, the patterns of comments that tell history, and the files allowed to read the
environment; the ledger (`ledger` in the config, beside it) holds {rule: {file: count}}. Rules, each counted per file:

    long_lines        lines over the limit, unless the part past the limit is inside a string literal or a URL
    swallowed_errors  an except clause with no type, or whose body only passes or continues;
                      contextlib.suppress(Exception) or suppress(BaseException)
    commented_code    a comment whose text is a Python statement
    history_comments  a comment or docstring matching one of the history patterns
    skipped_tests     a skip or expected-failure decorator, and every skipTest call
    env_readers       os.environ and os.getenv outside the allowed files
    suppressions      noqa, type: ignore, pylint: disable, limits:, jscpd:ignore and ast-grep-ignore comments
    junk_files        backup, temporary and copied files (.bak, .orig, ~, tmp-, -old, -copy)
"""
import argparse
import ast
import io
import json
import re
import sys
import tokenize
from pathlib import Path

URL = re.compile(r'https?://\S+')
SUPPRESSION = re.compile(r'#\s*(noqa|type:\s*ignore|pylint:\s*disable|limits:|jscpd:ignore)|ast-grep-ignore', re.I)
JUNK = re.compile(r'(\.(bak|orig|tmp|swp|rej)|~)$|^(tmp|temp)-|-(old|copy|backup)\.\w+$| copy(\.\w+)?$', re.I)
CODE_HINT = re.compile(r'[=(\[]|:\s*$|^(import|from|return|raise|if|for|while|def|class)\b')
SKIP_DECORATORS = {'skip', 'skipIf', 'skipUnless', 'expectedFailure', 'xfail'}
BROAD = {'Exception', 'BaseException'}


def _tokens(source):
    try:
        return list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, SyntaxError):
        return []


def long_lines(source, tree, config):
    limit = config['max_line']
    strings = [(t.start, t.end) for t in _tokens(source) if t.type == tokenize.STRING]

    def in_string(row):
        return any(start[0] <= row <= end[0] and (start[0] < row or start[1] < limit) and (end[0] > row or end[1] > limit)
                   for start, end in strings)
    count = 0
    for row, line in enumerate(source.splitlines(), start=1):
        if len(line) > limit and not URL.search(line[limit - 40:]) and not in_string(row): count += 1
    return count


def _only_passes(body):
    return all(isinstance(node, (ast.Pass, ast.Continue)) or
               (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)) for node in body)


def _suppresses_all(node):
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', '')
    return name == 'suppress' and any(isinstance(arg, ast.Name) and arg.id in BROAD for arg in node.args)


def swallowed_errors(source, tree, config):
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and (node.type is None or _only_passes(node.body)): count += 1
        elif isinstance(node, ast.Call) and _suppresses_all(node): count += 1
    return count


def _comments(source):
    return [t.string.lstrip('#').strip() for t in _tokens(source) if t.type == tokenize.COMMENT]


def _is_code(text):
    if not text or SUPPRESSION.search('#' + text) or not CODE_HINT.search(text): return False
    if re.match(r'^[A-Z][a-z]+\s', text) or text.endswith('.'): return False
    try:
        compile(text, '<comment>', 'exec')
    except SyntaxError:
        return False
    return True


def commented_code(source, tree, config):
    return sum(_is_code(text) for text in _comments(source))


def _docstrings(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            text = ast.get_docstring(node, clean=False)
            if text: yield text


def history_comments(source, tree, config):
    patterns = [re.compile(pattern) for pattern in config['history_patterns']]
    texts = _comments(source) + list(_docstrings(tree))
    return sum(any(pattern.search(text) for pattern in patterns) for text in texts)


def _name(node):
    if isinstance(node, ast.Call): node = node.func
    return node.attr if isinstance(node, ast.Attribute) else getattr(node, 'id', '')


def skipped_tests(source, tree, config):
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            count += sum(_name(decorator) in SKIP_DECORATORS for decorator in node.decorator_list)
        elif isinstance(node, ast.Call) and _name(node) == 'skipTest':
            count += 1
    return count


def env_readers(source, tree, config, path=''):
    if path in config.get('env_allowed', []): return 0
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in ('environ', 'getenv') and _name(node.value) == 'os':
            count += 1
    return count


def suppressions(source, tree, config):
    return sum(bool(SUPPRESSION.search(t.string)) for t in _tokens(source) if t.type == tokenize.COMMENT)


RULES = {'long_lines': long_lines, 'swallowed_errors': swallowed_errors, 'commented_code': commented_code,
         'history_comments': history_comments, 'skipped_tests': skipped_tests, 'env_readers': env_readers,
         'suppressions': suppressions}


def files(root, config):
    excluded = tuple(config.get('exclude', []))
    for folder in config['folders']:
        for path in sorted((root / folder).rglob('*')):
            rel = path.relative_to(root).as_posix()
            if path.is_file() and '__pycache__' not in path.parts and not rel.startswith(excluded): yield rel, path


def measure(root, config):
    counts = {rule: {} for rule in [*RULES, 'junk_files']}
    for rel, path in files(root, config):
        if JUNK.search(path.name): counts['junk_files'][rel] = 1
        if path.suffix != '.py': continue
        source = path.read_text(encoding='utf-8')
        tree = ast.parse(source)
        for rule, count_of in RULES.items():
            found = count_of(source, tree, config, rel) if rule == 'env_readers' else count_of(source, tree, config)
            if found: counts[rule][rel] = found
    return counts


def compare(counts, ledger):
    """(rises, falls): each a list of (rule, file, ceiling, now)."""
    rises, falls = [], []
    for rule, now in counts.items():
        ceilings = ledger.get(rule, {})
        for rel in sorted(set(now) | set(ceilings)):
            ceiling, found = ceilings.get(rel, 0), now.get(rel, 0)
            if found > ceiling: rises.append((rule, rel, ceiling, found))
            elif found < ceiling: falls.append((rule, rel, ceiling, found))
    return rises, falls


def totals(counts):
    return {rule: sum(per_file.values()) for rule, per_file in counts.items()}


def write(path, data):
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + '\n', encoding='utf-8')


def _arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--config', required=True)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--tighten', action='store_true')
    action.add_argument('--record', action='store_true')
    return parser.parse_args(argv)


def _record(ledger_path, counts):
    if ledger_path.exists(): sys.exit('guards: a ledger exists; ceilings only fall (--tighten)')
    write(ledger_path, counts)
    print('guards: recorded', totals(counts))
    return 0


def _check(ledger_path, counts, tighten):
    ledger = json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else {}
    rises, falls = compare(counts, ledger)
    for rule, rel, ceiling, found in rises: print(f'guards: {rule} rose in {rel}: {ceiling} -> {found}')
    if rises: return 1
    if tighten and falls:
        write(ledger_path, {rule: {k: v for k, v in now.items() if v} for rule, now in counts.items()})
        print(f'guards: {len(falls)} ceilings lowered')
    elif falls:
        print(f'guards: {len(falls)} ceilings can fall: run with --tighten')
    print('guards: totals', totals(counts))
    return 0


def main(argv=None):
    args = _arguments(argv)
    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text(encoding='utf-8'))
    root, ledger_path = (config_path.parent / config['root']).resolve(), config_path.parent / config['ledger']
    counts = measure(root, config)
    return _record(ledger_path, counts) if args.record else _check(ledger_path, counts, args.tighten)

if __name__ == '__main__':
    sys.exit(main())

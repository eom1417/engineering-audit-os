"""Size, branching and duplicated blocks — signals for where to look, never scores of quality."""
import ast
from collections import defaultdict
import re

from ...core.contracts.code_laws import complexity
from .. import digest, make
from ..source import language_of

NAME = 'metrics'
VERSION = '2'
LIMITATIONS = [
    'Branch counting is a lexical approximation, not a compiler-accurate cyclomatic complexity.',
    "A function's complexity is the code laws' count (eaos/core/contracts/code_laws.py) in Python; elsewhere 1 + its lexical "
    'branches. Either way a nested function is counted alone.',
    'Large or branch-heavy code is not a defect; it marks where a change scenario deserves review.',
    'Duplicate detection compares normalised lines; renamed variables still match, restructured logic does not.',
    'Generated and vendored code is only excluded when the snapshot excludes it.',
]
BRANCH = re.compile(r'\b(if|elif|else if|for|while|case|catch|except|&&|\|\||\?\?)\b|\?[^:]+:')
COMMENT = re.compile(r'^\s*(#|//|/\*|\*|--)')
WINDOW = 6
MIN_LINE_LENGTH = 12


def nesting_depth(lines, language):
    depth = maximum = 0
    if language == 'python':
        for line in lines:
            stripped = line.strip()
            if not stripped or COMMENT.match(line): continue
            indent = (len(line) - len(line.lstrip(' '))) // 4
            maximum = max(maximum, indent)
        return maximum
    for line in lines:
        depth += line.count('{') - line.count('}')
        maximum = max(maximum, depth)
    return max(maximum, 0)


def normalise(line): return re.sub(r'\s+', ' ', line.strip())


def _branches(lines): return sum(len(BRANCH.findall(line)) for line in lines)


def _readable_code(source):
    for item in source.readable():
        rel = item['path']
        if language_of(rel) is None: continue
        text = source.text(rel)
        if text is None: continue
        yield item, rel, text.split('\n')


def _file_metric(item, rel, lines, language, symbol_count):
    code_lines = [line for line in lines if line.strip() and not COMMENT.match(line)]
    return make('metric', NAME, VERSION, item['sha256'], {'path': rel},
                {'scope': 'file', 'lines': len(lines), 'code_lines': len(code_lines),
                 'branches': _branches(code_lines),
                 'max_nesting': nesting_depth(lines, language), 'symbols': symbol_count},
                limitations=LIMITATIONS)


def _symbol_metric(item, rel, lines, language, fact):
    start, end = fact['location']['start_line'], fact['location']['end_line']
    body = lines[start - 1:end]
    return make('metric', NAME, VERSION, item['sha256'],
                {'path': rel, 'start_line': start, 'end_line': end, 'symbol': fact['location'].get('symbol')},
                {'scope': fact['value']['kind'], 'lines': len(body),
                 'branches': _branches(body), 'complexity': fact['complexity'],
                 'max_nesting': nesting_depth(body, language)}, limitations=LIMITATIONS)


def _counter(lines, language, mine):
    """fact -> its complexity: the code laws' count of a Python function (its def line), else 1 + the lexical branches of
    its lines but those of the symbols nested in it."""
    exact = {}
    if language == 'python':
        try: tree = ast.parse('\n'.join(lines))
        except (SyntaxError, ValueError): tree = None
        exact = {node.lineno: complexity(node) for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))} if tree else {}
    def counted(fact):
        start, end = fact['location']['start_line'], fact['location']['end_line']
        if start in exact: return exact[start]
        nested = {line for other in mine if other is not fact and start < other['location']['start_line'] <= end
                  for line in range(other['location']['start_line'], other['location']['end_line'] + 1)}
        return 1 + _branches([lines[i - 1] for i in range(start, end + 1) if i not in nested and i <= len(lines)])
    return counted


def _windows_of(rel, lines):
    cleaned = [(index + 1, normalise(line)) for index, line in enumerate(lines)
               if len(normalise(line)) >= MIN_LINE_LENGTH and not COMMENT.match(line)]
    chunks = [cleaned[position:position + WINDOW] for position in range(len(cleaned) - WINDOW + 1)]
    return [(digest('\n'.join(text for _, text in chunk).encode('utf-8')),
             {'path': rel, 'start_line': chunk[0][0], 'end_line': chunk[-1][0]}) for chunk in chunks]


def _is_clone(places):
    distinct = {(place['path'], place['start_line']) for place in places}
    if len(distinct) < 2: return False
    return len({place['path'] for place in places}) >= 2 or len(places) >= 3


def _clone_fact(key, places):
    return make('clone_cluster', NAME, VERSION, key,
                {'path': sorted(place['path'] for place in places)[0]},
                {'window_lines': WINDOW, 'occurrences': sorted(places, key=lambda p: (p['path'], p['start_line'])),
                 'files': sorted({place['path'] for place in places})}, limitations=LIMITATIONS)


def _summary(facts, totals, clusters):
    metrics = [f for f in facts if f['kind'] == 'metric']
    hotspots = sorted((f for f in metrics if f['value']['scope'] != 'file'),
                      key=lambda f: (-f['value'].get('complexity', 0), -f['value']['lines'], f['location']['path']))[:20]
    largest = sorted((f for f in metrics if f['value']['scope'] == 'file'), key=lambda f: -f['value']['lines'])[:15]
    return {**totals, 'clone_clusters': clusters,
            'largest_files': [{'path': f['location']['path'], 'lines': f['value']['lines']} for f in largest],
            'most_branching_symbols': [{'path': f['location']['path'], 'symbol': f['location'].get('symbol'),
                                        'branches': f['value']['branches'], 'complexity': f['value'].get('complexity'),
                                        'lines': f['value']['lines']} for f in hotspots],
            'interpretation': 'Size and branching are attention signals. They are never severity, and never a reason to split code on their own.'}


def _symbols_by_path(target, source, symbols):
    from . import syntax
    if symbols is None:
        symbols = [f for f in syntax.run(target, source)['facts'] if f['kind'] == 'symbol']
    by_path = defaultdict(list)
    for fact in symbols: by_path[fact['location']['path']].append(fact)
    return by_path


def run(target, source, symbols=None, **options):
    by_path = _symbols_by_path(target, source, symbols)
    facts, fingerprints, windows = [], [], defaultdict(list)
    totals = {'files': 0, 'lines': 0, 'symbols': 0}
    for item, rel, lines in _readable_code(source):
        language = language_of(rel)
        mine = sorted(by_path.get(rel, []), key=lambda f: f['location']['start_line'])
        fingerprints.append(item['sha256'])
        totals['files'] += 1
        totals['lines'] += len(lines)
        totals['symbols'] += len(mine)
        facts.append(_file_metric(item, rel, lines, language, len(mine)))
        counted = _counter(lines, language, mine)
        facts += [_symbol_metric(item, rel, lines, language, {**fact, 'complexity': counted(fact)}) for fact in mine]
        for key, place in _windows_of(rel, lines): windows[key].append(place)
    clones = [_clone_fact(key, windows[key]) for key in sorted(windows) if _is_clone(windows[key])]
    facts += clones
    facts.sort(key=lambda f: (f['kind'], f['location']['path'], f['location'].get('start_line') or 0, f['id']))
    return {'facts': facts, 'summary': _summary(facts, totals, len(clones)), 'available': True,
            'input_sha': digest(''.join(sorted(set(fingerprints))).encode('utf-8')), 'reason': None}

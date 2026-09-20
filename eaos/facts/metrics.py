"""Size, branching and duplicated blocks — signals for where to look, never scores of quality."""
from collections import defaultdict
import re
from . import digest, make
from .source import language_of

NAME = 'metrics'
VERSION = '1'
LIMITATIONS = [
    'Branch counting is a lexical approximation, not a compiler-accurate cyclomatic complexity.',
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


def run(target, source, symbols=None, **options):
    from . import syntax
    if symbols is None:
        symbols = [f for f in syntax.run(target, source)['facts'] if f['kind'] == 'symbol']
    by_path = defaultdict(list)
    for fact in symbols: by_path[fact['location']['path']].append(fact)
    facts, fingerprints, windows = [], [], defaultdict(list)
    totals = {'files': 0, 'lines': 0, 'symbols': 0}
    for item in source.readable():
        rel = item['path']
        if language_of(rel) is None: continue
        text = source.text(rel)
        if text is None: continue
        lines = text.split('\n')
        language = language_of(rel)
        fingerprints.append(item['sha256'])
        totals['files'] += 1
        totals['lines'] += len(lines)
        code_lines = [line for line in lines if line.strip() and not COMMENT.match(line)]
        facts.append(make('metric', NAME, VERSION, item['sha256'], {'path': rel},
                          {'scope': 'file', 'lines': len(lines), 'code_lines': len(code_lines),
                           'branches': sum(len(BRANCH.findall(line)) for line in code_lines),
                           'max_nesting': nesting_depth(lines, language), 'symbols': len(by_path.get(rel, []))},
                          limitations=LIMITATIONS))
        for fact in sorted(by_path.get(rel, []), key=lambda f: f['location']['start_line']):
            start, end = fact['location']['start_line'], fact['location']['end_line']
            body = lines[start - 1:end]
            totals['symbols'] += 1
            facts.append(make('metric', NAME, VERSION, item['sha256'],
                              {'path': rel, 'start_line': start, 'end_line': end, 'symbol': fact['location'].get('symbol')},
                              {'scope': fact['value']['kind'], 'lines': len(body),
                               'branches': sum(len(BRANCH.findall(line)) for line in body),
                               'max_nesting': nesting_depth(body, language)}, limitations=LIMITATIONS))
        cleaned = [(index + 1, normalise(line)) for index, line in enumerate(lines)
                   if len(normalise(line)) >= MIN_LINE_LENGTH and not COMMENT.match(line)]
        for position in range(len(cleaned) - WINDOW + 1):
            chunk = cleaned[position:position + WINDOW]
            key = digest('\n'.join(text for _, text in chunk).encode('utf-8'))
            windows[key].append({'path': rel, 'start_line': chunk[0][0], 'end_line': chunk[-1][0]})
    clusters = 0
    for key in sorted(windows):
        places = windows[key]
        distinct = {(place['path'], place['start_line']) for place in places}
        if len(distinct) < 2 or len({place['path'] for place in places}) < 2 and len(places) < 3: continue
        clusters += 1
        facts.append(make('clone_cluster', NAME, VERSION, key,
                          {'path': sorted(place['path'] for place in places)[0]},
                          {'window_lines': WINDOW, 'occurrences': sorted(places, key=lambda p: (p['path'], p['start_line'])),
                           'files': sorted({place['path'] for place in places})}, limitations=LIMITATIONS))
    facts.sort(key=lambda f: (f['kind'], f['location']['path'], f['location'].get('start_line') or 0, f['id']))
    hotspots = sorted((f for f in facts if f['kind'] == 'metric' and f['value']['scope'] != 'file'),
                      key=lambda f: (-f['value']['branches'], -f['value']['lines'], f['location']['path']))[:20]
    summary = {**totals, 'clone_clusters': clusters,
               'largest_files': [{'path': f['location']['path'], 'lines': f['value']['lines']}
                                 for f in sorted((f for f in facts if f['kind'] == 'metric' and f['value']['scope'] == 'file'),
                                                 key=lambda f: -f['value']['lines'])[:15]],
               'most_branching_symbols': [{'path': f['location']['path'], 'symbol': f['location'].get('symbol'),
                                           'branches': f['value']['branches'], 'lines': f['value']['lines']} for f in hotspots],
               'interpretation': 'Size and branching are attention signals. They are never severity, and never a reason to split code on their own.'}
    return {'facts': facts, 'summary': summary, 'available': True,
            'input_sha': digest(''.join(sorted(set(fingerprints))).encode('utf-8')), 'reason': None}

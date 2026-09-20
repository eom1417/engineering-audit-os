"""Every way the system can be invoked: HTTP routes, CLI commands, jobs, containers.

This is the objective skeleton of a system. A detector reports only what it matched in the text;
an unsupported framework becomes a declared gap, never an invented route.
"""
from bisect import bisect_right
from . import digest, make
from .frameworks import MODULES, applicable
from .source import language_of

NAME = 'entrypoints'
VERSION = '1'
LIMITATIONS = [
    'Only the frameworks with a detector are covered; any other invocation path is undetected, not absent.',
    'Routes assembled at runtime (prefixes, dynamic registration, gateway rewrites) are not reconstructed.',
    'A detected route says nothing about who may call it; authentication and authorisation need their own evidence.',
    'A handler name is the nearest symbol in the same file; indirection through wrappers is not followed.',
]


class Context:
    """What a detector is allowed to see: one file, its text, and its symbol map."""

    def __init__(self, rel, text, language, symbols):
        self.rel, self.text, self.language = rel, text, language
        self.symbols = sorted(symbols, key=lambda s: s['start'])
        self._starts = [s['start'] for s in self.symbols]
        self._offsets = [0]
        for line in text.split('\n'): self._offsets.append(self._offsets[-1] + len(line) + 1)

    def line_of(self, offset): return bisect_right(self._offsets, offset)

    def symbol_at(self, line):
        index = bisect_right(self._starts, line) - 1
        while index >= 0:
            symbol = self.symbols[index]
            if symbol['start'] <= line <= symbol['end']: return symbol['name']
            index -= 1
        return None

    def symbol_after(self, line):
        for symbol in self.symbols:
            if symbol['start'] >= line: return symbol['name']
        return self.symbol_at(line)


def symbol_map(symbol_facts):
    table = {}
    for fact in symbol_facts:
        location = fact['location']
        table.setdefault(location['path'], []).append(
            {'name': location.get('symbol') or fact['value']['name'], 'start': location['start_line'], 'end': location['end_line']})
    return table


def run(target, source, symbols=None, **options):
    from . import syntax
    if symbols is None:
        symbols = [f for f in syntax.run(target, source)['facts'] if f['kind'] == 'symbol']
    table = symbol_map(symbols)
    facts, fingerprints, surfaces, frameworks = [], [], {}, {}
    covered_languages, uncovered = set(), {}
    for item in source.readable():
        rel = item['path']
        text = source.text(rel)
        if text is None: continue
        language = language_of(rel)
        context = Context(rel, text, language, table.get(rel, []))
        matched = False
        for module in MODULES:
            if not applicable(module, rel, language): continue
            matched = True
            for entry in module.detect(context):
                fingerprints.append(item['sha256'])
                surfaces[entry['surface']] = surfaces.get(entry['surface'], 0) + 1
                frameworks[entry['framework']] = frameworks.get(entry['framework'], 0) + 1
                covered_languages.add(language or 'manifest')
                facts.append(make('entry_point', NAME, VERSION, item['sha256'],
                                  {'path': rel, 'start_line': entry['line'], 'symbol': entry['handler']},
                                  {'surface': entry['surface'], 'route': entry['route'], 'http_method': entry['http_method'],
                                   'handler': entry['handler'], 'framework': entry['framework'], 'language': language,
                                   'category': source.category(rel), 'note': entry.get('note')},
                                  resolution='UNRESOLVED' if entry['route'] is None or entry['handler'] is None else 'RESOLVED', limitations=LIMITATIONS))
        if not matched and language and source.category(rel) == 'source':
            uncovered[language] = uncovered.get(language, 0) + 1
    facts.sort(key=lambda f: (f['value']['surface'], str(f['value']['route']), f['location']['path'], f['location'].get('start_line') or 0))
    production = [f for f in facts if f['value']['category'] != 'test']
    summary = {'entry_points': len(facts), 'production_entry_points': len(production),
               'test_only_entry_points': len(facts) - len(production),
               'by_surface': dict(sorted(surfaces.items())),
               'by_framework': dict(sorted(frameworks.items())),
               'languages_with_detections': sorted(covered_languages),
               'files_without_any_detector': dict(sorted(uncovered.items())),
               'interpretation': 'Detected invocation surfaces. Absence of a route here means no detector matched, not that the system cannot be invoked that way.'}
    return {'facts': facts, 'summary': summary, 'available': True,
            'input_sha': digest(''.join(sorted(set(fingerprints))).encode('utf-8')), 'reason': None}

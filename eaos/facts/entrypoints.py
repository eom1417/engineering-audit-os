"""Every way the system can be invoked: HTTP routes, CLI commands, jobs, containers.

This is the objective skeleton of a system. A detector reports only what it matched in the text;
an unsupported framework becomes a declared gap, never an invented route.

The same loop also emits ``data_access`` facts produced by framework detectors that declare
``FACT_KIND = 'data_access'``. Reading the file once and letting each detector contribute the
fact kind it owns keeps the persisted ledger a single observation per source, not two parallel
scans that could disagree about the file contents.
"""
from bisect import bisect_right
from . import digest, make
from .frameworks import MODULES, applicable, fact_kind
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
        self.prepared = {}
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


def _entry_point_fact(item, rel, language, entry, category):
    return make('entry_point', NAME, VERSION, item['sha256'],
                {'path': rel, 'start_line': entry['line'], 'symbol': entry['handler']},
                {'surface': entry['surface'], 'route': entry['route'], 'http_method': entry['http_method'],
                 'handler': entry['handler'], 'framework': entry['framework'], 'language': language,
                 'category': category, 'note': entry.get('note')},
                resolution='UNRESOLVED' if entry['route'] is None or entry['handler'] is None else 'RESOLVED',
                limitations=LIMITATIONS)


def _data_access_fact(item, rel, line, call, category):
    return make('data_access', NAME, VERSION, item['sha256'],
                {'path': rel, 'start_line': line, 'symbol': call.get('symbol') or 'data_access'},
                {'client': call['client'], 'target': call['target'], 'operation': call['operation'],
                 'category': category},
                limitations=LIMITATIONS)


def run(target, source, symbols=None, **options):
    from . import syntax
    if symbols is None:
        symbols = [f for f in syntax.run(target, source)['facts'] if f['kind'] == 'symbol']
    table = symbol_map(symbols)
    facts, fingerprints, surfaces, frameworks, data_access_by_client = [], [], {}, {}, {}
    covered_languages, uncovered = set(), {}
    # A detector that needs the whole project before reading one file (which names reach a database
    # client across imports, say) declares prepare(texts); what it returns per file reaches it as
    # context.prepared[its module name]. The core never names a detector.
    prepared = {}
    for module in MODULES:
        if hasattr(module, 'prepare'):
            prepared[module.__name__] = module.prepare({item['path']: source.text(item['path']) or '' for item in source.readable()
                                                        if applicable(module, item['path'], language_of(item['path']))})
    for item in source.readable():
        rel = item['path']
        text = source.text(rel)
        if text is None: continue
        language = language_of(rel)
        category = source.category(rel)
        context = Context(rel, text, language, table.get(rel, []))
        context.prepared = {name: per_file.get(rel) for name, per_file in prepared.items()}
        any_match = False
        for module in MODULES:
            if not applicable(module, rel, language): continue
            any_match = True
            kind = fact_kind(module)
            if kind == 'entry_point':
                for entry in module.detect(context):
                    fingerprints.append(item['sha256'])
                    surfaces[entry['surface']] = surfaces.get(entry['surface'], 0) + 1
                    frameworks[entry['framework']] = frameworks.get(entry['framework'], 0) + 1
                    covered_languages.add(language or 'manifest')
                    facts.append(_entry_point_fact(item, rel, language, entry, category))
            elif kind == 'data_access':
                for _offset, line, call in module.detect(context):
                    fingerprints.append(item['sha256'])
                    data_access_by_client[call['client']] = data_access_by_client.get(call['client'], 0) + 1
                    facts.append(_data_access_fact(item, rel, line, call, category))
        if not any_match and language and category == 'source':
            uncovered[language] = uncovered.get(language, 0) + 1
    facts.sort(key=lambda f: (f['value'].get('surface') or f['value'].get('client') or '',
                              str(f['value'].get('route') or f['value'].get('target') or ''),
                              f['location']['path'], f['location'].get('start_line') or 0))
    entry_point_facts = [f for f in facts if f['kind'] == 'entry_point']
    data_access_facts = [f for f in facts if f['kind'] == 'data_access']
    production = [f for f in entry_point_facts if f['value'].get('category') != 'test']
    summary = {'entry_points': len(entry_point_facts),
               'production_entry_points': len(production),
               'test_only_entry_points': len(entry_point_facts) - len(production),
               'data_access': len(data_access_facts),
               'data_access_by_client': dict(sorted(data_access_by_client.items())),
               'by_surface': dict(sorted(surfaces.items())),
               'by_framework': dict(sorted(frameworks.items())),
               'languages_with_detections': sorted(covered_languages),
               'files_without_any_detector': dict(sorted(uncovered.items())),
               'interpretation': 'Detected invocation surfaces. Absence of a route here means no detector matched, not that the system cannot be invoked that way.'}
    return {'facts': facts, 'summary': summary, 'available': True,
            'input_sha': digest(''.join(sorted(set(fingerprints))).encode('utf-8')), 'reason': None}

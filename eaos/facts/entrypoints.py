"""Every way the system can be invoked: HTTP routes, CLI commands, jobs, containers.

This is the objective skeleton of a system. A detector reports only what it matched in the text;
an unsupported framework becomes a declared gap, never an invented route.

The same loop also emits ``data_access`` facts produced by framework detectors that declare
``FACT_KIND = 'data_access'``, and the ``navigation`` facts (a link from one screen to another) of the detectors
that declare ``FACT_KIND = 'navigation'``. Reading the file once and letting each detector contribute the
fact kind it owns keeps the persisted ledger a single observation per source, not two parallel
scans that could disagree about the file contents.
"""
from bisect import bisect_right
from . import digest, make
from .frameworks import MODULES, applicable, fact_kind
from .source import language_of

NAME = 'entrypoints'
VERSION = '4'
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
                 'category': category, 'note': entry.get('note'),
                 **({'declared': entry['declared']} if entry.get('declared') else {})},
                resolution='UNRESOLVED' if entry['route'] is None or entry['handler'] is None else 'RESOLVED',
                limitations=LIMITATIONS)


def _tool_command_fact(item, rel, language, entry, category):
    """A declared command that runs only external tools: the project's command, not a way into its code."""
    return make('tool_command', NAME, VERSION, item['sha256'],
                {'path': rel, 'start_line': entry['line']},
                {'surface': entry['surface'], 'route': entry['route'], 'http_method': None, 'handler': None,
                 'framework': entry['framework'], 'tools': entry.get('tools', []), 'language': language,
                 'category': category},
                resolution='RESOLVED', limitations=LIMITATIONS)


def _data_access_fact(item, rel, line, call, category):
    return make('data_access', NAME, VERSION, item['sha256'],
                {'path': rel, 'start_line': line, 'symbol': call.get('symbol') or 'data_access'},
                {'client': call['client'], 'target': call['target'], 'operation': call['operation'],
                 'bounded': call.get('bounded'), 'category': category,
                 # the names a write sends, when its payload is an object literal in the call (values never kept)
                 **({'keys': call['keys'], 'keys_partial': call['keys_partial']} if 'keys' in call else {})},
                limitations=LIMITATIONS)


def _navigation_fact(file, line, link, limitations):
    return make('navigation', NAME, VERSION, file['item']['sha256'],
                {'path': file['rel'], 'start_line': line, 'symbol': link.get('symbol') or 'navigation'},
                {'target': link['target'], 'via': link['via'], 'dynamic': link['dynamic'], 'relative': link['relative'],
                 'category': file['category']},
                resolution='UNRESOLVED' if link['relative'] else None, limitations=limitations)


def _count(table, key): table[key] = table.get(key, 0) + 1


def _texts_for(module, source):
    return {item['path']: source.text(item['path']) or '' for item in source.readable()
            if applicable(module, item['path'], language_of(item['path']))}


def _prepared(source):
    # A detector that needs the whole project before reading one file (which names reach a database
    # client across imports, say) declares prepare(texts); what it returns per file reaches it as
    # context.prepared[its module name]. The core never names a detector.
    return {module.__name__: module.prepare(_texts_for(module, source)) for module in MODULES if hasattr(module, 'prepare')}


def _record_entry_points(module, context, file, tally):
    item, rel, language, category = file['item'], file['rel'], file['language'], file['category']
    for entry in module.detect(context):
        tally['fingerprints'].append(item['sha256'])
        if entry.get('kind') == 'tool_command':
            tally['facts'].append(_tool_command_fact(item, rel, language, entry, category))
            continue
        _count(tally['surfaces'], entry['surface'])
        _count(tally['frameworks'], entry['framework'])
        tally['covered_languages'].add(language or 'manifest')
        tally['facts'].append(_entry_point_fact(item, rel, language, entry, category))


def _record_data_access(module, context, file, tally):
    for _offset, line, call in module.detect(context):
        tally['fingerprints'].append(file['item']['sha256'])
        _count(tally['data_access_by_client'], call['client'])
        tally['facts'].append(_data_access_fact(file['item'], file['rel'], line, call, file['category']))


def _record_navigation(module, context, file, tally):
    for _offset, line, link in module.detect(context):
        tally['fingerprints'].append(file['item']['sha256'])
        _count(tally['navigation_by_via'], link['via'])
        tally['facts'].append(_navigation_fact(file, line, link, module.LIMITATIONS))


RECORDERS = {'entry_point': _record_entry_points, 'data_access': _record_data_access, 'navigation': _record_navigation}


def _scan_file(item, source, table, prepared, tally):
    rel = item['path']
    text = source.text(rel)
    if text is None: return
    file = {'item': item, 'rel': rel, 'language': language_of(rel), 'category': source.category(rel)}
    context = Context(rel, text, file['language'], table.get(rel, []))
    context.prepared = {name: per_file.get(rel) for name, per_file in prepared.items()}
    modules = [module for module in MODULES if applicable(module, rel, file['language'])]
    for module in modules:
        recorder = RECORDERS.get(fact_kind(module))
        if recorder: recorder(module, context, file, tally)
    if not modules and file['language'] and file['category'] == 'source':
        _count(tally['uncovered'], file['language'])


def _fact_order(f):
    return (f['value'].get('surface') or f['value'].get('client') or '',
            str(f['value'].get('route') or f['value'].get('target') or ''),
            f['location']['path'], f['location'].get('start_line') or 0)


def _summary(tally):
    facts = tally['facts']
    entry_point_facts = [f for f in facts if f['kind'] == 'entry_point']
    production = [f for f in entry_point_facts if f['value'].get('category') != 'test']
    return {'entry_points': len(entry_point_facts),
            'production_entry_points': len(production),
            'test_only_entry_points': len(entry_point_facts) - len(production),
            'tool_commands': len([f for f in facts if f['kind'] == 'tool_command']),
            'data_access': len([f for f in facts if f['kind'] == 'data_access']),
            'data_access_by_client': dict(sorted(tally['data_access_by_client'].items())),
            'navigation': sum(tally['navigation_by_via'].values()),
            'navigation_by_via': dict(sorted(tally['navigation_by_via'].items())),
            'by_surface': dict(sorted(tally['surfaces'].items())),
            'by_framework': dict(sorted(tally['frameworks'].items())),
            'languages_with_detections': sorted(tally['covered_languages']),
            'files_without_any_detector': dict(sorted(tally['uncovered'].items())),
            'interpretation': 'Detected invocation surfaces. Absence of a route here means no detector matched, not that the system cannot be invoked that way.'}


def run(target, source, symbols=None, **options):
    from . import syntax
    if symbols is None:
        symbols = [f for f in syntax.run(target, source)['facts'] if f['kind'] == 'symbol']
    table = symbol_map(symbols)
    tally = {'facts': [], 'fingerprints': [], 'surfaces': {}, 'frameworks': {}, 'data_access_by_client': {},
             'navigation_by_via': {}, 'covered_languages': set(), 'uncovered': {}}
    prepared = _prepared(source)
    for item in source.readable(): _scan_file(item, source, table, prepared, tally)
    tally['facts'].sort(key=_fact_order)
    return {'facts': tally['facts'], 'summary': _summary(tally), 'available': True,
            'input_sha': digest(''.join(sorted(set(tally['fingerprints']))).encode('utf-8')), 'reason': None}

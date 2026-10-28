"""Everything the journeys read from the check's records: the page routes and the links, the imports and the names
they bring, today's components and the target's, the features, the dead modules and the screen shots; and the file of
each page's component."""
import re
from collections import defaultdict
from pathlib import Path

from ....analysis.maps import architecture as arch_map
from .routes import TEST, _norm
from ....core.system.files import read_json

def _pages_and_links(report):
    pages, links = [], []     # the code's page and link rows; the crawl's pages stand in when the code names none
    for found in map(_page_or_link, arch_map.facts(report, 'entrypoints', 'entry_point') + arch_map.facts(report, 'entrypoints', 'navigation')):
        if found: (pages if found[0] == 'page' else links).append(found[1])
    from ....live.behavior.specs import crawled_pages      # the crawl's pages stand in when the code names none
    return pages or [{'route': p, 'declared': p, 'handler': '', 'router': 'live/crawl.json', 'line': None, 'fact': None, 'framework': 'crawl'}
                     for p in crawled_pages(report)], links


def _page_or_link(fact):
    """('page', row) of a page route, ('link', row) of a navigation; None for anything else, or anything in the tests."""
    value, loc = fact.get('value') or {}, fact.get('location') or {}
    path = str(loc.get('path') or '')
    if not path or TEST.search(path) or value.get('category') == 'test': return None
    if fact['kind'] == 'entry_point': return _page_row(fact, value, loc, path)
    if fact['kind'] == 'navigation': return _link_row(fact, value, loc, path)
    return None


def _page_row(fact, value, loc, path):
    """('page', row) of an entry point that is a page route; None for any other."""
    if value.get('surface') != 'page' or value.get('route') is None: return None
    return 'page', {'route': str(value['route']), 'declared': str(value.get('declared') or value['route']),
                    'handler': str(value.get('handler') or ''), 'router': path,
                    'line': loc.get('start_line'), 'fact': fact.get('id'), 'framework': value.get('framework')}


def _link_row(fact, value, loc, path):
    """('link', row) of a navigation with a target; None without one."""
    if not value.get('target'): return None
    return 'link', {'target': str(value['target']), 'via': value.get('via') or 'link', 'file': path,
                    'line': loc.get('start_line'), 'symbol': loc.get('symbol'), 'fact': fact.get('id'),
                    'dynamic': bool(value.get('dynamic')), 'relative': bool(value.get('relative'))}


def _names(report):
    """({(file, imported name): [modules]}, {top-level name: the files defining it})."""
    names, defined = defaultdict(list), defaultdict(set)
    for fact in arch_map.facts(report, 'syntax', 'import_edge') + arch_map.facts(report, 'syntax', 'symbol'):
        value, path = fact.get('value') or {}, arch_map.path_of(fact)
        if fact['kind'] == 'import_edge':
            for name in value.get('names') or []: names[(path, name)].append(str(value.get('module') or ''))
        elif value.get('name') and not value.get('parent'):
            defined[str(value['name'])].add(path)
    return names, defined


def _owners(comps):
    """{path: the deepest component holding it}."""
    owners = {}
    for c in sorted(comps, key=lambda c: len(str(c['name']))):
        owners.update({p: c for p in c.get('paths') or [] if isinstance(p, str)})
    return owners


def _target_of(target):
    target_of = {}
    for t in (t for t in target.get('target_components') or [] if isinstance(t, dict) and t.get('name')):
        target_of.update({p: t['name'] for p in t.get('paths') or [] if isinstance(p, str)})
    return target_of


def _feature_of(report):
    """{surface: the first feature naming it}."""
    features = read_json(report / 'features.json', {}) or {}
    feature_of = {}
    for f in (features.get('features') if isinstance(features, dict) else None) or []:
        if not (isinstance(f, dict) and f.get('name')): continue
        for s in f.get('surfaces') or []: feature_of.setdefault(str(s), str(f['name']))
    return feature_of


def _shots(report, media):
    """{route: the screen shots taken of it}; media: media.json's images, else the report's studio/media.json."""
    if media is None:
        media = read_json(report / 'studio/media.json', {}) or {}
        media = media.get('images') if isinstance(media, dict) else None
    shots = defaultdict(list)
    for image in media or []:
        if isinstance(image, dict) and image.get('kind') == 'screen' and image.get('route') and image.get('path'):
            shots[_norm(image['route'])].append(image['path'])
    return shots


def records(report, media=None):
    """Everything the journeys read, each piece empty when its record is missing. media: media.json's images when the
    exporter has them in hand, else the report's studio/media.json."""
    report = Path(report)
    pages, links = _pages_and_links(report)
    names, defined = _names(report)
    target = read_json(report / 'target-architecture.json', {}) or {}
    comps = [c for c in target.get('current_components') or [] if isinstance(c, dict) and c.get('name')]
    return {'pages': pages, 'links': links, 'imports': _imports(report), 'dead': _dead(report), 'names': names, 'defined': defined,
            'owners': _owners(comps), 'target_of': _target_of(target), 'feature_of': _feature_of(report),
            'shots': _shots(report, media), 'has_target': bool(comps)}


def _imports(report):
    """{file: the files it imports}."""
    return {arch_map.path_of(node): [d for d in (node.get('value') or {}).get('depends_on') or [] if isinstance(d, str)]
            for node in arch_map.facts(report, 'graph', 'graph_node')}


def _dead(report):
    """The modules the dead-code engine found unreachable."""
    return {arch_map.path_of(f) for f in arch_map.facts(report, 'deadcode', 'engine_finding')
            if (f.get('value') or {}).get('rule') == 'unreachable-module'}


def component_file(page, r):
    """The file of a page's component: the module the router imports under that name, resolved by the router's own
    imports; else the one file defining the name; else None."""
    handler, router = page['handler'], page['router']
    deps = r['imports'].get(router, [])
    for module in r['names'].get((router, handler), []):
        found = _imported(module, deps)
        if found: return found
    return _defining(handler, router, r['defined'])


def _imported(module, deps):
    """The one file of `deps` (the router's imports) that a module name resolves to; None when none or several do."""
    stem = module.rstrip('/').rsplit('/', 1)[-1]
    found = [d for d in deps if re.sub(r'\.\w+$', '', d).endswith('/' + stem) or re.sub(r'(/index)?\.\w+$', '', d).endswith('/' + stem)]
    return found[0] if len(found) == 1 else None


def _defining(handler, router, defined):
    """The one file outside the tests and the router defining the handler's name (the file named for it first)."""
    homes = sorted(p for p in defined.get(handler, ()) if not TEST.search(p) and p != router)
    named = [p for p in homes if re.sub(r'\.\w+$', '', p.rsplit('/', 1)[-1]) == handler]
    if len(named) == 1: return named[0]
    return homes[0] if len(homes) == 1 else None

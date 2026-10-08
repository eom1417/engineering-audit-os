"""studio/hidden.json: what the user sees against what runs unseen, and which screens set the unseen in motion.

Read only from records the check already wrote; nothing is invented, every item names its evidence (`fact`, `file`,
`line`) and every count its source (`src`):

    seen        the screens of studio/journeys.json (kind page), by area (the first segment of their route), and the
                dialog and form files they render (a file named …Dialog, …Form, …Modal, …Sheet, …Drawer)
    unseen      triggers   background jobs, schedules and containers (entry_point surface job or container), web hooks
                           (a server route whose path names a hook or a callback), edge functions (files under
                           supabase/functions/<name>/, netlify/functions/ or api/cron/)
                screens    routes that are not pages: layouts, redirects and catch-alls (journeys.json)
                server     server routes this repository answers (entry_point surface http)
                writes     the writes the code sends (data_access post, put, patch, delete, insert, update, upsert),
                           by resource
                outside    the outside services the code calls (runtime integration_target), by host
                config     environment variables read (config env_read), secret-shaped settings, committed credentials
                           (facts/secrets.json; the value is never read or written)
                build      CI steps and deployment targets (runtime ci_step, deployment_target), and the commands the
                           manifests declare (entry_point surface cli)
                dead       unreachable modules, unused symbols and unread constants (deadcode), leftovers, broken code
    links       a screen area sets an unseen item of triggers, server, writes, outside or config in motion when a file the area's screens render (three import steps)
                holds the item's evidence; an item of triggers, writes, outside or config that no screen reaches is
                flagged `no_screen`: it runs, or waits, with nothing the user sees in front of it
    components  each item is counted in the deepest component of target-architecture.json holding its file, so the
                System map can mark the components that hold unseen work

Buttons and inputs are not read yet (screens.json, NS40): the gap is written in `missing`.
"""
import re
from collections import defaultdict
from pathlib import Path

from .. import arch_map
from . import journeys as J

GROUPS = ('triggers', 'screens', 'server', 'writes', 'outside', 'config', 'build', 'dead')
LINKABLE = ('triggers', 'server', 'writes', 'outside', 'config')
WRITES = {'post', 'put', 'patch', 'delete', 'insert', 'update', 'upsert', 'remove', 'rpc'}
HOOK = re.compile(r'(?i)web-?hooks?|(^|/)hooks?(/|$)|callback|cron')
EDGE_FN = re.compile(r'^(?:.*/)?(?:supabase/functions/(?P<s>[^/]+)/|netlify/functions/(?P<n>[^/.]+)|api/cron/(?P<c>[^/.]+))')
DIALOG = re.compile(r'(?:^|/)(?P<name>[A-Z]\w*(?:Dialog|Form|Modal|Sheet|Drawer))\.[jt]sx?$')
MAX_ITEMS = 400
SRC = {
    'triggers': 'facts/entrypoints.json#entry_point[surface in job, container; http hook routes]; facts/graph.json#graph_node under supabase/functions, netlify/functions, api/cron',
    'screens': 'studio/journeys.json#screens[kind in layout, redirect, fallback]',
    'server': 'facts/entrypoints.json#entry_point[surface=http]',
    'writes': 'facts/entrypoints.json#data_access[operation in post, put, patch, delete, insert, update, upsert, remove, rpc]',
    'outside': 'facts/runtime.json#integration_target (distinct hosts)',
    'config': 'facts/config.json#env_read (distinct names), config_key[secret_shaped], config_file_unread; facts/secrets.json',
    'build': 'facts/runtime.json#ci_step, deployment_target; facts/entrypoints.json#entry_point[surface=cli]',
    'dead': 'facts/deadcode.json#engine_finding; facts/leftovers.json#leftover; facts/broken.json#broken_code',
    'seen': 'studio/journeys.json#screens[kind=page]',
    'dialogs': 'facts/graph.json#graph_node named …Dialog, …Form, …Modal, …Sheet, …Drawer, rendered by a screen',
    'no_screen': 'items of triggers, server, writes, outside and config no screen reaches by three import steps',
}


def _measure(value, src):
    return {'value': value if isinstance(value, int) and value >= 0 else None, 'src': src, 'unit': 'count'}


def _resource(target):
    segs = [s for s in re.split(r'[/?#]', str(target or '')) if s and not s.startswith(('{', ':', '$')) and s != 'api']
    return '/' + segs[0] if segs else str(target or '/')


def items_of(report, journeys):
    """[{id, group, kind, name, files, file, line, fact, detail}] of every unseen item, before the links."""
    report = Path(report)
    out = []

    def add(group, kind, name, fact, detail=None, files=None, item_id=None):
        loc = (fact or {}).get('location') or {}
        file = loc.get('path')
        out.append({'id': item_id or f"{group}:{kind}:{name}:{file}:{loc.get('start_line') or ''}", 'group': group, 'kind': kind,
                    'name': str(name)[:160], 'file': file, 'line': loc.get('start_line'), 'fact': (fact or {}).get('id'),
                    'files': sorted(set(files or ([file] if file else [])))[:40], 'detail': detail})

    for fact in arch_map.facts(report, 'entrypoints', 'entry_point'):
        v = fact.get('value') or {}
        if v.get('category') == 'test': continue
        if v.get('surface') in ('job', 'container'):
            add('triggers', v['surface'], v.get('route') or v.get('handler') or '?', fact, v.get('framework'))
        elif v.get('surface') == 'http':
            route = str(v.get('route') or '')
            kind = 'webhook' if HOOK.search(route) else 'endpoint'
            add('triggers' if kind == 'webhook' else 'server', kind, f"{v.get('http_method') or 'ANY'} {route}", fact, v.get('framework'))
        elif v.get('surface') == 'cli':
            add('build', 'command', v.get('route') or '?', fact, v.get('framework'))
    edge_fns = defaultdict(list)
    for node in arch_map.facts(report, 'graph', 'graph_node'):
        m = EDGE_FN.match(arch_map.path_of(node))
        if m: edge_fns[m.group('s') or m.group('n') or m.group('c')].append(node)
    for name, nodes in sorted(edge_fns.items()):
        nodes.sort(key=arch_map.path_of)
        add('triggers', 'edge_function', name, nodes[0], None, [arch_map.path_of(n) for n in nodes], f'triggers:edge_function:{name}')
    for s in journeys.get('screens') or []:
        if s['kind'] != 'page':
            out.append({'id': f"screens:{s['id']}", 'group': 'screens', 'kind': s['kind'], 'name': s['route'] + (f" ({s['title']})" if s.get('title') else ''),
                        'file': s['router'], 'line': s['line'], 'fact': s['fact'], 'files': [f for f in (s['router'], s.get('file')) if f], 'detail': None})
    writes = defaultdict(list)
    for fact in arch_map.facts(report, 'entrypoints', 'data_access'):
        v = fact.get('value') or {}
        if str(v.get('operation') or '').lower() in WRITES and v.get('category') != 'test':
            writes[(str(v.get('client') or 'http'), _resource(v.get('target')))].append(fact)
    for (client, resource), facts in sorted(writes.items()):
        facts.sort(key=lambda f: (arch_map.path_of(f), (f.get('location') or {}).get('start_line') or 0))
        ops = sorted({f"{str(f['value'].get('operation')).upper()} {f['value'].get('target')}" for f in facts})
        add('writes', client, resource, facts[0], '; '.join(ops[:8]) + (f' (+{len(ops) - 8})' if len(ops) > 8 else ''),
            [arch_map.path_of(f) for f in facts], f'writes:{client}:{resource}')
    hosts = defaultdict(list)
    for fact in arch_map.facts(report, 'runtime', 'integration_target'):
        host = (fact.get('value') or {}).get('host')
        if host: hosts[str(host)].append(fact)
    for host, facts in sorted(hosts.items()):
        facts.sort(key=arch_map.path_of)
        add('outside', 'host', host, facts[0], None, [arch_map.path_of(f) for f in facts], f'outside:{host}')
    envs = defaultdict(list)
    for fact in arch_map.facts(report, 'config', 'env_read'):
        name = (fact.get('value') or {}).get('name') or (fact.get('value') or {}).get('key')
        if name: envs[str(name)].append(fact)
    for name, facts in sorted(envs.items()):
        facts.sort(key=lambda f: (arch_map.path_of(f), (f.get('location') or {}).get('start_line') or 0))
        add('config', 'env', name, facts[0], None, [arch_map.path_of(f) for f in facts], f'config:env:{name}')
    for fact in arch_map.facts(report, 'config', 'config_key'):
        v = fact.get('value') or {}
        if v.get('secret_shaped'): add('config', 'secret_name', v.get('key') or '?', fact)
    for fact in arch_map.facts(report, 'config', 'config_file_unread'):
        add('config', 'unread_file', arch_map.path_of(fact), fact)
    for fact in arch_map.facts(report, 'secrets', 'committed_credential'):
        v = fact.get('value') or {}
        add('config', 'credential', v.get('key_family') or 'credential', fact, v.get('severity'))
    for kind in ('ci_step', 'deployment_target'):
        for fact in arch_map.facts(report, 'runtime', kind):
            v = fact.get('value') or {}
            add('build', kind, v.get('name') or v.get('target') or v.get('platform') or arch_map.path_of(fact), fact)
    for fact in arch_map.facts(report, 'deadcode', 'engine_finding'):
        v = fact.get('value') or {}
        add('dead', v.get('rule') or 'dead_code', (fact.get('location') or {}).get('symbol') or arch_map.path_of(fact), fact)
    for fact in arch_map.facts(report, 'leftovers', 'leftover'):
        add('dead', 'leftover', arch_map.path_of(fact), fact, (fact.get('value') or {}).get('reason'))
    for fact in arch_map.facts(report, 'broken', 'broken_code'):
        v = fact.get('value') or {}
        add('dead', 'broken', (fact.get('location') or {}).get('symbol') or arch_map.path_of(fact), fact, v.get('rule'))
    used = defaultdict(int)
    for item in out:
        used[item['id']] += 1
        if used[item['id']] > 1: item['id'] += f"#{used[item['id']]}"
    return out


def build(report, journeys, card_rows=()):
    """The section's body: {counts, src, seen, groups, items, links, components, missing}."""
    r = J.records(report, [])
    routers = {s['router'] for s in journeys.get('screens') or []}
    reach = {s['id']: J._reach(s['file'], r['imports'], J.DEPTH, stop=routers) if s.get('file') and s['file'] not in routers else set()
             for s in journeys.get('screens') or [] if s['kind'] == 'page'}
    owners = {p: c['name'] for p, c in r['owners'].items()}
    return assemble(items_of(report, journeys), journeys, reach, owners, card_rows)


def assemble(items, journeys, reach, owners, card_rows=()):
    """The body from the unseen items, the screens' reach ({screen id: files}) and the owner component of each file."""
    screens = [s for s in journeys.get('screens') or [] if s['kind'] == 'page']
    areas = defaultdict(list)
    for s in screens: areas[s['group']].append(s)
    seen = []
    area_files = {}
    for name, members in sorted(areas.items()):
        files = set().union(*(reach[s['id']] for s in members)) if members else set()
        area_files[f'area:{name}'] = files
        dialogs = sorted({m.group('name') for f in files for m in [DIALOG.search(f)] if m})
        seen.append({'id': f'area:{name}', 'name': name, 'screens': [s['id'] for s in members],
                     'routes': [s['route'] for s in members][:12], 'dialogs': dialogs[:24], 'dialog_count': len(dialogs)})
    card_of = {}
    for card in card_rows or []:
        for fid in card.get('evidence') or []: card_of.setdefault(fid, card.get('id'))
    links = defaultdict(lambda: {'items': [], 'count': 0})
    components = defaultdict(lambda: defaultdict(int))
    for item in items:
        item['card'] = card_of.get(item['fact'])
        item['areas'] = sorted(a for a, files in area_files.items() if any(f in files for f in item['files']))
        item['no_screen'] = item['group'] in LINKABLE and not item['areas'] and item['kind'] not in ('webhook', 'edge_function', 'job', 'container')
        comp = owners.get(item['file'] or '')
        item['component'] = comp
        if comp: components[comp][item['group']] += 1
        for a in item['areas'] if item['group'] in LINKABLE else ():
            link = links[(a, item['group'])]
            link['count'] += 1
            if len(link['items']) < 12: link['items'].append(item['id'])
    groups = []
    for g in GROUPS:
        mine = [i for i in items if i['group'] == g]
        mine.sort(key=lambda i: (not i['no_screen'], not i['card'], i['kind'], i['name']))
        groups.append({'id': g, 'count': _measure(len(mine), SRC[g]), 'kinds': dict(sorted(_count(i['kind'] for i in mine).items())),
                       'no_screen': sum(i['no_screen'] for i in mine), 'items': [i['id'] for i in mine[:MAX_ITEMS]],
                       'capped': max(len(mine) - MAX_ITEMS, 0)})
    shown = {i for g in groups for i in g['items']}
    missing = [{'id': 'controls', 'state': 'not_measured', 'step': 'NS40.T1', 'count': _measure(None, 'screens.json#screens[].inputs'),
             'detail': {'ar': 'الأزرار والحقول على كل شاشة لم تُقرأ بعد.', 'en': 'The buttons and inputs on each screen are not read yet.'}}] if screens else []
    return {
        'counts': {
            'seen': _measure(len(screens), SRC['seen']),
            'dialogs': _measure(sum(a['dialog_count'] for a in seen), SRC['dialogs']),
            'unseen': _measure(len(items), 'every item of the unseen groups'),
            'no_screen': _measure(sum(i['no_screen'] for i in items), SRC['no_screen']),
            **{g['id']: g['count'] for g in groups},
        },
        'src': SRC,
        'seen': seen,
        'groups': groups,
        'items': [i for i in items if i['id'] in shown],
        'links': [{'from': a, 'to': g, 'count': v['count'], 'items': v['items']} for (a, g), v in sorted(links.items())],
        'components': {c: dict(v) for c, v in sorted(components.items())},
        'missing': missing,
    }


def _count(values):
    out = defaultdict(int)
    for v in values: out[v] += 1
    return out


def hidden(report, journeys, card_rows=()):
    return build(report, journeys, card_rows)

"""The records the code paths read (eaos/report/studio/paths.py): the symbols and imports of every file, the entry points and
the calls they make, the traced flows and the tables. Each reader fills its pieces of one record dict; a record that is
missing or broken leaves its pieces empty.
"""
from ...analysis import system_map as sm

SERVER = ('http', 'endpoint', 'api', 'route', 'rpc', 'job', 'queue', 'cli', 'worker', 'webhook', 'cron', 'tool')
FUNCTIONS = ('function', 'method')


def line_number(value):
    return value if isinstance(value, int) and value >= 0 else None


def _enclosing(functions, path, line):
    """The function holding a line: the outermost top-level function around it, else the innermost one; None outside."""
    around = [f for f in functions.get(path, ()) if f['start'] <= (line or 0) <= f['end']]
    top = [f for f in around if not f['parent']]
    pick = min(top, key=lambda f: f['start']) if top else (max(around, key=lambda f: f['start']) if around else None)
    return pick['name'] if pick else None


def _symbols(report, r):
    """Each file's functions, the names it defines, the HTTP methods it exports and the packages it imports."""
    for fact in sm._facts(report, 'syntax', 'symbol', 'import_edge'):
        value, loc, path = fact.get('value') or {}, fact.get('location') or {}, sm._path(fact)
        if sm.is_test(path): continue
        if fact['kind'] == 'import_edge':
            if value.get('style') == 'absolute' and value.get('module'): r['packages'][path].add(str(value['module']))
            continue
        _symbol(r, value, loc, path)


def _symbol(r, value, loc, path):
    """One symbol: an HTTP method its file exports, a top-level name, a function with its lines."""
    name = str(value.get('name') or '')
    if value.get('exported') and name.upper() in sm.METHODS and name.isupper(): r['methods'][path].add(name)
    if name and not value.get('parent'): r['names'][name].add(path)
    if value.get('kind') in FUNCTIONS and isinstance(loc.get('start_line'), int):
        r['functions'][path].append({'name': name, 'parent': value.get('parent'), 'start': loc['start_line'],
                                     'end': loc.get('end_line') or loc['start_line']})


def _imports(report, r):
    for node in sm._facts(report, 'graph', 'graph_node'):
        r['imports'][sm._path(node)] = [d for d in (node.get('value') or {}).get('depends_on') or [] if isinstance(d, str)]


def _entry(r, fact, value, path, line):
    """A page, or a server route and the handler behind it."""
    entry = {'fact': fact, 'path': path, 'line': line, 'surface': str(value.get('surface') or ''),
             'route': str(value.get('route') or ''), 'method': value.get('http_method'), 'handler': value.get('handler')}
    if entry['surface'] == 'page': r['pages'].append(entry)
    elif entry['surface'] in SERVER or entry['method']:
        if entry['surface'] in ('http', 'endpoint', 'api', 'route', 'rpc') or entry['method']:
            r['routes'].append({'route': sm.clean_path(entry['route']), 'method': str(entry['method'] or 'ANY').upper(),
                                'handler': entry['handler'], 'file': path, 'fact': fact})
        if entry['handler']: r['servers'].append(entry)


def _call(value):
    """A data access as a call: a method and a URL, or what a database client does on a table."""
    client = str(value.get('client') or 'http')
    if client in ('http', 'fetch', 'axios'):
        method = str(value.get('operation') or 'get').upper()
        method = method if method in sm.METHODS else 'GET'
        url = sm.clean_path(value['target']) or '…'      # a URL built at run time: the call stays, its route unknown
        return {'id': f'A:{method} {url}', 'label': f'{method} {url}', 'url': url, 'method': method, 'table': None,
                'group': sm.api_group(url)}
    operation, table = str(value.get('operation') or 'query'), str(value['target'])
    return {'id': f'A:{client} {operation} {table}', 'label': f'{client} {operation} {table}', 'url': None,
            'method': operation, 'table': table, 'group': client}


def _entries(report, r):
    """The pages, the server routes and their handlers, and every call each file makes, in the order of its lines."""
    for fact in sm._facts(report, 'entrypoints', 'entry_point', 'data_access'):
        value, path, loc = fact.get('value') or {}, sm._path(fact), fact.get('location') or {}
        if not isinstance(value, dict) or not path or sm.is_test(path) or value.get('category') == 'test': continue
        line = line_number(loc.get('start_line'))
        if fact['kind'] == 'entry_point': _entry(r, fact, value, path, line)
        elif value.get('target'):
            r['calls'][path].append({**_call(value), 'fact': fact, 'path': path, 'line': line,
                                     'function': _enclosing(r['functions'], path, line)})
    for rows in r['calls'].values(): rows.sort(key=lambda c: (c['line'] or 0, c['id']))


def _flows(report, r):
    for fact in sm._facts(report, 'flows', 'flow'):
        value = fact.get('value') or {}
        entry = value.get('entry') or {}
        for route in [entry.get('route')] + [a.get('route') for a in value.get('also_reached_by') or [] if isinstance(a, dict)]:
            r['flows'].setdefault((entry.get('path'), entry.get('handler'), route), fact)
        r['flow_of'].setdefault((entry.get('path'), entry.get('handler')), fact)
        first = next((s.get('from_path') for s in value.get('steps') or [] if isinstance(s, dict) and s.get('from') == entry.get('handler')), None)
        r['flow_list'].append({'surface': entry.get('surface'), 'route': entry.get('route'), 'handler': entry.get('handler'),
                               'file': first})


def _tables(report, r):
    for fact in sm._facts(report, 'domain', 'data_table'):
        name, path = str((fact.get('value') or {}).get('name') or ''), sm._path(fact)
        if len(name) > 1 and name.lower() not in sm.NOT_TABLES and not sm.is_test(path): r['tables'][path].append((name, fact))


# In this order: a call names the function around it, which the symbols give.
READERS = (_symbols, _imports, _entries, _flows, _tables)

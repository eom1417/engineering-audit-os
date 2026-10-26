"""What a person does in the app: a route that creates or edits, or a Create…/Edit… dialog or form file a screen
renders, each with the shortest path of links from the start to it."""
import re

from .routes import SHARED, TEST, _segments, _words

FORM_SEGMENTS = {'new': 'create', 'create': 'create', 'add': 'create', 'edit': 'edit', 'register': 'create', 'signup': 'create'}
FORM_NAME = re.compile(r'^(?P<verb>Create|New|Add|Edit|Update|Register)(?P<object>[A-Z]\w*?)(?:Dialog|Form|Modal|Sheet|Drawer|Wizard|Page)?$')
FORM_FILE = re.compile(r'(?:^|/)(?P<name>(?:Create|New|Add|Edit|Update|Register)[A-Z]\w*?(?:Dialog|Form|Modal|Sheet|Drawer|Wizard))\.[jt]sx?$')
VERBS = {'create': ('إنشاء', 'Create'), 'new': ('إنشاء', 'Create'), 'add': ('إضافة', 'Add'), 'edit': ('تعديل', 'Edit'),
         'update': ('تحديث', 'Update'), 'register': ('تسجيل', 'Register')}


def _name(verb, obj):
    verb = verb.lower()
    ar, en = VERBS.get(verb, (verb, verb.title()))
    return {'ar': f'{ar}: {obj}', 'en': f'{en} {obj}'}


def _route_task(s, paths):
    """((verb, object), task) of a route that creates or edits, by its last segment or its component's name; else None."""
    segs = _segments(s['route'])
    static = [x for x in segs if not x.startswith(':')]
    verb = FORM_SEGMENTS.get(segs[-1].lower()) if segs and not segs[-1].startswith(':') else None
    hit = FORM_NAME.match(s['handler'] or '')
    if hit: verb, obj = hit.group('verb'), _words(hit.group('object'))
    elif verb: obj = _route_object(static, s['route'])
    else: return None
    return (verb.lower(), obj), {'id': f'task:{verb.lower()}:{obj.replace(" ", "-")}', 'name': _name(verb, obj), 'kind': 'route',
                                 'screen': s['id'], 'file': s['file'], 'line': None, 'path': paths.get(s['id'], []), 'dead': False,
                                 'src': 'route ' + s['route'] + (' (component ' + s['handler'] + ')' if hit else '')}


def _route_object(static, route):
    """What a create or edit route works on: the fixed segment before its verb, else its only one, else the route."""
    return static[-2] if len(static) > 1 else (static[0] if static else route)


def _dialog_task(f, renders, paths, dead):
    """((verb, object), task) of a Create…/Edit… dialog or form file a screen renders (or an unreachable one); else None."""
    m = FORM_FILE.search(f)
    hit = FORM_NAME.match(m.group('name')) if m and not TEST.search(f) else None
    if not hit: return None
    verb, obj = hit.group('verb'), _words(hit.group('object'))
    hosts = sorted(renders.get(f, ()), key=lambda sid: (sid not in paths, len(paths.get(sid, ())) or 99, sid))
    if len(hosts) >= SHARED * 2 or (not hosts and f not in dead): return None
    host = hosts[0] if hosts else None
    return (verb.lower(), obj), {'id': f'task:{verb.lower()}:{obj.replace(" ", "-")}', 'name': _name(verb, obj), 'kind': 'dialog',
                                 'screen': host, 'file': f, 'line': None, 'path': paths.get(host, []) if host else [], 'hosts': hosts[:6],
                                 'dead': not hosts,
                                 'src': 'file ' + f + (', rendered by ' + str(len(hosts)) + ' screen(s)' if hosts else
                                                       ', an unreachable module (facts/deadcode.json): no screen renders it')}


def _tasks(screens, renders, paths, files=(), dead=()):
    tasks, seen = [], set()
    found = [_route_task(s, paths) for s in screens if s['kind'] == 'page']
    found += [_dialog_task(f, renders, paths, dead) for f in sorted(set(renders) | set(files))]
    for key, task in filter(None, found):
        if key in seen: continue
        seen.add(key)
        tasks.append(task)
    tasks.sort(key=lambda t: (t.get('dead', False), not t['path'], len(t['path']) or 99, t['kind'] != 'route', t['id']))
    return tasks

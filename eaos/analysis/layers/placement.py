"""The layer map (M6.1): every file of the project in a layer of its reference type, with the reason and a confidence.

A file is placed by, in order: the project's own eaos.policy.json (its layers' path patterns), the reference type's path
patterns (eaos/rules/reference-architectures.json, the most specific wins), or what the file is made of: an HTTP framework
puts it in the layer whose role is `endpoint`, a database client in the `data` one, React or JSX in the `screen` one. A
file none of them places is a listed gap, never a guess.

Beside the layer, each file has a side: where its code runs. `browser` (shipped to the person's browser: 'use client',
React and JSX outside Next.js's server components, anything a browser file imports), `server` (an HTTP framework, a
database driver, Node's own modules, 'use server', `server-only`, Python and Go, anything only server files import),
`shared` (imported by both), `database` (migrations and schemas) or `test`. The sides are what the browser boundary
(M6.3) and the rules split (M6.8) read; the layers are what the boundaries (M6.2) read.
"""
import re
from collections import defaultdict, deque
from fnmatch import fnmatch

from .. import reference_architecture as reference_types
from ...facts.frameworks.server_entries import directive

HTTP = re.compile(r'^(express|fastify|koa|hono|@hono/[\w-]+|h3|restify|@nestjs/[\w-]+|next/server|flask|fastapi|starlette|'
                  r'django(\.\w+)*|aiohttp|tornado|net/http|github\.com/(gin-gonic/gin|labstack/echo|gofiber/fiber|go-chi/chi)\S*)$')
DATABASE = re.compile(r'^(pg|postgres|mysql2?|better-sqlite3|sqlite3|@prisma/client|drizzle-orm(/[\w-]+)*|knex|mongoose|mongodb|'
                      r'typeorm|sequelize|@neondatabase/serverless|@vercel/postgres|@planetscale/database|kysely|'
                      r'sqlalchemy(\.\w+)*|psycopg2?|psycopg|asyncpg|pymongo|django\.db(\.\w+)*|peewee|database/sql|gorm\.io/\S+|'
                      r'github\.com/jackc/pgx\S*)$')
NODE = re.compile(r'^(node:(?!test$)[\w/]+|fs|fs/promises|child_process|net|tls|dgram|cluster|worker_threads)$')
SCREEN = re.compile(r'^(react|react-dom(/[\w-]+)?|preact|solid-js|vue|svelte|react-native)$')
SUPABASE = re.compile(r'^@supabase/(supabase-js|ssr|auth-helpers-[\w-]+)$')
JSX = re.compile(r'<[A-Z][\w.]*[\s/>]|</\w+>|return\s*\(\s*<')
SERVER_ONLY = re.compile(r'''import\s+['"]server-only['"]''')
BROWSER_GLOBALS = re.compile(r'\b(document|window|localStorage|sessionStorage)\.|\bimport\.meta\.env\b')
SERVER_PATHS = ('supabase/functions/**', '**/*.server.ts', '**/*.server.js', '**/*.server.tsx', 'pages/api/**',
                'src/pages/api/**', '**/route.ts', '**/route.js', 'server/**', 'api/**', 'backend/**', 'netlify/functions/**')
CONFIG = re.compile(r'(^|/)[\w.-]+\.config\.(js|cjs|mjs|ts|mts)$')
BUILT = ('dist/', 'build/', 'out/', '.next/', '.output/', '.svelte-kit/', 'public/build/', 'storybook-static/')
SERVER_LANGUAGES = {'python', 'go', 'java', 'ruby', 'php', 'csharp', 'kotlin', 'rust', 'elixir', 'scala'}
HIGH, MEDIUM, LOW = 'high', 'medium', 'low'
# What a file's imports place it by when its path does not, the first that holds: a component that imports a database
# driver is a screen (the driver there is the breach), a handler that imports one is an endpoint.
MARKED = (('screen', 'screen', 'it is a component (React, JSX, Vue or Svelte)'),
          ('endpoint', 'endpoint', 'it imports an HTTP framework'),
          ('data', 'data', 'it imports a database client'), ('supabase', 'data', 'it imports the Supabase client'))


def built(path):
    """Whether a path is built output (what a build writes), which the browser boundary reads on its own."""
    return any(path.startswith(prefix) or f'/{prefix}' in path for prefix in BUILT)


def reference_of(project):
    """(the reference type rooted at the app's folder, its id) or (None, None)."""
    found, prefix = reference_types.locate(project.root)
    return (reference_types.rooted(reference_types.by_id(found), prefix), found) if found else (None, None)


IMPORTED = (('endpoint', HTTP), ('data', DATABASE), ('node', NODE), ('screen', SCREEN), ('supabase', SUPABASE))


def _component(path, text):
    """A component file: a Vue or Svelte file, or a JSX/TSX file that draws markup."""
    return path.endswith(('.vue', '.svelte')) or path.endswith(('.jsx', '.tsx')) and bool(JSX.search(text))


def _written(path, text):
    """What a file's own text says: its directive, `server-only`, markup, the browser's globals."""
    said = directive(text)
    marks = {said} if said else set()
    found = (('server', bool(SERVER_ONLY.search(text))), ('screen', _component(path, text)), ('browser', bool(BROWSER_GLOBALS.search(text))))
    return marks | {name for name, there in found if there}


def _marks(project, path):
    """What a file is made of: {'endpoint', 'data', 'screen', 'node', 'supabase', 'client', 'server', 'browser'}."""
    modules, text = project.imports.get(path, ()), project.text(path)
    imported = {name for name, pattern in IMPORTED if any(pattern.match(module) for module in modules)}
    return imported | _written(path, text)


def _server_path(path):
    return any(fnmatch(path, pattern) or pattern.endswith('/**') and path.startswith(pattern[:-3] + '/') for pattern in SERVER_PATHS)


def _own_side(project, path, marks, next_app):
    """The side a file's own code says, before what imports it: None when only its importers can say."""
    if CONFIG.search(path): return 'build'
    if 'client' in marks: return 'browser'
    if 'server' in marks or project.language(path) in SERVER_LANGUAGES or _server_path(path): return 'server'
    # A component is the browser's, whatever it imports (a database driver there is the breach), but in Next.js, which
    # renders a component on the server unless it says 'use client'.
    if 'screen' in marks: return 'server' if next_app else 'browser'
    if {'endpoint', 'data', 'node'} & marks: return 'server'
    return 'browser' if 'browser' in marks else None


def _reach(starts, edges):
    """Every file reached from `starts` by imports (type-only imports are not edges: the compiler erases them)."""
    seen, queue = set(starts), deque(starts)
    while queue:
        for target in edges.get(queue.popleft(), ()):
            if target not in seen: seen.add(target); queue.append(target)
    return seen


REACHED = {(True, True): 'shared', (True, False): 'browser', (False, True): 'server', (False, False): 'unknown'}


def sides(project, marks, next_app):
    """{path: side}: a file's own side, else the sides of the files that import it. A file whose own code is the
    server's stays `server` when a browser file imports it: that import is the breach the browser boundary reports."""
    own = {path: _own_side(project, path, marks[path], next_app) for path in project.code}
    browser = _reach([p for p, side in own.items() if side == 'browser'], project.edges)
    server = _reach([p for p, side in own.items() if side == 'server'], project.edges)
    return {path: own[path] or REACHED[(path in browser, path in server)] for path in project.code}


def _by_role(reference, role):
    return next((layer['name'] for layer in reference['layers'] if layer.get('role') == role), None) if reference else None


def _generic(pattern):
    """A pattern that places a whole tree or every file of a kind: its placement is a medium guess."""
    return pattern.startswith('**') or pattern.count('/') == 1 and pattern.endswith('/**') and pattern.split('/')[0] in ('apps', 'src', 'packages')


def _by_marks(reference, marks):
    for mark, role, why in MARKED:
        layer = _by_role(reference, role) if mark in marks else None
        if layer: return layer, why
    return None, None


def _role_conflict(reference, layer, marks):
    """A path pattern put the file in a layer whose role its own code contradicts (an HTTP handler in a screens folder)."""
    role = next((l.get('role') for l in reference['layers'] if l['name'] == layer), None)
    return ('endpoint' in marks and role == 'screen') or ('screen' in marks and role in ('endpoint', 'data'))


def place(path, reference, policy_layers, marks):
    """(layer, confidence, reason) of one file; (None, None, why) for a gap."""
    if policy_layers:
        for name, patterns in sorted(policy_layers.items()):
            if any(fnmatch(path, pattern) for pattern in patterns): return name, HIGH, "the project's own eaos.policy.json"
    if reference:
        layer, pattern = reference_types.layer_of(path, reference)
        if layer:
            confidence = MEDIUM if _generic(pattern) else HIGH
            if _role_conflict(reference, layer, marks): confidence = LOW
            return layer, confidence, f'its path matches {pattern}'
        layer, why = _by_marks(reference, marks)
        if layer: return layer, MEDIUM, why
    return None, None, 'no path pattern of the reference type and nothing it imports places it'


def layer_map(project, policy_layers=None):
    """{'type', 'rows': [{path, layer, side, confidence, reason}], 'gaps': [path], 'tests': n, 'built': [path]}."""
    reference, type_id = reference_of(project)
    marks = {path: _marks(project, path) for path in project.code}
    next_app = 'next' in project.packages
    side_of = sides(project, marks, next_app)
    rows = []
    for path in project.code:
        layer, confidence, reason = place(path, reference, policy_layers, marks[path])
        rows.append({'path': path, 'layer': layer, 'side': side_of[path], 'confidence': confidence, 'reason': reason,
                     'marks': sorted(marks[path])})
    rows += [{'path': path, 'layer': 'database', 'side': 'database', 'confidence': HIGH, 'reason': 'a migration or a schema',
              'marks': []} for path in project.schemas]
    return {'type': type_id, 'reference': reference, 'rows': rows, 'gaps': [row['path'] for row in rows if not row['layer']],
            'tests': len(project.tests), 'built': project.built}


def allowed(reference):
    """{layer: set of the layers it may use} of a reference type (a layer may always use itself)."""
    return {layer['name']: set(layer.get('allowed_dependencies') or ()) | {layer['name']} for layer in reference['layers']}


def by_path(rows):
    return {row['path']: row for row in rows}


def importers(project):
    """{path: [paths that import it]}."""
    found = defaultdict(list)
    for source, targets in project.edges.items():
        for target in targets: found[target].append(source)
    return found

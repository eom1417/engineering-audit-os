"""The first pass of a run's setup (eaos/live/setup.py): `detect()`, the draft run.json from the project's files alone:
the app's folder, its package manager, how it installs, starts, builds and is checked, the environment names it reads
(from .env.example files and the code; never from a real .env) and a value the run chooses for each, and the database
it needs. Deterministic."""
import re
import secrets
import socket
from pathlib import Path

from .assist import ENV_EXAMPLES, read_json
from .run_profile import DANGER

APP_FOLDERS = ('.', 'app', 'web', 'client', 'frontend', 'apps/web', 'apps/app', 'apps/frontend', 'packages/web')
LOCKFILES = (('pnpm-lock.yaml', 'pnpm'), ('yarn.lock', 'yarn'), ('bun.lockb', 'bun'), ('bun.lock', 'bun'), ('package-lock.json', 'npm'))
DATABASES = {
    'postgres': ('pg', 'postgres', 'pg-promise', '@neondatabase/serverless', '@vercel/postgres', 'postgresql'),
    'sqlite': ('better-sqlite3', 'sqlite3', 'sqlite', '@libsql/client'),
    'mysql': ('mysql', 'mysql2'),
    'mongodb': ('mongodb', 'mongoose'),
    'supabase': ('@supabase/supabase-js', '@supabase/ssr', '@supabase/auth-helpers-nextjs'),
}
ENV_IN_CODE = re.compile(r'(?:process\.env|import\.meta\.env)\.([A-Z][A-Z0-9_]{2,})|process\.env\[[\'"]([A-Z][A-Z0-9_]{2,})[\'"]\]')
SECRETISH = re.compile(r'(SECRET|TOKEN|KEY|PASSWORD|PASS|SALT|PRIVATE|CREDENTIAL)', re.I)
URLISH = re.compile(r'(URL|URI|HOST|ENDPOINT|DSN|ORIGIN|DOMAIN)$', re.I)
MAIL_NAMES = re.compile(r'^(SMTP|MAIL|EMAIL)_?(HOST|SERVER|URL|PORT)$')     # where the app sends its mail: the run's Mailpit
SCHEMES = (('REDIS', 'redis'), ('MONGO', 'mongodb'), ('AMQP', 'amqp'), ('RABBIT', 'amqp'))   # an address a client parses by scheme
STATIC_SERVERS = ('browser-sync', 'live-server', 'http-server', 'lite-server', 'serve', 'five-server')
SERVERS = ('express', 'fastify', 'koa', '@hapi/hapi', 'hono', '@nestjs/core', 'polka')
SITE_FOLDERS = ('dist', 'build', '_site', 'public', 'docs', 'site', 'www', '.')
DB_NAMES = re.compile(r'^(DATABASE_URL|POSTGRES_URL|POSTGRES_PRISMA_URL|POSTGRES_URL_NON_POOLING|DIRECT_URL|PG_?URL|DB_URL|NEON_DATABASE_URL)$')


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


# ---------------------------------------------------------------- 1. detect

def app_folder(project):
    """The folder holding the app's package.json: the first conventional one with a dev or start script."""
    project = Path(project)
    for folder in APP_FOLDERS:
        scripts = read_json(project / folder / 'package.json').get('scripts') or {}
        if 'dev' in scripts or 'start' in scripts: return folder
    for path in sorted(project.glob('*/package.json')) + sorted(project.glob('*/*/package.json')):
        if 'node_modules' in path.parts: continue
        scripts = read_json(path).get('scripts') or {}
        if 'dev' in scripts or 'start' in scripts: return path.parent.relative_to(project).as_posix()
    return None


def package_manager(project, folder):
    for base in (Path(project) / folder, Path(project)):
        for name, manager in LOCKFILES:
            if (base / name).is_file(): return manager, name
    return 'npm', None


def runner(manager):
    """How to call a package manager here: itself, or through corepack (shipped with Node) when pnpm or yarn is
    not installed, so a project on pnpm runs on a computer that never installed pnpm."""
    import shutil
    if manager in ('pnpm', 'yarn') and not shutil.which(manager) and shutil.which('corepack'): return ['corepack', manager]
    return [manager]


def install_argv(manager, lockfile):
    if manager == 'npm': return ['npm', 'ci', '--no-audit', '--no-fund'] if lockfile else ['npm', 'install', '--no-audit', '--no-fund']
    return runner(manager) + ['install', '--frozen-lockfile']


def run_script(manager, name, *extra):
    base = ['npm', 'run', name] if manager == 'npm' else runner(manager) + ['run', name]
    return base + (['--', *extra] if extra else [])


def script_is_safe(scripts, name, seen=None):
    """A package.json script runs only when neither it nor any script it calls deploys or reaches production."""
    seen = seen or set()
    if name in seen: return True
    seen.add(name)
    body = scripts.get(name)
    if body is None or DANGER.search(name) or DANGER.search(body): return False
    for called in re.findall(r'(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?([\w:.-]+)', body):
        if called in scripts and not script_is_safe(scripts, called, seen): return False
    return True


def dependencies(package):
    return {**(package.get('dependencies') or {}), **(package.get('devDependencies') or {})}


def framework(package):
    deps = dependencies(package)
    for name in ('expo', 'next', 'nuxt', 'astro', '@remix-run/dev', '@sveltejs/kit', 'vite', 'react-scripts'):
        if name in deps: return name
    return None


def dev_command(manager, package, port):
    """How the app starts for the lock: its framework's dev server on 127.0.0.1:<port>, without file watchers."""
    scripts, kind = package.get('scripts') or {}, framework(package)
    port = str(port)
    if kind == 'expo': return ['npx', 'expo', 'start', '--web', '--port', port, '--host', 'localhost'], {'CI': '1'}   # PORT is ignored
    if kind == 'next': return ['npx', 'next', 'dev', '-p', port, '-H', '127.0.0.1'], {}
    if kind in ('vite', '@sveltejs/kit', '@remix-run/dev'):
        return ['npx', 'vite', '--port', port, '--host', '127.0.0.1', '--strictPort'], {}
    if kind == 'astro': return ['npx', 'astro', 'dev', '--port', port, '--host', '127.0.0.1'], {}
    if kind == 'nuxt': return ['npx', 'nuxt', 'dev', '--port', port, '--host', '127.0.0.1'], {}
    if kind == 'react-scripts': return run_script(manager, 'start'), {'BROWSER': 'none', 'HOST': '127.0.0.1', 'PORT': port}
    for name in ('dev', 'start'):      # PORT: what a plain server reads, named in no .env (the golden trial's app never answered)
        if name in scripts and script_is_safe(scripts, name): return run_script(manager, name), {'PORT': port}
    return None, {}


def production_commands(manager, package, port):
    """(build, start) for the load baseline: the built app, never the dev server; an app with no build step (a plain Node
    server) is its own production, started as it starts ([] to build); (None, None) if unclear."""
    scripts, kind = package.get('scripts') or {}, framework(package)
    if kind == 'expo': return None, None       # its start script is the dev server
    build = [run_script(manager, 'build')] if 'build' in scripts and script_is_safe(scripts, 'build') else []
    port = str(port)
    if kind == 'next': return (build, ['npx', 'next', 'start', '-p', port, '-H', '127.0.0.1']) if build else (None, None)
    if _starts_built(scripts): return build, run_script(manager, 'start')
    if kind in ('vite', '@sveltejs/kit') and build: return build, ['npx', 'vite', 'preview', '--port', port, '--host', '127.0.0.1', '--strictPort']
    return None, None


def _starts_built(scripts):
    """Whether the start script is safe and runs no dev server or watcher: the built app, or a plain server."""
    return 'start' in scripts and script_is_safe(scripts, 'start') and not re.search(r'\b(vite|next dev|nodemon|--watch)\b', scripts['start'])


def _first_safe(scripts, names):
    """The first of `names` the project's scripts hold and may run (script_is_safe), or None."""
    return next((n for n in names if n in scripts and script_is_safe(scripts, n)), None)


def checks(manager, package):
    """The project's own checks: its typecheck, lint and test scripts (npm's placeholder test is not a test)."""
    scripts, found = package.get('scripts') or {}, []
    for names in (('typecheck', 'type-check', 'tsc', 'check-types', 'types'), ('lint',), ('test', 'test:unit')):
        name = _first_safe(scripts, names)
        if name and 'no test specified' not in scripts[name] and not re.search(r'\b(playwright|cypress)\b', scripts[name]):
            found.append(run_script(manager, name))
    return found


def environment_names(project, folder):
    """{name: example value or ''} from the example env files and the code. A real .env is never read."""
    names = _example_names(project, folder)
    for name in _code_names(Path(project) / folder): names.setdefault(name, '')
    return names


def _example_names(project, folder):
    """{name: example value} of the example env files, the first file naming it first."""
    names = {}
    for base in dict.fromkeys((Path(project) / folder, Path(project))):
        for example in ENV_EXAMPLES:
            path = base / example
            if not path.is_file(): continue
            for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
                match = re.match(r'\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*)$', line)
                if match: names.setdefault(match[1], match[2].strip().strip('"\''))
    return names


def _code_names(code):
    """Each environment name the app's code reads (process.env, import.meta.env), in the order it is met."""
    for path in [p for pattern in ('src/**/*', 'server/**/*', 'app/**/*', 'lib/**/*', 'pages/**/*', '*.config.*')
                 for p in code.glob(pattern)][:4000]:
        if path.suffix not in ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.vue', '.svelte') or 'node_modules' in path.parts: continue
        for match in ENV_IN_CODE.finditer(path.read_text(encoding='utf-8', errors='replace')):
            yield match[1] or match[2]


def _declarations(project, folder):
    """The text of the example env files, the code and the config files environment_names reads."""
    for base in dict.fromkeys((Path(project) / folder, Path(project))):
        for example in ENV_EXAMPLES:
            if (base / example).is_file(): yield base / example
    code = Path(project) / folder
    for path in [p for pattern in ('src/**/*', 'server/**/*', 'app/**/*', 'lib/**/*', 'pages/**/*', 'public/*', '*.config.*')
                 for p in code.glob(pattern)][:4000]:
        if path.suffix in ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.vue', '.svelte') and 'node_modules' not in path.parts \
                and path.is_file():
            yield path


def report_values(project, folder, names, report):
    """{name: folder in the report} for each name the project documents as a report's folder: a line
    `STUDIO_DATA=/path/to/report/studio` (an app whose dev server reads its data from a folder). The run points it
    at the report of this check, when that folder exists, so the app's screens show real data, not an empty state."""
    if not report or not names: return {}
    found = {}
    for path in _declarations(project, folder):
        text = path.read_text(encoding='utf-8', errors='replace')
        for name in names:
            match = re.search(rf'\b{re.escape(name)}\s*=\s*["\']?(?:\S*/)?report/([\w./-]*)', text)
            if name not in found and match:
                target = Path(report) / match[1].strip('/.')
                if target.is_dir(): found[name] = str(target)
    return found


def database_kind(project, folder, package):
    deps = dependencies(package)
    for base in (Path(project) / folder, Path(project)):
        schema = base / 'prisma/schema.prisma'
        if schema.is_file():
            provider = re.search(r'provider\s*=\s*"(\w+)"', schema.read_text(encoding='utf-8', errors='replace').split('datasource', 1)[-1])
            if provider: return {'postgresql': 'postgres', 'sqlite': 'sqlite', 'mysql': 'mysql', 'mongodb': 'mongodb'}.get(provider[1], provider[1])
    for kind in ('postgres', 'sqlite', 'mysql', 'mongodb', 'supabase'):
        if any(name in deps for name in DATABASES[kind]): return kind
    return None


def environment_values(names, port, database):
    """A value the run chooses for each name: the local database, the run's mail catcher, an address nobody answers, or
    a fresh random secret. Example values that are plainly not secrets (true, 3000, info) are kept; nothing is the owner's."""
    values, unset = {}, []
    for name, example in sorted(names.items()):
        if name in ('NODE_ENV',): continue
        value = _value(name, example, port, database)
        if value is None: unset.append(name)
        else: values[name] = value
    return values, unset


def _value(name, example, port, database):
    """The value the run chooses for one name (environment_values), or None when it chooses none."""
    if name == 'PORT': return str(port)
    if name in ('HOST', 'HOSTNAME'): return '127.0.0.1'
    # no address rather than a web one: an app falls back to its own database (SQLite), never parses http:// as one
    if DB_NAMES.match(name): return '{database_url}' if database == 'postgres' else None
    if MAIL_NAMES.match(name): return '{mail_port}' if name.endswith('PORT') else '127.0.0.1' if name.endswith(('HOST', 'SERVER')) else 'smtp://127.0.0.1:{mail_port}'
    if SECRETISH.search(name): return secrets.token_urlsafe(32)
    if URLISH.search(name): return next((f'{scheme}://127.0.0.1:9' for prefix, scheme in SCHEMES if name.startswith(prefix)), 'http://127.0.0.1:9')
    if example and re.fullmatch(r'(true|false|\d{1,6}|[a-z]{2,12}|[a-z-]{2,20})', example): return example
    return None


def prepare_commands(manager, package, project, folder, database):
    """Migrations for the run's empty database, when the project declares how it migrates."""
    scripts = package.get('scripts') or {}
    commands = _migrations(manager, scripts, Path(project) / folder) if database in ('postgres', 'sqlite') else []
    name = _first_safe(scripts, ('db:seed', 'seed'))
    if name and database: commands.append(run_script(manager, name))
    return commands


def _migrations(manager, scripts, app):
    """How the run's empty database gets the app's tables: Prisma's migrations (or its push), else the app's migrate script."""
    if (app / 'prisma/schema.prisma').is_file():
        return [['npx', 'prisma', 'migrate', 'deploy'] if (app / 'prisma/migrations').is_dir() else ['npx', 'prisma', 'db', 'push', '--skip-generate']]
    name = _first_safe(scripts, ('db:migrate', 'migrate:latest', 'migrate', 'db:push'))
    return [run_script(manager, name)] if name else []


def detect(project, report=None):
    """{'profile': the draft run.json, 'facts': what was found, 'limitations': [...]} from the files alone. A value the
    project documents as a folder of a report points at `report` (report_values)."""
    project = Path(project)
    folder = app_folder(project)
    if folder is None:
        from . import setup_python
        return setup_python.detect(project) or static_site(project, None, {}) or _unknown_app()
    package = read_json(project / folder / 'package.json')
    site = static_site(project, folder, package)
    if site: return site
    manager, lockfile = package_manager(project, folder)
    port = free_port()
    start, start_env = dev_command(manager, package, port)
    build, production = production_commands(manager, package, free_port())
    database = database_kind(project, folder, package)
    names = environment_names(project, folder)
    env, unset = environment_values(names, port, database)
    data = report_values(project, folder, unset, report)
    env, unset = {**env, **data}, [name for name in unset if name not in data]
    profile = {'schema_version': 1, 'app': folder, 'install': [install_argv(manager, lockfile)],
               'start': start or ['true'], 'port': port, 'health': '/', 'start_timeout': 180,
               'env': {'NODE_ENV': 'development', **start_env, **env},
               'checks': checks(manager, package)}
    prepare = prepare_commands(manager, package, project, folder, database)
    if prepare: profile['prepare'] = prepare
    if database in ('postgres', 'sqlite'): profile['database'] = {'kind': database, 'name': re.sub(r'\W', '_', project.name.lower())[:40] or 'app'}
    if production: profile['baseline'] = _production_profile(manager, lockfile, build, production, profile['env'], port)
    return {'profile': profile, 'facts': {'folder': folder, 'manager': manager, 'framework': framework(package), 'database': database,
                                          'env_names': sorted(names)}, 'limitations': _draft_limitations(start, database, unset)}


def _draft_limitations(start, database, unset):
    """What the draft run cannot do, from what detect() found."""
    limitations = []
    if start is None: limitations.append('no safe command starts the app (its dev and start scripts deploy, or there are none)')
    if database in ('mysql', 'mongodb'): limitations.append(f'the app uses {database}; EAOS starts PostgreSQL and SQLite only, so pages that need data may be empty')
    if database == 'supabase': limitations.append('the app talks to Supabase in the cloud; the run never reaches it, so pages that need data show their empty or error state')
    if unset: limitations.append('no value was chosen for: ' + ', '.join(unset[:12]))
    return limitations


def _production_profile(manager, lockfile, build, production, env, port):
    """run.json -> baseline: the built app, installed with its dev dependencies, on the port its start command names."""
    install = install_argv(manager, lockfile)
    return {'install': [install[:2] + ['--include=dev'] if manager == 'npm' else install], 'build': build, 'start': production,
            'port': next((int(production[production.index(flag) + 1]) for flag in ('--port', '-p') if flag in production), port),
            'env': {**{k: v for k, v in env.items() if k != 'NODE_ENV'}, 'NODE_ENV': 'production', 'PORT': str(port)}}


def static_site(project, folder, package):
    """detect()'s answer for a static site, served from its folder by Python's own server: pages with no package.json,
    or a package that only builds them and previews them with a static server (browser-sync: it ignores PORT, and the
    corpus' static site never answered); None for anything else."""
    deps = dependencies(package)
    if folder is not None and (framework(package) or any(n in deps for n in SERVERS) or not any(n in deps for n in STATIC_SERVERS)): return None
    base = Path(project) / (folder or '.')
    scripts = package.get('scripts') or {}
    build = [run_script(package_manager(project, folder)[0], 'build')] if folder and _first_safe(scripts, ('build',)) else []
    served = next((name for name in SITE_FOLDERS if (base / name / 'index.html').is_file()), 'dist' if build else None)
    if served is None: return None
    port = free_port()
    profile = {'schema_version': 1, 'app': folder or '.', 'install': [install_argv(*package_manager(project, folder))] if folder else [['true']],
               'start': ['python3', '-m', 'http.server', str(port), '--bind', '127.0.0.1', '--directory', served], 'port': port,
               'health': '/', 'start_timeout': 180, 'env': {}, 'checks': []}
    if build: profile['build'] = build
    return {'profile': profile, 'facts': {'folder': folder or '.', 'manager': folder and package_manager(project, folder)[0],
                                          'framework': 'static', 'database': None, 'env_names': []}, 'limitations': []}


def _unknown_app():
    """An app EAOS does not know how to start by itself (neither a JavaScript nor a Python web app, nor a static site): a draft that starts
    nothing, so the run's records never keep an earlier app's profile, and the assistant works out how to start it from
    the project's own documentation (_attempts), with safe() as the judge of every command it proposes."""
    profile = {'schema_version': 1, 'app': '.', 'install': [['true']], 'start': ['true'], 'port': free_port(), 'health': '/',
               'start_timeout': 180, 'env': {}, 'checks': []}
    return {'profile': profile, 'facts': {'folder': '.', 'manager': None, 'framework': None, 'database': None, 'env_names': [],
                                          'reason': 'no package.json with a dev or start script: the assistant works out how to start it'},
            'limitations': []}

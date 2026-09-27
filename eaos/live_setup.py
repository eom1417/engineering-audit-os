"""Set up a project's run with nothing written by hand (NS9.T3): run.json, a local database, sign-in, consent.

What a person once had to write for chief-ops (a run profile, a database, a seed script, an authorization),
this module finds or makes, in three passes:

  1. detect(): the app's folder, its package manager, how it installs, starts, builds and is checked, the
     environment names it reads (from .env.example files and the code; never from a real .env), and the
     database it needs. Deterministic, from the files alone.
  2. verify(): the draft is run for real in the sandbox (the project started, its first page opened in a
     browser that reaches 127.0.0.1 only). The page answers, or it does not; it asks for a sign-in, or not.
  3. assist(): when the page does not answer, or asks for a sign-in, the person's own AI assistant reads the
     project's documentation and the failure, and proposes changes: environment values, commands, and a seed
     script that signs in and adds sample data. Every proposal passes safe() before it runs: no command that
     deploys or reaches production, no address that is not 127.0.0.1, no file outside the run's folder. Then
     verify() runs again, at most ATTEMPTS times.

Nothing is guessed silently: what could not be made to work is written to run.json -> limitations, and shown.
The project folder is never written; everything goes to the run's folder (the guided workspace's runtime/).
"""
import json
import re
import secrets
import socket
import subprocess
from datetime import date, timedelta
from pathlib import Path

ATTEMPTS = 5
APP_FOLDERS = ('.', 'app', 'web', 'client', 'frontend', 'apps/web', 'apps/app', 'apps/frontend', 'packages/web')
# A script that deploys, publishes or reaches a hosted environment never runs, whatever it is called.
DANGER = re.compile(r'\b(deploy\w*|railway|vercel|netlify|flyctl|heroku|firebase|gh-pages|publish|wrangler|surge|'
                    r'kubectl|terraform|pulumi|gcloud|aws|azure|az\s|ssh|scp|rsync|docker\s+push|'
                    r'supabase\s+(db\s+push|link|functions\s+deploy)|release|staging|production|prod)\b', re.I)
LOCKFILES = (('pnpm-lock.yaml', 'pnpm'), ('yarn.lock', 'yarn'), ('bun.lockb', 'bun'), ('bun.lock', 'bun'), ('package-lock.json', 'npm'))
DATABASES = {
    'postgres': ('pg', 'postgres', 'pg-promise', '@neondatabase/serverless', '@vercel/postgres', 'postgresql'),
    'sqlite': ('better-sqlite3', 'sqlite3', 'sqlite', '@libsql/client'),
    'mysql': ('mysql', 'mysql2'),
    'mongodb': ('mongodb', 'mongoose'),
    'supabase': ('@supabase/supabase-js', '@supabase/ssr', '@supabase/auth-helpers-nextjs'),
}
ENV_EXAMPLES = ('.env.example', '.env.sample', '.env.template', '.env.local.example', '.env.development.example', 'example.env')
ENV_IN_CODE = re.compile(r'(?:process\.env|import\.meta\.env)\.([A-Z][A-Z0-9_]{2,})|process\.env\[[\'"]([A-Z][A-Z0-9_]{2,})[\'"]\]')
SECRETISH = re.compile(r'(SECRET|TOKEN|KEY|PASSWORD|PASS|SALT|PRIVATE|CREDENTIAL)', re.I)
URLISH = re.compile(r'(URL|URI|HOST|ENDPOINT|DSN|ORIGIN|DOMAIN)$', re.I)
DB_NAMES = re.compile(r'^(DATABASE_URL|POSTGRES_URL|POSTGRES_PRISMA_URL|POSTGRES_URL_NON_POOLING|DIRECT_URL|PG_?URL|DB_URL|NEON_DATABASE_URL)$')


def read_json(path):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}


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
    for name in ('next', 'nuxt', 'astro', '@remix-run/dev', '@sveltejs/kit', 'vite', 'react-scripts'):
        if name in deps: return name
    return None


def dev_command(manager, package, port):
    """How the app starts for the lock: its framework's dev server on 127.0.0.1:<port>, without file watchers."""
    scripts, kind = package.get('scripts') or {}, framework(package)
    port = str(port)
    if kind == 'next': return ['npx', 'next', 'dev', '-p', port, '-H', '127.0.0.1'], {}
    if kind in ('vite', '@sveltejs/kit', '@remix-run/dev'):
        return ['npx', 'vite', '--port', port, '--host', '127.0.0.1', '--strictPort'], {}
    if kind == 'astro': return ['npx', 'astro', 'dev', '--port', port, '--host', '127.0.0.1'], {}
    if kind == 'nuxt': return ['npx', 'nuxt', 'dev', '--port', port, '--host', '127.0.0.1'], {}
    if kind == 'react-scripts': return run_script(manager, 'start'), {'BROWSER': 'none', 'HOST': '127.0.0.1'}
    for name in ('dev', 'start'):
        if name in scripts and script_is_safe(scripts, name): return run_script(manager, name), {}
    return None, {}


def production_commands(manager, package, port):
    """(build, start) for the load baseline: the built app, never the dev server; (None, None) if unclear."""
    scripts, kind = package.get('scripts') or {}, framework(package)
    if 'build' not in scripts or not script_is_safe(scripts, 'build'): return None, None
    build = [run_script(manager, 'build')]
    port = str(port)
    if kind == 'next': return build, ['npx', 'next', 'start', '-p', port, '-H', '127.0.0.1']
    if 'start' in scripts and script_is_safe(scripts, 'start') and not re.search(r'\b(vite|next dev|nodemon|--watch)\b', scripts['start']):
        return build, run_script(manager, 'start')
    if kind in ('vite', '@sveltejs/kit'): return build, ['npx', 'vite', 'preview', '--port', port, '--host', '127.0.0.1', '--strictPort']
    return None, None


def checks(manager, package):
    """The project's own checks: its typecheck, lint and test scripts (npm's placeholder test is not a test)."""
    scripts, found = package.get('scripts') or {}, []
    for names in (('typecheck', 'type-check', 'tsc', 'check-types', 'types'), ('lint',), ('test', 'test:unit')):
        name = next((n for n in names if n in scripts and script_is_safe(scripts, n)), None)
        if name and 'no test specified' not in scripts[name] and not re.search(r'\b(playwright|cypress)\b', scripts[name]):
            found.append(run_script(manager, name))
    return found


def environment_names(project, folder):
    """{name: example value or ''} from the example env files and the code. A real .env is never read."""
    names = {}
    for base in dict.fromkeys((Path(project) / folder, Path(project))):
        for example in ENV_EXAMPLES:
            path = base / example
            if not path.is_file(): continue
            for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
                match = re.match(r'\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*)$', line)
                if match: names.setdefault(match[1], match[2].strip().strip('"\''))
    code = Path(project) / folder
    for path in [p for pattern in ('src/**/*', 'server/**/*', 'app/**/*', 'lib/**/*', 'pages/**/*', '*.config.*')
                 for p in code.glob(pattern)][:4000]:
        if path.suffix not in ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.vue', '.svelte') or 'node_modules' in path.parts: continue
        for match in ENV_IN_CODE.finditer(path.read_text(encoding='utf-8', errors='replace')):
            names.setdefault(match[1] or match[2], '')
    return names


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
    """A value the run chooses for each name: the local database, an address nobody answers, or a fresh random
    secret. Example values that are plainly not secrets (true, 3000, info) are kept; nothing is the owner's."""
    values, unset = {}, []
    for name, example in sorted(names.items()):
        if name in ('NODE_ENV',): continue
        if name == 'PORT': values[name] = str(port)
        elif name in ('HOST', 'HOSTNAME'): values[name] = '127.0.0.1'
        elif DB_NAMES.match(name) and database == 'postgres': values[name] = '{database_url}'
        elif SECRETISH.search(name): values[name] = secrets.token_urlsafe(32)
        elif URLISH.search(name): values[name] = 'http://127.0.0.1:9'
        elif example and re.fullmatch(r'(true|false|\d{1,6}|[a-z]{2,12}|[a-z-]{2,20})', example): values[name] = example
        else: unset.append(name)
    return values, unset


def prepare_commands(manager, package, project, folder, database):
    """Migrations for the run's empty database, when the project declares how it migrates."""
    scripts, commands = package.get('scripts') or {}, []
    if database == 'postgres' or database == 'sqlite':
        if (Path(project) / folder / 'prisma/schema.prisma').is_file():
            migrations = (Path(project) / folder / 'prisma/migrations').is_dir()
            commands.append(['npx', 'prisma', 'migrate', 'deploy'] if migrations else ['npx', 'prisma', 'db', 'push', '--skip-generate'])
        else:
            name = next((n for n in ('db:migrate', 'migrate:latest', 'migrate', 'db:push') if n in scripts and script_is_safe(scripts, n)), None)
            if name: commands.append(run_script(manager, name))
    name = next((n for n in ('db:seed', 'seed') if n in scripts and script_is_safe(scripts, n)), None)
    if name and database: commands.append(run_script(manager, name))
    return commands


def detect(project):
    """{'profile': the draft run.json, 'facts': what was found, 'limitations': [...]} from the files alone."""
    project = Path(project)
    folder = app_folder(project)
    if folder is None:
        return {'profile': None, 'facts': {'reason': 'no package.json with a dev or start script'},
                'limitations': ['EAOS runs JavaScript and TypeScript web apps for now; this project is not one it can start by itself']}
    package = read_json(project / folder / 'package.json')
    manager, lockfile = package_manager(project, folder)
    port = free_port()
    start, start_env = dev_command(manager, package, port)
    build, production = production_commands(manager, package, free_port())
    database = database_kind(project, folder, package)
    names = environment_names(project, folder)
    env, unset = environment_values(names, port, database)
    limitations = []
    if start is None: limitations.append('no safe command starts the app (its dev and start scripts deploy, or there are none)')
    if database in ('mysql', 'mongodb'): limitations.append(f'the app uses {database}; EAOS starts PostgreSQL and SQLite only, so pages that need data may be empty')
    if database == 'supabase': limitations.append('the app talks to Supabase in the cloud; the run never reaches it, so pages that need data show their empty or error state')
    if unset: limitations.append('no value was chosen for: ' + ', '.join(unset[:12]))
    profile = {'schema_version': 1, 'app': folder, 'install': [install_argv(manager, lockfile)],
               'start': start or ['true'], 'port': port, 'health': '/', 'start_timeout': 180,
               'env': {'NODE_ENV': 'development', **start_env, **env},
               'checks': checks(manager, package)}
    prepare = prepare_commands(manager, package, project, folder, database)
    if prepare: profile['prepare'] = prepare
    if database in ('postgres', 'sqlite'): profile['database'] = {'kind': database, 'name': re.sub(r'\W', '_', project.name.lower())[:40] or 'app'}
    if build and production:
        baseline_env = {k: v for k, v in profile['env'].items() if k != 'NODE_ENV'}
        profile['baseline'] = {'install': [install_argv(manager, lockfile)[:2] + ['--include=dev'] if manager == 'npm' else install_argv(manager, lockfile)],
                               'build': build, 'start': production, 'port': int(production[production.index('--port') + 1]) if '--port' in production
                               else (int(production[production.index('-p') + 1]) if '-p' in production else port),
                               'env': {**baseline_env, 'NODE_ENV': 'production', 'PORT': str(port)}}
    return {'profile': profile, 'facts': {'folder': folder, 'manager': manager, 'framework': framework(package), 'database': database,
                                          'env_names': sorted(names)}, 'limitations': limitations}


# ---------------------------------------------------------------- 2. verify

PROBE = r"""
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ args: ['--proxy-server=http://127.0.0.1:9', '--proxy-bypass-list=127.0.0.1;localhost;[::1]'] });
  const page = await browser.newPage(process.env.EAOS_STORAGE_STATE ? { storageState: process.env.EAOS_STORAGE_STATE } : {});
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e.message).slice(0, 300)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 300)); });
  const visit = async (path) => {
    let status = 0;
    try { const r = await page.goto(new URL(path, process.env.BASE_URL).href, { waitUntil: 'networkidle', timeout: 60000 }); status = r ? r.status() : 0; }
    catch (e) { errors.push(String(e.message).slice(0, 300)); }
    return { path, status, url: page.url(), password: await page.locator('input[type=password]').count().catch(() => 0),
             text: (await page.locator('body').innerText().catch(() => '')).slice(0, 1500) };
  };
  const first = await visit('/');
  const others = [];
  for (const path of JSON.parse(process.env.EAOS_ROUTES || '[]')) others.push(await visit(path));
  console.log(JSON.stringify({ ...first, others, errors: errors.slice(0, 10) }));
  await browser.close();
})();
"""


def routes(report, limit=4):
    """A few of the lock's screens without parameters, to see that each one is a screen of its own."""
    plan = read_json(Path(report) / 'behavior-lock/plan.json') if report else {}
    found = [s for spec in plan.get('specs') or [] for s in spec.get('surfaces') or []
             if s.startswith('/') and s != '/' and ':' not in s and '*' not in s]
    return list(dict.fromkeys(found))[:limit]


def stuck(page):
    """Every screen visited shows the first page's text: a chooser or a gate stands in front of the app."""
    others = page.get('others') or []
    words = lambda text: ' '.join((text or '').split())
    return len(others) >= 2 and all(words(o.get('text')) == words(page.get('text')) for o in others)


def signed_out(page):
    """The first page asks for a sign-in: a password field, or a login address it was sent to."""
    return bool(page.get('password')) or bool(re.search(r'/(login|signin|sign-in|auth)(\b|/|\?|$)', page.get('url') or '', re.I))


def verify(project, runtime, attempt, report=None, mode='lock'):
    """Run the draft: install (and, for the baseline, build), start, seed, open the first page and a few screens.
    {'ok', 'page', 'fixtures', 'failure'}"""
    from .live_run import LiveRun
    runtime = Path(runtime)
    live = LiveRun(project, runtime, 'S05', mode=mode)
    if mode == 'baseline': report = None           # the load test opens the pages anonymously: the first page is enough
    record = {'attempt': attempt, 'fixtures': {}}
    try:
        live.setup()
        base = live.start()
        state = runtime / 'setup' / 'storage-state.json'
        if state.exists(): state.unlink()
        record['fixtures'] = dict(live.seed(base, state))
        record['seed_output'] = getattr(live, 'seed_output', '')
        script = live.sandbox.copy / '.eaos-probe.cjs'
        script.write_text(PROBE, encoding='utf-8')
        code, out, err = live.run(['node', str(script)], timeout=600, env={
            'BASE_URL': base, 'EAOS_STORAGE_STATE': str(state) if state.is_file() else '',
            'EAOS_ROUTES': json.dumps(routes(report))})
        page = json.loads(out.strip().splitlines()[-1]) if code == 0 and out.strip() else {'status': 0, 'errors': [(out + err)[-800:]]}
        record['page'] = page
        bad = [o for o in [page, *(page.get('others') or [])] if not 200 <= o.get('status', 0) < 400]
        record['ok'] = not bad and not signed_out(page) and not stuck(page)
        if not record['ok']:
            record['failure'] = ('the first page asks for a sign-in' if signed_out(page) else
                                 'every screen shows the same page, so something (a chooser, a gate) stands in front of the app. '
                                 'The page says:\n' + '\n'.join(l for l in (page.get('text') or '').splitlines() if l.strip())[:600] if stuck(page) else
                                 f"{bad[0].get('path', '/')} answered {bad[0].get('status')}: {'; '.join(page.get('errors') or [])[:600]}")
    except Exception as problem:            # a failed start is the evidence the assistant needs, not a crash
        record['ok'] = False
        record['failure'] = f'{type(problem).__name__}: {problem}'[-2500:]
    finally:
        if not record.get('ok') and record.get('seed_output') and record.get('failure'):
            record['failure'] += '\nThe seed script said:\n' + record['seed_output'][-1500:]
        live.stop()
        live.record(f"setup/{'baseline-' if mode == 'baseline' else ''}attempt-{attempt}.json")
    return record


# ---------------------------------------------------------------- 3. assist

ASSIST_SYSTEM = """You set up a web app to run on this computer for automated checks, in an isolated copy, with a
local database EAOS provides. You do not change the app. You answer with one JSON object:
{"action": "final", "result": {"reason": "<one sentence>",
  "env": {"NAME": "value"}, "start": ["argv", "..."] or null, "install": [["argv"]] or null,
  "prepare": [["argv"]] or null, "database": "postgres" or "none" or null,
  "seed_script": "<a Node.js script>" or null, "fixtures": {"E2E_NAME": "value"} or null}}
"env" is the complete environment: it replaces the current one, so keep what still applies. For "start",
"install" and "prepare", null keeps the current value and [] removes it (no prepare commands at all).
"database": "none" when the app runs without one locally; "postgres" gives it EAOS's local PostgreSQL.
Rules, each one enforced: every address is http://127.0.0.1 or http://localhost; no real secret (generate
values); no command that deploys, publishes, or reaches a hosted service; commands run in the app's folder.
Use "{database_url}" for the local database's address, and "{run_dir}" (an empty folder of the run's own,
outside the app, made for you) for any folder the app needs outside its code: backups, uploads, data. Never
create folders with commands. The seed script runs with Node after the app starts,
with BASE_URL and EAOS_STORAGE_STATE in its environment; require('playwright') is available. It signs in the
way the app itself allows locally (a development sign-in the docs describe, or signing up through the page),
adds a little sample data if the app is empty, and saves the browser state with
context.storageState({ path: process.env.EAOS_STORAGE_STATE }). Its console output ends with one JSON line of
fixture values it created, for example {"E2E_PROFILEID": "..."}, when the checks need them."""

DOCS = ('README.md', 'README', 'CLAUDE.md', 'AGENTS.md', 'CONTRIBUTING.md', 'docs/DEVELOPMENT.md', 'docs/SETUP.md',
        'docs/development.md', 'docs/setup.md', 'docs/LOCAL.md')


def _excerpt(project, folder, limit=40000):
    parts, used = [], 0
    for base in dict.fromkeys((Path(project), Path(project) / folder)):
        for name in DOCS + ENV_EXAMPLES:
            path = base / name
            if path.is_file() and used < limit:
                text = path.read_text(encoding='utf-8', errors='replace')[:min(12000, limit - used)]
                parts.append(f'=== {path.relative_to(project)}\n{text}')
                used += len(text)
    return '\n\n'.join(parts)


BASELINE_NOTE = """This time the app runs as it does in production, for a load test: built (the "build" commands), then
started from the build ("start"), with NODE_ENV=production, on the port the profile names. The fields you return
(env, start, install, prepare, database, and also "build": [["argv"]]) apply to that production run only. The
load test opens the pages without signing in, so no seed script is needed. The database, when the app needs one
in production, is EAOS's local PostgreSQL; its user is the superuser "postgres", and a prepare step may create the
roles the app requires with the app's own scripts."""


SOURCE_SUFFIXES = ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.json', '.vue', '.svelte')


def relevant_source(project, folder, failure, limit=3, context=60):
    """The code that raised the failure: each distinctive phrase of the error, looked up in the project's own
    source (never its build output or libraries), with the lines around it. The assistant fixes what it can see."""
    root = Path(project) / folder
    # Error lines, and the page's own words ("Where are you working?"): both are written somewhere in the code.
    phrases = sorted({p.strip(' .:-') for p in re.split(r'[\n|]| - |: |\s{2,}', failure or '') if len(p.strip()) >= 16},
                     key=len, reverse=True)[:16]                    # the most distinctive first
    found, seen = [], set()
    files = [f for f in root.rglob('*') if f.suffix in SOURCE_SUFFIXES and f.is_file()
             and not any(part in ('node_modules', 'dist', 'dist-server', 'build', '.next', 'coverage') for part in f.parts)][:6000]
    for phrase in phrases:
        needle = phrase[:60]
        for path in files:
            text = path.read_text(encoding='utf-8', errors='replace')
            at = text.find(needle)
            if at < 0 or path in seen: continue
            seen.add(path)
            lines = text.splitlines()
            line = text.count('\n', 0, at)
            start, end = max(0, line - context), min(len(lines), line + context)
            found.append(f'=== {path.relative_to(Path(project))} (lines {start + 1}-{end})\n' + '\n'.join(lines[start:end]))
            break
        if len(found) >= limit: break
    return '\n\n'.join(found)


def assist_messages(project, runtime, detected, failure, needs, mode='lock'):
    folder = detected['profile']['app']
    package = read_json(Path(project) / folder / 'package.json')
    profile = json.loads((Path(runtime) / 'run.json').read_text(encoding='utf-8'))
    if mode == 'baseline': profile = {**{k: v for k, v in profile.items() if k != 'baseline'}, **(profile.get('baseline') or {})}
    brief = {'what_failed': failure, 'current_profile': profile,
             'detected': detected['facts'], 'scripts': package.get('scripts'), 'fixtures_the_checks_need': needs}
    return [{'role': 'system', 'content': ASSIST_SYSTEM + ('\n\n' + BASELINE_NOTE if mode == 'baseline' else '')},
            {'role': 'user', 'content': 'The situation:\n' + json.dumps(brief, ensure_ascii=False, indent=1)
             + '\n\nThe project documentation:\n' + _excerpt(project, folder)
             + ('\n\nThe code that raised the failure:\n' + source if (source := relevant_source(project, folder, failure)) else '')}]


def safe(proposal):
    """Reasons a proposal may not run; empty when it may."""
    problems = []
    for name, value in (proposal.get('env') or {}).items():
        for host in re.findall(r'[a-z][a-z0-9+.-]*://(?:[^@/\s]*@)?([^:/\s?#]+)', str(value), re.I):
            if host not in ('127.0.0.1', 'localhost', '{database_url}') and not str(value).startswith('{database_url}'):
                problems.append(f'{name} points at {host}, not at this computer')
    commands = ([proposal.get('start')] + list(proposal.get('install') or []) + list(proposal.get('prepare') or [])
                + list(proposal.get('build') or []))
    for argv in [c for c in commands if c]:
        text = ' '.join(map(str, argv))
        if DANGER.search(text): problems.append(f'refused: {text[:120]}')
        if argv and Path(str(argv[0])).name not in ('npm', 'npx', 'pnpm', 'yarn', 'bun', 'node', 'corepack', 'true'):
            problems.append(f'refused, not a package manager or node: {text[:120]}')
    script = proposal.get('seed_script') or ''
    if DANGER.search(script): problems.append(f"the seed script mentions {DANGER.search(script)[0]!r}, which a run never reaches")
    for host in re.findall(r'https?://([^:/\s\'"`]+)', script):
        if host not in ('127.0.0.1', 'localhost'): problems.append(f'the seed script reaches {host}')
    return problems


def apply(runtime, proposal, mode='lock'):
    """Merge a safe proposal into run.json (into its `baseline` for the production run); a seed script is
    written beside it, never into the project."""
    path = Path(runtime) / 'run.json'
    profile = json.loads(path.read_text(encoding='utf-8'))
    target = profile.setdefault('baseline', {}) if mode == 'baseline' else profile
    if proposal.get('env') is not None:          # the complete environment: what it leaves out is dropped
        target['env'] = {k: str(v) for k, v in proposal['env'].items()}
    target.setdefault('env', {}).update({k: str(v) for k, v in (proposal.get('fixtures') or {}).items()})
    for key in ('start', 'install', 'prepare') + (('build',) if mode == 'baseline' else ()):
        if proposal.get(key) is None: continue
        if proposal[key]: target[key] = proposal[key]
        elif key == 'prepare': target.pop('prepare', None)    # [] removes; start and install are never empty
    if proposal.get('database') == 'none' and mode == 'lock':
        profile.pop('database', None)
        profile['env'] = {k: v for k, v in profile['env'].items() if '{database_url}' not in v}
    elif proposal.get('database') == 'postgres' and 'database' not in profile:
        profile['database'] = {'kind': 'postgres', 'name': 'app'}
    if proposal.get('seed_script') and mode == 'lock':
        seed = Path(runtime) / 'setup' / 'seed.cjs'
        seed.parent.mkdir(parents=True, exist_ok=True)
        seed.write_text(proposal['seed_script'], encoding='utf-8')
        profile['seed'] = [['node', str(seed)]]
    write_profile(runtime, profile)
    return profile


def write_profile(runtime, profile):
    from .artifact_contracts import contracts, validate
    problems = validate(profile, contracts()['run-profile'])
    if problems: raise ValueError(f'run.json would break its contract: {problems[0]}')
    path = Path(runtime) / 'run.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    path.chmod(0o600)       # generated secrets live here: the run's own, but still nobody else's business


def fixtures_needed(report):
    """The E2E_* names the lock's specs skip without."""
    names = set()
    for spec in (Path(report) / 'behavior-lock/playwright').glob('*.spec.ts') if report else []:
        names |= set(re.findall(r'needs_fixture: set (E2E_[A-Z0-9_]+)', spec.read_text(encoding='utf-8')))
    return sorted(names)


# ---------------------------------------------------------------- consent, and the whole setup

def setup_baseline(project, runtime, detected, provider, say, attempts=3):
    """The production run the load baseline needs: built, started from the build, the first page answering.
    Marked in run.json -> baseline.verified, so the load test only runs on a production run that works."""
    runtime, record, refusal = Path(runtime), {'ok': False, 'failure': ''}, ''
    (runtime / 'setup').mkdir(parents=True, exist_ok=True)
    for attempt in range(1, attempts + 1):
        say(f'baseline-{attempt}')
        record = verify(project, runtime, attempt, mode='baseline')
        if record['ok'] or provider is None: break
        failure = record['failure'] + (f'. Your previous proposal was refused and not applied: {refusal}' if refusal else '')
        answer, _ = provider.complete(assist_messages(project, runtime, detected, failure, [], mode='baseline'))
        proposal = answer.get('result') or {}
        refused = safe(proposal)
        refusal = '; '.join(refused)
        (runtime / f'setup/baseline-proposal-{attempt}.json').write_text(
            json.dumps({'proposal': proposal, 'refused': refused}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        if not refused: apply(runtime, proposal, mode='baseline')
        if attempt == attempts:
            record = verify(project, runtime, attempt + 1, mode='baseline')
            if refused and not record['ok']: record['failure'] = 'the assistant proposed something unsafe, which was refused: ' + refused[0]
    profile = json.loads((runtime / 'run.json').read_text(encoding='utf-8'))
    profile['baseline']['verified'] = record['ok']
    write_profile(runtime, profile)
    return record


def authorize(project, runtime, granted_by, days=30):
    """authorization.json for the project's current commit: the run stages, nothing passed from the environment."""
    from .sandbox import head
    commit = head(project)
    if not commit: raise RuntimeError(f'{project} is not a git repository')
    grant = {'schema_version': 1, 'project': Path(project).name, 'commit': commit, 'granted_by': granted_by,
             'stages': ['S05', 'S08', 'S09', 'S10', 'S11', 'S12', 'S13', 'S14'], 'env_allow': [],
             'expires': (date.today() + timedelta(days=days)).isoformat(),
             'note': 'Granted by answering yes in eaos next: runs happen in an isolated copy on this computer.'}
    path = Path(runtime) / 'authorization.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(grant, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return grant


def setup(project, runtime, report=None, provider=None, say=print):
    """Detect, verify, and ask the assistant when needed: run.json that works, or one whose limits are written.
    {'ok', 'attempts', 'limitations', 'page'}"""
    runtime = Path(runtime)
    (runtime / 'setup').mkdir(parents=True, exist_ok=True)
    detected = detect(project)
    if detected['profile'] is None:
        return {'ok': False, 'attempts': 0, 'limitations': detected['limitations'], 'page': None}
    needs = fixtures_needed(report)
    write_profile(runtime, detected['profile'])
    (runtime / 'setup/detected.json').write_text(json.dumps(detected, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    limitations, attempts, record, refusal = list(detected['limitations']), 0, None, ''
    while attempts < ATTEMPTS:
        attempts += 1
        say(attempts)
        record = verify(project, runtime, attempts, report)
        known = {**json.loads((runtime / 'run.json').read_text())['env'], **record['fixtures']}
        missing = [name for name in needs if name not in known]
        if record['ok'] and not missing: break
        if provider is None:
            limitations.append('no AI assistant was available to work out: ' + (record.get('failure') or 'the fixtures ' + ', '.join(missing)))
            break
        failure = record.get('failure') or ('the checks need fixture values: ' + ', '.join(missing))
        if refusal: failure += f'. Your previous proposal was refused and not applied: {refusal}'
        answer, _ = provider.complete(assist_messages(project, runtime, detected, failure, needs))
        proposal = answer.get('result') or {}
        refused = safe(proposal)
        (runtime / f'setup/proposal-{attempts}.json').write_text(json.dumps({'proposal': proposal, 'refused': refused},
                                                                           ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        refusal = '; '.join(refused)
        if refused:
            limitations.append('the assistant proposed something unsafe, which was refused: ' + refused[0])
            continue
        apply(runtime, proposal)
    ok = bool(record and record['ok'])
    if ok and (detected['profile'].get('baseline') or {}).get('build'):
        speed = setup_baseline(project, runtime, detected, provider, say)
        if not speed['ok']: limitations.append('speed cannot be measured: ' + speed['failure'][:300])
    if record and not ok and record.get('failure') and not any(record['failure'] in l for l in limitations):
        limitations.append('the app could not be made to answer: ' + record['failure'][:300])
    profile = json.loads((runtime / 'run.json').read_text(encoding='utf-8'))
    # Names the first draft left without a value may have one now.
    unset = [n for n in detected['facts']['env_names'] if n not in profile['env'] and n != 'NODE_ENV']
    limitations = [l for l in limitations if not l.startswith('no value was chosen for')]
    if unset and ok: limitations.append('run without a value for: ' + ', '.join(unset[:12]) + (' …' if len(unset) > 12 else ''))
    if record and missing: limitations.append('screens that need these values are not recorded: ' + ', '.join(missing))
    profile['limitations'] = sorted(set(limitations))
    write_profile(runtime, profile)
    return {'ok': ok, 'attempts': attempts, 'limitations': profile['limitations'], 'page': (record or {}).get('page')}

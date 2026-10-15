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

setup() is the flow `setup` of the live map (eaos/progress/flow.py): its stages are FLOW, written as they happen to
<runtime>/progress/setup.jsonl, each attempt a step with its outcome.
"""
import json
import re
import secrets
import socket
from datetime import date, timedelta
from pathlib import Path

from . import progress
from .live_assist import ENV_EXAMPLES, assist_messages, read_json
from .progress.flow import OPTIONAL, Stage
from .run_profile import DANGER, apply, safe, write_profile

ATTEMPTS = 5
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
    `STUDIO_DATA=/path/to/report/studio` (EAOS's own Studio reads its data so, studio/vite.config.ts). The run points it
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


def detect(project, report=None):
    """{'profile': the draft run.json, 'facts': what was found, 'limitations': [...]} from the files alone. A value the
    project documents as a folder of a report points at `report` (report_values)."""
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
    data = report_values(project, folder, unset, report)
    env, unset = {**env, **data}, [name for name in unset if name not in data]
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

# The page a verify opens in a browser that reaches 127.0.0.1 only: the first page and a few screens, as JSON.
PROBE = (Path(__file__).resolve().parent / 'templates/setup/probe.cjs').read_text(encoding='utf-8')


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


# The words of a page that shows nothing yet: no data, no report, an empty list.
EMPTY = re.compile(r'\b(no (data|reports?|results?|items?|records?|content|entries)\b|nothing (here|to show|yet)|is empty\b|'
                   r'(not|none) (found|available|loaded) yet)|لا (يوجد|توجد|شيء|بيانات)|فارغ', re.I)


def empty_state(page, unset):
    """Why the first page is no working app although it answered: it shows an empty, "no data" state while the run
    has no value for a name the app reads, so every screen would be pictured empty. '' otherwise."""
    text = ' '.join((page.get('text') or '').split())
    if not unset or not (EMPTY.search(text) or len(text.split()) < 3): return ''
    return ('the first page shows an empty, no-data state while the app runs without a value for: ' + ', '.join(unset[:12])
            + '. Give it one (often a folder or address the app reads its data from); the page says: ' + (text[:400] or '(nothing)'))


def _probe(live, base, state, report):
    """What the probe saw of the first page and a few screens."""
    script = live.sandbox.copy / '.eaos-probe.cjs'
    script.write_text(PROBE, encoding='utf-8')
    code, out, err = live.run(['node', str(script)], timeout=600, env={
        'BASE_URL': base, 'EAOS_STORAGE_STATE': str(state) if state.is_file() else '',
        'EAOS_ROUTES': json.dumps(routes(report))})
    return json.loads(out.strip().splitlines()[-1]) if code == 0 and out.strip() else {'status': 0, 'errors': [(out + err)[-800:]]}


def _failure(page, empty):
    """Why the page is no working app, '' when it is one."""
    bad = [o for o in [page, *(page.get('others') or [])] if not 200 <= o.get('status', 0) < 400]
    if signed_out(page): return 'the first page asks for a sign-in'
    if stuck(page):
        return ('every screen shows the same page, so something (a chooser, a gate) stands in front of the app. '
                'The page says:\n' + '\n'.join(l for l in (page.get('text') or '').splitlines() if l.strip())[:600])
    if bad: return f"{bad[0].get('path', '/')} answered {bad[0].get('status')}: {'; '.join(page.get('errors') or [])[:600]}"
    return empty


def verify(project, runtime, attempt, report=None, mode='lock'):
    """Run the draft: install (and, for the baseline, build), start, seed, open the first page and a few screens.
    {'ok', 'page', 'fixtures', 'failure'}"""
    from .live_run import LiveRun
    runtime = Path(runtime)
    live = LiveRun(project, runtime, 'S05', mode=mode)
    served, report = (report, None) if mode == 'baseline' else (None, report)    # the load opens the pages anonymously
    record = {'attempt': attempt, 'fixtures': {}}
    try:
        live.setup()
        base = live.start()
        from .runtime_baseline import refuse_a_page_server
        refuse_a_page_server(served, base)
        state = runtime / 'setup' / 'storage-state.json'
        if state.exists(): state.unlink()
        record['fixtures'] = dict(live.seed(base, state))
        record['seed_output'] = getattr(live, 'seed_output', '')
        page = record['page'] = _probe(live, base, state, report)
        names = (read_json(runtime / 'setup/detected.json').get('facts') or {}).get('env_names') or []
        empty = '' if mode == 'baseline' else empty_state(page, [n for n in names if n not in live.profile.get('env', {}) and n != 'NODE_ENV'])
        failure = _failure(page, empty)
        record['ok'] = not failure
        if failure: record['failure'] = failure
    except Exception as problem:            # a failed start is the evidence the assistant needs, not a crash
        record['ok'] = False
        record['failure'] = f'{type(problem).__name__}: {problem}'[-2500:]
    finally:
        if not record.get('ok') and record.get('seed_output') and record.get('failure'):
            record['failure'] += '\nThe seed script said:\n' + record['seed_output'][-1500:]
        live.stop()
        live.record(f"setup/{'baseline-' if mode == 'baseline' else ''}attempt-{attempt}.json")
    return record


# ---------------------------------------------------------------- 3. assist (what the assistant is told: eaos/live_assist.py)

def fixtures_needed(report):
    """The E2E_* names the lock's specs skip without."""
    names = set()
    for spec in (Path(report) / 'behavior-lock/playwright').glob('*.spec.ts') if report else []:
        names |= set(re.findall(r'needs_fixture: set (E2E_[A-Z0-9_]+)', spec.read_text(encoding='utf-8')))
    return sorted(names)


# ---------------------------------------------------------------- consent, and the whole setup

FLOW = (
    Stage('detect', description='Find, from the files alone, how the app installs, starts and builds, the environment '
                                'names it reads and the database it needs'),
    Stage('attempt', requires=('detect',),
          description=f'Start the app in the separate copy and open its first screens; when it does not answer, ask '
                      f'the assistant what to change and try again (at most {ATTEMPTS} attempts)'),
    Stage('baseline', requires=('attempt',), necessity=OPTIONAL,
          absent_when='the app has no production build, or it did not start in development',
          description='Build the production version of the app, start it from the build and open its first page, '
                      'for the speed test'),
)

def setup_baseline(project, runtime, detected, provider, say, report=None, attempts=3):
    """The production run the load baseline needs: built, started from the build, the first page answering, and the
    server routes of the code (`report`) served, not answered with the page. Marked in run.json -> baseline.verified,
    so the load test only runs on a production run that works; the assistant reads why an attempt failed."""
    runtime, record, refusal = Path(runtime), {'ok': False, 'failure': ''}, ''
    (runtime / 'setup').mkdir(parents=True, exist_ok=True)
    for attempt in range(1, attempts + 1):
        say(f'baseline-{attempt}')
        progress.step(f'attempt {attempt}', attempt - 1, attempts, 'running')
        record = verify(project, runtime, attempt, report, mode='baseline')
        progress.step(f'attempt {attempt}', attempt, attempts, 'ok' if record['ok'] else 'failed',
                      reason=(record.get('failure') or '')[:200], reason_code='' if record['ok'] else 'baseline_failed')
        if record['ok'] or provider is None: break
        refused = _ask(project, runtime, provider, detected, record['failure'], refusal, [], f'baseline-proposal-{attempt}', 'baseline')
        refusal = '; '.join(refused)
        if attempt == attempts:
            record = verify(project, runtime, attempt + 1, report, mode='baseline')
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
    {'ok', 'attempts', 'limitations', 'page'}. Written as it happens as the flow `setup` (FLOW)."""
    with progress.Flow(runtime, 'setup', FLOW):
        return _setup(project, Path(runtime), report, provider, say)


def _setup(project, runtime, report, provider, say):
    (runtime / 'setup').mkdir(parents=True, exist_ok=True)
    progress.begin('detect')
    detected = detect(project, report)
    if detected['profile'] is None:
        why = '; '.join(detected['limitations'])[:300]
        progress.end('detect', 'unavailable', why, 'no_app_profile')
        for name in ('attempt', 'baseline'): progress.skip(name, why, 'no_app_profile')
        return {'ok': False, 'attempts': 0, 'limitations': detected['limitations'], 'page': None}
    needs = fixtures_needed(report)
    kept = (read_json(runtime / 'run.json') or {}).get('baseline') or {}
    if kept.get('verified'): detected['profile']['baseline'] = kept     # the production run that worked, often the assistant's
    write_profile(runtime, detected['profile'])
    (runtime / 'setup/detected.json').write_text(json.dumps(detected, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    limitations = list(detected['limitations'])
    progress.begin('attempt')
    record, attempts, missing = _attempts(project, runtime, report, provider, say, detected, needs, limitations)
    ok = bool(record['ok'])
    if ok: progress.end('attempt')
    else: progress.end('attempt', 'failed', (record.get('failure') or 'the app did not answer')[:300],
                       'no_assistant' if provider is None else 'app_not_answering')
    _baseline(project, runtime, report, provider, say, detected, ok, limitations)
    if not ok and record.get('failure') and not any(record['failure'] in text for text in limitations):
        limitations.append('the app could not be made to answer: ' + record['failure'][:300])
    return _close(runtime, detected, ok, attempts, record, missing, limitations)


def _attempts(project, runtime, report, provider, say, detected, needs, limitations):
    """Verify the run, and while it fails ask the assistant for a safe change, at most ATTEMPTS times.
    (the last record, the attempts made, the fixtures still missing)."""
    refusal = ''
    for attempts in range(1, ATTEMPTS + 1):
        say(attempts)
        progress.step(f'attempt {attempts}', attempts - 1, ATTEMPTS, 'running')
        record = verify(project, runtime, attempts, report)
        known = {**json.loads((runtime / 'run.json').read_text())['env'], **record['fixtures']}
        missing = [name for name in needs if name not in known]
        failure = '' if record['ok'] and not missing else \
            record.get('failure') or 'the checks need fixture values: ' + ', '.join(missing)
        progress.step(f'attempt {attempts}', attempts, ATTEMPTS, 'failed' if failure else 'ok', reason=failure[:200],
                      reason_code='' if not failure else 'app_not_answering' if not record['ok'] else 'fixtures_missing')
        if not failure: break
        if provider is None:
            limitations.append('no AI assistant was available to work out: ' + (record.get('failure') or 'the fixtures ' + ', '.join(missing)))
            break
        refused = _ask(project, runtime, provider, detected, failure, refusal, needs, f'proposal-{attempts}')
        refusal = '; '.join(refused)
        if refused:
            limitations.append('the assistant proposed something unsafe, which was refused: ' + refused[0])
            progress.step(f'attempt {attempts}', attempts, ATTEMPTS, 'failed', reason=refused[0][:200], reason_code='proposal_refused')
    return record, attempts, missing


def _ask(project, runtime, provider, detected, failure, refusal, needs, name, mode='lock'):
    """Ask the assistant for a change, write it with what safe() refused to setup/<name>.json, and apply it when safe.
    The refusals, none when it was applied; the last refusal is told on the next ask."""
    if refusal: failure += f'. Your previous proposal was refused and not applied: {refusal}'
    answer, _ = provider.complete(assist_messages(project, runtime, detected, failure, needs, mode=mode), stage='setup')
    proposal = answer.get('result') or {}
    refused = safe(proposal)
    (runtime / f'setup/{name}.json').write_text(json.dumps({'proposal': proposal, 'refused': refused}, ensure_ascii=False, indent=1) + '\n',
                                               encoding='utf-8')
    if not refused: apply(runtime, proposal, mode=mode)
    return refused


def _baseline(project, runtime, report, provider, say, detected, ok, limitations):
    """The stage `baseline`: the production run, once the app answered in development and has a build."""
    if not ok:
        progress.skip('baseline', 'the app did not start in development, so its production build was not tried', 'app_not_answering')
    elif not (detected['profile'].get('baseline') or {}).get('build'):
        progress.skip('baseline', 'the app has no production build command', 'no_build')
    else:
        progress.begin('baseline')
        speed = setup_baseline(project, runtime, detected, provider, say, report)
        if speed['ok']:
            progress.end('baseline')
        else:
            limitations.append('speed cannot be measured: ' + speed['failure'][:300])
            progress.end('baseline', 'failed', speed['failure'][:300], 'baseline_failed')


def _close(runtime, detected, ok, attempts, record, missing, limitations):
    """Write the run's final limitations into run.json, and the setup's answer."""
    profile = json.loads((runtime / 'run.json').read_text(encoding='utf-8'))
    # Names the first draft left without a value may have one now.
    unset = [n for n in detected['facts']['env_names'] if n not in profile['env'] and n != 'NODE_ENV']
    limitations = [text for text in limitations if not text.startswith('no value was chosen for')]
    if unset and ok: limitations.append('run without a value for: ' + ', '.join(unset[:12]) + (' …' if len(unset) > 12 else ''))
    if missing: limitations.append('screens that need these values are not recorded: ' + ', '.join(missing))
    profile['limitations'] = sorted(set(limitations))
    write_profile(runtime, profile)
    return {'ok': ok, 'attempts': attempts, 'limitations': profile['limitations'], 'page': record.get('page')}

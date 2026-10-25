"""The first pass of a run's setup for a Python web app (setup_detect.py does JavaScript ones): Django, Flask, FastAPI
and Streamlit, found from the project's files alone; how it installs, prepares its database, starts and is checked,
and the environment names its code reads. Deterministic: a Python app runs without an assistant (the corpus' four
Python apps never started without one, M5.1)."""
import re
from pathlib import Path

PY_ENV = re.compile(r'''os\.(?:environ\.get|getenv)\(\s*['"]([A-Z][A-Z0-9_]{2,})['"]|os\.environ\[\s*['"]([A-Z][A-Z0-9_]{2,})['"]\s*\]''')
SKIP = {'.venv', 'venv', 'env', 'node_modules', '.git', 'tests', 'test', 'site-packages', '__pycache__', 'migrations'}
MARKERS = ('manage.py', 'requirements.txt', 'pyproject.toml', 'setup.py')
FIRST = ('streamlit_app.py', 'app.py', 'main.py', 'wsgi.py', 'run.py', 'server.py', 'Home.py')    # tried before the others
INIT_DB = re.compile(r'''command\(\s*['"]((?:init|create)[-_]?db)['"]''')


def folder(project):
    """The folder of the Python app: the project's root, or the first folder beside it with a Python project's file."""
    project = Path(project)
    if any((project / name).is_file() for name in MARKERS): return '.'
    for path in sorted(project.glob('*/')):
        if path.name not in SKIP and any((path / name).is_file() for name in MARKERS): return path.name
    return None


def _read(path):
    return path.read_text(encoding='utf-8', errors='replace') if path.is_file() else ''


def _requirements(app):
    """The lowercase text that names the app's dependencies: its requirements files and pyproject.toml."""
    return '\n'.join(_read(path) for path in [*sorted(app.glob('requirements*.txt')), app / 'pyproject.toml', app / 'setup.py']).lower()


def _modules(app):
    """(module name, text) of the app's Python files outside tests and environments, the usual entry points first."""
    paths = [p for p in app.rglob('*.py') if not SKIP & set(p.relative_to(app).parts[:-1]) and len(p.relative_to(app).parts) <= 4][:2000]
    paths.sort(key=lambda p: (len(p.relative_to(app).parts), p.name not in FIRST, FIRST.index(p.name) if p.name in FIRST else 0, str(p)))
    for path in paths:
        parts = path.relative_to(app).with_suffix('').parts
        yield '.'.join(parts[:-1] if parts[-1] == '__init__' else parts), _read(path)


def _flask_app(app, modules):
    """What `flask --app` names: FLASK_APP of .flaskenv or an example env file, else the first module that makes the app."""
    for name in ('.flaskenv', '.env.example', '.env.sample'):
        declared = re.search(r'^\s*FLASK_APP\s*=\s*["\']?([\w.:()]+)', _read(app / name), re.M)
        if declared: return declared[1].removesuffix('.py')
    return next((name for name, text in modules if re.search(r'\bFlask\(|\bdef create_app\(', text)), None)


def _asgi(modules):
    """`module:variable` of the first FastAPI (or Starlette) app the code makes."""
    for name, text in modules:
        made = re.search(r'^(\w+)\s*=\s*(?:FastAPI|Starlette)\(', text, re.M)
        if made: return f'{name}:{made[1]}'
    return None


def _kind(app, needs, modules):
    """(framework, what it starts) of the app, or (None, None)."""
    if (app / 'manage.py').is_file(): return 'django', 'manage.py'
    entry = _streamlit(needs, modules)
    if entry: return 'streamlit', entry
    if 'flask' in needs:
        target = _flask_app(app, list(modules))
        if target: return 'flask', target
    if re.search(r'\b(fastapi|starlette)\b', needs):
        target = _asgi(modules)
        if target: return 'fastapi', target
    return None, None


def _streamlit(needs, modules):
    """The file `streamlit run` starts: the first top-level module that imports Streamlit, or None."""
    if 'streamlit' not in needs: return None
    entry = next((name for name, text in modules if '.' not in name and re.search(r'^\s*import streamlit', text, re.M)), None)
    return entry + '.py' if entry else None


def start(kind, target, port):
    port = str(port)
    return {'django': ['python', 'manage.py', 'runserver', f'127.0.0.1:{port}', '--noreload'],
            'flask': ['python', '-m', 'flask', '--app', target, 'run', '--host', '127.0.0.1', '--port', port, '--no-reload'],
            'fastapi': ['python', '-m', 'uvicorn', target, '--host', '127.0.0.1', '--port', port],
            'streamlit': ['python', '-m', 'streamlit', 'run', target, '--server.port', port, '--server.address', '127.0.0.1',
                          '--server.headless', 'true', '--browser.gatherUsageStats', 'false']}[kind]


def install(app):
    if (app / 'requirements.txt').is_file(): return [['python', '-m', 'pip', 'install', '-q', '--disable-pip-version-check', '-r', 'requirements.txt']]
    if (app / 'pyproject.toml').is_file() or (app / 'setup.py').is_file():
        return [['python', '-m', 'pip', 'install', '-q', '--disable-pip-version-check', '-e', '.']]
    return [['true']]


def prepare(kind, target, app, needs, modules):
    """The commands that give the run's empty database the app's tables: Django's migrations, Flask-Migrate's, a Flask
    `init-db` command, or Alembic's."""
    if kind == 'django': return [['python', 'manage.py', 'migrate', '--noinput']]
    if kind == 'flask': return _flask_tables(target, app, needs, modules)
    if (app / 'alembic.ini').is_file() and 'alembic' in needs: return [['python', '-m', 'alembic', 'upgrade', 'head']]
    return []


def _flask_tables(target, app, needs, modules):
    """Flask-Migrate's migrations, else the app's own `init-db` command."""
    if (app / 'migrations/alembic.ini').is_file() and 'flask-migrate' in needs: return [['python', '-m', 'flask', '--app', target, 'db', 'upgrade']]
    command = next((found[1] for _, text in modules for found in [INIT_DB.search(text)] if found), None)
    return [['python', '-m', 'flask', '--app', target, command]] if command else []


def environment_names(app, modules):
    """{name: ''} of every environment name the code reads, after those of the example env files."""
    from .setup_detect import _example_names
    names = _example_names(app, '.')
    for _, text in modules:
        for found in PY_ENV.finditer(text): names.setdefault(found[1] or found[2], '')
    return names


def detect(project):
    """{'profile', 'facts', 'limitations'} of a Python web app (setup_detect.detect's form), or None when the project
    holds none EAOS knows how to start."""
    from .setup_detect import environment_values, free_port
    where = folder(project)
    if where is None: return None
    app = Path(project) / where
    needs, modules = _requirements(app), list(_modules(app))
    kind, target = _kind(app, needs, modules)
    if kind is None: return None
    port, names = free_port(), environment_names(app, modules)
    env, unset = environment_values(names, port, None)
    profile = {'schema_version': 1, 'app': where, 'install': install(app), 'start': start(kind, target, port), 'port': port,
               'health': '/', 'start_timeout': 180, 'env': {'PYTHONUNBUFFERED': '1', **env},
               'checks': [['python', '-m', 'pytest', '-q']] if re.search(r'^pytest\b', needs, re.M) else []}
    commands = prepare(kind, target, app, needs, modules)
    if commands: profile['prepare'] = commands
    limitations = ['no value was chosen for: ' + ', '.join(unset[:12])] if unset else []
    return {'profile': profile, 'facts': {'folder': where, 'manager': 'pip', 'framework': kind, 'database': None,
                                          'env_names': sorted(names)}, 'limitations': limitations}

"""The first pass of a run's setup for a PHP web app (live/app/detect.py does JavaScript ones, detect_python.py Python
ones): its folder served by PHP's own server, its Composer packages installed, its PHPUnit suite as its check, from the
project's files alone."""
import json
from pathlib import Path

# The folders a PHP app serves from, the commonest first (public/ of Laravel and Symfony, web/, p/).
SERVED = ('public', 'web', 'p', 'htdocs', '.')
# PHP's own server answers one request at a time unless told to fork workers, so a crawl would go one page at a time.
WORKERS = '4'


def served(project):
    """The folder holding the app's front page, index.php; None for no PHP app."""
    return next((name for name in SERVED if (Path(project) / name / 'index.php').is_file()), None)


def install(project):
    """Composer's install of the locked packages, or nothing without a composer.json."""
    return [['composer', 'install', '--no-interaction', '--no-progress']] if (Path(project) / 'composer.json').is_file() else [['true']]


def checks(project):
    """The project's PHPUnit suite when it declares PHPUnit and configures it; else none."""
    root = Path(project)
    try: dev = json.loads((root / 'composer.json').read_text(encoding='utf-8')).get('require-dev') or {}
    except (OSError, ValueError, AttributeError): return []
    configured = any((root / name).is_file() for name in ('phpunit.xml', 'phpunit.xml.dist'))
    return [['php', 'vendor/bin/phpunit']] if 'phpunit/phpunit' in dev and configured else []


def detect(project):
    """{'profile', 'facts', 'limitations'} of a PHP web app, or None when the project serves no index.php."""
    from ...core.system.local_db import free_port
    folder = served(project)
    if folder is None or not (Path(project) / 'composer.json').is_file() and folder == '.': return None
    port = free_port()
    profile = {'schema_version': 1, 'app': '.', 'install': install(project), 'start': ['php', '-S', f'127.0.0.1:{port}', '-t', folder],
               'port': port, 'health': '/', 'start_timeout': 180, 'env': {'PHP_CLI_SERVER_WORKERS': WORKERS}, 'checks': checks(project)}
    return {'profile': profile, 'facts': {'folder': '.', 'manager': 'composer', 'framework': 'php', 'database': None, 'env_names': [],
                                          'reason': f'a PHP app: {folder}/index.php served by PHP\'s own server'},
            'limitations': []}

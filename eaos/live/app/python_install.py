"""How a Python project installs in a run's own environment, its test requirements with it: read by the web app's
setup (detect_python.py) and by a project with no interface (own_checks.py), from its files alone."""
import re

from ...core.system.files import tomllib

MANIFESTS = ('requirements.txt', 'pyproject.toml', 'setup.py')


def _read(path):
    return path.read_text(encoding='utf-8', errors='replace') if path.is_file() else ''


def install(app):
    pip = ['python', '-m', 'pip', 'install', '-q', '--disable-pip-version-check']
    extra = test_extra(app)
    steps = [pip + ['-r', 'requirements.txt']] if (app / 'requirements.txt').is_file() else []
    if (not steps or extra) and ((app / 'pyproject.toml').is_file() or (app / 'setup.py').is_file()):
        steps.append(pip + ['-e', f'.[{extra}]' if extra else '.'])      # the test extra beside the requirements too
    group = [] if extra else test_group(app)
    if group: steps.append(pip + group)
    return steps or [['true']]


def test_extra(app):
    """The pyproject.toml extra that brings pytest (`[project.optional-dependencies] test = ["pytest"]`), or None: its
    tests need it installed, or every gate would say its tests passed while none had run."""
    try: extras = tomllib.loads(_read(app / 'pyproject.toml')).get('project', {}).get('optional-dependencies') or {}
    except (tomllib.TOMLDecodeError, AttributeError): return None
    if not isinstance(extras, dict): return None
    return next((name for name, deps in extras.items()
                 if any(re.match(r'pytest\b', str(d).strip().lower()) for d in deps)), None)


def test_group(app):
    """The requirements of the pyproject.toml dependency group that brings pytest (`[dependency-groups] tests =
    ["pytest", ...]`, its included groups read in), or []: pip 24, the one a run's environment has, installs no group
    by name, so a library's tests would run without pytest."""
    try: groups = tomllib.loads(_read(app / 'pyproject.toml')).get('dependency-groups') or {}
    except (tomllib.TOMLDecodeError, AttributeError): return []
    if not isinstance(groups, dict): return []

    def read(name, seen):
        rows = []
        for row in groups.get(name) or []:
            if isinstance(row, str): rows.append(row)
            elif isinstance(row, dict) and row.get('include-group') not in seen:
                rows += read(row['include-group'], seen | {name})
        return rows
    found = (read(name, {name}) for name in groups)
    return next((rows for rows in found if any(re.match(r'pytest\b', row.strip().lower()) for row in rows)), [])

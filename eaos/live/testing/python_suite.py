"""Which command runs a Python project's own tests from its root (verify.py `python_tests`, read by the coverage stage
and every batch gate): pytest when the project configures it; else unittest on tests/, on the folders of it that are
packages too; else the root's tests.py and test_*.py modules by name. A test under a folder unittest cannot enter, or
under a dependency's folder (node_modules, an environment), is none of the project's. M9.5: the move gate proved
nothing of a small app keeping its tests at its root; M9.3: EAOS's own check found no suite once its tests were by
layer."""
import sys
from pathlib import Path

# The interpreter running EAOS is the one sure to exist with the runtime extra: a bare `python` on PATH lost all
# execution evidence where only `python3` ships.
INTERPRETER = sys.executable or 'python3'
DEFAULT_COMMANDS = [[INTERPRETER, '-m', 'pytest', '-q'], [INTERPRETER, '-m', 'unittest', 'discover', '-s', 'tests']]
NOT_THE_PROJECTS = {'node_modules', '.venv', 'venv', 'env', 'site-packages', '__pycache__'}


def command(root):
    """The command, or None when the project keeps no tests EAOS can run."""
    root = Path(root)
    folder, modules = _in_tests(root), _at_root(root)
    if not (folder or modules): return None
    if _pytest_configured(root): return DEFAULT_COMMANDS[0]
    return DEFAULT_COMMANDS[1] if folder else [INTERPRETER, '-m', 'unittest', *modules]


def _in_tests(root):
    """True when unittest's discovery of tests/ finds a test_*.py: in tests/ itself, or in a package under it."""
    tests = root / 'tests'
    for found in tests.rglob('test_*.py'):
        between = found.relative_to(tests).parts[:-1]
        if NOT_THE_PROJECTS & set(between) or any(part.startswith('.') for part in between): continue
        if all((tests.joinpath(*between[:depth]) / '__init__.py').is_file() for depth in range(1, len(between) + 1)): return True
    return False


def _at_root(root):
    """The root's test modules by name (tests, test_x): named, so nothing else of the project is imported to find them."""
    return [p.stem for p in sorted([*root.glob('test_*.py'), *root.glob('tests.py')]) if p.is_file()]


def _pytest_configured(root):
    toml = root / 'pyproject.toml'
    return any((root / name).is_file() for name in ('pytest.ini', 'conftest.py')) or \
        (toml.is_file() and '[tool.pytest' in toml.read_text(encoding='utf-8', errors='replace'))

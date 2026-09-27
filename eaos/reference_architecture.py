"""Reference architectures: for each kind of project, the layers it should have and the infrastructure it needs.

The catalogue is data (eaos/rules/reference-architectures.json): per type, named layers with their
responsibility, the layers each may depend on, and the path patterns that place today's files in them;
and an infrastructure baseline whose every item says why it matters and how success is measured.

choose() picks the type from the project's own files (package.json, pyproject.toml, requirements*.txt, and
the names of a few files), in catalogue order; it never runs anything. locate() also finds an application kept
in one conventional folder (app/, web/, client/, frontend/), and rooted() moves the layer paths under it. layer_of() places a path in the
layer whose matching pattern is the most specific, so src/components/ui/button.tsx is ui, not features.
"""
import json
import re
from fnmatch import fnmatch
from pathlib import Path

CATALOGUE = Path(__file__).resolve().parent / 'rules/reference-architectures.json'
REQUIREMENT = re.compile(r'^\s*([A-Za-z0-9][A-Za-z0-9._-]*)')


def catalogue():
    return json.loads(CATALOGUE.read_text(encoding='utf-8'))


def by_id(identifier):
    return next(t for t in catalogue()['types'] if t['id'] == identifier)


def _package_names(root):
    try: data = json.loads((root / 'package.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): return set()
    return set(data.get('dependencies') or {}) | set(data.get('devDependencies') or {})


def _python_names(root):
    names = []
    pyproject = root / 'pyproject.toml'
    if pyproject.is_file():
        import tomllib
        try: data = tomllib.loads(pyproject.read_text(encoding='utf-8'))
        except (tomllib.TOMLDecodeError, UnicodeDecodeError): data = {}
        project = data.get('project') or {}
        names += project.get('dependencies') or []
        for group in (project.get('optional-dependencies') or {}).values(): names += group
    for path in root.glob('requirements*.txt'):
        names += path.read_text(encoding='utf-8', errors='replace').splitlines()
    return {m.group(1).lower().replace('_', '-') for line in names for m in [REQUIREMENT.match(line)] if m}


SOURCE_SUFFIXES = {'.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.go', '.java', '.rb', '.php', '.cs', '.kt', '.swift', '.rs'}


def _workspace(root):
    """A workspace monorepo: pnpm-workspace.yaml, turbo.json, or package.json workspaces."""
    if (root / 'pnpm-workspace.yaml').is_file() or (root / 'turbo.json').is_file(): return True
    try: return bool(json.loads((root / 'package.json').read_text(encoding='utf-8')).get('workspaces'))
    except (OSError, ValueError): return False


TEST_PARTS = {'tests', 'test', '__tests__', 'e2e', 'fixtures'}


def _python_program(root):
    """Python is the program, not a helper: a .py file outside test folders, and no package.json beside it
    (a Node project with one Python end-to-end test is not a Python command-line tool)."""
    if (root / 'package.json').is_file(): return False
    return any(not set(path.relative_to(root).parts[:-1]) & TEST_PARTS for path in root.glob('**/*.py'))


def matches(rule, root):
    packages, python = _package_names(root), _python_names(root)
    # A server kept in its own folder declares its database driver in its own package.json.
    for folder in rule.get('dirs_any') or ():
        packages |= _package_names(root / folder)
    if rule.get('package_json_all') and not set(rule['package_json_all']) <= packages: return False
    if rule.get('package_json_any') and not set(rule['package_json_any']) & packages: return False
    if set(rule.get('package_json_none') or ()) & packages: return False
    has_python_rule = 'python_deps_any' in rule or 'files_any' in rule
    if has_python_rule:
        by_deps = bool(set(rule.get('python_deps_any') or ()) & python)
        by_files = any(list(root.glob(pattern)) for pattern in rule.get('files_any') or ())
        if not (by_deps or by_files): return False
    if rule.get('python_files') and not _python_program(root): return False
    if rule.get('dirs_any') and not any((root / name).is_dir() for name in rule['dirs_any']): return False
    if rule.get('workspace') and not _workspace(root): return False
    # The last type of the catalogue: any project with a source file gets a target, read from its folder names.
    if rule.get('any_source') and not any(p.suffix in SOURCE_SUFFIXES for p in root.rglob('*') if 'node_modules' not in p.parts): return False
    return bool(rule)


# Where an application may sit inside its repository: at the root, or in one conventional folder
# (chief-ops keeps its package.json in app/). The first folder a catalogue type matches is the app root.
APP_ROOTS = ('', 'app', 'web', 'client', 'frontend', 'src/app')


def locate(project_dir):
    """(type id, app root prefix such as 'app/' or '') of the first type that fits, or (None, '')."""
    root = Path(project_dir)
    types = catalogue()['types']
    # Every specific type in every conventional folder first; the fallback (any_source) only when none fits,
    # or an app kept in app/ would be read as a generic project from the repository root.
    for fallback in (False, True):
        for folder in APP_ROOTS:
            base = root / folder if folder else root
            if not base.is_dir(): continue
            found = next((t['id'] for t in types if bool(t['detect'].get('any_source')) == fallback and matches(t['detect'], base)), None)
            if found: return found, f'{folder}/' if folder else ''
    return None, ''


def choose(project_dir):
    """The id of the reference type that fits the project, read from its own files; None when none fits."""
    return locate(project_dir)[0]


def rooted(reference, prefix):
    """The reference with every layer path under the app root, so repository paths place directly."""
    if not prefix: return reference
    import copy
    reference = copy.deepcopy(reference)
    for layer in reference['layers']:
        layer['paths'] = [prefix + pattern if not pattern.startswith('**') else pattern for pattern in layer.get('paths') or ()]
    reference['root'] = prefix
    return reference


def layer_of(path, reference):
    """(layer name, pattern) placing a path in a reference type's layers; the most specific pattern wins."""
    best = None
    for layer in reference['layers']:
        for pattern in layer.get('paths') or ():
            if fnmatch(path, pattern) or (pattern.endswith('/**') and path.startswith(pattern[:-3] + '/')):
                weight = len(pattern.replace('*', ''))
                if best is None or weight > best[2]: best = (layer['name'], pattern, weight)
    return (best[0], best[1]) if best else (None, None)

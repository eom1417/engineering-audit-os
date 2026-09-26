"""Reference architectures: for each kind of project, the layers it should have and the infrastructure it needs.

The catalogue is data (eaos/rules/reference-architectures.json): per type, named layers with their
responsibility, the layers each may depend on, and the path patterns that place today's files in them;
and an infrastructure baseline whose every item says why it matters and how success is measured.

choose() picks the type from the project's own files (package.json, pyproject.toml, requirements*.txt, and
the names of a few files), in catalogue order; it never runs anything. layer_of() places a path in the
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


def matches(rule, root):
    packages, python = _package_names(root), _python_names(root)
    if rule.get('package_json_all') and not set(rule['package_json_all']) <= packages: return False
    if rule.get('package_json_any') and not set(rule['package_json_any']) & packages: return False
    if set(rule.get('package_json_none') or ()) & packages: return False
    has_python_rule = 'python_deps_any' in rule or 'files_any' in rule
    if has_python_rule:
        by_deps = bool(set(rule.get('python_deps_any') or ()) & python)
        by_files = any(list(root.glob(pattern)) for pattern in rule.get('files_any') or ())
        if not (by_deps or by_files): return False
    if rule.get('python_files') and not any(root.glob('**/*.py')): return False
    return bool(rule)


def choose(project_dir):
    """The id of the reference type that fits the project, read from its own files; None when none fits."""
    root = Path(project_dir)
    return next((t['id'] for t in catalogue()['types'] if matches(t['detect'], root)), None)


def layer_of(path, reference):
    """(layer name, pattern) placing a path in a reference type's layers; the most specific pattern wins."""
    best = None
    for layer in reference['layers']:
        for pattern in layer.get('paths') or ():
            if fnmatch(path, pattern) or (pattern.endswith('/**') and path.startswith(pattern[:-3] + '/')):
                weight = len(pattern.replace('*', ''))
                if best is None or weight > best[2]: best = (layer['name'], pattern, weight)
    return (best[0], best[1]) if best else (None, None)

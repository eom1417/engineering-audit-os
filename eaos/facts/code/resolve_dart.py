"""Dart's imports to files: `package:<name>/<path>` is `<path>` under the `lib/` of the package `pubspec.yaml` names
`<name>`, any other URI is relative to the importing file (`'store.dart'`, `'../api/core.dart'`), and `dart:` is the
SDK. Reading only URIs that start with a dot would leave a Flutter app's graph with almost no edge."""
import posixpath
import re
from pathlib import PurePosixPath

NAME = re.compile(r'^name:\s*["\']?([A-Za-z0-9_]+)', re.M)


def packages(source, known):
    """{package name: its folder ('' at the root)} of every pubspec.yaml in a folder holding a known Dart file or
    above it."""
    folders = {''}
    for path in known:
        if path.endswith('.dart'):
            folders |= {parent.as_posix() for parent in PurePosixPath(path).parents if parent.as_posix() != '.'}
    found = {}
    for folder in sorted(folders, key=len):
        named = NAME.search(source.text(posixpath.join(folder, 'pubspec.yaml')) or '')
        if named: found.setdefault(named.group(1), folder)
    return found


def candidates(importer, module, context):
    """The file a Dart import names, as a one-item list; [] for the SDK or a package outside the project."""
    if module.startswith('dart:'): return []
    if module.startswith('package:'):
        if 'dart_packages' not in context: context['dart_packages'] = packages(context['source'], context['known'])
        name, _, rest = module[len('package:'):].partition('/')
        folder = context['dart_packages'].get(name)
        return [] if folder is None else [posixpath.join(folder, 'lib', rest)]
    if ':' in module: return []
    return [posixpath.normpath(posixpath.join(posixpath.dirname(importer), module))]

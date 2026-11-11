"""The prefixes Express-style mounts give a file's routes: `.use('/api', router)` (or Hono's `.route('/api', router)`),
on `app`, a router variable or a `Router()` chain, followed to the file the router is imported from.

A mount is read as (owner, prefix, names): `const api = Router().use(tags)` makes `api` the owner of an unprefixed
mount of `tags`; `export default Router().use('/api', api)` mounts the local `api` under /api. A name imported from
another file (default or named, relative or through an `@/` alias) mounts that whole file. Prefixes compose along the
chain, a cycle ends the walk, and a file no one mounts keeps its routes as written. Not a JavaScript interpreter: a
router passed through a function, or a prefix built at runtime, is not followed.
"""
import re
from types import SimpleNamespace

from ..code.resolve import js_aliases, js_candidates
from .http_access import IMPORT

MOUNT = re.compile(r'''\.(?:use|route)\(\s*(?:(?P<quote>['"`])(?P<prefix>[^'"`]*)(?P=quote)\s*,\s*)?'''
                   r'''(?P<names>[A-Za-z_$][\w$]*(?:\s*,\s*[A-Za-z_$][\w$]*)*)\s*\)''')
REQUIRE = re.compile(r'''\b(?:const|let|var)\s+(?:([A-Za-z_$][\w$]*)|\{([^}]*)\})\s*=\s*require\(\s*['"]([^'"]+)['"]\s*\)''')
HEAD = re.compile(r'''\s*(?:(?:export\s+)?(?:const|let|var)\s+(?P<var>[\w$]+)\s*=|(?P<receiver>[\w$]+)\s*\.)''')
ROOT = '<file>'


def prepare(texts):
    """{file: {owner: [prefixes]}} for each file some mount reaches, ROOT holding the prefixes of the file itself."""
    aliases = js_aliases(SimpleNamespace(text=texts.get), texts)
    graph = {rel: _mounts(rel, text, texts, aliases) for rel, text in texts.items() if MOUNT.search(text)}
    walk, out = _Walk(graph), {}
    for rel, owners in sorted(_owners(graph).items()):
        prefixes = {owner: sorted(walk.prefixes(rel, owner, frozenset())) for owner in owners}
        if any(value != [''] for value in prefixes.values()): out[rel] = prefixes
    return out


def _owners(graph):
    """{file: the routers it names in a mount, and ROOT}, for each file that mounts or is mounted."""
    owners = {rel: {ROOT} for rel in graph}
    for rel, mounts in graph.items():
        for owner, _prefix, target in mounts:
            owners[rel].add(owner)
            target_rel, name = target if isinstance(target, tuple) else (target, ROOT)
            owners.setdefault(target_rel, {ROOT}).add(name)
    return owners


def prefixes_of(prepared, owner):
    """The prefixes a route declared on `owner` in this file is served under: [''] when nothing mounts it."""
    return (prepared or {}).get(owner) or (prepared or {}).get(ROOT) or ['']


def join(prefix, route):
    if not prefix: return route
    return (prefix.rstrip('/') + '/' + route.lstrip('/')).rstrip('/') or '/'


def _mounts(rel, text, texts, aliases):
    """[(owner, prefix, target)]: target is a file (an imported name) or (rel, local name)."""
    imports = _imports(rel, text, texts, aliases)
    out = []
    for match in MOUNT.finditer(text):
        owner = _owner(text, match.start())
        for name in re.split(r'\s*,\s*', match.group('names')):
            out.append((owner, match.group('prefix') or '', imports.get(name) or (rel, name)))
    return out


def _imports(rel, text, texts, aliases):
    """{local name: the file it is imported from}, for the imports that resolve to a file of the project."""
    found = {}
    for default, listed, spec in IMPORT.findall(text) + REQUIRE.findall(text):
        target = next((c for c in js_candidates(rel, spec, aliases) if c in texts), None)
        if not target: continue
        names = [default] + [part.split(' as ')[-1].split(':')[-1].strip() for part in listed.split(',')]
        found.update({name: target for name in names if name})
    return found


def _owner(text, offset):
    """The router a `.use(` belongs to: the variable its statement declares, else the receiver it is called on, else
    the file itself (`export default Router().use(...)`). A chain continues over lines starting with `.`."""
    start = text.rfind('\n', 0, offset) + 1
    while start and text[start:offset + 1].lstrip().startswith('.'): start = text.rfind('\n', 0, start - 1) + 1
    statement = text[start:offset + 1].rsplit(';', 1)[-1]
    head = HEAD.match(statement)
    return (head.group('var') or head.group('receiver')) if head else ROOT


class _Walk:
    """Composes prefixes up the mount graph; a path that comes back to a router it passed ends there."""

    def __init__(self, graph):
        self.parents = {}
        for rel, mounts in graph.items():
            for owner, prefix, target in mounts:
                key = target if isinstance(target, tuple) else (target, ROOT)
                self.parents.setdefault(key, []).append(((rel, owner), prefix))

    def prefixes(self, rel, owner, seen):
        """The full prefixes of `owner` in `rel`: through the local mounts of it, then those of the file."""
        key = (rel, owner)
        if key in seen: return set()
        parents = self.parents.get(key) or ([] if owner == ROOT else [((rel, ROOT), '')])
        found = set()
        for (parent_rel, parent_owner), prefix in parents:
            found |= {join(above, prefix) for above in self.prefixes(parent_rel, parent_owner, seen | {key})}
        return found or {''}  # a router no one mounts, or a cycle cut here, is served where it is declared

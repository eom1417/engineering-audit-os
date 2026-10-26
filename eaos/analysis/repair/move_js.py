"""JavaScript and TypeScript's part of a move (moves.py): every import, export-from, require, dynamic import and test
mock (`vi.mock`, `jest.mock`) whose specifier names a moved file, or that a moved file writes, spelled again for the new
places in the form it was written: relative stays relative and an alias (`@/`) stays an alias while the file is still
under its folder; no extension, a folder's index, or the `.js` a TypeScript file writes for its `.ts`, kept as they were.
A package name (`react`) is never touched."""
import posixpath
import re
from pathlib import PurePosixPath

from ...facts.code.resolve import JS_SUFFIXES, js_aliases, js_candidates, js_directory

SPECIFIER = re.compile(r'''(?:\bfrom|\bimport|\brequire\s*\(|\bimport\s*\(|\.(?:mock|doMock|unmock|requireActual|importActual)\s*\()'''
                       r'''\s*(['"])([^'"\n]+)\1''')


def aliases(read, known):
    """The project's path aliases (tsconfig and jsconfig paths, vite's alias, `@/` for src/), as the resolver reads them."""
    class Reader:
        def text(self, path): return read(path)
    return js_aliases(Reader(), known)


def spans(path, text, moves, aliased=()):
    """[(start, end, new specifier)] offsets in `text`, the file at `path` before the move."""
    out = []
    for match in SPECIFIER.finditer(text):
        spec = match.group(2)
        new = _respelled(path, spec, moves, aliased)
        if new and new != spec: out.append((match.start(2), match.end(2), new))
    return out


def _respelled(importer, spec, moves, aliased):
    """The specifier again when it or its importer moved; None when it names a package or a file not in the project."""
    plain, query = (spec.split('?', 1) + [''])[:2]
    target = next((c for c in js_candidates(importer, plain, aliased) if c in moves.known), None)
    if target is None or not moves.moved(importer, target): return None
    written = _written_base(importer, plain, aliased, target)
    if written is None: return None
    base = _new_base(target, moves.new(target), written)
    new = _as_alias(plain, base, aliased) if not plain.startswith('.') else None
    new = new or _relative(moves.new(importer), base)
    return new + ('?' + query if query else '')


def _written_base(importer, spec, aliased, target):
    """What the specifier points at as a path (before any extension or index the loader adds), or None."""
    if spec.startswith('.'): return js_directory(importer, spec)
    for prefix, folders in aliased:
        if spec == prefix.rstrip('/') or spec.startswith(prefix):
            found = _alias_base(spec[len(prefix):], folders, target)
            if found: return found
    return None


def _alias_base(rest, folders, target):
    """The folder of an alias that holds `target`, joined to the rest of the specifier, or None."""
    for folder in folders:
        base = (folder + rest).strip('/') if folder.endswith('/') or not rest else f'{folder}/{rest}'.strip('/')
        if target == base or target.startswith((base + '.', base + '/')): return base
    return None


def _new_base(old, new, written):
    """The new file written as the old one was: with its extension, without it, as its folder, or as the `.js` of a `.ts`."""
    if old == written: return new
    rest = old[len(written):]
    if rest.startswith('/'):                                   # a folder's index
        return posixpath.dirname(new) if PurePosixPath(new).name == PurePosixPath(old).name else _stem(new)
    if rest in JS_SUFFIXES: return _stem(new)                  # no extension
    written_suffix = PurePosixPath(written).suffix              # ./env.js naming ./env.ts
    return _stem(new) + written_suffix if written_suffix else _stem(new)


def _stem(path):
    suffix = PurePosixPath(path).suffix
    return path[:-len(suffix)] if suffix else path


def _as_alias(spec, base, aliased):
    """`base` under the alias the specifier was written with, while it is still under that alias's folder."""
    for prefix, folders in aliased:
        if spec != prefix.rstrip('/') and not spec.startswith(prefix): continue
        for folder in folders:
            root = folder.rstrip('/')
            if base == root or base.startswith(root + '/'): return prefix + base[len(root):].lstrip('/')
    return None


def _relative(importer, base):
    rel = posixpath.relpath(base, posixpath.dirname(importer) or '.')
    return rel if rel.startswith('.') else './' + rel

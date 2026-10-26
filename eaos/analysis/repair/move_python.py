"""Python's part of a move (moves.py): every import that names a moved module, or that a moved file writes, spelled
again for the new places, in the style it was written (relative stays relative), with the names it binds unchanged
(`from pkg import pipeline_run` becomes `from pkg.pipeline import run as pipeline_run`); and every dotted name a string
writes (`mock.patch('pkg.mod.name')`). Each rewrite is a span of the file's text; nothing else is touched.

A move Python cannot express (an import found through a folder the moved file leaves) raises Unmovable."""
import ast
import re
from pathlib import PurePosixPath

NEWLINE = re.compile(r'\r\n|\r|\n')      # Python's own line ends: a form feed or \x1c is not one


class Unmovable(ValueError):
    """A move this tool cannot make without changing what the code means: refused, with its reason."""


def dotted(path):
    """The module path parts of a file: a/b/c.py -> (a, b, c); a/b/__init__.py -> (a, b)."""
    parts = PurePosixPath(path).with_suffix('').parts
    return parts[:-1] if parts and parts[-1] == '__init__' else parts


def resolve(importer, module, level, known, roots=()):
    """(the file a module names, the folder its absolute name is read from, None when relative), or None (outside).
    An absolute name is read from the root, then each of `roots` (src/), then the importer's own folders."""
    parts = tuple(module.split('.')) if module else ()
    if level:
        base = PurePosixPath(importer).parent
        for _ in range(level - 1): base = base.parent
        return _found(base.joinpath(*parts).as_posix(), known, None)
    folders = [p.as_posix() + '/' for p in PurePosixPath(importer).parents if p.as_posix() != '.']
    for prefix in dict.fromkeys(['', *(r for r in roots if r), *folders]):
        hit = _found(prefix + '/'.join(parts), known, prefix)
        if hit: return hit
    return None


def _found(stem, known, prefix):
    stem = '' if stem == '.' else stem
    for path in ((stem + '.py') if stem else None, (stem + '/__init__.py') if stem else '__init__.py'):
        if path in known: return path, prefix
    return None


def spell(importer, target_parts, prefix, roots=()):
    """How `importer` names the module `target_parts`: relative (prefix None) or absolute from `prefix`, one of the
    source `roots` (src/: on the path for every importer) or a folder of the importer's own (on its path only there)."""
    if prefix is None:
        package = PurePosixPath(importer).parent.parts
        common = 0
        while common < min(len(package), len(target_parts)) and package[common] == target_parts[common]: common += 1
        if not common:      # a relative import never climbs past the top package
            raise Unmovable(f'{importer} would import {".".join(target_parts) or "the root"} from outside its package')
        return '.' * (len(package) - common + 1) + '.'.join(target_parts[common:])
    root = tuple(PurePosixPath(prefix).parts)
    if target_parts[:len(root)] != root or not (prefix in roots or PurePosixPath(importer).as_posix().startswith(prefix)):
        raise Unmovable(f'{importer} finds {".".join(target_parts)} through the folder {prefix or "."}, which the move leaves')
    return '.'.join(target_parts[len(root):])


class Moves:
    """The files' places before and after: `mapping` {old: new} of the moved files, `known` every file before, `roots`
    the folders absolute names are read from ('' the repository's root; a src/ layout adds 'src/')."""

    def __init__(self, mapping, known, roots=('',)):
        self.mapping, self.known, self.roots = dict(mapping), set(known), tuple(roots)

    def new(self, path):
        return self.mapping.get(path, path)

    def moved(self, *paths):
        return any(p in self.mapping for p in paths if p)

    def dotted_names(self):
        """{old dotted name: new} of every moved module, read from each root both places are under (two parts at least:
        a lone name in a string is too likely something else)."""
        names = {}
        for old, new in self.mapping.items():
            if not old.endswith('.py'): continue
            for root in self.roots:
                if old.startswith(root) and new.startswith(root):
                    before, after = dotted(old[len(root):]), dotted(new[len(root):])
                    if len(before) > 1 and before != after: names['.'.join(before)] = '.'.join(after)
        return names


def spans(path, text, moves):
    """[(start, end, new text)] offsets in `text`, the file at `path` before the move."""
    try: tree = ast.parse(text)
    except SyntaxError: return []
    offsets = _line_offsets(text)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom): out += _from_import(path, node, text, offsets, moves)
        elif isinstance(node, ast.Import): out += _import(path, node, tree, offsets, moves)
    out += _dotted_strings(tree, text, offsets, moves, out)
    return out


def _line_offsets(text):
    """(where each line starts in `text`, each line): ast counts its columns in UTF-8 bytes of the line."""
    starts, lines, at = [0], [], 0
    for match in NEWLINE.finditer(text):
        lines.append(text[at:match.start()])
        at = match.end()
        starts.append(at)
    return starts, lines + [text[at:]]


def _point(offsets, line, column):
    """The character offset in the text of a line and a byte column (a line holding non-ASCII text moves them apart)."""
    starts, lines = offsets
    return starts[line - 1] + len(lines[line - 1].encode('utf-8')[:column].decode('utf-8', errors='ignore'))


def _span(node, offsets):
    return _point(offsets, node.lineno, node.col_offset), _point(offsets, node.end_lineno, node.end_col_offset)


def _from_import(path, node, text, offsets, moves):
    """The statement again when an import of it changes; [] when nothing it names moved."""
    module, level = node.module or '', node.level
    base = resolve(path, module, level, moves.known, moves.roots)
    groups, changed = {}, False
    for alias in node.names:
        child = resolve(path, f'{module}.{alias.name}' if module else alias.name, level, moves.known, moves.roots) if alias.name != '*' else None
        written, name, did = _submodule(path, alias, child, moves) or _attribute(path, node, alias, base, moves)
        changed = changed or did
        groups.setdefault(written, []).append(name)
    if not changed: return []
    start, end = _span(node, offsets)
    indent = text[offsets[0][node.lineno - 1]:start]
    joiner = '\n' + indent if not indent.strip() else '; '
    return [(start, end, joiner.join(_statement(written, names) for written, names in groups.items()))]


def _statement(written, names):
    """`from X import a, b`; a module moved to the top (written '') is imported by its own name: `import mod`."""
    return f"from {written} import {', '.join(names)}" if written else f"import {', '.join(names)}"


def _submodule(path, alias, child, moves):
    """(the package a moved submodule is imported from now, its name bound as before, True), or None."""
    if not (child and moves.moved(path, child[0])): return None
    parts = dotted(moves.new(child[0]))
    local = alias.asname or alias.name
    return spell(moves.new(path), parts[:-1], child[1], moves.roots), parts[-1] + (f' as {local}' if parts[-1] != local else ''), True


def _attribute(path, node, alias, base, moves):
    """(the module a name is imported from, the name as written, whether the module's spelling changed)."""
    shown = alias.name + (f' as {alias.asname}' if alias.asname else '')
    if base and moves.moved(path, base[0]):
        return spell(moves.new(path), dotted(moves.new(base[0])), base[1], moves.roots), shown, True
    if not base and node.level and moves.moved(path) and alias.name != '*':
        raise Unmovable(f'{path} imports {alias.name} from a folder that is not a package, and moves away from it')
    return '.' * node.level + (node.module or ''), shown, False


def _import(path, node, tree, offsets, moves):
    """`import a.b.c [as m]` with a moved a.b.c: the statement, and without `as`, every a.b.c the file then writes."""
    out = []
    for alias in node.names:
        hit = resolve(path, alias.name, 0, moves.known, moves.roots)
        if not hit or not moves.moved(path, hit[0]): continue
        new = spell(moves.new(path), dotted(moves.new(hit[0])), hit[1], moves.roots)
        if new == alias.name: continue
        if len(node.names) > 1: raise Unmovable(f'{path}:{node.lineno} imports several modules on one line, one of them moved')
        start, end = _span(node, offsets)
        out.append((start, end, f'import {new}' + (f' as {alias.asname}' if alias.asname else '')))
        if not alias.asname: out += _uses(tree, offsets, alias.name, new)
    return out


def _uses(tree, offsets, old, new):
    """Each a.b.c (the attribute chain a plain `import a.b.c` binds) the file writes, named again."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and _chain(node) == old: out.append((*_span(node, offsets), new))
    return out


def _chain(node):
    names = []
    while isinstance(node, ast.Attribute):
        names.append(node.attr)
        node = node.value
    return '.'.join([node.id, *reversed(names)]) if isinstance(node, ast.Name) else None


def _dotted_strings(tree, text, offsets, moves, taken):
    """A string that writes a moved module's dotted name (`'pkg.mod.name'`, as mock.patch and importlib take it)."""
    names = moves.dotted_names()
    out = []
    for node in (n for n in ast.walk(tree) if names and _dotted_literal(n)):
        new = _renamed(node.value, names)
        start, end = _span(node, offsets)
        plain = len(text[start:end]) == len(node.value) + 2               # no escape, not an f-string's part
        if new is not None and plain and not any(start < b and a < end for a, b, _ in taken): out.append((start + 1, end - 1, new))
    return out


def _dotted_literal(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and '.' in node.value


def _renamed(value, names):
    """`value` with its leading moved dotted name replaced, the longest first; None when it starts with none."""
    for old in sorted(names, key=len, reverse=True):
        if value == old or value.startswith(old + '.'): return names[old] + value[len(old):]
    return None

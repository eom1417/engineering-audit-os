"""The files a build script hands a bundler to start from (esbuild's `entryPoints`, rollup's `input`, webpack's
`entry`) or loads itself (`import(pathToFileURL(path.join(SRC, 'words', file)).href)`). The script computes each path (`path.join(SRC, 'places', place, 'index.js')`) and never imports it, so the
import graph reached none of them, and on EAOS's own Studio 96 modules were said to be dead (2026-10-24).

A path is read from its `path.join`/`path.resolve` and the constants it is built from: a literal is itself, the
script's own folder (`__dirname`, `import.meta.url`) its folder, and any other value one folder name (`*`).
"""
import re
from fnmatch import fnmatchcase
from pathlib import PurePosixPath

BUNDLER = re.compile(r'''(?:from\s+|require\(\s*)['"](?:esbuild|rollup|webpack|vite)['"]''')
ENTRIES = re.compile(r'\b(?:entryPoints|entry|input)\s*:\s*|\bimport\(')
CONSTANT = re.compile(r'\b(?:const|let|var)\s+(\w+)\s*=\s*(path\.(?:join|resolve)\()')
CALL = re.compile(r'path\.(?:join|resolve)\(')
LITERAL = re.compile(r'''^['"`]([^'"`$]*)['"`]$''')
HERE = re.compile(r'__dirname|import\.meta\.(?:url|dirname)')


def entries(path, text, known):
    """The known files a build script at `path` hands its bundler or loads; none when it imports no bundler."""
    if not BUNDLER.search(text): return set()
    folder, constants = PurePosixPath(path).parent, {}
    for match in CONSTANT.finditer(text): constants[match.group(1)] = _call(text, match.end(2), folder, constants)
    globs = {_call(text, call.end(), folder, constants) for start in ENTRIES.finditer(text)
             for call in CALL.finditer(text, start.end(), _value_end(text, start.end()))}
    return {file for glob in globs if glob for file in known if fnmatchcase(file, glob) and _same_depth(file, glob)}


def _call(text, start, folder, constants):
    """The path one `path.join(` or `path.resolve(` call names, as a glob; None when it climbs above the root."""
    parts = []
    for argument in _arguments(text[start:_closing(text, start)]):
        literal = LITERAL.match(argument)
        if literal: parts.append(literal.group(1))
        elif HERE.search(argument): parts = [str(folder)]
        elif argument in constants: parts = [constants[argument] or '']
        else: parts.append('*')
    return _normal('/'.join(parts))


def _arguments(inside):
    """A call's arguments, split at the commas outside any bracket."""
    out, depth, current = [], 0, ''
    for char in inside:
        depth += char in '([{' and 1 or -(char in ')]}')
        if char == ',' and not depth: out.append(current.strip()); current = ''
        else: current += char
    return [argument for argument in out + [current.strip()] if argument]


def _value_end(text, start):
    """Where the value at `start` ends: its closing bracket, or the comma or bracket that ends a bare value."""
    if text[start:start + 1] in ('[', '{'): return _closing(text, start + 1) + 1
    depth = 0
    for at in range(start, len(text)):
        if not depth and text[at] in ',}]\n': return at
        depth += text[at] in '([{' and 1 or -(text[at] in ')]}')
    return len(text)


def _closing(text, start):
    """Where the bracket opened just before `start` closes (or the line ends, for a bare value)."""
    depth = 1
    for at in range(start, len(text)):
        depth += text[at] in '([{' and 1 or -(text[at] in ')]}')
        if depth == 0: return at
    return len(text)


def _normal(glob):
    parts = []
    for part in glob.split('/'):
        if part == '..':
            if not parts: return None
            parts.pop()
        elif part not in ('', '.'): parts.append(part)
    return '/'.join(parts)


def _same_depth(file, glob):
    """`*` stands for one folder name, never several."""
    return file.count('/') == glob.count('/')

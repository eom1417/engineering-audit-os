"""The move tool (M8.5): files and folders moved to their new places, every import and every path that names them
written again, and every name the code exposes kept, so the program does exactly what it did. Python (move_python.py)
and JavaScript or TypeScript (move_js.py); any other text file (a document, package.json, a CI workflow, a Dockerfile)
has the paths it writes to a moved file or folder renamed, from the repository's root or from its own folder.

    plan(root, moves)       {mapping {old file: new file}, folders, refused [reasons]}: nothing written
    apply(root, moves)      the moves made in `root` (a copy: never the person's project), with git when it is a
                            repository; returns what moved and which files were written again
    dry_run(target, moves)  apply() on an isolated copy, like every codemod (codemods.py): {exit, files_changed, refused}

`moves` is [{'from': path, 'to': path}], a file or a folder each. Every edit is computed from the files as they were
before anything moves, then made once: a span is never edited twice. A move that would change what the code means is
refused whole, with its reason (Unmovable): an import found through a folder the file leaves, a file that finds its
neighbours from its own place (`__file__`, `__dirname`, `import.meta.url`) and leaves its folder, a destination taken.
"""
import os
import posixpath
import re
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from . import move_js, move_python
from .move_python import Moves, Unmovable

PYTHON = ('.py',)
SCRIPT = tuple(move_js.JS_SUFFIXES)
OWN_PLACE = {'.py': re.compile(r'\b__file__\b'), 'js': re.compile(r'\b__dirname\b|\b__filename\b|import\.meta\.(?:url|dirname|filename)')}
MENTION = re.compile(r'(?<![\w.@/-])((?:\.{1,2}/)*[\w@][\w.@-]*(?:/[\w.@-]+)+/?)')
NOT_TEXT = ('package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'bun.lockb', 'poetry.lock', 'uv.lock', 'Cargo.lock')
BIGGEST = 2 * 1024 * 1024


def files(root):
    """Every file of the project, relative and in posix form: git's own list in a repository (what a push publishes and
    what the code can name), else every file outside the folders tools fill (node_modules, .venv...)."""
    if (Path(root) / '.git').exists():          # its own repository, not a folder inside another one
        done = subprocess.run(['git', '-C', str(root), 'ls-files', '-co', '--exclude-standard'], capture_output=True, text=True)
        if done.returncode == 0: return sorted(set(done.stdout.splitlines()))
    from ...core.project.workspace import SKIP_DIRS
    found = []
    for base, directories, names in os.walk(root):
        directories[:] = [d for d in directories if d not in SKIP_DIRS]
        found += [(Path(base) / n).relative_to(root).as_posix() for n in names]
    return sorted(found)


def _clean(path):
    return posixpath.normpath(str(path).strip().strip('/')) if str(path).strip().strip('/') else ''


def plan(root, moves, known=None):
    """{mapping, folders, refused}: each move's files and where they go, and every reason the batch cannot be made."""
    known = set(known if known is not None else files(root))
    mapping, folders, refused = {}, {}, []
    for move in moves:
        old, new = _clean(move['from']), _clean(move['to'])
        inside = sorted(p for p in known if p.startswith(old + '/'))
        if old in known: mapping[old] = new
        elif inside:
            folders[old] = new
            mapping.update({p: new + p[len(old):] for p in inside})
        else: refused.append(f'{old} is not in the project')
    refused += _clashes(mapping, known) + _own_place(root, mapping) + _packages(mapping, known)
    return {'mapping': mapping, 'folders': folders, 'refused': refused}


def _clashes(mapping, known):
    """A destination another file holds after the move, or that two files are both moved to."""
    staying = known - set(mapping)
    out = [f'{new} is already there' for new in sorted(set(mapping.values())) if new in staying]
    seen = {}
    for old, new in sorted(mapping.items()):
        if new in seen: out.append(f'{old} and {seen[new]} would both become {new}')
        seen[new] = old
    return out


def _own_place(root, mapping):
    """A file that finds other files from its own place and would leave its folder."""
    out = []
    for old, new in sorted(mapping.items()):
        if posixpath.dirname(old) == posixpath.dirname(new): continue
        suffix = PurePosixPath(old).suffix
        pattern = OWN_PLACE['.py'] if suffix in PYTHON else OWN_PLACE['js'] if suffix in SCRIPT else None
        if pattern and pattern.search(_read(root, old) or ''):
            out.append(f'{old} finds other files from its own place, and would leave its folder')
    return out


def _packages(mapping, known):
    """A Python module moved where a module of the folder's new package name already is (pkg/run.py beside pkg.py)."""
    after = (known - set(mapping)) | set(mapping.values())
    out = []
    for new in sorted(set(mapping.values())):
        if not new.endswith('.py'): continue
        for folder in PurePosixPath(new).parents:
            if folder.as_posix() != '.' and folder.as_posix() + '.py' in after:
                out.append(f'{new} would sit in the folder {folder}, beside the module {folder}.py of the same name')
    return out


def _read(root, path):
    file = Path(root) / path
    try:
        if file.stat().st_size > BIGGEST or PurePosixPath(path).name in NOT_TEXT: return None
        with open(file, encoding='utf-8', newline='') as read: return read.read()      # its own line ends kept
    except (OSError, UnicodeDecodeError): return None


def edits(root, drawn, known):
    """{file before the move: its new text} for every file whose text changes."""
    known = set(known)
    moves = Moves(drawn['mapping'], known, _roots(known))
    aliased = move_js.aliases(lambda p: _read(root, p), known)
    out = {}
    for path in sorted(known):
        text = _read(root, path)
        if text is None: continue
        found = _spans(path, text, moves, aliased, drawn['folders'])
        if found: out[path] = _edited(text, found)
    return out


def _roots(known):
    """'' and each folder that holds top packages without being one (src/, a test folder put on the path)."""
    roots = {''}
    for path in known:
        parts = PurePosixPath(path).parts
        if len(parts) > 2 and parts[-1] == '__init__.py' and '/'.join(parts[:-2]) + '/__init__.py' not in known:
            roots.add('/'.join(parts[:-2]) + '/')
    return roots


def _spans(path, text, moves, aliased, folders):
    suffix = PurePosixPath(path).suffix
    found = move_python.spans(path, text, moves) if suffix in PYTHON else move_js.spans(path, text, moves, aliased) if suffix in SCRIPT else []
    return found + _mentions(path, text, moves, folders)


def _mentions(path, text, moves, folders):
    """Each path the text writes to a moved file or folder (from the root or from the file's own folder), and, in a
    moved file, each path it writes from its folder to a file that stays."""
    out = []
    for match in MENTION.finditer(text):
        new = _mention(path, match.group(1), moves, folders)
        if new and new != match.group(1): out.append((match.start(1), match.end(1), new))
    return out


def _mention(path, token, moves, folders):
    """The path `token` again: written from the root, it stays so; written from the file's folder, it is written from
    the file's new folder. None when it names nothing that moves."""
    slash = '/' if token.endswith('/') else ''
    new = None if token.startswith('.') else _moved_to(_clean(token), moves, folders)
    if new: return new + slash
    new = _from_folder(path, token, moves, folders) if posixpath.dirname(path) or token.startswith('.') else None
    return new + slash if new else None


def _from_folder(path, token, moves, folders):
    """`token`, written from the file's folder, written from its new folder; None when neither it nor the file moves."""
    named = _clean(posixpath.join(posixpath.dirname(path), token))
    new = _moved_to(named, moves, folders) or (named if moves.moved(path) and _exists(named, moves.known) else None)
    if new is None: return None
    rel = posixpath.relpath(new, posixpath.dirname(moves.new(path)) or '.')
    return './' + rel if token.startswith('./') and not rel.startswith('.') else rel


def _moved_to(named, moves, folders):
    return moves.mapping.get(named) or folders.get(named) or _inside_folder(named, folders)


def _inside_folder(named, folders):
    for old, new in folders.items():
        if named.startswith(old + '/'): return new + named[len(old):]
    return None


def _exists(named, known):
    return named in known or any(p.startswith(named + '/') for p in known)


def _edited(text, found):
    """The text with each span replaced, the first found winning where two overlap."""
    kept = []
    for start, end, new in found:
        if not any(start < b and a < end for a, b, _ in kept): kept.append((start, end, new))
    for start, end, new in sorted(kept, reverse=True): text = text[:start] + new + text[end:]
    return text


def apply(root, moves):
    """Make the moves in `root`; {moved, rewritten, created}. Raises Unmovable, with every reason, and writes nothing."""
    root = Path(root)
    known = files(root)
    drawn = plan(root, moves, known)
    if drawn['refused']: raise Unmovable('; '.join(drawn['refused']))
    texts = edits(root, drawn, known)
    git = (root / '.git').exists()
    for old, new in sorted(drawn['mapping'].items()): _move(root, old, new, git)
    for old, text in texts.items(): (root / drawn['mapping'].get(old, old)).write_text(text, encoding='utf-8', newline='')
    created = _new_packages(root, drawn['mapping'], set(known))
    _prune(root, drawn['mapping'])
    return {'moved': len(drawn['mapping']), 'rewritten': sorted(drawn['mapping'].get(p, p) for p in texts), 'created': created}


def _move(root, old, new, git):
    (root / new).parent.mkdir(parents=True, exist_ok=True)
    if git and subprocess.run(['git', '-C', str(root), 'mv', '-k', old, new], capture_output=True).returncode == 0 \
            and (root / new).exists(): return
    shutil.move(str(root / old), str(root / new))


def _new_packages(root, mapping, known):
    """An __init__.py in each folder the move made for a Python module of a package, so it stays importable as before;
    a folder that was there before the move is left as it was (src/ is no package)."""
    created, there = [], {PurePosixPath('.')} | {folder for p in known for folder in PurePosixPath(p).parents}
    for old, new in sorted(mapping.items()):
        if not _in_package(old, known): continue
        for folder in reversed(PurePosixPath(new).parents):
            if folder in there or (root / folder / '__init__.py').exists(): continue
            (root / folder / '__init__.py').write_text('', encoding='utf-8')
            created.append((folder / '__init__.py').as_posix())
    return created


def _in_package(path, known):
    """Whether `path` is a Python module of a regular package (its folder holds an __init__.py)."""
    return path.endswith('.py') and bool(posixpath.dirname(path)) and posixpath.dirname(path) + '/__init__.py' in known


def _prune(root, mapping):
    """The folders the moves emptied, removed."""
    for old in sorted(mapping, key=lambda p: -p.count('/')):
        for folder in PurePosixPath(old).parents:
            if folder.as_posix() == '.': break
            path = root / folder
            if path.is_dir() and not any(path.iterdir()): path.rmdir()
            else: break


def dry_run(target, moves):
    """{exit, files_changed, refused} of the moves on an isolated copy of `target`: nothing of the project is written."""
    from ...live.testing.verify import isolated_copy
    from .codemods import _changed, _stats
    with tempfile.TemporaryDirectory(prefix='eaos-move-') as holder:
        copy = isolated_copy(Path(target), Path(holder) / 'project')
        before = _stats(copy)
        try: apply(copy, moves)
        except Unmovable as refused: return {'exit': 1, 'files_changed': 0, 'refused': str(refused)}
        return {'exit': 0, 'files_changed': len(_changed(copy, target, before, _stats(copy))), 'refused': ''}

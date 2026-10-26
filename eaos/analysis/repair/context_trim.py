"""The assistants' context trimmed safely (M8.6): what an assistant reads at the start of every session (M7.9,
eaos/facts/repository/context.py) made lighter without losing one instruction.

    plan(root, private_to=None)   {edits {file: new text}, archive, private, kept_twice, personal, renamed}; nothing written
    apply(root, private_to=None)  the plan written in `root` (a copy: never the person's project); Untrimmable when an
                                  instruction of the files before is not found again in exactly one file after

What it does: a done item (`- [x] ...`) moves to the archive file (rules: context_archive), never deleted; a line said in
two files stays only in the one the other imports (CLAUDE.md's `@AGENTS.md`), so every assistant still reads it once (a
line read by two different assistants is kept twice, and said so); a path a file names that is not there is pointed at
the one file of that name. A person's own instructions (rules: context_personal, and the machine details of dev_details)
are proposed to move to the private file the person names (`private_to`), the public file keeping the rest. Only the
repository's own files are read and written, never an assistant's own folders (~/.claude, ~/.codex)."""
import posixpath
import re
from collections import Counter
from pathlib import Path, PurePosixPath

from ...facts.repository.catalog import limits as craft_limits
from ...facts.repository.context import DONE, IMPORT, files as context_files
from ...facts.repository.craft import BACKTICKED
from .moves import files as repository_files

DONE_LINE = re.compile(DONE.pattern.replace('(?m)', ''))


class Untrimmable(ValueError):
    """A trim that would lose or repeat an instruction: refused whole, with its reason."""


def read(root, known, rules):
    """{path: text} of every context file a session reads (CLAUDE.md's @imports among them), inside the repository."""
    out, queue = {}, context_files(known, rules)
    while queue:
        path = queue.pop(0)
        if path in out or path not in known: continue
        out[path] = (Path(root) / path).read_text(encoding='utf-8', errors='replace')
        if PurePosixPath(path).name == 'CLAUDE.md':
            queue += [posixpath.normpath(posixpath.join(posixpath.dirname(path), name)) for name in IMPORT.findall(out[path])]
    return out


def imported(texts):
    """{file: every context file it reads with it} (CLAUDE.md's @imports, followed)."""
    direct = {path: {posixpath.normpath(posixpath.join(posixpath.dirname(path), n)) for n in IMPORT.findall(text)}
              if PurePosixPath(path).name == 'CLAUDE.md' else set() for path, text in texts.items()}
    out = {}
    for path in direct:
        seen, queue = set(), list(direct[path])
        while queue:
            name = queue.pop()
            if name not in seen: seen.add(name); queue += list(direct.get(name, ()))
        out[path] = seen
    return out


def said(line):
    return ' '.join(line.split())


def plan(root, private_to=None):
    rules = craft_limits()
    known = set(repository_files(root))
    texts = read(root, known, rules)
    lines = {path: text.splitlines(keepends=True) for path, text in texts.items()}
    archive = _done(lines)
    kept_twice = _repeats(lines, imported(texts), rules)
    renamed = _stale(lines, known)
    personal = _personal(lines, rules)
    private = _private(lines, personal) if private_to else []
    edits = {path: ''.join(rows) for path, rows in lines.items() if ''.join(rows) != texts[path]}
    return {'edits': edits, 'archive': archive, 'private': private, 'kept_twice': kept_twice, 'personal': personal,
            'renamed': renamed, 'before': texts, 'archive_file': rules['context_archive'], 'private_file': private_to}


def _done(lines):
    """Each done item taken out of its file: [(file, line)]."""
    out = []
    for path, rows in lines.items():
        out += [(path, row) for row in rows if DONE_LINE.match(row)]
        rows[:] = [row for row in rows if not DONE_LINE.match(row)]
    return out


def _repeats(lines, reads, rules):
    """A line said in two files removed from each one that imports another saying it; [(line, files)] of those kept twice:
    files no assistant reads together."""
    kept = []
    for text, paths in _said_twice(lines, rules):
        stays = sorted(p for p in paths if not reads.get(p, set()) & paths) or sorted(paths)[:1]   # read with nothing else saying it
        for other in paths - set(stays): lines[other][:] = [row for row in lines[other] if said(row) != text]
        if len(stays) > 1: kept.append((text, stays))
    return kept


def _said_twice(lines, rules):
    """[(line, the files saying it)] of each long line said in more than one file."""
    where = {}
    for path, rows in lines.items():
        for row in (r for r in rows if len(said(r)) >= rules['context_repeat_chars']): where.setdefault(said(row), set()).add(path)
    return sorted((text, paths) for text, paths in where.items() if len(paths) > 1)


def _stale(lines, known):
    """{named: the one file of that name} for each path a context file names that is not there."""
    by_name = {}
    for path in known: by_name.setdefault(PurePosixPath(path).name, []).append(path)
    renamed = {}
    for path, rows in lines.items():
        for index, row in enumerate(rows):
            for named in BACKTICKED.findall(row):
                there = posixpath.normpath(posixpath.join(posixpath.dirname(path), named))
                found = by_name.get(PurePosixPath(named).name) or []
                if named in known or there in known or len(found) != 1: continue
                renamed[named] = found[0]
                rows[index] = rows[index].replace(f'`{named}', f'`{found[0]}')
    return renamed


def _personal(lines, rules):
    """[(file, line, what)] of each line that speaks as one person or publishes a detail of one machine."""
    patterns = [(re.compile(p), what) for p, what in rules['context_personal'] + rules['dev_details']]
    out = []
    for path, rows in lines.items():
        for row in rows:
            what = next((what for pattern, what in patterns if pattern.search(row)), None)
            if what: out.append((path, row.rstrip('\n'), what))
    return out


def _private(lines, personal):
    """The personal lines taken out of their files, for the private file the person named."""
    taken = {(path, line) for path, line, _ in personal}
    out = []
    for path, rows in lines.items():
        out += [(path, row) for row in rows if (path, row.rstrip('\n')) in taken]
        rows[:] = [row for row in rows if (path, row.rstrip('\n')) not in taken]
    return out


def _section(existing, moved):
    """The archive or private file with the moved lines appended, each group under the file it came from."""
    text = existing or '# Moved out of the assistants\' context by EAOS (M8.6): kept, read when needed\n'
    for source in dict.fromkeys(path for path, _ in moved):
        text += f'\n## From {source}\n\n' + ''.join(row if row.endswith('\n') else row + '\n' for path, row in moved if path == source)
    return text


def instructions(text):
    """The instructions a text holds: each line with words in it, said once (blank lines and pure markup are none)."""
    return {said(row) for row in text.splitlines() if re.search(r'\w{2,}', row) and not row.lstrip().startswith('#')}


def verify(drawn, after):
    """Each instruction of the context before that is not found again in exactly one file after (the context, the
    archive, the private file), a renamed path read as renamed; [] when none."""
    counts = Counter(line for text in after.values() for line in instructions(text))
    wanted = sorted({_renamed(line, drawn['renamed']) for text in drawn['before'].values() for line in instructions(text)})
    twice = {said(text) for text, _ in drawn['kept_twice']}
    return [_problem(line, counts[line]) for line in wanted if counts[line] != 1 and line not in twice or not counts[line]]


def _problem(line, count):
    return f'lost: {line[:120]}' if not count else f'said {count} times: {line[:120]}'


def _renamed(line, renamed):
    for old, new in renamed.items(): line = line.replace(f'`{old}', f'`{new}')
    return line


def apply(root, private_to=None):
    """Write the plan in `root`; the summary. Untrimmable, with every lost or repeated instruction, writes nothing."""
    root = Path(root)
    drawn = plan(root, private_to)
    after = _after(root, drawn, private_to)
    problems = verify(drawn, after)
    if problems: raise Untrimmable('; '.join(problems[:10]))
    written = sorted(path for path, text in after.items() if text != drawn['before'].get(path))
    for path in written:
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(after[path], encoding='utf-8')
    return {'archived': len(drawn['archive']), 'private': len(drawn['private']), 'renamed': drawn['renamed'],
            'kept_twice': drawn['kept_twice'], 'personal': drawn['personal'], 'written': written,
            'tokens_before': sum(len(t) for t in drawn['before'].values()) // 4,
            'tokens_after': sum(len(after[p]) for p in drawn['before']) // 4}


def _after(root, drawn, private_to):
    """{file: its text after the trim}: the context files, and the archive and private file with what moved to them."""
    after = {path: drawn['edits'].get(path, text) for path, text in drawn['before'].items()}
    for path, moved in {drawn['archive_file']: drawn['archive'], **({private_to: drawn['private']} if private_to else {})}.items():
        if moved: after[path] = _section(_existing(root, path), moved)
    return after


def _existing(root, path):
    file = Path(root) / path
    return file.read_text(encoding='utf-8') if file.is_file() else ''

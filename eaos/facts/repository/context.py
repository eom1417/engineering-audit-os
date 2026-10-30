"""The context an assistant reads at the start of every session (M7.9): the instruction files (AGENTS.md, CLAUDE.md and
the files it imports with @, GEMINI.md, the Cursor and Copilot rules, the project's skills), measured in tokens: how
heavy they are, the lines said in more than one, and the done items still in them. EAOS's own blocks between their marker
lines (eaos/ai/assistant/setup.py, the pinned rules of eaos/analysis/rules/context.py) are never counted against the person."""
import posixpath
import re
from collections import defaultdict
from pathlib import PurePosixPath

from .catalog import finding

IMPORT = re.compile(r'(?m)^@([\w./-]+\.md)\s*$')
DONE = re.compile(r'(?m)^\s*[-*] \[[xX]\] ')


def tokens(text):
    return len(text) // 4          # about four characters a token, the measure an assistant's limits are read in


def files(everything, limits):
    """The context files a session reads: the named ones, those CLAUDE.md files import, every file of the skill folders."""
    named = [p for p in sorted(everything) if p in limits['context_files']]
    named += [p for p in sorted(everything) if any(p.startswith(folder + '/') for folder in limits['context_folders'])]
    return named


def followed(start, everything, read):
    """{path: read(path)} of the context files from `start`, the files a CLAUDE.md imports followed, inside the repository."""
    out, queue = {}, list(start)
    while queue:
        path = queue.pop(0)
        if path in out or path not in everything: continue
        out[path] = read(path)
        if PurePosixPath(path).name == 'CLAUDE.md':
            queue += [posixpath.normpath(posixpath.join(posixpath.dirname(path), name)) for name in IMPORT.findall(out[path])]
    return out


def texts(source, everything, limits):
    """{path: its text without EAOS's own block}, the imported files of a CLAUDE.md among them; of a skill only what a
    session reads before it is used."""
    return followed(files(everything, limits), everything,
                    lambda path: _preloaded(path, _without_eaos(source.text(path) or '', limits), limits))


def _preloaded(path, text, limits):
    """What a session reads of a context file before anyone asks: all of it, but of a skill (a folder of
    `skill_folders`) only its SKILL.md's front matter, its name and description; its body and its other files are read
    when the skill is used."""
    if not any(path.startswith(folder + '/') for folder in limits['skill_folders']): return text
    if PurePosixPath(path).name != 'SKILL.md' or not text.startswith('---'): return ''
    return text[:text.find('\n---', 3) + 4] if '\n---' in text[3:] else ''


def _without_eaos(text, limits):
    """The text without EAOS's own blocks: its guide's and the person's pinned rules' (M16)."""
    for begin, end in limits['eaos_block']:
        while begin in text and end in text.split(begin, 1)[1]:
            head, rest = text.split(begin, 1)
            text = head + rest.split(end, 1)[1]
    return text


def heavy(read, limits):
    total = sum(tokens(text) for text in read.values())
    if total <= limits['context_tokens'] or not read: return []
    return [finding('context-heavy', next(iter(read)), {'files': ', '.join(list(read)[:6]), 'tokens': total})]


def repeats(read, limits):
    seen = defaultdict(set)
    for path, text in read.items():
        for line in text.splitlines():
            said = ' '.join(line.split())
            if len(said) >= limits['context_repeat_chars']: seen[said].add(path)
    twice = {line: paths for line, paths in seen.items() if len(paths) > 1}
    if not twice: return []
    where = sorted({p for paths in twice.values() for p in paths})
    return [finding('context-repeat', where[0], {'count': len(twice), 'files': ', '.join(where[:6]),
                                                 'tokens': sum(tokens(line) * (len(paths) - 1) for line, paths in twice.items())})]


def done(read, limits):
    return [finding('context-done', path, {'path': path, 'count': len(DONE.findall(text))})
            for path, text in read.items() if len(DONE.findall(text)) >= limits['context_done_items']]

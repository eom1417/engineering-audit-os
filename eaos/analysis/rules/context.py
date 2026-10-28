"""Where a pinned rule is held beside its guard (M16.4, M16.3b), both written from the one registry and never sources of
their own: the assistant's context of the project (its CLAUDE.md / AGENTS.md, between EAOS's rule markers) and, with the
person's consent, the project's git pre-commit hook (between the same kind of markers). Unpinning writes them again
from the registry: a rule's line and, with the last pinned rule, the hook's block go; a file EAOS made for them alone
is removed; everything else in those files stays as the person wrote it.
"""
import os
import re
import shlex
import stat
import subprocess
from pathlib import Path

BEGIN = '<!-- EAOS rules: begin (your pinned rules, written by EAOS from its rule registry; change them with eaos rules) -->'
END = '<!-- EAOS rules: end -->'
HOOK_BEGIN = '# EAOS rules: begin (eaos rules hook: the rules you pinned, checked on what you commit)'
HOOK_END = '# EAOS rules: end'
IMPORT = re.compile(r'(?m)^@AGENTS\.md\s*$')
HEADER = {'en': 'Rules the person pinned for this project. Keep every one of them in every change; EAOS refuses a change '
                'that breaks one.',
          'ar': 'قواعد ثبّتها صاحب المشروع. التزم بكل وحدة منها في كل تعديل؛ EAOS يرفض أي تعديل يكسر وحدة منها.'}


def _strip(text, begin, end):
    """`text` without EAOS's block between `begin` and `end` (and the blank line before it)."""
    while begin in text and end in text.split(begin, 1)[1]:
        head, rest = text.split(begin, 1)
        text = head.rstrip('\n') + ('\n' if head.strip() else '') + rest.split(end, 1)[1].lstrip('\n')
    return text


def files(project):
    """The context files the block goes into: AGENTS.md when CLAUDE.md imports it (read once by every assistant), else
    those of CLAUDE.md and AGENTS.md that exist; none: AGENTS.md, and a CLAUDE.md that imports it, both made."""
    project = Path(project)
    claude, agents = project / 'CLAUDE.md', project / 'AGENTS.md'
    if claude.is_file() and IMPORT.search(claude.read_text(encoding='utf-8', errors='replace')): return [agents], []
    present = [f for f in (claude, agents) if f.is_file()]
    return (present, []) if present else ([agents], [claude, agents])


def block(rules, lang):
    lines = [BEGIN, HEADER[lang], '']
    lines += [f"- {rule['words']} ({rule['id']}, {_guarded(rule)})" for rule in rules]
    return '\n'.join(lines + [END])


def _guarded(rule):
    kind = (rule.get('guard') or {}).get('kind')
    return {'pattern': 'guarded by a code pattern', 'test': 'guarded by a test', 'detector': "guarded by EAOS's detectors",
            'none': 'EAOS cannot guard it: keep it yourself'}.get(kind, 'its guard is not written yet')


def _written(path, text, pinned, where, lang):
    """A context file's text with EAOS's block, or a CLAUDE.md made to read the AGENTS.md made beside it; `where`: (the
    files the block goes into, the files made for it)."""
    targets, to_make = where
    if pinned and path in targets: return (text.rstrip('\n') + '\n\n' if text.strip() else '') + block(pinned, lang) + '\n'
    return '@AGENTS.md\n' if pinned and path in to_make else text


def _put(path, text, ours):
    """The file written with `text`; one EAOS made (`ours`) left with nothing of the person's is removed. Whether written."""
    if ours and text.strip() in ('', '@AGENTS.md'):
        path.unlink(missing_ok=True)
        return False
    if not (path.is_file() or text.strip()): return False
    path.write_text(text, encoding='utf-8')
    return True


def write(project, pinned, made, lang='en'):
    """The block written from `pinned` (the rules pinned now) into the context files, or taken out of them when none is;
    `made`: the files EAOS made before for the block alone, removed once it is gone. (the files written, made now)."""
    project = Path(project)
    targets, to_make = files(project)
    to_make = to_make if pinned else []
    written = []
    for path in dict.fromkeys([*targets, *to_make, *(project / m for m in made)]):
        name = str(path.relative_to(project))
        text = _written(path, _strip(path.read_text(encoding='utf-8') if path.is_file() else '', BEGIN, END), pinned, (targets, to_make), lang)
        if _put(path, text, not pinned and name in made): written.append(name)
    return written, sorted({*made, *(str(p.relative_to(project)) for p in to_make)}) if pinned else []


# ---------------------------------------------------------------- the hook

def hook_path(project):
    """The pre-commit hook git runs for the project (core.hooksPath respected; a linked hook is the file it links to)."""
    found = subprocess.run(['git', '-C', str(project), 'rev-parse', '--git-path', 'hooks/pre-commit'], capture_output=True, text=True)
    if found.returncode: raise ValueError('this project is not a git repository: a commit hook needs one')
    path = Path(found.stdout.strip())
    return (path if path.is_absolute() else Path(project) / path).resolve()


def hook_block(command, project):
    line = ' '.join(shlex.quote(part) for part in [*command, 'check', '--changed', '--staged', '--hook', '--project', str(project)])
    return f'{HOOK_BEGIN}\n{line} || exit 1\n{HOOK_END}\n'


def hook(project, command, on, made=False):
    """EAOS's block in the project's pre-commit hook, put right after its first line (so an `exit 0` below it never
    skips it) or taken out; the hook file made when none was there, removed when EAOS made it and its block is gone.
    (the hook's path, whether EAOS made it)."""
    path = hook_path(project)
    text = _strip(path.read_text(encoding='utf-8') if path.is_file() else '', HOOK_BEGIN, HOOK_END)
    if not on:
        if made and text.strip() in ('', '#!/bin/sh'): path.unlink(missing_ok=True)
        elif path.is_file(): path.write_text(text, encoding='utf-8')
        return path, False
    making = not path.is_file()
    head, _, rest = (text or '#!/bin/sh\n').partition('\n')
    if not head.startswith('#!'): head, rest = '#!/bin/sh', text
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'{head}\n{hook_block(command, project)}{rest}', encoding='utf-8')
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path, making or made


def hooked(project):
    """Whether the project's pre-commit hook holds EAOS's block now."""
    try: path = hook_path(project)
    except ValueError: return False
    return path.is_file() and HOOK_BEGIN in path.read_text(encoding='utf-8', errors='replace') and os.access(path, os.X_OK)

"""A batch of the assistants' context (M8.6): the files an assistant reads every session trimmed (analysis/repair/
context_trim.py) on a branch of their own, never mixed with fix cards or moves.

    proposal(target, private_to=None)   what the trim would do, nothing written: the done items it archives, the lines
                                        said twice it keeps once, the paths it fixes, the person's own lines it proposes
                                        to move to their private file, and the tokens every session saves
    make(batch)                         the trim made in a clone of the authorised commit and committed; refused whole
                                        when an instruction is not found again in exactly one file, or when it would
                                        write anything but the context files, the archive and the private file

The branch is handed over like a wave's (waves.apply); accept and undo decide it."""
import posixpath

from ...analysis.repair import context_trim
from ...core.project.ledger import TRAILER
from .execute import commit_all, git, own_batch, record_batch

# An assistant's own folders: never written, even inside the repository.
ASSISTANT_FOLDERS = ('.claude', '.codex', '.cursor', '.gemini', '.github/copilot')


def private_problem(private_to):
    """Why `private_to` cannot hold the person's own lines (outside the repository, or an assistant's folder), else ''."""
    if not private_to: return ''
    clean = posixpath.normpath(private_to)
    if posixpath.isabs(private_to) or clean.startswith('..'): return f'{private_to} is outside the repository'
    if clean.startswith(ASSISTANT_FOLDERS): return f"{private_to} is in an assistant's own folder"
    return ''


def proposal(target, private_to=None):
    """What a trim of `target`'s context would do, as the person reads it before deciding; nothing written."""
    drawn = context_trim.plan(target, private_to if not private_problem(private_to) else None)
    before = sum(len(text) for text in drawn['before'].values()) // 4
    after = sum(len(drawn['edits'].get(path, text)) for path, text in drawn['before'].items()) // 4
    return {'files': sorted(drawn['before']), 'archive': [row.strip() for _, row in drawn['archive']],
            'archive_file': drawn['archive_file'], 'kept_once': sorted(drawn['edits']), 'kept_twice': drawn['kept_twice'],
            'renamed': drawn['renamed'], 'personal': drawn['personal'], 'private_file': drawn['private_file'],
            'tokens_before': before, 'tokens_after': after, 'refused': private_problem(private_to)}


def make(batch):
    """The trim made and checked in a copy: the summary, `kept` the files written, empty when refused (why in
    `refused`). `batch`: {target, runtime, number, private_to, deliver_as}."""
    batch = {**batch, 'kind': 'context', 'items': []}
    root, base = own_batch(batch['target'], batch['runtime'], f"CONTEXT-{batch['number']}")
    if (why := private_problem(batch.get('private_to'))): return record_batch(batch, root, base, [], [why])
    allowed = set(context_trim.plan(root)['before']) | set(_extra(batch))
    try: done = context_trim.apply(root, batch.get('private_to'))
    except context_trim.Untrimmable as problem: return record_batch(batch, root, base, [], [f'an instruction would be lost or repeated: {problem}'])
    if not done['written']: return record_batch(batch, root, base, [], ['nothing to trim: the context is already as light as it can be made'])
    if (stray := sorted(set(_changed(root)) - allowed)):
        git(root, 'reset', '--hard', '--quiet', base)
        return record_batch(batch, root, base, [], [f'the trim would write files that are not the context: {", ".join(stray[:5])}'])
    commit_all(root, f"Trim the assistants' context: {done['archived']} done item(s) archived, {done['tokens_before'] - done['tokens_after']} "
                     f"tokens fewer every session\n\nExecuted by EAOS (context batch).\n\n{TRAILER}: context")
    batch['extra'] = {k: done[k] for k in ('archived', 'private', 'renamed', 'kept_twice', 'tokens_before', 'tokens_after')}
    return record_batch(batch, root, base, done['written'], [])


def _extra(batch):
    """The files a trim may add: the archive and the private file."""
    from ...facts.repository.catalog import limits
    return [limits()['context_archive']] + ([posixpath.normpath(batch['private_to'])] if batch.get('private_to') else [])


def _changed(root):
    return [line[3:] for line in git(root, 'status', '--porcelain', '--untracked-files=all').stdout.splitlines()]

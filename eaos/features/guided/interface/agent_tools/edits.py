"""An assistant's edits applied to the isolated copy: each file kept inside it, a text replaced once, with the
file's own line ends; all or nothing; then committed, or taken back."""
from pathlib import Path

from ... import journey as guided
from ....fix.journey import finish as batch_finish


def _inside(root, relative):
    path = (Path(root) / relative).resolve()
    if Path(root).resolve() not in path.parents or '.git' in path.relative_to(Path(root).resolve()).parts:
        raise ValueError(f'{relative}: not a file of the project')
    return path


def _kept(path):
    """A file's text with its own line ends: read as text, a Windows file came back with \\n, and the edit wrote every
    line of it back changed."""
    with path.open(encoding='utf-8', newline='') as file: return file.read()


def _line_ends(text, find, replace):
    """`find` and `replace` with the file's own line ends: fix_read shows a Windows file's lines without their \\r, and
    the text an assistant copies from them has none."""
    if '\r\n' in text and '\r\n' not in find and find.replace('\n', '\r\n') in text:
        return find.replace('\n', '\r\n'), replace.replace('\r\n', '\n').replace('\n', '\r\n')
    return find, replace


def _not_once(relative, times):
    """Why an edit was refused, and what to do: read the lines again, they are not what the edit remembers."""
    if not times:
        return (f'{relative}: the text to find is not in the file as it is now: read those lines again with fix_read '
                f'(an '
                'earlier edit, or a change taken back, may have changed them) and copy `find` from them, without the '
                'line numbers')
    return f'{relative}: the text to find occurs {times} times, not once: take more lines around it so it is found once'


def _apply(root, edits):
    """Each edit: {path, find, replace} (find occurs exactly once), {path, content} (the whole file, new or not),
    or {path, delete: true}. All or nothing."""
    staged = {}
    for edit in edits:
        path = _inside(root, edit.get('path') or '')
        staged[edit['path']] = _edited(edit, path, staged)
    for relative, text in staged.items():
        path = _inside(root, relative)
        if text is None:
            if path.is_file(): path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w', encoding='utf-8', newline='') as out: out.write(text)
    return sorted(staged)


def _edited(edit, path, staged):
    """What one edit leaves of its file: None (deleted), its new content, or its text so far with `find` replaced
    once."""
    relative = edit['path']
    if edit.get('delete'): return None
    if 'content' in edit:
        if not isinstance(edit['content'], str): raise ValueError(f'{relative}: content must be text')
        return edit['content']
    text = staged.get(relative) if relative in staged else (_kept(path) if path.is_file() else None)
    if text is None: raise ValueError(f'{relative}: does not exist; send its whole content instead')
    return _replaced(relative, text, edit.get('find'), edit.get('replace'))


def _replaced(relative, text, find, replace):
    """`text` with `find` replaced by `replace`, once: ValueError unless `find` occurs exactly once."""
    if not isinstance(find, str) or not isinstance(replace, str) or not find:
        raise ValueError(f'{relative}: an edit needs `find` and `replace`, or `content`, or `delete`')
    find, replace = _line_ends(text, find, replace)
    if text.count(find) != 1: raise ValueError(_not_once(relative, text.count(find)))
    return text.replace(find, replace, 1)


def _committed(root, card, arguments, repair):
    """((the files changed, those beyond the card's own paths), None), the change committed in the copy; else (None, why
    nothing was kept), the copy as it was. A change beyond the card is kept only with the assistant's `beyond_why`, said
    in its commit body, since it adds what nobody asked for."""
    from ....fix.journey.waves import commit
    summary, why = arguments.get('summary') or '', (arguments.get('beyond_why') or '').strip()
    try:
        changed = _apply(root, arguments['edits'])
        outside = [] if repair else batch_finish.beyond(card, changed)
        if outside and not why: stop = _unexplained(outside)
        else:
            told = f"{summary.strip() or card.get('title') or ''}\n\nBeyond the card: {', '.join(outside)}: {why}"
            commit(root, card, told if outside else summary)
            return (changed, outside), None
    except (ValueError, RuntimeError, OSError, UnicodeDecodeError) as problem:
        stop = {'why': f'the edit could not be applied: {problem}',
                'what_now': 'Nothing changed. Read the file again with fix_read and send a corrected edit.'}
    guided._git(root, 'checkout', '--quiet', '--', '.')
    guided._git(root, 'clean', '-fdq')
    return (None, None), stop


def _unexplained(outside):
    return {'why': f"it changed files beyond the card's own ({', '.join(outside[:10])}) and gave no beyond_why",
            'beyond_the_card': outside,
            'what_now': "The change was taken back. Keep it to the card's files and to what the card asks; or, when "
                        "each other file "
                        'must change for this fix (the one-source gate made it reach the copies of what it changed, '
                        'say), send '
                        'fix_edit again with beyond_why: one sentence per other file, or one for all.'}

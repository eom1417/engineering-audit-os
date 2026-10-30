"""A project's extension guide written (M18.3): docs/EXTENDING.md between EAOS's marker lines, from what
eaos/analysis/understanding/extending.py drew, and one pointer line in the assistants' context files, between its own
markers; the guide is never copied into them. What the person wrote below the guide's end line stays. Written only in a
copy, on a branch of its own (eaos/journeys/fix/context_batch.py), or in a build's copy at each milestone."""
import shlex
import shutil
import subprocess
from pathlib import Path

from ..rules import context as context_files
from ..understanding import extending
from ...core.project import rules as registry
from ...core.system.files import read_json
from ...engines.code import gitnexus
from ...engines.process import run

BEGIN = '<!-- EAOS guide: begin (written by EAOS from the project itself; what you write below the end line stays) -->'
END = '<!-- EAOS guide: end -->'
POINTER_BEGIN = '<!-- EAOS guide pointer: begin (one line, written by EAOS) -->'
POINTER_END = '<!-- EAOS guide pointer: end -->'
FOLDERS = ('docs', 'doc', 'documentation')
NAME = 'EXTENDING.md'
SKILLS_IGNORED = '.claude/skills/gitnexus*'


def place(tree):
    """Where the guide lives: where one is, else the project's docs folder, a new docs/ when it has none."""
    for candidate in [f'{folder}/{NAME}' for folder in FOLDERS] + [NAME]:
        if candidate in tree: return candidate
    folder = next((f for f in FOLDERS if any(path.startswith(f + '/') for path in tree)), FOLDERS[0])
    return f'{folder}/{NAME}'


def tracked(root):
    done = subprocess.run(['git', '-C', str(root), 'ls-files'], capture_output=True, text=True)
    return set(done.stdout.splitlines()) if done.returncode == 0 else set()


def pinned_ids(project):
    """The ids of the rules pinned on the project now; none when it has no registry."""
    return [rule['id'] for rule in registry.load(project)['rules'] if rule['scope']['kind'] == 'pinned' and rule['state'] == 'active']


def _quoted(paths):
    return ', '.join(f'`{path}`' for path in paths)


def _layers_text(layers, gaps):
    if not layers: return []
    rows = [f"| {l['name']} | {l['role'] or ''} | {_quoted(l['folders'])} | {l['files']} | {', '.join(l['allowed']) or 'none'} |" for l in layers]
    told = [f'{gaps} file(s) are in no layer yet.'] if gaps else []
    return ['## The layers', '', '| Layer | Role | Where | Files | May use |', '|---|---|---|---|---|', *rows, '', *told, *([''] if told else [])]


def _areas_text(areas):
    if not areas: return []
    rows = [f"| {a['name']} | {_quoted(a['files'])} | {_quoted(a['entries'])} |" for a in areas]
    return ['## The areas (GitNexus)', '', 'With the map built (`project_map`), each area has a short skill, `gitnexus-area-<area>`.', '',
            '| Area | Its main files | Where to start |', '|---|---|---|', *rows, '']


def _checks_text(drawn):
    """The project's own checks and tests, said once, so no one searches for them."""
    checks = ', '.join(f'`{command}`' for command in drawn['checks']) or 'it declares none'
    tests = next((r['test'] or r['example'] for r in drawn['recipes'] if r['id'] == 'test'), None)
    return ['## The checks', '', f'Before merging: {checks}. Tests: ' + (f'beside `{tests}`.' if tests else 'this project has none yet.'), '']


def _new_file(recipe):
    return f"a new file beside `{recipe['example']}`" if recipe['grows'] == 'added' else f"`{recipe['example']}`"


def _touch_line(recipe):
    steps = [_new_file(recipe), *(f'`{path}`' for path in recipe['touch'] if path != recipe['example'])]
    read_from = f" (Read from the last {recipe['seen']} commits of this kind.)" if recipe['seen'] > 1 else ''
    return '- **Touch, in order:** ' + '; '.join(f'({n}) {step}' for n, step in enumerate(steps, 1)) + '.' + read_from


def _test_line(recipe):
    return [f"- **Test:** `{recipe['test']}`."] if recipe['test'] and recipe['test'] != recipe['example'] else []


def _recipe_text(recipe):
    made = f"{recipe['commit']['sha']}, {recipe['commit']['date']}" if recipe['commit'] else 'from the layout: no commit shows one added'
    return [f"### {recipe['title']}", f"- **Last real example:** `{recipe['example']}` ({made}).",
            f"- **Read only:** {_quoted(recipe['read'])}.", _touch_line(recipe), *_test_line(recipe), '']


def text(drawn, name):
    """The guide's text from `drawn` (extending.draft), for the project called `name`."""
    pinned = [f"Rules pinned on this project hold in every change: {', '.join(drawn['pinned'])} (their words are in your context file)."] if drawn['pinned'] else []
    head = [BEGIN, f'# Extending {name}', '',
            '**Adding anything starts here.** Read the recipe of what you add, not the whole project: it names the files to read and '
            'to touch, in order, taken from how this project really grew.', *pinned, '']
    recipes = [line for recipe in drawn['recipes'] for line in _recipe_text(recipe)]
    missing = [f"**Not in this project yet:** {'; '.join(drawn['missing'])}. Keep the layers above when adding the first one.", ''] if drawn['missing'] else []
    return '\n'.join([*head, *_layers_text(drawn['layers'], drawn['gaps']), *_areas_text(drawn['areas']), *_checks_text(drawn), '## Recipes', '', *recipes, *missing, END]) + '\n'


def _keep_below(old, new):
    return new + old.split(END, 1)[1].lstrip('\n') if END in old else new + ('\n' + old if old.strip() else '')


def write(root, drawn):
    """The guide and its pointer written in `root` (a copy); the files whose text changed."""
    root = Path(root)
    tree = tracked(root)
    path = place(tree)
    target = root / path
    old = target.read_text(encoding='utf-8') if target.is_file() else ''
    written = []
    new = _keep_below(old, text(drawn, root.name))
    if new != old:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new, encoding='utf-8')
        written.append(path)
    line = f'Adding anything to this project starts at `{path}`: the files to read and to touch, in order, per kind of addition.'
    return written + context_files.hold_block(root, POINTER_BEGIN, POINTER_END, line)


def drawn_from_report(root, report, project=None):
    """What the guide says for the copy at `root`, from the check's folder `report`; None when no check has read its layers."""
    if not report or not (Path(report) / 'layers.json').is_file(): return None
    record = read_json(Path(report) / 'layers.json', {}) or {}
    tree = tracked(root) or {row['path'] for row in record.get('map') or []}
    return extending.draft(root, report, tree, record, pinned_ids(project) if project else ())


def give_map(project, home):
    """GitNexus's map of the person's project, with their yes: the index under `home`, the skills in its .claude/skills, kept
    from git by its own .git/info/exclude, and its MCP registered for this project alone when Claude Code is there."""
    project = Path(project)
    made = gitnexus.make_map(project, home, project / '.claude' / 'skills')
    excluded = project / '.git' / 'info' / 'exclude'
    if excluded.parent.is_dir() and SKILLS_IGNORED not in (excluded.read_text(encoding='utf-8') if excluded.is_file() else ''):
        with excluded.open('a', encoding='utf-8') as file: file.write(f'{SKILLS_IGNORED}\n')
    command = ['claude', 'mcp', 'add', '--scope', 'local', '--env', f"GITNEXUS_HOME={made['registry']}", 'gitnexus', '--', 'gitnexus', 'mcp']
    registered = bool(shutil.which('claude')) and run(command, cwd=project, timeout=60)[0] == 0
    return {**made, 'registered': registered, 'register_yourself': None if registered else shlex.join(command)}


def written_ignored(root, written):
    """The files of `written` git would not take (an ignored context file): they stay out of the branch."""
    return [path for path in written if subprocess.run(['git', '-C', str(root), 'check-ignore', '-q', '--no-index', path]).returncode == 0]

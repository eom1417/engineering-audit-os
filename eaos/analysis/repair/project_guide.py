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
    told = [f'{gaps} file(s) are in no layer yet.', ''] if gaps else []
    return ['## The layers', '', *_layer_rows(layers), '', *told]


def _layer_rows(layers):
    """A project's declared rules say what a layer must not use, the shorter list; a reference type what it may."""
    denies = any(layer['denied'] for layer in layers)
    head = 'Must not use' if denies else 'May use'
    rows = [f"| {l['name']} | {_quoted(l['folders'])} | {l['files']} | {', '.join(l['denied'] if denies else l['allowed']) or '-'} |" for l in layers]
    return [f'| Layer | Where | Files | {head} |', '|---|---|---|---|', *rows]


def _areas_text(areas):
    if not areas: return []
    rows = [f"| {a['name']} | {_quoted(a['files'])} | {_quoted(a['entries'])} |" for a in areas]
    return ['## The areas', '', '| Area | Its main files | Where to start |', '|---|---|---|', *rows, '']


def _places_text(recipes):
    rows = [f"| {r['title']} | `{r['home']}` | `{r['example']}` |" for r in recipes if r['grows'] == 'added']
    if not rows: return []
    return ['## Where new code goes', '', 'New code goes here, not in a new place; a new place updates this table.', '',
            '| Kind | Its folder | Example |', '|---|---|---|', *rows, '']


def _reuse_text(reuse):
    if not reuse: return []
    return ['## Reuse first', '', 'Before writing a helper, look here: the files most of the project already uses.', '',
            *(f"- `{row['path']}` ({row['users']} files use it)" for row in reuse), '']


def _sensitive_text(sensitive):
    if not sensitive: return []
    return ['## Sensitive files', '', 'Complex and often changed: read them whole, change them in small steps, run every check.', '',
            *(f"- `{row['path']}` ({row['commits']} commits, complexity {row['complexity']})" for row in sensitive), '']


def _features_text(features):
    if not features: return []
    rows = [f"| {f['name']} | {_quoted(f['surfaces'])} | {', '.join(f['tables']) or '-'} |" for f in features]
    return ['## Features today', '', '| Feature | Where it starts | Its data |', '|---|---|---|', *rows, '']


def _checks_text(drawn):
    """The project's own checks and where its tests live, said once, so no one searches for them."""
    checks = ', '.join(f'`{command}`' for command in drawn['checks']) or 'it declares none'
    home = drawn['tests']
    tests = f"{home['count']} tests, in {_quoted(f'{folder}/' for folder in home['folders'])}." if home['count'] else 'this project has none yet.'
    return ['## The checks', '', f'Before merging: {checks}.', f'Tests: {tests}', '']


def _feature_text(drawn):
    titles = {recipe['id']: recipe['title'] for recipe in drawn['recipes']}
    steps = [f'{n}. {titles[step]}: its recipe below.' for n, step in enumerate(drawn['feature_steps'], 1)]
    if not steps: return []
    return ['## Add a new feature', '', 'Reuse first; then, in this order:', *steps, '',
            'A feature is finished when it can be reached from where people use it, it keeps the layers, it wrote nothing '
            '"Reuse first" already has, its tests and the checks pass, and this guide says it.', '']


def _new_file(recipe):
    return f"a new file beside `{recipe['example']}`" if recipe['grows'] == 'added' else f"`{recipe['example']}`"


def _touch_line(recipe):
    steps = [_new_file(recipe), *(f'`{path}`' for path in recipe['touch'] if path != recipe['example'])]
    read_from = f" (Read from the last {recipe['seen']} commits of this kind.)" if recipe['seen'] > 1 else ''
    return '- **Touch, in order:** ' + '; '.join(f'({n}) {step}' for n, step in enumerate(steps, 1)) + '.' + read_from


def _test_line(recipe):
    return [f"- **Test:** `{recipe['test']}`."] if recipe['test'] and recipe['test'] != recipe['example'] else []


def _keep_line(recipe):
    if not recipe.get('layer'): return []
    denied = f": it must not use {', '.join(recipe['denied'])}" if recipe['denied'] else ''
    return [f"- **What must stay true:** it belongs to the layer {recipe['layer']}{denied}."]


def _recipe_text(recipe):
    made = f"{recipe['commit']['sha']}, {recipe['commit']['date']}" if recipe['commit'] else 'from the layout: no commit shows one added'
    return [f"### {recipe['title']}", f"- **Last real example:** `{recipe['example']}` ({made}).",
            f"- **Read only:** {_quoted(recipe['read'])}.", _touch_line(recipe), *_keep_line(recipe), *_test_line(recipe), '']


def _closing_text(drawn):
    heavy = ['## Do not read by default', '', 'Too large to read by chance; open one only when the task names it: '
             + _quoted(f'{folder}/' for folder in drawn['heavy']) + '.', ''] if drawn['heavy'] else []
    missing = ['## Not in this project yet', '', '; '.join(drawn['missing']) + '. Keep the layers above when adding the first one.', ''] if drawn['missing'] else []
    departures = ['## Known departures', '', 'Where the project breaks its own structure today. Follow the tables for new code, not these.', '',
                  *(f'- {said}' for said in drawn['departures']), ''] if drawn['departures'] else []
    return [*heavy, *missing, *departures]


def text(drawn, name):
    """The guide's text from `drawn` (extending.draft), for the project called `name`."""
    pinned = [f"Rules pinned on this project hold in every change: {', '.join(drawn['pinned'])} (their words are in your context file)."] if drawn['pinned'] else []
    head = [BEGIN, f'# Extending {name}', '',
            '**Adding anything starts here.** Read the recipe of what you add, then its example; read further only if the recipe '
            'leaves a question. It is taken from how this project really grew.', *pinned, '']
    recipes = [line for recipe in drawn['recipes'] for line in _recipe_text(recipe)]
    return '\n'.join([*head, *_layers_text(drawn['layers'], drawn['gaps']), *_places_text(drawn['recipes']), *_reuse_text(drawn['reuse']),
                      *_sensitive_text(drawn['sensitive']), *_features_text(drawn['features']), *_areas_text(drawn['areas']), *_checks_text(drawn),
                      *_feature_text(drawn), '## Recipes', '', *recipes, *_closing_text(drawn), END]) + '\n'


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

"""Build a project from its plan, driven by the person's AI assistant (docs/BUILD-FROM-PLAN.md).

The same way as fixing (eaos/agent_tools.py), from the other end: there is no current state to audit, so the target
comes from the plan, and the gap is the whole build.

  blueprint_start   the plan, from any file or pasted text, saved in ~/EAOS/<project>/blueprint/SOURCE.md
  blueprint_spec    the product spec the assistant wrote from it: checked, with what is missing and what to ask
  blueprint_design  the stack, the target architecture, the project's own eaos.policy.json and the build plan
  build_start       (after the person agrees) a milestone of build cards in an isolated copy of the project
  build_edit        one card's files: kept only when every gate passes (layers, planned folders, vendors in their
                    adapter, no import cycle, no broken reference, no copied code, and the project's own typecheck,
                    lint and tests); otherwise taken back with the reasons
  build_skip / build_finish   close the milestone (dead code too, now), hand it over as the branch eaos/build-N,
                    stacked on the one before, and open the next

At the end the person takes the last branch in (accept, from agent_tools) and every milestone comes with it.
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import agent_tools, blueprint, guided

CONSENT = ('May I build your project from its blueprint in a separate copy, milestone by milestone, checking every '
           'step, and hand each milestone to your project as a new branch (nothing else in your project changes)?')
CHECK_SCRIPTS = ('typecheck', 'lint', 'test')


def folder(state):
    return guided.outputs(state) / 'blueprint'


def _read(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else default


def _write(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def _git(where, *args):
    return subprocess.run(['git', '-C', str(where), *args], capture_output=True, text=True)


def _state(project):
    state = agent_tools.project_state(project, new=True)
    if state.get('mode') != 'build':
        state['mode'] = 'build'
        guided.save(state)
    return state


# ---------------------------------------------------------------- the blueprint

def blueprint_start(source=None, text=None, project=None):
    state = _state(project)
    plan = blueprint.read_source(source, text)
    where = folder(state)
    where.mkdir(parents=True, exist_ok=True)
    (where / 'SOURCE.md').write_text(plan + '\n', encoding='utf-8')
    catalogue = blueprint.stacks()['concerns']
    return {'saved': str(where / 'SOURCE.md'), 'characters': len(plan), 'plan_text': plan[:40000], 'more': len(plan) > 40000,
            'spec_format': blueprint.SPEC,
            'stack_catalogue': {concern: {'title': entry['title'], 'recommended': entry['recommended'],
                                          'options': {key: option['why'] for key, option in entry['options'].items()}}
                                for concern, entry in catalogue.items()},
            'what_now': 'Read the plan whole. Write the product spec in spec_format: group the features into modules with one '
                        'responsibility each, give every piece of data one owning module, turn each feature into checkable '
                        'acceptance criteria. Where the plan is thin, research what products of this kind need and add it as a '
                        'decision with options and your recommendation. Ask the person only what they must decide (choices, '
                        'with your recommendation first), including whether they have technology preferences. Then call '
                        'blueprint_spec with the spec.'}


def blueprint_spec(spec, project=None):
    state = _state(project)
    problems, questions = blueprint.validate_spec(spec)
    _write(folder(state) / 'product-spec.json', spec)
    state['blueprint'] = {**(state.get('blueprint') or {}), 'spec_ok': not problems, 'open_questions': len(questions)}
    guided.save(state)
    return {'problems': problems, 'questions': questions,
            'what_now': ('Fix these in the spec and call blueprint_spec again.' if problems else
                         'Ask the person these questions (choices, your recommendation first), put their answers in the spec '
                         '(decisions[].chosen, stack_preferences), call blueprint_spec again, then blueprint_design.' if questions else
                         'The spec is complete: call blueprint_design.')}


def blueprint_design(stack=None, project=None):
    state = _state(project)
    spec = _read(folder(state) / 'product-spec.json')
    if spec is None: return {'status': 'no_spec', 'what_now': 'Call blueprint_start, then blueprint_spec.'}
    problems, questions = blueprint.validate_spec(spec)
    if problems: return {'status': 'spec_incomplete', 'problems': problems, 'what_now': 'Fix the spec with blueprint_spec first.'}
    chosen = blueprint.choose_stack(spec, stack)
    built = blueprint.design(spec, chosen)
    where = folder(state)
    _write(where / 'stack.json', chosen)
    _write(where / 'target-architecture.json', built['architecture'])
    _write(where / 'eaos.policy.json', built['policy'])
    _write(where / 'plan.json', built['plan'])
    (where / 'BLUEPRINT.md').write_text(blueprint.document(spec, chosen, built) + '\n', encoding='utf-8')
    publish(state, spec, chosen, built)
    state['blueprint'] = {**(state.get('blueprint') or {}), 'designed': agent_tools._now(),
                          'cards': len(built['plan']['tasks']), 'milestones': [m['id'] for m in built['plan']['milestones']]}
    state.setdefault('built', [])
    guided.save(state)
    return {'status': 'designed', 'blueprint': str(where / 'BLUEPRINT.md'), 'for_the_person': str(guided.outputs(state) / 'BLUEPRINT.html'),
            'stack': {concern: {'chosen': row['name'], 'why': row['why'], 'change_later': row['switch']} for concern, row in chosen.items()},
            'layers': sorted(built['policy']['layers']), 'rules': [r['reason'] for r in built['policy']['rules']],
            'vendors_kept_in_one_place': built['policy']['vendors'],
            'milestones': [{'id': m['id'], 'name': m['name'], 'cards': len(m['tasks'])} for m in built['plan']['milestones']],
            'open_questions': questions,
            'what_now': 'Tell the person, simply, the parts, the technologies and why, and the order of the build. Then call '
                        'build_start (it asks their agreement once).'}


def publish(state, spec=None, stack=None, built=None):
    """BLUEPRINT.html in the outputs folder, beside README.md: the blueprint and the build's progress for a person."""
    where = folder(state)
    spec = spec or _read(where / 'product-spec.json')
    stack = stack or _read(where / 'stack.json')
    if not (spec and stack): return None
    built = built or {'policy': _read(where / 'eaos.policy.json'), 'plan': _read(where / 'plan.json')}
    target = guided.outputs(state) / 'BLUEPRINT.html'
    target.write_text(blueprint.page(spec, stack, built, state.get('built')), encoding='utf-8')
    return target


def open_blueprint(project=None, show=True):
    state = _state(project)
    page = publish(state)
    if page is None: return {'status': 'no_blueprint', 'what_now': 'Draw the blueprint first: blueprint_start, blueprint_spec, blueprint_design.'}
    opened = False
    if show:
        import webbrowser
        try: opened = webbrowser.open(page.resolve().as_uri())
        except Exception: opened = False
    return {'blueprint_for_people': str(page), 'opened_in_browser': opened, 'outputs_folder': str(guided.outputs(state))}


# ---------------------------------------------------------------- the build

def _plan(state):
    return _read(folder(state) / 'plan.json')


def _cards(state):
    return {card['id']: card for card in (_plan(state) or {}).get('tasks', [])}


def _ensure_git(state):
    """A project folder that is not a git repository yet becomes one, with one first commit: the branches of the build
    need a history to hang on. Nothing else in the folder is touched."""
    project = Path(state['project'])
    if (project / '.git').exists() and _git(project, 'rev-parse', 'HEAD').returncode == 0: return False
    if not (project / '.git').exists(): _git(project, 'init', '-q')
    readme = project / 'README.md'
    if not readme.exists():
        spec = _read(folder(state) / 'product-spec.json', {})
        readme.write_text(f"# {spec.get('name') or project.name}\n\n{spec.get('summary') or ''}\n", encoding='utf-8')
    _git(project, 'add', 'README.md')
    _git(project, '-c', 'user.name=EAOS', '-c', 'user.email=eaos@localhost', 'commit', '-q', '--allow-empty', '-m', 'Start the project')
    return True


def build_start(project=None, person_agreed=False):
    state = _state(project)
    if state.get('open_build'):
        build = state['open_build']
        return {'status': 'open', 'milestone': build['milestone'], 'to_do': _left(build), 'kept': list(build['kept']),
                'what_now': 'This milestone is open: build the cards left with build_edit, then build_finish.'}
    plan = _plan(state)
    if not plan: return {'status': 'no_blueprint', 'what_now': 'Call blueprint_start, blueprint_spec and blueprint_design first.'}
    if not person_agreed and not (state.get('consent') or {}).get('build'):
        return {'status': 'needs_agreement', 'ask_the_person': CONSENT,
                'what_now': 'Ask the person this, in their language. Only if they say yes, call build_start with person_agreed=true.'}
    state['consent'] = {**(state.get('consent') or {}), 'build': True, 'at': agent_tools._now()}
    started = _ensure_git(state)
    done = {card for record in state.get('built') or [] for card in record['kept'] + list(record['skipped'])}
    milestone = next((m for m in plan['milestones'] if any(c not in done for c in m['tasks'])), None)
    if milestone is None:
        guided.save(state)
        return {'status': 'built', 'what_now': 'Every milestone is built. Ask the person whether to take the last branch in '
                                               '(accept with person_agreed=true), then offer the audit of the built project.'}
    from .live_setup import authorize
    runtime = guided.runtime_of(state)
    who = _git(state['project'], 'config', 'user.name').stdout.strip() or os.environ.get('USER') or 'the owner'
    authorize(state['project'], runtime, who)
    number = len(state.get('built') or []) + 1
    root = runtime / 'candidates' / f'BUILD-{number}'
    shutil.rmtree(root, ignore_errors=True)
    root.parent.mkdir(parents=True, exist_ok=True)
    clone = subprocess.run(['git', 'clone', '-q', '--no-hardlinks', state['project'], str(root)], capture_output=True, text=True)
    if clone.returncode: raise RuntimeError(f'could not copy the project: {clone.stderr[-300:]}')
    previous = (state.get('built') or [None])[-1]
    if previous and previous.get('branch'):             # stacked: this milestone starts where the last one ended
        _git(root, 'fetch', '-q', state['project'], f"{previous['branch']}:{previous['branch']}")
        _git(root, 'checkout', '-q', previous['branch'])
    _git(root, 'checkout', '-q', '-b', f'eaos/build-{number}')
    if number == 1: _commit_blueprint(state, root)
    build = {'number': number, 'milestone': milestone['id'], 'root': str(root), 'base': _git(root, 'rev-parse', 'HEAD').stdout.strip(),
             'cards': milestone['tasks'], 'kept': {}, 'skipped': {}, 'installed': None}
    state['open_build'] = build
    guided.save(state)
    cards = _cards(state)
    return {'status': 'opened', 'milestone': {'id': milestone['id'], 'name': milestone['name']}, 'copy': str(root),
            'git_started': started, 'cards': [_brief(cards[c]) for c in milestone['tasks']],
            'rules': _read(Path(root) / 'eaos.policy.json', {}).get('rules'),
            'what_now': 'Build the cards in order, each with build_edit: only the files that card needs, in the folders it names, '
                        'with its tests, the least code that meets its acceptance. Reuse what exists (shared/, web/src/ui, '
                        'web/src/api, the adapters) instead of writing it again. Read the copy with build_read. A card that '
                        'fails comes back with the reasons: fix them and send it again. Then build_finish.'}


def _commit_blueprint(state, root):
    """The target as part of the project: its policy at the top, the blueprint in docs/blueprint/."""
    where = folder(state)
    shutil.copyfile(where / 'eaos.policy.json', Path(root) / 'eaos.policy.json')
    docs = Path(root) / 'docs' / 'blueprint'
    docs.mkdir(parents=True, exist_ok=True)
    for name in ('BLUEPRINT.md', 'product-spec.json', 'stack.json', 'target-architecture.json', 'plan.json'):
        if (where / name).is_file(): shutil.copyfile(where / name, docs / name)
    _git(root, 'add', '-A')
    _git(root, '-c', 'user.name=EAOS', '-c', 'user.email=eaos@localhost', 'commit', '-q', '-m',
         'The blueprint: target structure, policy and build plan (EAOS)')


def _brief(card):
    return {k: card.get(k) for k in ('id', 'title', 'module', 'feature', 'paths', 'acceptance', 'tests', 'depends_on', 'why', 'budget_lines')}


def _left(build):
    return [c for c in build['cards'] if c not in build['kept'] and c not in build['skipped']]


def _open(state):
    build = state.get('open_build')
    if not build: raise LookupError('no milestone is open: call build_start')
    return build


def build_read(path, project=None, start=1, end=None):
    state = _state(project)
    root = Path(_open(state)['root'])
    file = agent_tools._inside(root, path or '.') if path not in ('', '.') else root
    if file.is_dir():
        return {'folder': path or '.', 'entries': sorted(p.name + ('/' if p.is_dir() else '') for p in file.iterdir()
                                                         if p.name not in ('.git', 'node_modules'))[:500]}
    if not file.is_file(): raise ValueError(f'{path} does not exist in the copy yet')
    lines = file.read_text(encoding='utf-8', errors='replace').splitlines()
    start = max(int(start or 1), 1)
    end = min(int(end or len(lines)), len(lines), start + 1999)
    return {'path': path, 'lines': len(lines), 'text': '\n'.join(f'{n:>5}  {lines[n - 1]}' for n in range(start, end + 1))}


def build_edit(card, edits, summary='', project=None):
    state = _state(project)
    build = _open(state)
    if card not in build['cards'] and card != 'FIX':
        raise ValueError(f"{card} is not in milestone {build['milestone']}: {', '.join(build['cards'])} (or FIX for a correction)")
    if not edits: raise ValueError('no edit was sent')
    return agent_tools._start('build_edit', state, {'card': card, 'edits': edits, 'summary': summary}, runner='eaos.build_tools')


def _checks(root, build, progress):
    """The project's own scripts, on the copy: install when the manifests changed, then typecheck, lint and test."""
    root = Path(root)
    manifest = root / 'package.json'
    if not manifest.is_file(): return [], build
    scripts = json.loads(manifest.read_text(encoding='utf-8')).get('scripts') or {}
    stamp = ''.join(sorted(_git(root, 'ls-files', '-s', '--', '*package.json', 'package-lock.json').stdout.split()))
    env = {k: v for k, v in os.environ.items() if k in ('PATH', 'HOME', 'LANG', 'TMPDIR', 'PLAYWRIGHT_BROWSERS_PATH')}
    env.update(CI='1', NODE_ENV='test')
    failed = []
    if build.get('installed') != stamp or not (root / 'node_modules').is_dir():
        progress(0, 4, 'installing the libraries')
        done = subprocess.run(['npm', 'install', '--no-audit', '--no-fund', '--loglevel=error'], cwd=root, capture_output=True,
                              text=True, timeout=1800, env=env)
        if done.returncode:
            return [{'gate': 'install', 'where': 'package.json', 'what': 'npm install failed: ' + (done.stdout + done.stderr)[-1500:]}], build
        build = {**build, 'installed': stamp}
    for index, script in enumerate(CHECK_SCRIPTS, start=1):
        if script not in scripts:
            failed.append({'gate': 'scripts', 'where': 'package.json', 'what': f'there is no "{script}" script: the skeleton declares it'})
            continue
        progress(index, 4, f'npm run {script}')
        done = subprocess.run(['npm', 'run', script], cwd=root, capture_output=True, text=True, timeout=1800, env=env)
        if done.returncode:
            failed.append({'gate': script, 'where': 'package.json', 'what': f'npm run {script} failed: ' + (done.stdout + done.stderr)[-2000:]})
    return failed, build


def _gates(state, root, card=None, closing=False, progress=lambda *_: None):
    from .facts.run import collect
    rules = _read(Path(root) / 'eaos.policy.json') or _read(folder(state) / 'eaos.policy.json')
    problems, build = _checks(root, state['open_build'], progress)
    state['open_build'] = build
    with tempfile.TemporaryDirectory(prefix='eaos-build-facts-') as out:
        progress(3, 4, 'reading the structure: layers, cycles, copies' + (', dead code' if closing else ''))
        collect(Path(root).resolve(), out)
        problems += blueprint.build_problems(root, out, rules, closing=closing)
    if card and card != 'FIX':
        added = _git(root, 'diff', '--name-only', '--diff-filter=A', 'HEAD~1', 'HEAD').stdout.split()
        kind = _cards(state)[card]['pattern']
        if kind != 'build_skeleton' and not any('.test.' in p or '.spec.' in p or p.startswith('e2e/') for p in added):
            problems.append({'gate': 'tests', 'where': card, 'what': 'the card adds no test: its acceptance criteria are checked by tests'})
    return problems


def _build_edit_job(project, arguments, progress):
    state = guided.load(project)
    build = state['open_build']
    root, card = Path(build['root']), arguments['card']
    try:
        changed = agent_tools._apply(root, arguments['edits'])
        _git(root, 'add', '-A')
        title = card if card == 'FIX' else f"{card}: {_cards(state)[card]['title'][:70]}"
        done = _git(root, '-c', 'user.name=EAOS', '-c', 'user.email=eaos@localhost', 'commit', '-q', '-m',
                    f"{title}\n\n{arguments.get('summary') or ''}\n\nBuilt with EAOS.")
        if done.returncode: raise ValueError('the edit changed nothing')
    except (ValueError, OSError, UnicodeDecodeError) as problem:
        _git(root, 'checkout', '-q', '--', '.'); _git(root, 'clean', '-fdq', '-e', 'node_modules')
        return {'card': card, 'kept': False, 'why': [f'the edit could not be applied: {problem}'], 'what_now': 'Nothing changed: correct the edit.'}
    problems = _gates(state, root, card, progress=progress)
    if problems:
        _git(root, 'reset', '-q', '--hard', 'HEAD~1'); _git(root, 'clean', '-fdq', '-e', 'node_modules')
        guided.save(state)
        return {'card': card, 'kept': False, 'files': changed, 'why': problems[:25], 'more_problems': max(0, len(problems) - 25),
                'what_now': 'The change was taken back. Fix every reason (keep the structure the blueprint names) and send the '
                            'card again with build_edit, whole.'}
    if card != 'FIX': state['open_build']['kept'][card] = _git(root, 'rev-parse', 'HEAD').stdout.strip()
    guided.save(state)
    left = _left(state['open_build'])
    return {'card': card, 'kept': True, 'files': changed, 'left': left,
            'what_now': 'Next card with build_edit.' if left else 'Every card of this milestone is built: call build_finish.'}


def build_skip(card, reason, project=None):
    state = _state(project)
    build = _open(state)
    if card not in build['cards']: raise ValueError(f"{card} is not in milestone {build['milestone']}")
    build['skipped'][card] = reason[:300]
    guided.save(state)
    return {'card': card, 'skipped': True, 'left': _left(build)}


def build_finish(project=None):
    state = _state(project)
    build = _open(state)
    if _left(build): return {'status': 'cards_left', 'left': _left(build), 'what_now': 'Build or skip them first.'}
    return agent_tools._start('build_finish', state, {}, runner='eaos.build_tools')


def _build_finish_job(project, arguments, progress):
    state = guided.load(project)
    build = state['open_build']
    root = Path(build['root'])
    # Dead code is judged when the whole build is there: a shared part made early is used by a later milestone.
    last = _plan(state)['milestones'][-1]['id'] == build['milestone']
    problems = _gates(state, root, closing=last, progress=progress)
    guided.save(state)
    if problems:
        return {'delivered': False, 'why': problems[:25],
                'what_now': 'The milestone as a whole breaks these: fix them with build_edit (card="FIX"), then build_finish again.'}
    branch = f"eaos/build-{build['number']}"
    fetched = _git(state['project'], 'fetch', '-q', str(root), f'+{branch}:{branch}')
    if fetched.returncode: raise RuntimeError(f'could not create {branch}: {fetched.stderr[-300:]}')
    record = {'number': build['number'], 'milestone': build['milestone'], 'branch': branch, 'base': build['base'],
              'kept': list(build['kept']), 'skipped': build['skipped'], 'stat': _git(root, 'diff', '--shortstat', f"{build['base']}..HEAD").stdout.strip()}
    state.setdefault('built', []).append(record)
    state.setdefault('waves', []).append({'number': build['number'], 'branch': branch, 'base': build['base'], 'kept': record['kept'],
                                          'failed': build['skipped'], 'stat': record['stat'], 'status': 'applied', 'via': 'build'})
    for older in state['waves'][:-1]:                   # stacked: the last branch holds every milestone before it
        if older.get('via') == 'build' and older.get('status') == 'applied': older['status'] = 'superseded'
    state.pop('open_build', None)
    guided.save(state)
    publish(state)
    remaining = [m['id'] for m in _plan(state)['milestones'] if m['id'] not in {r['milestone'] for r in state['built']}]
    return {'delivered': True, 'branch': branch, 'milestone': build['milestone'], 'changes': record['stat'], 'milestones_left': remaining,
            'what_now': ('Call build_start for the next milestone, without asking the person again.' if remaining else
                         f'Every milestone is built, on {branch}. Tell the person simply what was built and ask whether to take it in '
                         '(accept with person_agreed=true). Then offer the audit of the finished project.')}


def status(project=None):
    from . import handover
    state = _state(project)
    guided.reconcile(state)
    plan, bp, build = _plan(state), state.get('blueprint') or {}, state.get('open_build')
    done = [r['milestone'] for r in state.get('built') or []]
    answer = {'project': state['project'], 'mode': 'build from a plan', 'outputs_folder': str(guided.outputs(state)),
              'blueprint': str(folder(state) / 'BLUEPRINT.md') if bp.get('designed') else None,
              'milestones_built': done, 'open_milestone': build['milestone'] if build else None}
    if not (folder(state) / 'SOURCE.md').is_file(): step = ('blueprint_start', 'no plan has been read yet')
    elif not bp.get('spec_ok'): step = ('blueprint_spec', 'the product spec is missing or incomplete')
    elif not bp.get('designed'): step = ('blueprint_design', 'the target and the build plan are not drawn yet')
    elif build: step = ('build_edit, then build_finish', f"milestone {build['milestone']} is open")
    elif plan and len(done) < len(plan['milestones']): step = ('build_start', 'the next milestone is waiting')
    elif any(w.get('status') == 'applied' for w in state.get('waves') or []):
        step = ('accept', 'everything is built: the person decides whether to take the last branch in')
    else: step = ('audit', 'everything is built and taken in: offer the check of the finished project')
    answer['next'] = {'tool': step[0], 'why': step[1]}
    answer['handover'] = handover.brief(state)
    return answer


JOBS = {'build_edit': _build_edit_job, 'build_finish': _build_finish_job}

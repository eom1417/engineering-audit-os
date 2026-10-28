"""Build a project from its plan, driven by the person's AI assistant (docs/BUILD-FROM-PLAN.md).

The same way as fixing (eaos/journeys/agent_tools/), from the other end: there is no current state to audit, so the target
comes from the plan, and the gap is the whole build.

  blueprint_start   the plan, from any file or pasted text, saved in ~/EAOS/<project>/blueprint/SOURCE.md
  blueprint_spec    the product spec the assistant wrote from it: checked, with what is missing and what to ask
  blueprint_design  the stack, the target architecture, the project's own eaos.policy.json and the build plan
                    (these three, the blueprint, in eaos/journeys/build_from_plan/blueprint.py)
  build_start      (after the person agrees) a milestone of build cards in an isolated copy of the project
  build_edit        one card's files: kept only when every gate passes (layers, planned folders, vendors in their
                    adapter, no import cycle, no broken reference, no copied code, and the project's own typecheck,
                    lint and tests: eaos/journeys/build_from_plan/checks.py); otherwise taken back with the reasons
  build_skip / build_finish   close the milestone (dead code too, now), hand it over as the branch eaos/build-N,
                    stacked on the one before, and open the next

At the end the person takes the last branch in (accept, from agent_tools) and every milestone comes with it.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .. import agent_tools, guided, catalog as journeys
from . import look as build_look
from .blueprint import (_plan, _state, answered, blueprint_answer, blueprint_design, blueprint_spec, blueprint_start,  # noqa: F401
                        folder, open_blueprint, publish, studio_build)
from .checks import _checks, _git, _milestone_tidy
from .look import read as _read

from ...core.project import state as project_state
from ...core.project.state import waiting_batch
from ...core.system.clock import now

HOLDS = 3       # refused finishes of one milestone in a row; the next refusal hands it over with what stays unproven
CONSENT = ('May I build your project from its blueprint in a separate copy, milestone by milestone, checking every '
           'step, and hand each milestone to your project as a new branch (nothing else in your project changes)?')


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


def _open_answer(build):
    return {'status': 'open', 'milestone': build['milestone'], 'to_do': _left(build), 'kept': list(build['kept']),
            'what_now': 'This milestone is open: build the cards left with build_edit, then build_finish.'}


def _next_milestone(state, plan):
    """The first milestone with a card neither kept nor skipped yet, or None."""
    done = {card for record in state.get('built') or [] for card in record['kept'] + list(record['skipped'])}
    return next((m for m in plan['milestones'] if any(c not in done for c in m['tasks'])), None)


def _milestone_copy(state, runtime, number):
    """The isolated copy of milestone `number` on its own branch, stacked on the branch the last milestone ended on."""
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
    return root


def build_start(project=None, person_agreed=False):
    state = _state(project)
    if state.get('open_build'): return _open_answer(state['open_build'])
    plan = _plan(state)
    if not plan: return {'status': 'no_blueprint', 'what_now': 'Call blueprint_start, blueprint_spec and blueprint_design first.'}
    if not person_agreed and not (state.get('consent') or {}).get('build'):
        return {'status': 'needs_agreement', 'ask_the_person': CONSENT,
                'what_now': 'Ask the person this, in their language. Only if they say yes, call build_start with person_agreed=true.'}
    state['consent'] = {**(state.get('consent') or {}), 'build': True, 'at': agent_tools._now()}
    started = _ensure_git(state)
    milestone = _next_milestone(state, plan)
    if milestone is None:
        guided.save(state)
        return {'status': 'built', 'what_now': 'Every milestone is built. Ask the person whether to take the last branch in '
                                               '(accept with person_agreed=true), then offer the audit of the built project.'}
    from ...live.app.setup import authorize, owner
    runtime = project_state.runtime_of(state)
    authorize(state['project'], runtime, owner(state['project']))
    number = len(state.get('built') or []) + 1
    root = _milestone_copy(state, runtime, number)
    build = {'number': number, 'milestone': milestone['id'], 'root': str(root), 'base': _git(root, 'rev-parse', 'HEAD').stdout.strip(),
             'cards': milestone['tasks'], 'kept': {}, 'skipped': {}, 'installed': None, 'began': now('milliseconds')}
    state['open_build'] = build
    guided.save(state)
    publish(state)
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
    for source in [where / name for name in ('BLUEPRINT.md', 'product-spec.json', 'stack.json', 'plan.json')] + \
            [guided.report_of(state) / 'target-architecture.json']:
        if source.is_file(): shutil.copyfile(source, docs / source.name)
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
    if file.is_dir(): return _folder_listing(path, file)
    if not file.is_file(): raise ValueError(f'{path} does not exist in the copy yet')
    lines = file.read_text(encoding='utf-8', errors='replace').splitlines()
    start = max(int(start or 1), 1)
    end = min(int(end or len(lines)), len(lines), start + 1999)
    return {'path': path, 'lines': len(lines), 'text': '\n'.join(f'{n:>5}  {lines[n - 1]}' for n in range(start, end + 1))}


def _folder_listing(path, folder_path):
    """A folder of the copy: its entries, sub-folders marked with '/', without .git and node_modules."""
    return {'folder': path or '.', 'entries': sorted(p.name + ('/' if p.is_dir() else '') for p in folder_path.iterdir()
                                                     if p.name not in ('.git', 'node_modules'))[:500]}


def build_edit(card, edits, summary='', project=None):
    state = _state(project)
    build = _open(state)
    skipped = {c for record in state.get('built') or [] for c in record['skipped']}       # built late: a requirement waits on it
    if card not in build['cards'] and card not in skipped and card != 'FIX':
        raise ValueError(f"{card} is not in milestone {build['milestone']}: {', '.join(build['cards'])} (or FIX for a correction)")
    if not edits: raise ValueError('no edit was sent')
    return agent_tools._start('build_edit', state, {'card': card, 'edits': edits, 'summary': summary}, runner='eaos.journeys.build_from_plan.steps')


def _gates(state, root, card=None, closing=False, progress=lambda *_: None):
    """The build's gates on the copy: its own scripts, then the gates every change passes (eaos/analysis/repair/gates.py) against
    nothing before it, held to the blueprint's policy: the fast security engines on every card, CodeQL too when a
    milestone closes, where it may run; dead code once the milestone closes, when the cards after can no longer use it;
    the repository's craft and context on the whole copy at each milestone's proof (M8.7)."""
    from ..fix.execute import GATE_ENGINES
    from ...facts.run import collect
    from ...analysis.repair.gates import found
    rules = _read(Path(root) / 'eaos.policy.json') or _read(folder(state) / 'eaos.policy.json')
    problems, build = _checks(root, state['open_build'], progress, project_state.runtime_of(state) / 'browsers' if closing else None)
    state['open_build'] = build
    changed = _git(root, 'ls-files').stdout.split() if closing else _git(root, 'diff', '--name-only', 'HEAD~1', 'HEAD').stdout.split()
    with tempfile.TemporaryDirectory(prefix='eaos-build-facts-') as out:
        progress(3, 4, 'reading the structure and security: layers, cycles, copies, weaknesses' + (', dead code' if closing else ''))
        collect(Path(root).resolve(), out, engines=list(GATE_ENGINES) + (['codeql'] if closing else []))
        problems += found(None, out, changed, rules, dead=closing)
        problems += [p for p in _milestone_tidy(root, out, card, closing) if p not in problems]
    if card and card != 'FIX': problems += _untested(state, root, card)
    return problems


def _untested(state, root, card):
    """The card's problem when its commit adds no test (its skeleton aside)."""
    added = _git(root, 'diff', '--name-only', '--diff-filter=A', 'HEAD~1', 'HEAD').stdout.split()
    if _cards(state)[card]['pattern'] == 'build_skeleton' or any('.test.' in p or '.spec.' in p or p.startswith('e2e/') for p in added): return []
    return [{'gate': 'tests', 'where': card, 'what': 'the card adds no test: its acceptance criteria are checked by tests'}]


def _build_edit_job(project, arguments, progress):
    state = project_state.load(project)
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
    publish(state)
    left = _left(state['open_build'])
    return {'card': card, 'kept': True, 'files': changed, 'left': left,
            'what_now': 'Next card with build_edit.' if left else 'Every card of this milestone is built: call build_finish.'}


def build_skip(card, reason, project=None):
    state = _state(project)
    build = _open(state)
    if card not in build['cards']: raise ValueError(f"{card} is not in milestone {build['milestone']}")
    build['skipped'][card] = reason[:300]
    guided.save(state)
    publish(state)
    return {'card': card, 'skipped': True, 'left': _left(build)}


def build_finish(project=None):
    state = _state(project)
    build = _open(state)
    if _left(build): return {'status': 'cards_left', 'left': _left(build), 'what_now': 'Build or skip them first.'}
    return agent_tools._start('build_finish', state, {}, runner='eaos.journeys.build_from_plan.steps')


def _build_finish_job(project, arguments, progress):
    state = project_state.load(project)
    build = state['open_build']
    root = Path(build['root'])
    # Dead code is judged when the whole build is there: a shared part made early is used by a later milestone.
    last = _plan(state)['milestones'][-1]['id'] == build['milestone']
    problems, look = _held(state, root, build, last, progress)
    if (held := _holding(state, build, problems)):
        return {**held, 'why': problems[:25],
                'what_now': 'The milestone as a whole breaks these: fix them with build_edit (card="FIX"; a requirement no kept card '
                            'builds: build the card it names with build_edit; a design departure: follow DESIGN.md; a load scenario: '
                            'make that route fast under load, an index or less work per request), then build_finish again.'}
    # pictured on the copy before the state is saved: a save removes a delivered build's copy (waves/live_map.py saved)
    look = look or (build_look.look(state, root, progress) if _screens(state, build) else None)
    branch = f"eaos/build-{build['number']}"
    fetched = _git(state['project'], 'fetch', '-q', str(root), f'+{branch}:{branch}')
    if fetched.returncode: raise RuntimeError(f'could not create {branch}: {fetched.stderr[-300:]}')
    record = _record_built(state, build, branch, root, [p['what'] if isinstance(p, dict) else str(p) for p in problems])
    state.pop('open_build', None)
    guided.save(state)
    publish(state)
    if last: shutil.rmtree(project_state.runtime_of(state) / 'browsers', ignore_errors=True)    # fetched for the journeys alone
    remaining = _not_built(state)
    return {'delivered': True, 'branch': branch, 'milestone': build['milestone'], 'changes': record['stat'], 'milestones_left': remaining,
            **_unproven(record),
            'look': look,
            'what_now': ('Call build_start for the next milestone, without asking the person again; what `look` found (departures '
                         'from DESIGN.md, screen problems, a Lighthouse score under 90) is fixed there first, with build_edit '
                         'card="FIX".' if remaining else
                         f'Every milestone is built, on {branch}. Tell the person simply what was built (and, when `look` names '
                         'stages not done, that the screens were not checked and why) and ask whether to take it in '
                         '(accept with person_agreed=true). Then offer the audit of the finished project.')}


def _screens(state, build):
    """Whether the milestone's kept cards made a screen (a file under web/)."""
    return any(p.startswith('web/') for c in build['kept'] for p in _cards(state)[c]['paths'])


def _holding(state, build, problems):
    """The answer that holds the milestone back while it is refused fewer than HOLDS times in a row, else None."""
    build['refused'] = build.get('refused', 0) + 1 if problems else 0
    guided.save(state)
    return {'delivered': False, 'refused': f"{build['refused']} of {HOLDS}"} if problems and build['refused'] < HOLDS else None


def _unproven(record):
    return ({'unproven': record['unproven'][:25], 'why_delivered': f'refused {HOLDS} times in a row: handed over with what stays '
             'unproven, for the person to decide; tell them plainly'} if record.get('unproven') else {})


def _record_built(state, build, branch, root, unproven=()):
    """The milestone handed over on `branch`, recorded among the built ones and the waves (where it supersedes the
    milestones before it), with what stays `unproven` when it was handed over refused (HOLDS); its record."""
    record = {'number': build['number'], 'milestone': build['milestone'], 'branch': branch, 'base': build['base'],
              'kept': list(build['kept']), 'skipped': build['skipped'], 'stat': _git(root, 'diff', '--shortstat', f"{build['base']}..HEAD").stdout.strip(),
              'began': build.get('began'), 'ended': now('milliseconds'), **({'unproven': list(unproven)} if unproven else {})}
    state.setdefault('built', []).append(record)
    state.setdefault('waves', []).append({'number': build['number'], 'branch': branch, 'base': build['base'], 'kept': record['kept'],
                                          'failed': build['skipped'], 'stat': record['stat'], 'status': 'applied', 'via': 'build',
                                          **({'unproven': record['unproven']} if unproven else {})})
    for older in state['waves'][:-1]:                   # stacked: the last branch holds every milestone before it
        if older.get('via') == 'build' and older.get('status') == 'applied': older['status'] = 'superseded'
    return record


def _not_built(state):
    """The ids of the plan's milestones not built yet."""
    built = {r['milestone'] for r in state['built']}
    return [m['id'] for m in _plan(state)['milestones'] if m['id'] not in built]


def _held(state, root, build, last, progress):
    """(what holds a milestone back, the finished product's look): its gates; the last one's requirements and screens too,
    pictured before it is delivered."""
    problems = _gates(state, root, closing=last, progress=progress)
    if not last: return problems, None
    problems += _unbuilt(state, build)
    look = None if problems else build_look.look(state, root, progress, final=True)
    return problems + build_look.unusable(look), look


def _unbuilt(state, build):
    """The plan's requirements no kept card builds (requirements[].covered_by, the cards' `covers`): the last milestone
    is not delivered while one is left."""
    kept, covering = _kept(state, build), _covering(_plan(state))
    spec = _read(folder(state) / 'product-spec.json', {})
    return [{'gate': 'requirement', 'where': r['id'], 'what': f"requirement {r['id']} ({str(r.get('text') or '')[:120]}) is built by no "
             f"kept card: build {', '.join(covering.get(r['id']) or ['a card for it'])}"}
            for r in spec.get('requirements') or [] if isinstance(r, dict) and not kept & set(covering.get(r.get('id')) or [])]


def _kept(state, build):
    """Every card kept: by the milestones built and by the open one."""
    return {c for record in state.get('built') or [] for c in record['kept']} | set(build['kept'])


def _covering(plan):
    """{requirement id: the ids of the cards that cover it}."""
    covering = {}
    for card in plan['tasks']:
        for requirement in card.get('covers') or []: covering.setdefault(requirement, []).append(card['id'])
    return covering


def status(project=None):
    from .. import handover
    state = _state(project)
    guided.reconcile(state)
    plan, bp, build = _plan(state), state.get('blueprint') or {}, state.get('open_build')
    done = [r['milestone'] for r in state.get('built') or []]
    answer = {'project': state['project'], 'mode': 'build from a plan', 'outputs_folder': str(guided.outputs(state)),
              'blueprint': str(folder(state) / 'BLUEPRINT.md') if bp.get('designed') else None,
              'milestones_built': done, 'open_milestone': build['milestone'] if build else None}
    step = _next_step(state, plan, bp, build, done)
    answer['next'] = {'tool': step[0], 'why': step[1]}
    answer['handover'] = handover.brief(state)
    return answer


def _next_step(state, plan, bp, build, done):
    """(tool, why) of the next step of building from a plan."""
    if not (folder(state) / 'SOURCE.md').is_file(): return 'blueprint_start', 'no plan has been read yet'
    if not bp.get('spec_ok'): return 'blueprint_spec', 'the product spec is missing or incomplete'
    if not bp.get('designed'): return 'blueprint_design', 'the target and the build plan are not drawn yet'
    if build: return 'build_edit, then build_finish', f"milestone {build['milestone']} is open"
    if plan and len(done) < len(plan['milestones']): return 'build_start', 'the next milestone is waiting'
    if waiting_batch(state) is not None:
        return 'accept', 'everything is built: the person decides whether to take the last branch in'
    return 'audit', 'everything is built and taken in: offer the check of the finished project'


def status_of(project=None):
    """The status of the project's way: building from a plan, or checking and fixing. A build whose acceptance check is
    done goes on as check and fix (its mode becomes the check's). A folder not made yet is a new project built from its
    plan, which reading the plan makes (the Studio's "Build from a plan" names it first)."""
    where = Path(project or os.getcwd()).expanduser().resolve()
    if not where.exists():
        return {'project': str(where), 'mode': 'build from a plan', 'next': {'tool': 'blueprint_start', 'why': 'a new project: reading its plan makes its folder'}}
    state = project_state.load(where)
    if (state or {}).get('mode') == 'build' and journeys.which(state) != 'build':
        state['mode'] = 'check'
        guided.save(state)
    return status(project) if (state or {}).get('mode') == 'build' else agent_tools.status(project)


JOBS = {'build_edit': _build_edit_job, 'build_finish': _build_finish_job}

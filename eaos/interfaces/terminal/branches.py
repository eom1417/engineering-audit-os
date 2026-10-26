"""The terminal's accept, undo, branch and branches commands (eaos/interfaces/terminal/commands.py holds the others and
the way each one runs): what will happen said first, the person's yes, then the Studio's own core does it."""
import subprocess

from .. import govern
from ...journeys import guided
from ..mcp_server.server import refuse_in_studio_run
from ..govern_words import WORDS, text_of, words
from ...core.project import state as project_state
from .commands import _project, _said, agreed, command, say


def _files(project, base, branch):
    out = subprocess.run(['git', '-C', str(project), 'diff', '--name-only', f'{base}...{branch}'], capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if line]


def decide(args, lang, operation):
    """Accept or undo the batch waiting: what will happen said first, the person's yes (or --yes), then the Studio's own
    way when a run handed it over (the run records it), else the assistant's tool."""
    from ...journeys import agent_tools
    from ...core.project.state import waiting_batch
    refuse_in_studio_run(operation)
    actions = govern.core(args.project)
    state = project_state.current(args.project)
    guided.reconcile(state)
    wave = waiting_batch(state)
    if wave is None: return guided.box(lang, words('nothing', lang), commands=['eaos next'], status='warn')
    target = (actions.branches.accept_where() if actions.branches.is_repo() else {}).get('target') or state.get('branch')
    count = len(_files(actions.project, target, wave['branch']))
    agreed(actions.project, operation, words(f'{operation}_what', lang, branch=wave['branch'], target=target, count=count), args.yes)
    run = next((r for r in actions.store.all() if (r.get('result') or {}).get('branch') == wave['branch'] and not r.get('outcome')), None)
    if run: result = actions.decide(run['id'], operation, {'confirm': actions.preview(operation, {})['confirm']['token']})['result']
    else: result = getattr(agent_tools, operation)(str(actions.project), person_agreed=True)
    return _decided(result, wave, lang)


def _decided(result, wave, lang):
    """The box that ends accept or undo: done, with the progress now; or not done, and why."""
    totals = result.get('progress') or {}
    if result.get('status') in ('accepted', 'undone'):
        return guided.box(lang, words(result['status'], lang, branch=wave['branch'], target=result.get('merged_into'), closed=totals.get('closed', 0),
                                      total=totals.get('total', 0)), where=result.get('report_for_people'), commands=['eaos next'])
    guided.box(lang, words('not_done', lang, why=result.get('what_now') or result.get('error') or result.get('status')), status='warn',
               commands=[f"git merge {wave['branch']}"] if result.get('status') == 'conflict' else ['eaos status'])
    return 0


accept = command(lambda args, lang: decide(args, lang, 'accept'))
undo = command(lambda args, lang: decide(args, lang, 'undo'))


@command
def branch(args, lang):
    from ...journeys.agent_tools import branches_of
    if not args.name:
        found = branches_of(args.project)
        for row in found['branches']:
            mark = '✓' if row['name'] == found['working_branch'] else '★' if row['name'] == (found.get('recommended') or {}).get('name', found.get('recommended')) else ' '
            say(f"{mark} {row['name']:<30} {(row.get('last_commit') or '')[:10]}  +{row.get('ahead_of_main') or 0}/-{row.get('behind_main') or 0}")
        return guided.box(lang, words('branches', lang, branch=found['working_branch'] or '-'), commands=['eaos branch <name>'])
    actions = govern.core(args.project)
    agreed(actions.project, 'choose_branch', words('branch_what', lang, branch=args.name), args.yes)
    done = actions.branches.select({'branch': args.name})
    guided.box(lang, text_of(_said(actions, done['run']), lang), commands=['eaos check', 'eaos status'])


def _branch_list(project, lang):
    found = govern.core(project).branches.inventory()
    for row in found['branches']:
        compare = row['compare']
        say(f"{'🔒' if row['protected'] else '  '} {row['name']:<34} {row['kind']:<6} {row['ownership'].get('owner', ''):<8} "
            f"+{compare['ahead'] if compare['ahead'] is not None else '?'}/-{compare['behind'] if compare['behind'] is not None else '?'}")
    guided.box(lang, words('branches', lang, branch=found.get('base') or '-'), commands=['eaos branches merge <name>', 'eaos branches cleanup'])


def _preview_lines(preview, lang):
    """The main facts of a branch change's preview."""
    for commit in _listed(preview, 'commits')[:10]: say(f"   {commit['commit'][:9]} {commit['subject']}")
    for row in _listed(preview, 'files')[:20]: say(f"   {row['status']} {row['path']}")
    for commit in _listed(preview, 'lost_commits')[:10]: say(f"   ⚠️ {commit.get('commit', '')[:9]} {commit.get('subject', '')}")
    for row in _listed(preview, 'branches'): say(f"   − {row.get('branch')}")
    for row in _listed(preview, 'worktrees'): say(f"   − {row.get('path')}")
    if preview.get('needs_unchecked_ack'): say('   ' + words('unchecked_merge', lang))


def _listed(preview, key):
    """One list of a branch change's preview; [] when it has none."""
    return preview.get(key) or []


@command
def branches(args, lang):
    project = _project(args)
    if args.op == 'list': return _branch_list(project, lang)
    actions = govern.core(project)
    if args.op == 'restore':
        agreed(project, 'branches restore', words('restore_what', lang, name=args.name), args.yes)
        return guided.box(lang, text_of(_said(actions, govern.restore(project, args.name)['run']), lang), commands=['eaos branches'])
    preview = govern.branch_preview(project, args.op, args.name, args.into)
    _preview_lines(preview, lang)
    if preview.get('blocked') or not preview.get('confirm'):
        from ..studio_actions.branches import Blocked
        raise Blocked(preview.get('blocked') or [WORDS['blocked']], needs='blocked')
    question = words(f'{args.op}_what', lang, name=args.name, target=preview.get('target'),
                     **{key: len(_listed(preview, key)) for key in ('commits', 'files', 'branches', 'worktrees')})
    agreed(project, 'branches ' + ('protect' if args.op == 'unprotect' else args.op), question, args.yes)
    done = govern.branch_change(project, args.op, preview, preview['confirm']['token'], (preview.get('confirm_unmerged') or {}).get('token'))
    guided.box(lang, text_of(_said(actions, done['run']), lang), commands=['eaos branches', 'eaos status'])


guided.COMMANDS.update(accept=accept, undo=undo)    # eaos start's steps name them (registered here: see guided)

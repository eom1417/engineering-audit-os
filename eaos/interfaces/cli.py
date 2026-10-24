"""The eaos command: the guided journey (start, next, status...), the Studio, the MCP server, the tools, and the
few commands a task card's acceptance check runs (facts, policy, decided, recheck)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from .. import __version__
from ..core.check_paths import PATHS
from ..core.workspace import bounded_int, read


def facts_command(args):
    from ..facts.run import collect
    selected=[name for name,flag in [('history',args.history)] if flag] or None
    print(json.dumps(collect(args.target,args.out,selected,args.max_commits,exclude=args.exclude,
                             engines=args.engines),ensure_ascii=False,indent=2))
    return 0


def audit_command(args):
    from ..pipeline import execute, resume
    run = resume if args.resume else execute
    out = Path(args.out).resolve()
    manifest = run(args.target, args.out, only=args.only or (), skip=args.skip or (), language=args.lang,
                   exclude=args.exclude, engines=args.engines, goal=args.goal, runtime=args.run_app,
                   **({'intake': args.intake} if args.intake else {}))
    result = read(out / 'report-result.json') if (out / 'report-result.json').is_file() else {}
    violations = result.get('output_spec_violations', ['the output contract was never checked'])
    status = 'OUTPUT_SPEC_VIOLATED' if violations else 'REVIEW_REQUIRED' if manifest['status'] == 'COMPLETE' else manifest['status']
    print(json.dumps({'status': status, 'stages': {name: row['status'] for name, row in manifest['stages'].items()},
                      'seconds': manifest['seconds'], 'output_spec_violations': violations,
                      'not_examined': {name: row['reason'] for name, row in manifest['stages'].items() if row['status'] != 'ok'},
                      'manifest': str(out / 'run-manifest.json')}, ensure_ascii=False, indent=2))
    from ..journeys.guided import box
    box(args.lang, 'اكتمل الفحص' if args.lang == 'ar' else 'The check is done', where=out / 'START-HERE.md',
        commands=[f'eaos start {args.target}'], status='ok' if status == 'REVIEW_REQUIRED' else 'warn',
        note=('للمتابعة بخطوات موجِّهة' if args.lang == 'ar' else 'to go on with guided steps'), stream=sys.stderr)
    return 0 if status == 'REVIEW_REQUIRED' else 2


def handover_hook(args):
    """A session-start hook of Claude Code or Codex: the folder comes on stdin ({"cwd": ...}); when EAOS has work there,
    the context to add to the session. Never fails and never prints anything else: a hook must not stop a session."""
    try:
        import os
        raw = sys.stdin.read() if not sys.stdin.isatty() else ''
        folder = (json.loads(raw) if raw.strip() else {}).get('cwd') or os.getcwd()
        from ..journeys.handover import hook_context
        context = hook_context(folder)
        if context:
            print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': context}}, ensure_ascii=False))
    except Exception:                       # a broken hook would cost the person their session; say nothing instead
        pass
    return 0


def guided_command(args):
    from ..journeys import handover  # noqa: F401
    from . import terminal  # noqa: F401  (register the work log on the report, and the terminal's accept, undo and check)
    from ..journeys.guided import main as guided_main
    return guided_main(args)


def studio_command(args):
    if args.background: return studio_in_background(args)
    from .api.server import run_foreground
    return run_foreground(args.project, port=args.port, show=not args.no_open, remote_origin=args.remote_origin)


def studio_in_background(args):
    """`eaos studio --background`: the project's Studio started (or found running), opened on "Preparing the tools"
    while the tools the check needs are installing, its address printed, and back at once; the tools' install starts."""
    from ..core import toolchain
    from ..journeys.agent_tools import open_studio, project_state
    project = project_state(args.project)['project']
    toolchain.prepare(project)
    opened = open_studio(project, show=not args.no_open, route='' if toolchain.ready(project) else '/tools')
    if 'studio' not in opened:
        print(opened.get('error'), opened.get('log'), sep='\n')
        return 1
    print(f"EAOS Studio: {opened['studio']}")
    return 0


def decided_command(args):
    from ..core.decided import main
    return main(args)


def recheck_command(args):
    from ..analysis.recheck import main
    return main(args)


def tools_command(args):
    from ..core.toolchain import main as toolchain_main
    return toolchain_main(args)


def policy_command(args):
    from ..analysis.policy import check as check_policy, init as init_policy
    if args.action=='init':
        print(json.dumps(init_policy(args.target,args.out,args.policy),ensure_ascii=False,indent=2));return 0
    result=check_policy(args.target,args.out,args.policy)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 2 if result['status']=='VIOLATED' else 0


def terminal(name):
    """The governance command `name` of eaos/interfaces/terminal.py, imported when it runs."""
    return lambda args: getattr(__import__('eaos.interfaces.terminal', fromlist=[name]), name)(args)


def governance_commands(s):
    """Full governance from a terminal, without the Studio (eaos/interfaces/terminal.py over eaos/interfaces/govern.py, the Studio's own core)."""
    from .govern import CONTROLS
    from ..core.store import contract
    def command(name, text, func=None):
        q = s.add_parser(name, help=text)
        q.add_argument('--project', default='.')
        q.add_argument('--lang', choices=['ar', 'en'], default=None)
        q.set_defaults(func=terminal(func or name))
        return q
    q = command('check', 'Check the project now, in the background: the time it takes first, then a new check (nothing in it changes)')
    q.add_argument('--path', nargs='+', choices=sorted(PATHS), default=None, help='check only these paths')
    q.add_argument('--mode', choices=['normal', 'speed'], default=None)
    q.add_argument('--assistant', choices=['claude', 'codex', 'none'], default=None, help='the AI the check uses, or none')
    q.add_argument('--sign-in', choices=['hand', 'test_user', 'none'], default=None,
                   help='an app behind a sign-in: you sign in when the check asks, a test user, or none (kept)')
    q.add_argument('--published', default=None, help='the published address, read signed in and read only, for this check')
    q.add_argument('--run-app', action='store_true', help='run your app in an isolated copy (its pages, sign-in, speed); kept')
    q.add_argument('--again-from', dest='again_from', metavar='STAGE', help='go on from this stage of the last check: it and the stages reading it run again')
    q.add_argument('--watch', action='store_true', help='follow it here until it ends')
    command('watch', 'Follow a run live: its stages, the time left, the cost so far, and its questions').add_argument('run', nargs='?')
    command('runs', 'The runs: running, queued and ended').add_argument('--all', action='store_true', help='also those already read')
    for name in CONTROLS: command(name, f'{name.capitalize()} a run (the newest it applies to by default)', 'control').add_argument('run', nargs='?')
    command('waiting', 'What waits for you: the questions of the runs and of the report, a branch to accept or undo, a sign-in')
    q = command('sign-in', 'Sign in to your app while a check asks for it (a window, or a page of its own)', 'signing_in')
    q.add_argument('--signed-out', action='store_true', help='go on without signing in'); q.add_argument('--forget', action='store_true', help='forget your sign-ins')
    q = command('answer', 'Answer what waits for you: eaos answer <id> <option>')
    q.add_argument('id'); q.add_argument('option', nargs='?'); q.add_argument('--text', default=None, help='your own answer instead of an option')
    q.add_argument('--assistant', default=None, help='a report question: who reviews your answer (claude, codex, or handoff)')
    q = command('problems', 'What the check found, most important first')
    from ..analysis.model import AREAS, SEVERITIES
    q.add_argument('--area', choices=AREAS, help="only this area, as the Studio's filter")
    q.add_argument('--severity', choices=SEVERITIES, help="only this severity, as the Studio's filter")
    q.add_argument('--kind', help='only this kind of problem (its pattern: dead_code, security_weakness, …)')
    q.add_argument('--where', help='only problems in paths containing this'); q.add_argument('--text')
    q.add_argument('--fixable', action='store_true'); q.add_argument('--limit', type=int, default=30); q.add_argument('--offset', type=int, default=0)
    command('problem', 'One problem whole: what, why, the evidence with its code, the change').add_argument('id')
    for verb in contract()['verbs']:
        q = command(verb['id'], f"{verb['label']['en']} these cards (a preview first): ids, or --group by=value", 'act')
        q.add_argument('ids', nargs='*'); q.add_argument('--group', help='area=…, severity=…, component=…, gap=… or operation=…')
        q.add_argument('--assistant', default=None, help='claude, codex, or handoff (your assistant takes it)')
        q.add_argument('--yes', action='store_true', help='agree to what the preview shows')
        if verb['changes_code']: q.add_argument('--auto-accept', action='store_true', help='accept it by itself when its checks pass')
    q = command('branch', 'The branch EAOS checks and fixes: the list, or move to one')
    q.add_argument('name', nargs='?'); q.add_argument('--yes', action='store_true')
    q = command('branches', 'Every branch, and merge, delete, protect, unprotect, clean up or restore one (a preview, then your yes)')
    q.add_argument('op', nargs='?', default='list', choices=['list', 'merge', 'delete', 'protect', 'unprotect', 'cleanup', 'restore'])
    q.add_argument('name', nargs='?'); q.add_argument('--into', default=None, help='merge: the branch to merge into')
    q.add_argument('--yes', action='store_true')
    command('history', 'Every check on record: the score, the open problems, closed of total')
    q = command('compare', 'Two checks of the history side by side'); q.add_argument('first'); q.add_argument('second')
    command('usage', 'What the assistant used: tokens and cost, per check stage and per run')
    q = s.add_parser('govern', help='The headless host that starts this project\'s runs while no Studio runs (the commands start it)')
    q.add_argument('project'); q.add_argument('--answer'); q.add_argument('--option'); q.add_argument('--text')
    q.set_defaults(func=terminal('govern_host'))


def _guided_commands(s):
    """The guided journey: start, next, status and the few steps around them."""
    for name, text in (('start', 'Start here: check a project and get a plain report (nothing in it changes)'),
                       ('next', 'Do the next step for the project in this folder'),
                       ('status', 'Where this project stands, and what comes next'),
                       ('doctor', 'Is this computer ready? Every missing piece, with its fix'),
                       ('clean', 'Remove the temporary copies EAOS made; reports stay'),
                       ('accept', 'Take the latest batch of fixes into your project (its branch, merged)'),
                       ('undo', 'Throw the latest batch of fixes away (its branch, deleted)'),
                       ('show', 'Print what the check found, in plain words'),
                       ('do', 'Ask in your own words: eaos do "check my project"'),
                       ('assistant', 'Teach your AI assistant (Claude Code, Codex) to use EAOS: eaos assistant install')):
        q=s.add_parser(name,help=text)
        if name == 'do': q.add_argument('request',nargs='*')
        elif name == 'assistant': q.add_argument('action',nargs='?',choices=['install'],default='install')
        if name in ('do', 'assistant'): q.add_argument('--project',default='.')
        else: q.add_argument('project',nargs='?',default='.' if name != 'doctor' else None)
        q.add_argument('--lang',choices=['ar','en'],default=None)
        q.add_argument('--yes',action='store_true',help='answer yes to the question this step asks')
        if name == 'doctor': q.add_argument('--fix',action='store_true',help='install what is missing')
        if name == 'clean': q.add_argument('--pictures',action='store_true',help="also delete the reports' screen pictures and the assistant's raw runs")
        if name == 'start':
            q.add_argument('--no-watch',action='store_true',help='do not open the live map in the running Studio')
            q.add_argument('--assistant',choices=['claude','codex','none'],default=None,
                           help='the AI assistant the check uses on this project (kept), or none for a check without AI')
            q.add_argument('--path',nargs='+',choices=sorted(PATHS),default=None,
                           help='check only these paths (eaos/pipeline/paths.py); the complete check by default')
            q.add_argument('--mode',choices=['normal','speed'],default=None,help='speed: several assistants at once, faster but '
                           'more tokens (kept for this project)')
        q.set_defaults(func=guided_command)


def main(argv=None):
    from .command_groups import epilog
    p=argparse.ArgumentParser(prog='eaos',description='Check a project with ready-made tools and your AI assistant, and fix it safely',
                              epilog=epilog(),formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--version',action='version',version='EAOS '+__version__)
    s=p.add_subparsers(dest='command',required=True)
    _guided_commands(s)
    q=s.add_parser('handover',help='Where the work stopped, and what to tell another assistant to go on (after a usage limit)')
    q.add_argument('project',nargs='?',default='.')
    q.add_argument('--lang',choices=['ar','en'],default=None)
    q.add_argument('--hook',action='store_true',help='for an assistant\'s session-start hook (eaos assistant install sets it): '
                   'read its JSON on stdin and answer with the context to add')
    q.set_defaults(func=lambda args: handover_hook(args) if args.hook else guided_command(args))
    q=s.add_parser('studio',help='Open the live EAOS Studio of this project in your browser (on this computer only)')
    q.add_argument('project',nargs='?',default='.')
    q.add_argument('--port',type=int,default=0,help='the port on 127.0.0.1 (default: a free one)')
    q.add_argument('--no-open',action='store_true',help='print the address without opening the browser')
    q.add_argument('--background',action='store_true',help='start it in the background, print its address and return')
    q.add_argument('--remote-origin', help='one exact https://<project>--<port>.dev.remote.e-m.sa origin; keeps token and CSRF checks')
    q.set_defaults(func=studio_command)
    q=s.add_parser('mcp',help='EAOS as MCP tools for an AI assistant (stdio); eaos assistant install registers it')
    q.set_defaults(func=lambda args: __import__('eaos.interfaces.mcp_govern', fromlist=['main']).main())
    q=s.add_parser('facts',help='Deterministic facts about a target; no model is used')
    q.add_argument('target');q.add_argument('--out',required=True);q.add_argument('--history',action='store_true')
    q.add_argument('--max-commits',type=bounded_int,default=2000)
    q.add_argument('--exclude',action='append',default=[])
    q.add_argument('--engines',nargs='*',default=None,metavar='ENGINE',
                   help='also run the pinned external engines; name a subset, or pass the flag alone for all')
    q.set_defaults(func=facts_command)
    q=s.add_parser('audit',help='Run the whole pipeline in one command and report what each stage did')
    q.add_argument('target');q.add_argument('--out',required=True)
    q.add_argument('--lang',choices=['ar','en'],default='ar')
    q.add_argument('--goal',choices=['onboarding','debugging','evolution','architecture'],default='evolution')
    q.add_argument('--exclude',action='append',default=[])
    q.add_argument('--engines',nargs='*',default=None,metavar='ENGINE')
    q.add_argument('--run-app',default=None,metavar='FOLDER',
                   help='run the app in an isolated copy under FOLDER during the check (your consent): setup, lock, screens, speed')
    q.add_argument('--intake',default=None,metavar='FILE',help="the owner's answers to the intake questions: JSON {question id: answer}")
    q.add_argument('--only',action='append',default=[],metavar='STAGE')
    q.add_argument('--skip',action='append',default=[],metavar='STAGE')
    q.add_argument('--resume',action='store_true')
    q.set_defaults(func=audit_command)
    q=s.add_parser('decided',help='Exit 0 once an observation carries a recorded decision (the acceptance of an investigation)')
    q.add_argument('report'); q.add_argument('uid')
    q.set_defaults(func=decided_command)
    q=s.add_parser('recheck',help='Collect facts on a changed copy and let one claim\'s probe decide; exit 0 when the observation is gone')
    q.add_argument('root',nargs='?',default='.')
    q.add_argument('--spec',required=True,help='the probe as JSON: {"probe_type": ..., "specification": {...}}')
    q.set_defaults(func=recheck_command)
    q=s.add_parser('policy',help='Check the declared architecture policy, or scaffold one')
    q.add_argument('action',choices=['check','init']);q.add_argument('target');q.add_argument('--out',required=True)
    q.add_argument('--policy',default=None)
    q.set_defaults(func=policy_command)
    q=s.add_parser('tools',help='Install every external tool at its pinned version, or check what is installed')
    q.add_argument('action',choices=['install','doctor'])
    q.add_argument('--stage',choices=['assessment','execution'],default=None)
    q.add_argument('--project',default=None,help='install first what the check needs on this project')
    q.add_argument('--only',default=None,help='comma-separated tool names')
    q.add_argument('--skip',default=None,help='comma-separated tool names to leave out')
    q.add_argument('--json',action='store_true')
    q.set_defaults(func=tools_command)
    governance_commands(s)
    args=p.parse_args(argv)
    args.words = list(sys.argv[1:] if argv is None else argv)
    try:
        return args.func(args) or 0
    except (ValueError,OSError,KeyError,TypeError,UnicodeError) as e:
        print(f'eaos: {e}',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())

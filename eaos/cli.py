"""The eaos command: the guided journey (start, next, status...), the Studio, the MCP server, the tools, and the
few commands a task card's acceptance check runs (facts, policy, decided, recheck)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from . import __version__
from .workspace import bounded_int, read


def facts_command(args):
    from .facts.run import collect
    selected=[name for name,flag in [('history',args.history)] if flag] or None
    print(json.dumps(collect(args.target,args.out,selected,args.max_commits,exclude=args.exclude,
                             engines=args.engines),ensure_ascii=False,indent=2))
    return 0


def audit_command(args):
    from .pipeline import execute, resume
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
    from .guided import box
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
        from .handover import hook_context
        context = hook_context(folder)
        if context:
            print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': context}}, ensure_ascii=False))
    except Exception:                       # a broken hook would cost the person their session; say nothing instead
        pass
    return 0


def guided_command(args):
    from . import handover  # noqa: F401  (registers the work log on the report for people)
    from .guided import main as guided_main
    return guided_main(args)


def studio_command(args):
    if args.background: return studio_in_background(args)
    from .api.server import run_foreground
    return run_foreground(args.project, port=args.port, show=not args.no_open, remote_origin=args.remote_origin)


def studio_in_background(args):
    """`eaos studio --background`: the project's Studio started (or found running), opened on "Preparing the tools"
    while the tools the check needs are installing, its address printed, and back at once; the tools' install starts."""
    from . import toolchain
    from .agent_tools import open_studio, project_state
    project = project_state(args.project)['project']
    toolchain.prepare(project)
    opened = open_studio(project, show=not args.no_open, route='' if toolchain.ready(project) else '/tools')
    if 'studio' not in opened:
        print(opened.get('error'), opened.get('log'), sep='\n')
        return 1
    print(f"EAOS Studio: {opened['studio']}")
    return 0


def decided_command(args):
    from .decided import main
    return main(args)


def recheck_command(args):
    from .recheck import main
    return main(args)


def tools_command(args):
    from .toolchain import main as toolchain_main
    return toolchain_main(args)


def policy_command(args):
    from .policy import check as check_policy, init as init_policy
    if args.action=='init':
        print(json.dumps(init_policy(args.target,args.out,args.policy),ensure_ascii=False,indent=2));return 0
    result=check_policy(args.target,args.out,args.policy,args.lang)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 2 if result['status']=='VIOLATED' else 0


def main(argv=None):
    from .command_groups import epilog
    p=argparse.ArgumentParser(prog='eaos',description='Check a project with ready-made tools and your AI assistant, and fix it safely',
                              epilog=epilog(),formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--version',action='version',version='EAOS '+__version__)
    s=p.add_subparsers(dest='command',required=True)
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
        q.set_defaults(func=guided_command)
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
    q.set_defaults(func=lambda args: __import__('eaos.mcp_server', fromlist=['main']).main())
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
    q.add_argument('--policy',default=None);q.add_argument('--lang',choices=['ar','en'],default='ar')
    q.set_defaults(func=policy_command)
    q=s.add_parser('tools',help='Install every external tool at its pinned version, or check what is installed')
    q.add_argument('action',choices=['install','doctor','refresh'],help='refresh: a new vulnerability database, moved in whole')
    q.add_argument('--stage',choices=['assessment','execution'],default=None)
    q.add_argument('--project',default=None,help='install first what the check needs on this project')
    q.add_argument('--only',default=None,help='comma-separated tool names')
    q.add_argument('--skip',default=None,help='comma-separated tool names to leave out')
    q.add_argument('--json',action='store_true')
    q.set_defaults(func=tools_command)
    args=p.parse_args(argv)
    try:
        return args.func(args) or 0
    except (ValueError,OSError,KeyError,TypeError,UnicodeError) as e:
        print(f'eaos: {e}',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())

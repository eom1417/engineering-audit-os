"""The optional deep checks a person asks for by name, beside a finished check's report: the logic-flaw hunt (M9.2)
and the simulated users (M10: eaos experience plan | run | judge | replay | report). Thin: each finds the person's
assistant and calls the analysis that does the work. The hunt says what it will spend and asks, then runs the check
again from its claims so the cards and their triage include what it found; the experience drives the app's isolated
copy already running (--base)."""
import sys
from pathlib import Path


SPEND = ("The logic-flaw hunt asks your assistant twice on its deep tier, each a long reading of the code (up to "
         "{minutes} minutes in all), then runs this check again from its claims, so its AI stages ask again too. "
         "On a subscription it uses your plan; on a key it costs about what two long code reviews cost. "
         "The spend shows in `eaos usage`.")


def _assistant(name, max_calls):
    """The person's assistant on this machine, or an error that says there is none."""
    from ..ai import provider
    _, found = provider(max_calls=max_calls, name=name)
    if found is None: raise ValueError('no AI assistant is installed here (claude or codex): this check needs one')
    return found


def _agreed(args):
    """What the hunt will spend, then the person's yes (or --yes); False when they did not agree."""
    print(SPEND.format(minutes=args.minutes))
    if args.yes: return True
    if not sys.stdin.isatty():
        print('Not started: add --yes to agree.'); return False
    return input('Go on? [y/N] ').strip().lower() in ('y', 'yes')


def hunt_flaws(target, out, assistant, minutes):
    """The hunt on the code of `target` beside its check's report `out`, its spend counted with the check's own use:
    its summary (hunt.Unfinished or Stuck when it did not finish). The command and the MCP tool both call it."""
    from ..analysis.logic_flaws import record
    from ..core.system.usage import FILE as USAGE
    assistant.config['usage'] = str(Path(out) / USAGE)     # eaos/core/system/usage.py
    return record.run(target, Path(out), assistant, minutes)


def logic_flaws_command(args):
    from ..analysis.logic_flaws import hunt, record
    from ..core.system.process import Stuck
    from ..pipeline.run import again, same_source
    out = Path(args.out).resolve()
    same_source(args.target, out)                    # the report of a check of this very code, or a plain refusal
    if not _agreed(args): return 1
    try: summary = hunt_flaws(args.target, out, _assistant(args.assistant, args.max_calls), args.minutes)
    except (hunt.Unfinished, Stuck) as failed:
        print(f'logic flaws: the hunt did not finish ({failed}); nothing was kept. Try again, or with a longer --minutes.')
        return 2
    print(f"logic flaws: {summary['flaws']} kept ({summary['holds']} held by the second reading), {summary['dropped']} set aside, "
          f"{summary['reviewed']} routes read; {out / record.RECORD}. The check goes on from its claims, so its cards include them.")
    again(args.target, out, 'claims')
    return 0


def logic_flaws_tool(project=None, person_agreed=False, minutes=None):
    """The MCP tool (eaos/interfaces/mcp_server/server.py logic_flaws): the spend asked first, then the hunt as a job."""
    from ..analysis.logic_flaws import hunt
    from ..journeys import agent_tools, guided
    state = agent_tools.state_of(project)
    if not guided.scan_done(state): return {'error': 'there is no check to hunt logic flaws from', 'what_now': 'Call audit first.'}
    minutes = minutes or hunt.MINUTES
    if not person_agreed:
        return {'status': 'needs_agreement', 'ask_the_person': SPEND.format(minutes=minutes),
                'what_now': 'Ask the person; only after their yes, call again with person_agreed=true. It returns a job to follow with wait.'}
    return agent_tools._start('logic_flaws', state, {'minutes': minutes}, runner='eaos.interfaces.deep_checks')


def _logic_flaws_job(project, arguments, progress):
    """The hunt on the checked commit with the person's chosen assistant, then the check again from its claims."""
    from ..core.project import state as project_state
    from ..journeys import agent_tools, guided
    state = project_state.load(project)
    found = hunt_flaws(guided.source(state, state.get('scanned_commit')), guided.report_of(state),
                       _assistant(guided.chosen_assistant(state), 4), arguments['minutes'])
    return {'logic_flaws': found, **agent_tools.JOBS['audit'](project, {'again_from': 'claims'}, progress)}


JOBS = {'logic_flaws': _logic_flaws_job}


def _app(args):
    """The running copy: its address, each kind of user's browser state (<kind>.json in --sessions), its run folder."""
    if not args.base: raise ValueError('this step drives the running copy of the app: give its address with --base')
    folder = Path(args.sessions) if args.sessions else None
    sessions = {path.stem: path for path in folder.glob('*.json')} if folder and folder.is_dir() else {}
    return {'base': args.base.rstrip('/'), 'sessions': sessions, 'runtime': args.runtime, 'database': args.database}


def experience_command(args):
    from ..analysis.experience import simulation
    from ..report.experience.document import write
    from ..report.experience.story import story, summary
    step = args.step
    if step == 'plan': said = {'personas': len(simulation.prepare(args.out, _assistant(args))[0]['personas'])}
    elif step == 'run': said = {k: v for k, v in simulation.simulate(args.out, args.target, _app(args), _assistant(args)).items() if k in ('seconds', 'calls', 'seeded')}
    elif step == 'judge': said = simulation.judged(args.out, _app(args), _assistant(args))
    elif step == 'replay': said = simulation.replays(args.out, _app(args))['summary']
    else: said = {'written': [str(path) for path in write(args.out, args.lang)], 'difficulties': len(summary(story(args.out))['difficulties']['ranked'])}
    print(f'experience {step}: {said}')


def commands(s):
    """The deep checks' commands."""
    from ..analysis.logic_flaws import hunt
    from ..core.project.workspace import bounded_int
    q = s.add_parser('logic-flaws', help="Hunt logic flaws with your assistant (a deep check, after a check): skipped steps, races, "
                                         "wrong checks; each candidate read twice, kept as facts the plan makes cards of")
    q.add_argument('target'); q.add_argument('--out', required=True, help="the finished check's report folder")
    q.add_argument('--assistant', choices=['claude', 'codex'], default=None)
    q.add_argument('--max-calls', type=int, default=4)
    q.add_argument('--minutes', type=bounded_int, default=hunt.MINUTES, help='the most the hunt may take, wall clock (default 40)')
    q.add_argument('--yes', action='store_true', help='agree to the time and cost it shows')
    q.set_defaults(func=logic_flaws_command)
    q = s.add_parser('experience', help='Simulated users try the running app (after a check): plan the personas and data, run them '
                                        'with hand-offs and support, judge what they met, replay saved journeys, write EXPERIENCE.md')
    q.add_argument('step', choices=['plan', 'run', 'judge', 'replay', 'report'])
    q.add_argument('target'); q.add_argument('--out', required=True, help="the finished check's report folder")
    q.add_argument('--base', default=None, help="the address of the app's isolated copy, already running")
    q.add_argument('--sessions', default=None, help='a folder of browser states, one <kind of user>.json each')
    q.add_argument('--runtime', default=None, help="the run's folder: its own database is seeded with the history")
    q.add_argument('--database', default=None, help="the copy's SQLite file, when it keeps one inside the run")
    q.add_argument('--assistant', choices=['claude', 'codex'], default=None)
    q.add_argument('--max-calls', type=int, default=400)
    q.add_argument('--lang', choices=['ar', 'en'], default='ar')
    q.set_defaults(func=experience_command)

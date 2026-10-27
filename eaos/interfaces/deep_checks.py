"""The optional deep checks a person asks for by name, beside a finished check's report: the logic-flaw hunt (M9.2)
and the simulated users (M10: eaos experience plan | run | judge | replay | report). Thin: each finds the person's
assistant and calls the analysis that does the work. The hunt says what it will spend and asks, then runs the check
again from its claims so the cards and their triage include what it found; the experience drives the app's isolated
copy already running (--base), and its judging runs the check again from its claims the same way."""
import sys
from pathlib import Path


def _assistant(args):
    """The person's assistant on this machine, or an error that says there is none."""
    from ..ai import provider
    _, found = provider(max_calls=args.max_calls, name=args.assistant)
    if found is None: raise ValueError('no AI assistant is installed here (claude or codex): this check needs one')
    return found


def _agreed(args):
    """What the hunt will spend, then the person's yes (or --yes); False when they did not agree."""
    print(f"The logic-flaw hunt asks your assistant twice on its deep tier, each a long reading of the code (up to "
          f"{args.minutes} minutes in all), then runs this check again from its claims, so its AI stages ask again too. "
          f"On a subscription it uses your plan; on a key it costs about what two long code reviews cost. "
          f"The spend shows in `eaos usage`.")
    if args.yes: return True
    if not sys.stdin.isatty():
        print('Not started: add --yes to agree.'); return False
    return input('Go on? [y/N] ').strip().lower() in ('y', 'yes')


def logic_flaws_command(args):
    from ..analysis.logic_flaws import hunt, record
    from ..core.system.process import Stuck
    from ..core.system.usage import FILE as USAGE
    from ..pipeline.run import again, same_source
    out = Path(args.out).resolve()
    same_source(args.target, out)                    # the report of a check of this very code, or a plain refusal
    if not _agreed(args): return 1
    assistant = _assistant(args)
    assistant.config['usage'] = str(out / USAGE)     # eaos/core/system/usage.py: counted with the check's own use
    try: summary = record.run(args.target, out, assistant, args.minutes)
    except (hunt.Unfinished, Stuck) as failed:
        print(f'logic flaws: the hunt did not finish ({failed}); nothing was kept. Try again, or with a longer --minutes.')
        return 2
    print(f"logic flaws: {summary['flaws']} kept ({summary['holds']} held by the second reading), {summary['dropped']} set aside, "
          f"{summary['reviewed']} routes read; {out / record.RECORD}. The check goes on from its claims, so its cards include them.")
    again(args.target, out, 'claims')
    return 0


def _app(args):
    """The running copy: its address, each kind of user's browser state (<kind>.json in --sessions), its run folder."""
    if not args.base: raise ValueError('this step drives the running copy of the app: give its address with --base')
    folder = Path(args.sessions) if args.sessions else None
    sessions = {path.stem: path for path in folder.glob('*.json')} if folder and folder.is_dir() else {}
    return {'base': args.base.rstrip('/'), 'sessions': sessions, 'runtime': args.runtime, 'database': args.database}


def _judged(args, simulation):
    """The difficulties judged, then the check run again from its claims, so the confirmed ones become cards (the
    report of a check of this very code, as the logic-flaw hunt asks)."""
    from ..pipeline.run import again, same_source
    same_source(args.target, args.out)
    said = simulation.judged(args.out, _app(args), _assistant(args))
    again(args.target, args.out, 'claims')
    return said


def experience_command(args):
    from ..analysis.experience import simulation
    from ..report.experience.document import write
    from ..report.experience.story import story, summary
    step = args.step
    if step == 'plan': said = {'personas': len(simulation.prepare(args.out, _assistant(args))[0]['personas'])}
    elif step == 'run': said = {k: v for k, v in simulation.simulate(args.out, args.target, _app(args), _assistant(args)).items() if k in ('seconds', 'calls', 'seeded')}
    elif step == 'judge': said = _judged(args, simulation)
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

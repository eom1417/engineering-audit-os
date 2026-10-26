"""The optional deep checks a person asks for by name, beside a finished check's report: the logic-flaw hunt (M9.2)
and the simulated users (M10: eaos experience plan | run | judge | replay | report). Thin: each finds the person's
assistant and calls the analysis that does the work; the app's isolated copy is the one already running (--base)."""
from pathlib import Path


def _assistant(args):
    """The person's assistant on this machine, or an error that says there is none."""
    from ..ai import provider
    _, found = provider(max_calls=args.max_calls, name=args.assistant)
    if found is None: raise ValueError('no AI assistant is installed here (claude or codex): this check needs one')
    return found


def logic_flaws_command(args):
    from ..analysis.logic_flaws import record
    summary = record.run(args.target, args.out, _assistant(args))
    print(f"logic flaws: {summary['flaws']} kept ({summary['holds']} held by the second reading), {summary['dropped']} set aside, "
          f"{summary['reviewed']} routes read; {args.out}/{record.RECORD}")


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
    q = s.add_parser('logic-flaws', help="Hunt logic flaws with your assistant (a deep check, after a check): skipped steps, races, "
                                         "wrong checks; each candidate read twice, kept as facts the plan makes cards of")
    q.add_argument('target'); q.add_argument('--out', required=True, help="the finished check's report folder")
    q.add_argument('--assistant', choices=['claude', 'codex'], default=None)
    q.add_argument('--max-calls', type=int, default=4)
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

"""The optional deep checks a person asks for by name, beside a finished check's report: the logic-flaw hunt (M9.2).
Thin: each says what it will spend and asks, finds the person's assistant, calls the analysis that does the work, then
runs the check again from its claims so the cards and their triage include what it found."""
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

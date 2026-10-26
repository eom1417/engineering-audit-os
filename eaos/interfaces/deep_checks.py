"""The optional deep checks a person asks for by name, beside a finished check's report: the logic-flaw hunt (M9.2).
Thin: each finds the person's assistant and calls the analysis that does the work."""


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


def commands(s):
    """The deep checks' commands."""
    q = s.add_parser('logic-flaws', help="Hunt logic flaws with your assistant (a deep check, after a check): skipped steps, races, "
                                         "wrong checks; each candidate read twice, kept as facts the plan makes cards of")
    q.add_argument('target'); q.add_argument('--out', required=True, help="the finished check's report folder")
    q.add_argument('--assistant', choices=['claude', 'codex'], default=None)
    q.add_argument('--max-calls', type=int, default=4)
    q.set_defaults(func=logic_flaws_command)

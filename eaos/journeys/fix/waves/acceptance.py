"""One collection of facts, every acceptance: the engines a changed copy is read with, and each card's own check
read from that collection (a probe, the dead-code check) or run."""
import json
import re
import subprocess
import tempfile
from pathlib import Path

DEADCODE = re.compile(r"== \('([^']+)', '([^']*)', '([\w-]+)'\)")


def engines_for(cards):
    """The engines a collection of facts on a changed copy runs: the security gate's (eaos/journeys/fix/execute.py
    GATE_ENGINES), and those a card's own recheck asks again (a security card names the engines that found it)."""
    from ..execute import GATE_ENGINES
    named = set()
    for card in cards:
        named |= set(((_spec(card) or {}).get('specification') or {}).get('engines') or [])
    return sorted(set(GATE_ENGINES) | named)


def _spec(card):
    """The probe a `recheck --spec` acceptance asks, or None when the card's check is not a probe."""
    argv = card.get('verify_command') or []
    return json.loads(argv[argv.index('--spec') + 1]) if 'recheck' in argv and '--spec' in argv else None


def batch_acceptance(report, cards, root, collected=None, runtime=None):
    """{card id: exit code} for every card's acceptance, from one collection of facts on `root` (`collected`,
    when the caller already made it, with engines_for(cards)). A `recheck --spec` acceptance and the dead-code check
    are read from that collection; a failing-tests card runs its command again (`runtime`: the run's, for the profile);
    anything else runs as written."""
    from ....facts.run import collect, read_available
    with tempfile.TemporaryDirectory(prefix='eaos-wave-facts-') as scratch:
        out = Path(collected or scratch)
        if not collected: collect(Path(root).resolve(), out, engines=engines_for(cards))
        sets = read_available(out)
        dead = {(f['location'].get('path'), f['location'].get('symbol'), f['value'].get('rule'))
                for f in (sets.get('deadcode') or {}).get('facts', [])}
        where = {'out': out, 'root': root, 'runtime': runtime}
        return {card['id']: _acceptance_exit(card, sets, dead, where) for card in cards}


# What a probe reads beside the collection, made again on the copy as eaos recheck makes it
# (eaos/analysis/claims/recheck.py MORE): the load model, the layers (never in the collection, eaos/facts/run.py), and
# a person's rule's own guard, whose stored finding is the check's, never the copy's.
AGAIN = ('load_blocker_present', 'boundary_finding_present', 'rule_broken')


def _decided(spec, sets, out, root):
    from ....analysis.claims.probes import decide_probe
    from ....analysis.claims.recheck import MORE
    query = (spec.get('specification') or {}).get('query')
    if query in AGAIN:
        for name, made in MORE[query](root, out, spec['specification']).items(): sets[name] = made
    return decide_probe(spec, sets)


def _probe_exit(spec, sets, out, root):
    status, _ = _decided(spec, sets, out, root)
    return 0 if status == 'REFUTED' else 1 if status in ('CONFIRMED', 'PARTIAL') else 2


def _still(card, out, root):
    """What a card's own probe still finds on the copy, in its words; '' when its check is not a probe."""
    from ....facts.run import read_available
    spec = _spec(card)
    if _tests_command(spec): return f"the project's tests do not pass on the copy: {_tests_command(spec)}"
    return _decided(spec, read_available(out), out, root)[1] if spec else ''


def _tests_command(spec):
    """The command of a failing-tests card (eaos/analysis/layers/operations.py _failing), or None for any other
    probe."""
    specification = (spec or {}).get('specification') or {}
    return (specification.get('params') or {}).get('command') if specification.get('rule') == 'tests-failing' else None


def _tests_exit(spec, root, runtime):
    """A failing-tests card: its command run again on the copy as the gates run it (eaos/journeys/fix/execute.py
    project_checks), never read from the code. 0 when it passes; 2 when it could not run here (no profile, the program
    missing, the setup failed)."""
    from ..execute import project_checks
    from ....live.isolation.sandbox import AuthorizationError
    command = _tests_command(spec)
    if not (runtime and command): return 2
    try: rows = project_checks(root, runtime, 'S09', 'acceptance')
    except (RuntimeError, OSError, AuthorizationError): return 2
    row = next((r for r in rows if ' '.join(map(str, r['argv'])) == command), None)
    return 2 if row is None or row['exit'] in (126, 127) else 0 if row['exit'] == 0 else 1


def _acceptance_exit(card, sets, dead, where):
    """One card's acceptance exit: read from the collection when it is a probe or the dead-code check, else run;
    `where`: {'out', 'root', 'runtime'}."""
    argv, spec, root = card.get('verify_command') or [], _spec(card), where['root']
    if _tests_command(spec): return _tests_exit(spec, root, where['runtime'])
    if spec: return _probe_exit(spec, sets, where['out'], root)
    found = DEADCODE.search(argv[-1]) if argv else None
    if found: return 1 if found.groups() in dead else 0
    if argv: return subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=1800).returncode  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- a card's acceptance check, a list argv run in the candidate copy, no shell
    return None

"""One collection of facts, every acceptance: the engines a changed copy is read with, and each card's own check
read from that collection (a probe, the dead-code check) or run."""
import json
import re
import subprocess
import tempfile
from pathlib import Path

DEADCODE = re.compile(r"== \('([^']+)', '([^']*)', '([\w-]+)'\)")


def engines_for(cards):
    """The engines a collection of facts on a changed copy runs: the security gate's (eaos/journeys/execute.py GATE_ENGINES),
    and those a card's own recheck asks again (a security card names the engines that found it)."""
    from ..execute import GATE_ENGINES
    named = set()
    for card in cards:
        argv = card.get('verify_command') or []
        if 'recheck' in argv and '--spec' in argv:
            named |= set((json.loads(argv[argv.index('--spec') + 1]).get('specification') or {}).get('engines') or [])
    return sorted(set(GATE_ENGINES) | named)


def batch_acceptance(report, cards, root, collected=None):
    """{card id: exit code} for every card's acceptance, from one collection of facts on `root` (`collected`,
    when the caller already made it, with engines_for(cards)). A `recheck --spec` acceptance and the dead-code check
    are read from that collection; anything else runs as written."""
    from ...facts.run import collect, read_available
    with tempfile.TemporaryDirectory(prefix='eaos-wave-facts-') as scratch:
        out = Path(collected or scratch)
        if not collected: collect(Path(root).resolve(), out, engines=engines_for(cards))
        sets = read_available(out)
        dead = {(f['location'].get('path'), f['location'].get('symbol'), f['value'].get('rule'))
                for f in (sets.get('deadcode') or {}).get('facts', [])}
        return {card['id']: _acceptance_exit(card, sets, dead, out, root) for card in cards}


def _probe_exit(spec, sets, out):
    from ...analysis.probes import decide_probe
    if (spec.get('specification') or {}).get('query') == 'load_blocker_present' and 'load_model' not in sets:
        from ...analysis.load_model import compute, project
        sets['load_model'] = project(compute(out))
    status, _ = decide_probe(spec, sets)
    return 0 if status == 'REFUTED' else 1 if status in ('CONFIRMED', 'PARTIAL') else 2


def _still(card, out):
    """What a card's own probe still finds on the copy, in its words; '' when its check is not a probe."""
    from ...facts.run import read_available
    from ...analysis.probes import decide_probe
    argv = card.get('verify_command') or []
    if not ('recheck' in argv and '--spec' in argv): return ''
    return decide_probe(json.loads(argv[argv.index('--spec') + 1]), read_available(out))[1]


def _acceptance_exit(card, sets, dead, out, root):
    """One card's acceptance exit: read from the collection when it is a probe or the dead-code check, else run."""
    argv = card.get('verify_command') or []
    if 'recheck' in argv and '--spec' in argv:
        return _probe_exit(json.loads(argv[argv.index('--spec') + 1]), sets, out)
    found = DEADCODE.search(argv[-1]) if argv else None
    if found: return 1 if found.groups() in dead else 0
    if argv: return subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=1800).returncode
    return None

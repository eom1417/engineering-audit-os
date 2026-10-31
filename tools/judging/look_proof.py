"""The style oracle at the gate (M18.8): on a baseline app already checked, the three outcomes a batch can have, each on its own copy through the
lock as a batch runs it: a zero-change edit passes, a colour changed without a word is refused, the same colour declared passes.

    python tools/judging/look_proof.py <the baseline app's folder, checked>
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from eaos.journeys import guided  # noqa: E402
from eaos.core.project import state as project_state  # noqa: E402
from eaos.journeys.fix.execute import commit_all, own_batch  # noqa: E402
from eaos.live.behavior.lock import LockPass, verify_lock  # noqa: E402
from eaos.live.behavior.look_oracle import look_changed  # noqa: E402

PAGE = 'index.html'
COLOUR = re.compile(r'#[0-9a-fA-F]{6}\b')


def _first_colour(text):
    found = COLOUR.search(text)
    if not found: raise SystemExit(f'{PAGE} writes no colour to change')
    return found[0]


def _next(colour):
    return colour[:-1] + ('0' if colour[-1].lower() == 'f' else format(int(colour[-1], 16) + 1, 'x'))


def _rgb(colour):
    return 'rgb(' + ', '.join(str(int(colour[i:i + 2], 16)) for i in (1, 3, 5)) + ')'


def edits(text):
    """{name: (the page edited, what the batch declares)}."""
    colour = _first_colour(text)
    token = text.replace(colour, 'var(--proof)').replace('<style>', f'<style>:root{{--proof:{colour}}}', 1)
    shifted = text.replace(colour, _next(colour))
    return {'zero': (token, []), 'undeclared': (shifted, []),
            'declared': (shifted, [{'property': None, 'from': _rgb(colour), 'to': _rgb(_next(colour))}])}


def outcome(state, name, page, look):
    report, runtime = guided.report_of(state), project_state.runtime_of(state)
    root, _ = own_batch(state['project'], runtime, f'LOOK-{name}')
    (Path(root) / PAGE).write_text(page, encoding='utf-8')
    commit_all(root, f'look proof: {name}')
    verdict = verify_lock(report, root, runtime, LockPass(f'look-{name}', exact=look == []))
    return verdict['failed'], look_changed(runtime, f'look-{name}', look)


def main(project):
    state = guided.load(str(Path(project).resolve()))
    text = (Path(state['project']) / PAGE).read_text(encoding='utf-8')
    wanted = {'zero': False, 'undeclared': True, 'declared': False}
    problems = []
    for name, (page, look) in edits(text).items():
        failed, said = outcome(state, name, page, look)
        print(f'{name}: {failed} spec(s) failed; oracle: {said[:300] or "nothing undeclared"}')
        if bool(said) != wanted[name]: problems.append(name)
    print('look proof: ' + (f"wrong on {', '.join(problems)}" if problems else 'a zero change kept, an undeclared one refused, a declared one kept'))
    return 1 if problems else 0


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))

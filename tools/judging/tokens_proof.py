"""A design batch on a real app (M18.18): on a project already checked with its app running, its look's values named, nothing asked of a model, and the
batch's verdict as a person would get it. Run it on the lab's stacks (tools/judging/design_lab.json, tools/corpus.json).

    python tools/judging/tokens_proof.py <the project's folder, checked>
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from eaos.core.project import state as project_state  # noqa: E402
from eaos.journeys import guided  # noqa: E402
from eaos.journeys.fix.tokens_batch import make, proposal  # noqa: E402
from eaos.live.app import setup as live_setup  # noqa: E402


def main(project):
    state = guided.load(str(Path(project).resolve()))
    runtime = project_state.runtime_of(state)
    live_setup.authorize(state['project'], runtime, live_setup.owner(state['project']))
    drawn = proposal(state['project'])
    print('would name:', json.dumps({k: (len(v) if k == 'files' else v) for k, v in drawn.items()}, ensure_ascii=False)[:400])
    if drawn['refused']: return 0
    began = time.monotonic()
    summary = make({'target': state['project'], 'runtime': runtime, 'number': 1, 'report': guided.report_of(state), 'deliver_as': 'proof/design-1'})
    print(f"{round(time.monotonic() - began)} s; kept {len(summary['kept'])} files; refused: {str(summary['refused'])[:1400]}")
    return 0 if summary['kept'] else 1


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))

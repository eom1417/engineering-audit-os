"""The fix proof (M7.0): a real batch on the checked baseline app, through every gate, as an assistant would send it.

Four of its dead-module cards are fixed in one batch: one soundly (the batch's own codemod deletes the module), three
each deleting their module and breaking something besides, one way each:
  TASK-024  a screen: the home screen says something else (the behaviour lock)
  TASK-025  a test: the report's total loses its decimals (the project's own test)
  TASK-026  a boundary: a new write that no sign-in guards (the layers, at the edit)
The proof holds when only the sound card reaches the batch's branch, each breaking one is refused for its own break,
and the person's project is untouched (its branch, its commit, its files) until accept.

    python tools/fix_proof.py <the baseline app's folder, checked>      (tools/golden_trial.sh runs it)
"""
import os
import subprocess
import sys
from pathlib import Path

os.environ['EAOS_HEADLESS'] = '1'           # no Studio opens for the batch

from eaos.journeys import agent_tools, guided  # noqa: E402
from eaos.live.app import setup as live_setup  # noqa: E402

SOUND = 'TASK-023'
EDITS = {
    'TASK-024': [{'path': 'web/Checkout.jsx', 'delete': True},
                 {'path': 'index.html', 'find': '<p>Your orders, their reports and your account.</p>', 'replace': '<p>Welcome.</p>'}],
    'TASK-025': [{'path': 'web/Orders.jsx', 'delete': True},
                 {'path': 'report.js', 'find': 'total: total.toFixed(2)', 'replace': 'total: String(total)'}],
    'TASK-026': [{'path': 'web/payments.js', 'delete': True},
                 {'path': 'server.js', 'find': "  if (url.pathname === '/api/login' && req.method === 'POST') return login(req, res);",
                  'replace': "  if (url.pathname === '/api/wipe' && req.method === 'POST') { orders.length = 0; return send(res, 200, {}); }\n"
                             "  if (url.pathname === '/api/login' && req.method === 'POST') return login(req, res);"}],
}


def done(answer, project):
    """A job's answer once it ends."""
    while answer.get('status') in ('running', 'busy') and answer.get('job'):
        answer = agent_tools.wait(answer['job'], 600, project)
    return answer.get('result') or answer


def _git(project, *argv):
    return subprocess.run(['git', '-C', project, *argv], capture_output=True, text=True).stdout.strip()


def _where(project):
    """The person's branch, commit and unsaved files: what a batch must leave alone until accept."""
    return _git(project, 'rev-parse', '--abbrev-ref', 'HEAD'), _git(project, 'rev-parse', 'HEAD'), _git(project, 'status', '--porcelain')


def _batch(project):
    """The app set up and locked, then the batch: opened on the four cards, the breaking ones sent by hand, handed over.
    ({card: its fix_edit answer}, the hand-over's answer)."""
    state = guided.load(project)
    live_setup.authorize(guided.source(state), guided.runtime_of(state), 'fix proof')
    ran = live_setup.setup(guided.source(state), guided.runtime_of(state), report=guided.report_of(state), provider=None)
    state['setup'] = {'commit': guided.tip(state), 'ok': ran['ok'], 'attempts': ran['attempts'], 'limitations': ran['limitations']}
    guided.safety_run(state)
    done(agent_tools.fix_start(project, cards=[SOUND, *EDITS]), project)
    # the batch's codemods delete every dead module by themselves: the breaking cards are taken back, then sent as an
    # assistant that also broke something would send them
    for card in EDITS: agent_tools.fix_skip(card, 'sent again by hand', project=project)
    edited = {card: done(agent_tools.fix_edit(card, edits, project=project), project) for card, edits in EDITS.items()}
    return edited, done(agent_tools.fix_finish(project, leave_out=True), project)


def _problems(project, edited, finished, moved):
    """What the batch did that it must not have: [] when the proof holds."""
    problems = [] if edited['TASK-026'].get('kept') is False else [f"the unguarded write was kept at its edit: {edited['TASK-026']}"]
    if (finished.get('kept') or []) != [SOUND]:
        problems.append(f"the branch keeps {finished.get('kept')}, not the sound card alone; left out: {finished.get('failed')}")
    if moved: problems.append(f"the person's project changed before accept: {moved}")
    if 'legacy.js' in _git(project, 'ls-tree', '-r', '--name-only', finished.get('branch') or 'HEAD').split():
        problems.append(f"the branch {finished.get('branch')} still has legacy.js")
    return problems


def main(project):
    project = str(Path(project).resolve())
    before = _where(project)
    edited, finished = _batch(project)
    after = _where(project)
    problems = _problems(project, edited, finished, f'{before} -> {after}' if after != before else '')
    refused = '; '.join(f'{card} ({str(why)[:120]})' for card, why in (finished.get('failed') or {}).items())
    print('fix proof: ' + ('; '.join(problems) if problems else f"the sound card reached {finished.get('branch')}; refused: "
                           f"TASK-026 at its edit ({str(edited['TASK-026'].get('why'))[:120]}), {refused}"))
    return 1 if problems else 0


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))

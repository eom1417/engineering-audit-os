"""The fix proof (M7.0): a real batch on the checked baseline app, through every gate, as an assistant would send it.

Five cards are fixed in one batch. Two soundly: a dead module (legacy.js, the batch's own codemod deletes it) and one
source per pattern (M15.7: the reports screen's lines, copied into the export and the invoice, written once in
report.js and called from both, what differed a parameter; the behaviour lock green). Three dead-module cards each
delete their module and break something besides, one way each:
  web/Checkout.jsx  a screen: the home screen says something else (the behaviour lock)
  web/Orders.jsx    a test: the report's total loses its decimals (the project's own test)
  web/payments.js   a boundary: a new write that no sign-in guards (the layers, at the edit)
Each card is found in the check's plan by its module, never by its number: a new kind of card renumbers the plan.
The proof holds when only the sound cards reach the batch's branch, each breaking one is refused for its own break,
and the person's project is untouched (its branch, its commit, its files) until accept.

    python tools/fix_proof.py <the baseline app's folder, checked>      (tools/golden_trial.sh runs it)
"""
import json
import os
import subprocess
import sys
from pathlib import Path

os.environ['EAOS_HEADLESS'] = '1'           # no Studio opens for the batch

from eaos.journeys import agent_tools, guided  # noqa: E402
from eaos.live.app import setup as live_setup  # noqa: E402

SOUND = 'legacy.js'
COPIED = 'invoice.js'            # the near copies' card is found by this place


def one_source(project):
    """The sound fix of the near copies: orderLines written once in report.js, what the invoice did differently (a
    missing quantity counted as none) its parameter, and the export and the invoice calling it."""
    def whole(path, first, last):
        text = (Path(project) / path).read_text(encoding='utf-8')
        start = text.index(first)
        return text[start:text.index(last, start) + len(last)]
    export = whole('export.js', '// The orders as a file to download.', '`\\ntotal,${total.toFixed(2)}`;\n}\n')
    invoice = whole('invoice.js', '// The invoice of one order', "count: lines.length };\n}\n")
    return [
        {'path': 'report.js', 'find': 'function orderLines(orders) {', 'replace': 'function orderLines(orders, missing = 1) {'},
        {'path': 'report.js', 'find': '    const quantity = Number(order.quantity) || 1;\n    const amount = price * quantity;\n    total += amount;\n    lines.push',
         'replace': '    const quantity = Number(order.quantity) || missing;\n    const amount = price * quantity;\n    total += amount;\n    lines.push'},
        {'path': 'export.js', 'find': export, 'replace': "const { orderLines } = require('./report');\n\n// The orders as a file to download.\n"
                                                        "function exportLines(orders) {\n  const { lines, total } = orderLines(orders);\n"
                                                        "  return lines.map(line => [line.item, line.quantity, line.price, line.amount].join(',')).join('\\n') + `\\ntotal,${total}`;\n}\n"},
        {'path': 'invoice.js', 'find': invoice, 'replace': "// The invoice of one order: the reports screen's lines, a missing quantity counted as none.\n"
                                                              "const { orderLines } = require('./report');\n\nconst invoiceLines = orders => orderLines(orders, 0);\n"},
    ]


EDITS = {
    'web/Checkout.jsx': [{'path': 'web/Checkout.jsx', 'delete': True},
                 {'path': 'index.html', 'find': '<p>Your orders, their reports and your account.</p>', 'replace': '<p>Welcome.</p>'}],
    'web/Orders.jsx': [{'path': 'web/Orders.jsx', 'delete': True},
                 {'path': 'report.js', 'find': 'total: total.toFixed(2)', 'replace': 'total: String(total)'}],
    'web/payments.js': [{'path': 'web/payments.js', 'delete': True},
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


def cards(project):
    """{module: the id of its dead-module card} in the check's plan, and COPIED: the near copies' card."""
    plan = json.loads((guided.report_of(guided.load(project)) / 'plan.json').read_text(encoding='utf-8'))
    tasks = plan.get('tasks') or []
    found = {task['paths'][0]: task['id'] for task in tasks if task.get('pattern') == 'remove_dead' and len(task.get('paths') or []) == 1}
    return {**found, COPIED: next((task['id'] for task in tasks if _copied(task)), None)}


def _copied(task):
    """Whether a card is the near copies' of COPIED."""
    return task.get('pattern') == 'one_source' and COPIED in (task.get('paths') or []) and 'near copies' in str(task.get('title')).lower()


def _batch(project, ids):
    """The app set up and locked, then the batch: opened on the four cards, the breaking ones sent by hand, handed over.
    ({card: its fix_edit answer}, the hand-over's answer)."""
    state = guided.load(project)
    live_setup.authorize(guided.source(state), guided.runtime_of(state), 'fix proof')
    ran = live_setup.setup(guided.source(state), guided.runtime_of(state), report=guided.report_of(state), provider=None)
    state['setup'] = {'commit': guided.tip(state), 'ok': ran['ok'], 'attempts': ran['attempts'], 'limitations': ran['limitations']}
    guided.safety_run(state)
    done(agent_tools.fix_start(project, cards=[ids[SOUND], ids[COPIED], *(ids[module] for module in EDITS)]), project)
    # the batch's codemods delete every dead module by themselves: the breaking cards are taken back, then sent as an
    # assistant that also broke something would send them
    for module in EDITS: agent_tools.fix_skip(ids[module], 'sent again by hand', project=project)
    edited = {module: done(agent_tools.fix_edit(ids[module], edits, project=project), project)
              for module, edits in [(COPIED, one_source(project)), *EDITS.items()]}
    return edited, done(agent_tools.fix_finish(project, leave_out=True), project)


def _problems(project, edited, finished, moved, sound):
    """What the batch did that it must not have: [] when the proof holds."""
    problems = [] if edited['web/payments.js'].get('kept') is False else [f"the unguarded write was kept at its edit: {edited['web/payments.js']}"]
    if sorted(finished.get('kept') or []) != sorted(sound):
        problems.append(f"the branch keeps {finished.get('kept')}, not the sound cards alone; left out: {finished.get('failed')}")
    if 'orderLines(orders, 0)' not in _git(project, 'show', f"{finished.get('branch') or 'HEAD'}:invoice.js"):
        problems.append(f"the branch {finished.get('branch')} does not call the one source from the invoice")
    if moved: problems.append(f"the person's project changed before accept: {moved}")
    if 'legacy.js' in _git(project, 'ls-tree', '-r', '--name-only', finished.get('branch') or 'HEAD').split():
        problems.append(f"the branch {finished.get('branch')} still has legacy.js")
    return problems


def main(project):
    project = str(Path(project).resolve())
    before = _where(project)
    ids = cards(project)
    edited, finished = _batch(project, ids)
    after = _where(project)
    if ids[COPIED] is None: return print('fix proof: the check made no card of the near copies of invoice.js') or 1
    problems = _problems(project, edited, finished, f'{before} -> {after}' if after != before else '', [ids[SOUND], ids[COPIED]])
    refused = '; '.join(f'{card} ({str(why)[:120]})' for card, why in (finished.get('failed') or {}).items())
    print('fix proof: ' + ('; '.join(problems) if problems else f"the sound cards reached {finished.get('branch')}; refused: "
                           f"{ids['web/payments.js']} at its edit ({str(edited['web/payments.js'].get('why'))[:120]}), {refused}"))
    return 1 if problems else 0


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))

"""The rules proof (M16.6): the person's own rules on a project that keeps breaking them, end to end, no token spent.

On a copy of the golden app, people's records are written in three files (the requirement the person keeps repeating:
"the people's data lives only in the database") and a total is kept to two decimals by a test of the project's own.
Then, as the person and their assistant would:
  1. the first rule is said through MCP and pinned, then said again in the terminal (counted, never a second rule); the
     second is said for the batch of fixes only (not pinned); each gets its guard (a pattern proved on its examples, the
     project's own test);
  2. the check makes one card for the first rule with its three places;
  3. one batch fixes it: a fix of one place only is refused (the card's own check still finds the rest), a fix of every
     place that breaks the second rule is refused with its words, the sound fix is kept, handed over and accepted;
  4. the second rule stops with its batch; the first, pinned, holds on: with the commit hook on (the person's yes), a
     later commit that writes a phone number in the code again is refused, in seconds, saying it came back.

    EAOS_HOME=<scratch> EAOS_OUTPUT=<scratch> python tools/rules_proof.py <an empty folder>
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

os.environ['EAOS_HEADLESS'] = '1'

from eaos.journeys import agent_tools, guided  # noqa: E402
from eaos.live.app import setup as live_setup  # noqa: E402
from eaos.interfaces import rules as person_rules  # noqa: E402
from eaos.interfaces.mcp_server import rules as tools  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WORDS = 'The people\'s data lives only in the database: never write names, phones or e-mails in the code'
RECORDS = {'contacts.js': 'contacts', 'team.js': 'team', 'seed.js': 'customers'}
PEOPLE = "[\n  { name: 'Sara Ali', phone: '0551234567' },\n  { name: 'Omar Saleh', phone: '0559876543' },\n]"
GUARD = {'kind': 'pattern', 'language': 'javascript', 'message': "people's data written in the code",
         'rule': {'kind': 'object', 'has': {'kind': 'pair', 'has': {'field': 'key', 'regex': '^(name|phone|email)$'}}, 'inside': {'kind': 'array', 'stopBy': 'end'}},
         'files': ['*.js'], 'examples': {'broken': ["const team = [{ name: 'Sara', phone: '055' }];"],
                                         'kept': ["const pages = [{ path: '#/now', label: 'Now' }];", "const team = await db.all('team');"]}}
TOTAL = "// A total as the screens show it.\nmodule.exports = amount => Number(amount).toFixed(2);\n"
TOTAL_TEST = ("const test = require('node:test');\nconst assert = require('node:assert');\n"
              "test('a total keeps two decimals', () => assert.strictEqual(require('./total')(3), '3.00'));\n")


def git(project, *argv, check=True):
    return subprocess.run(['git', '-C', str(project), *argv], capture_output=True, text=True, check=check)


def made(folder):
    """The golden app with people's records in three files and its total's test: a git project."""
    project = Path(folder) / 'app'
    shutil.copytree(ROOT / 'tests/fixtures/golden-app', project)
    for name, what in RECORDS.items():
        (project / name).write_text(f'// The {what}, typed in while the page was built.\nmodule.exports = {PEOPLE};\n', encoding='utf-8')
    (project / 'total.js').write_text(TOTAL, encoding='utf-8')
    (project / 'total.test.js').write_text(TOTAL_TEST, encoding='utf-8')
    git(project.parent, 'init', '-q', str(project))
    git(project, 'add', '-A')
    git(project, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'the app')
    return project


def said(project):
    """Step 1: the rules said through two doors, pinned or for the batch, each guarded."""
    first = tools.rule('add', words=WORDS, pin=True, person_agreed=True, project=str(project))
    again = person_rules.add(project, WORDS.replace(':', ',') + '!', 'terminal')
    total = person_rules.add(project, 'Every total keeps two decimals', 'terminal')
    tools.rule('guard', id=first['rule']['id'], guard=GUARD, project=str(project))
    person_rules.guard(project, total['rule']['id'], {'kind': 'test', 'command': ['node', '--test', 'total.test.js'], 'files': ['total.js']})
    return {'pinned': first['rule']['id'], 'again': again['repeat'], 'batch': total['rule']['id']}


def checked(project):
    """Step 2: the check (the app run in its copy, no AI); the rule's card and its places."""
    eaos = [sys.executable, '-m', 'eaos', 'check', '--run-app', '--assistant', 'none', '--lang', 'en', '--watch', '--project', str(project)]
    subprocess.run(eaos, cwd=project, capture_output=True, text=True, timeout=3600, env={**os.environ, 'PYTHONPATH': str(ROOT)})
    plan = json.loads((guided.report_of(guided.load(project)) / 'plan.json').read_text(encoding='utf-8'))
    return next((t for t in plan['tasks'] if t.get('pattern') == 'person_rule'), None)


def done(answer, project):
    while answer.get('status') in ('running', 'busy') and answer.get('job'):
        answer = agent_tools.wait(answer['job'], 600, project)
    return answer.get('result') or answer


def _database(name):
    return {'path': name, 'write': f"// The {RECORDS[name]}, read from the database.\nconst db = require('./db');\n"
                                   f"module.exports = () => db.all('{RECORDS[name]}');\n"}


DB = {'path': 'db.js', 'write': "// The app's database (a stand-in the tests replace).\nmodule.exports = { all: async table => [] };\n"}
EDITS = {
    'one place': [DB, _database('contacts.js')],
    'every place, the totals broken': [DB, *map(_database, RECORDS), {'path': 'total.js', 'write': 'module.exports = amount => String(amount);\n'}],
    'every place': [DB, *map(_database, RECORDS)],
}


def batch(project, card, rules):
    """Step 3: the batch, its edits as an assistant would send them, handed over and accepted."""
    state = guided.load(project)
    live_setup.authorize(guided.source(state), guided.runtime_of(state), 'rules proof')
    ran = live_setup.setup(guided.source(state), guided.runtime_of(state), report=guided.report_of(state), provider=None)
    state['setup'] = {'commit': guided.tip(state), 'ok': ran['ok'], 'attempts': ran['attempts'], 'limitations': ran['limitations']}
    guided.safety_run(state)
    opened = done(agent_tools.fix_start(project, cards=[card['id']]), project)
    told = [r['id'] for r in (opened.get('to_do') or [{}])[0].get('your_rules') or []]
    edited = {name: done(agent_tools.fix_edit(card['id'], edits, project=project), project) for name, edits in EDITS.items()}
    finished = done(agent_tools.fix_finish(project), project)
    accepted = agent_tools.accept(project, person_agreed=True)
    return {'told': told, 'edited': edited, 'finished': finished, 'accepted': accepted.get('status')}


def committed_again(project):
    """Step 4: the hook on, and a later commit that writes people's data in the code again: (refused, seconds, said)."""
    person_rules.hook(project, True, agreed=True)
    (project / 'staff.js').write_text(f"// The staff, written in again.\nmodule.exports = {PEOPLE};\n", encoding='utf-8')
    git(project, 'add', '-A')
    began = time.monotonic()
    commit = git(project, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'staff', check=False)
    return commit.returncode != 0, round(time.monotonic() - began, 1), commit.stdout + commit.stderr


def problems(rules, card, fixed, again):
    edited, found = fixed['edited'], []
    if rules['again'] != 1: found.append(f"the rule said again made another rule ({rules['again']})")
    if not card or sorted(p.split(':')[0] for p in card.get('paths') or []) != sorted(RECORDS): found.append(f'the card does not name the three places: {card}')
    if sorted(fixed['told']) != sorted([rules['pinned'], rules['batch']]): found.append(f"the assistant was not told both rules: {fixed['told']}")
    if edited['one place'].get('kept') is not False: found.append(f"a fix of one place was kept: {edited['one place']}")
    if 'Every total keeps two decimals' not in str(edited['every place, the totals broken'].get('why')): found.append(f"the fix that broke the totals was not refused by its rule: {edited['every place, the totals broken']}")
    if edited['every place'].get('kept') is not True or fixed['accepted'] != 'accepted': found.append(f"the sound fix was not kept and taken in: {edited['every place']}, {fixed['accepted']}")
    if not again[0] or 'came back' not in again[2]: found.append(f'the later commit was not refused as a rule that came back: {again}')
    return found


def main(folder):
    project = made(Path(folder).resolve())
    rules = said(project)
    card = checked(project)
    fixed = batch(project, card, rules) if card else {'told': [], 'edited': {name: {} for name in EDITS}, 'accepted': None}
    listed = {r['id']: r for r in person_rules.listing(project)['rules']}
    again = committed_again(project)
    found = problems(rules, card, fixed, again)
    if listed[rules['batch']]['state'] != 'ended': found.append(f"the batch's rule did not stop with its batch: {listed[rules['batch']]}")
    print(json.dumps({'card': card and card['id'], 'told': fixed['told'], 'refused': {k: str(v.get('why'))[:160] for k, v in fixed['edited'].items() if v.get('kept') is False},
                      'branch': (fixed.get('finished') or {}).get('branch'), 'batch_rule': listed[rules['batch']]['history'][-1],
                      'hook': {'refused': again[0], 'seconds': again[1], 'said': again[2].strip()[-300:]}}, ensure_ascii=False, indent=1))
    print('rules proof: ' + ('; '.join(found) if found else 'every rule kept, guarded, found in all its places, fixed in one batch, '
                             'the batch\'s rule ended with it, the pinned one held at the commit'))
    return 1 if found else 0


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))

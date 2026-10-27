"""The three journeys proved end to end (M9.3): repair a corpus app, build from a PRD, add a feature, with the real
assistant, and the runtime of one full check measured against the M1 target (docs/METRICS.md "Runtime", <= 100 MB).

    python tools/journeys_proof.py <scratch> <journey> [...]      journeys, in this order when several are named:
      repair-cli     the smallest passing corpus app with screens (flaskr), checked with `eaos check --run-app`, then one
                     card fixed with `eaos fix --assistant claude` and handed over on its branch
      extend         on the repair-cli app, its batch accepted (`eaos accept`): a feature added through the MCP tools
                     (extend_start, extend_plan, fix_start ... fix_finish) by Claude, headless
      repair-studio  the same repair on a fresh copy through a Studio's action API on port 8198 (token, CSRF, origin)
      extend-studio  on the repair-studio app: accept, the Studio's extend_start run, then a Fix of the cards it planned
      build          a ten-line PRD built through the MCP tools by Claude, headless, to its first milestone's proof gate
                     (build_finish delivering eaos/build-1)
      runtime[=<project home>]  a full check's runtime (tools/metrics.py `size`), its largest folders (repair-cli's)

Each journey runs in <scratch>/<journey>/ with an EAOS home of its own; each step's outcome (passed, seconds, the
assistant's cost, the reason on failure) goes into <scratch>/results/<journey>.json. Run it in a transient unit.
"""
import contextlib
import json
import os
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
os.environ['EAOS_HEADLESS'] = '1'                       # no Studio opens by itself for a run
os.environ.setdefault('EAOS_SIGN_IN_WAIT', '30')        # nobody signs in to a proof

import corpus  # noqa: E402  (beside this file)
from fix_proof import _git  # noqa: E402
from metrics import MB, size  # noqa: E402

EAOS = str(Path(sys.executable).parent / 'eaos')
APP = 'flaskr'                  # the smallest passing corpus app with screens (task-api has none: no safety net to fix behind)
PORT = 8198
ASSISTANT = 'claude'
RUN_LIMIT = 40 * 60             # seconds one run may take
PRD = """# Reading list
A small web app where one person keeps the books they want to read.
- The home page lists the books, newest first, with title and author.
- A form adds a book: title (required) and author (required).
- Each book can be marked as read; read books show a tick.
- A book can be deleted.
- The data is kept in a local SQLite database.
- English only; one user, no sign-in.
- It must run with one command and have tests for every feature.
"""
# A link on every page: refused on every screen before the lock knew an intended change (M9.7).
FEATURE = ('Add an About page at /about saying "Flaskr, a small blog" with the number of posts, linked as "About" from '
           'the navigation every page shows.')



# ---------------------------------------------------------------- recording

class Journey:
    """One journey's folder, its own EAOS home and output, and its steps' outcomes."""

    def __init__(self, scratch, name):
        self.name, self.folder = name, Path(scratch) / name
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = Path(scratch) / 'results' / f'{name}.json'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.steps = []
        os.environ.update(EAOS_HOME=str(self.folder / 'home'), EAOS_OUTPUT=str(self.folder / 'output'))

    def step(self, name, work):
        """work() -> {'passed': bool, 'cost_usd'?, 'reason'?, ...}: timed and kept; an exception is its failure."""
        began = time.monotonic()
        try: outcome = work()
        except Exception as failed:      # noqa: BLE001 -- any failure of a step is its outcome, recorded with its reason
            outcome = {'passed': False, 'reason': f'{type(failed).__name__}: {failed}', 'trace': traceback.format_exc()[-1500:]}
        outcome = {'step': name, 'passed': bool(outcome.pop('passed')), 'seconds': round(time.monotonic() - began), **outcome}
        self.steps.append(outcome)
        self.path.write_text(json.dumps({'journey': self.name, 'steps': self.steps}, indent=1) + '\n', encoding='utf-8')
        print(f"{self.name}/{name}: {'PASS' if outcome['passed'] else 'FAIL'} {outcome['seconds']} s "
              f"{outcome.get('cost_usd') or ''} {outcome.get('reason') or ''}", flush=True)
        return outcome


def eaos(*argv, cwd=None, timeout=RUN_LIMIT):
    done_ = subprocess.run([EAOS, *argv], cwd=cwd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    return done_.returncode, (done_.stdout + done_.stderr)[-3000:]


def cost(use):
    return round(use['cost_usd'], 3) if use and use.get('cost_usd') is not None else None


# ---------------------------------------------------------------- the app and its check

def fetched(folder):
    """The corpus app at its pinned commit in folder/app, a repository of its own (tools/corpus.py)."""
    app = next(a for a in json.loads(corpus.CATALOG.read_text(encoding='utf-8'))['apps'] if a['name'] == APP)
    if not (folder / 'app').exists(): corpus.fetch(app, folder)
    return folder / 'app'


def report_of(app):
    from eaos.journeys import agent_tools, guided
    return guided.report_of(agent_tools.state_of(str(app)))


def checked(app):
    """What a check left: passed when no stage failed (one that does not apply says `unavailable`, with its reason) and
    the plan has cards."""
    from eaos.core.system.usage import of_check
    report = report_of(app)
    manifest = json.loads((report / 'run-manifest.json').read_text(encoding='utf-8'))
    said = {name: f"{row['status']}: {row.get('reason')}" for name, row in manifest['stages'].items() if row['status'] != 'ok'}
    bad = {name: why for name, why in said.items() if not why.startswith(('skipped', 'unavailable'))}
    cards = len(json.loads((report / 'plan.json').read_text(encoding='utf-8')).get('tasks') or [])
    return {'passed': bool(cards) and not bad, 'stages': len(manifest['stages']), 'not_ok': said, 'cards': cards,
            'check_seconds': round(manifest.get('seconds') or 0), 'cost_usd': cost((of_check(report) or {}).get('total')),
            **({'reason': f'stages failed: {bad}'} if bad else {})}


def earlier(app):
    """The check an earlier run of this proof left in the journey's home, judged again rather than paid for twice."""
    try: return {**checked(app), 'reused': 'the check of an earlier run of this proof (check_seconds is its wall time)'}
    except (OSError, ValueError, LookupError): return None


def card_to_fix(app):
    """The card the repair fixes: the most important one EAOS can fix by itself, else the most important one."""
    from eaos.journeys import agent_tools
    rows = agent_tools.findings(str(app), fixable_only=True, limit=1)['findings'] or agent_tools.findings(str(app), limit=1)['findings']
    if not rows: raise LookupError('the check made no card to fix')
    return rows[0]['id']


def batch_outcome(app, record, use, branches_before):
    """A fix run's outcome: passed when it ended done and its batch reached a new branch of the project."""
    new = sorted(set(_git(str(app), 'branch', '--list', 'eaos/*', '--format=%(refname:short)').split()) - set(branches_before))
    result = record.get('result') or {}
    kept = result.get('cards_closed') or []
    passed = record.get('state') == 'done' and bool(new)
    return {'passed': passed, 'run': record['id'], 'state': record.get('state'), 'branch': new, 'cards_closed': kept,
            'cost_usd': cost(use), **({} if passed else {'reason': f"run {record.get('state')}, new branches {new}: "
                                                                    f"{str(record.get('error') or result)[:400]}"})}


def branches(app):
    return _git(str(app), 'branch', '--list', 'eaos/*', '--format=%(refname:short)').split()


# ---------------------------------------------------------------- the journeys

def repair_cli(scratch):
    journey = Journey(scratch, 'repair-cli')
    app = fetched(journey.folder)
    def check():
        if (before := earlier(app)): return before
        code, said = eaos('check', '--project', str(app), '--run-app', '--assistant', ASSISTANT, '--sign-in', 'none', '--lang', 'en', '--watch')
        return checked(app) if code == 0 else {'passed': False, 'reason': f'eaos check exit {code}: {said[-600:]}'}
    if not journey.step('check', check)['passed']: return journey
    journey.step('fix', lambda: fix_cli(app))
    return journey


def fix_cli(app):
    from eaos.interfaces import govern
    card, before = card_to_fix(app), branches(app)
    code, said = eaos('fix', card, '--project', str(app), '--assistant', ASSISTANT, '--yes', '--lang', 'en')
    if code: return {'passed': False, 'card': card, 'reason': f'eaos fix exit {code}: {said[-600:]}'}
    actions = govern.core(str(app))
    record = max((r for r in actions.store.all() if r.get('verb') == 'fix'), key=lambda r: r.get('created') or '')
    eaos('watch', record['id'], '--project', str(app), '--lang', 'en')
    record = actions.store.load(record['id'])
    return {'card': card, **batch_outcome(app, record, actions._run_use(record)['usage'], before)}


def extend(scratch):
    journey = Journey(scratch, 'repair-cli')         # the repaired app, its home and its check
    journey.name, journey.path, journey.steps = 'extend', journey.path.with_name('extend.json'), []
    app = journey.folder / 'app'
    def accept():
        repaired = json.loads(journey.path.with_name('repair-cli.json').read_text(encoding='utf-8'))['steps'][-1]
        if not (repaired['step'] == 'fix' and repaired['passed']): return {'passed': False, 'reason': 'the repair handed over no batch to accept'}
        head = _git(str(app), 'rev-parse', 'HEAD')
        if any(line.startswith(f"{repaired['card']}:") for line in _git(str(app), 'log', '--format=%s').splitlines()):   # its branch goes at accept
            return {'passed': True, 'head': _git(str(app), 'log', '--oneline', '-1'), 'reused': 'accepted by an earlier run of this proof'}
        code, said = eaos('accept', str(app), '--yes', '--lang', 'en')
        moved = _git(str(app), 'rev-parse', 'HEAD') != head
        return {'passed': code == 0 and moved, 'head': _git(str(app), 'log', '--oneline', '-1'),
                **({} if code == 0 and moved else {'reason': f'eaos accept exit {code}, HEAD moved {moved}: {said[-600:]}'})}
    if not journey.step('accept the repair', accept)['passed']: return journey
    prompt = (f'Use the eaos tools, always with project="{app}", to add this feature to the project: {FEATURE} '
              'If status shows a batch still open, fix_abandon it first. Call extend_start with that text, write the spec and call extend_plan until it fits (nobody is here to ask: '
              'take your own recommendation for every choice). Then fix_start with exactly the cards extend_plan added, '
              'build each with fix_read and fix_edit (a test for it too), and call fix_finish; repair on top with '
              'fix_edit card="REPAIR" if it asks. End when fix_finish handed the batch over, saying its branch.')
    def build_feature():
        before = branches(app)
        use, said = assistant(prompt, app, journey.folder, 'm9-proof-extend')
        new = sorted(set(branches(app)) - set(before))
        planned = [m for m in (json.loads((report_of(app) / 'plan.json').read_text(encoding='utf-8')).get('milestones') or [])
                   if str(m.get('id', '')).startswith('EXT') or 'feature' in str(m.get('name', '')).lower()]
        files = _git(str(app), 'diff', '--name-only', f'HEAD...{new[-1]}').split() if new else []
        passed = bool(new) and bool(files)
        return {'passed': passed, 'branch': new, 'files': files, 'milestones_added': [m.get('id') for m in planned], 'cost_usd': cost(use),
                'said': said[-500:], **({} if passed else {'reason': f'no batch handed over: {said[-400:]}'})}
    journey.step('add the feature', build_feature)
    return journey


@contextlib.contextmanager
def served(journey, app):
    """A Studio of the app on PORT for the journey's steps; its action API once it answers, else None."""
    token_file = journey.folder / 'studio.token'
    log, env = open(journey.folder / 'studio.log', 'a'), {**os.environ, 'EAOS_STUDIO_TOKEN_FILE': str(token_file)}
    server = subprocess.Popen([EAOS, 'studio', str(app), '--port', str(PORT), '--no-open'], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, env=env)
    try:
        up = journey.step('studio up', lambda: studio_up(token_file))
        yield Studio(token_file.read_text(encoding='utf-8').strip()) if up['passed'] else None
    finally:      # never left running: a Studio outliving the proof keeps its runs and their assistant going
        server.terminate()
        try: server.wait(30)
        except subprocess.TimeoutExpired: server.kill()
        log.close()


def repair_studio(scratch):
    journey = Journey(scratch, 'repair-studio')
    app = fetched(journey.folder)
    with served(journey, app) as api:
        if api is None: return journey
        def check():
            from eaos.interfaces import govern
            if (before := earlier(app)): return before
            inputs = govern.check_inputs(None, ASSISTANT, None, sign_in='none', run_app=True)
            record = api.run({'action': 'audit', 'inputs': inputs, 'lang': 'en'})
            return checked(app) if record['state'] == 'done' else {'passed': False, 'reason': f"check run {record['state']}: {record.get('error')}"}
        if journey.step('check', check)['passed']: journey.step('fix', lambda: studio_fix(api, app, [card_to_fix(app)]))
    return journey


def studio_fix(api, app, cards):
    """A Fix of these cards as the Studio starts one: its preview, then the run with the preview's confirm token."""
    before, selection = branches(app), {'kind': 'cards', 'cards': cards}
    preview = api.post('/api/actions/fix/preview', {'verb': 'fix', 'selection': selection, 'assistant': ASSISTANT})
    record = api.run({'action': 'fix', 'verb': 'fix', 'selection': selection, 'assistant': ASSISTANT,
                      'confirm': (preview.get('confirm') or {}).get('token')})
    use = api.use(record['id'])
    return {'cards': cards, **batch_outcome(app, record, use, before)}


def extend_studio(scratch):
    """The extend journey through the Studio on the repair-studio app: its repair accepted (the preview's confirm), the
    feature planned by the Studio's "Read a feature's plan to add" run, then built by a Fix of its cards."""
    journey = Journey(scratch, 'repair-studio')
    journey.name, journey.path, journey.steps = 'extend-studio', journey.path.with_name('extend-studio.json'), []
    app = journey.folder / 'app'
    with served(journey, app) as api:
        if api is None: return journey
        def accept():
            repaired = json.loads(journey.path.with_name('repair-studio.json').read_text(encoding='utf-8'))['steps'][-1]
            if api.get(f"/api/runs/{repaired['run']}")['run'].get('outcome') == 'accepted':
                return {'passed': True, 'reused': 'accepted by an earlier run of this proof', 'head': _git(str(app), 'log', '--oneline', '-1')}
            token = api.post('/api/actions/accept/preview', {})['confirm']['token']
            answer = api.post(f"/api/runs/{repaired['run']}/accept", {'confirm': token})
            return {'passed': answer['run'].get('outcome') == 'accepted', 'outcome': answer['run'].get('outcome'), 'head': _git(str(app), 'log', '--oneline', '-1')}
        if not journey.step('accept the repair', accept)['passed']: return journey
        planned = journey.step('plan the feature', lambda: studio_plan(api, app))
        if planned['passed']: journey.step('build the feature', lambda: studio_fix(api, app, planned['cards']))
    return journey


def studio_plan(api, app):
    """The Studio's "Read a feature's plan to add" run, to the cards it plans. The run ends on its question to the person
    ("build it?"): it is stopped there, and their yes is the Fix of its cards, started next."""
    from eaos.journeys import agent_tools
    record = api.run({'action': 'extend_start', 'inputs': {'text': FEATURE}, 'assistant': ASSISTANT, 'lang': 'en'}, until=('waiting_for_person',))
    asked = record['state'] == 'waiting_for_person' and (record.get('question') or {}).get('text')
    if asked: record = api.post(f"/api/runs/{record['id']}/stop", {})['run']
    cards = (agent_tools.state_of(str(app)).get('extend') or {}).get('cards') or []
    use = api.use(record['id'])
    return {'passed': bool(cards) and (record['state'] == 'done' or bool(asked)), 'cards': cards, 'state': record['state'],
            'asked': asked, 'cost_usd': cost(use), 'reason': None if cards else f"no card planned: {str(record.get('result') or record.get('error'))[:400]}"}


def studio_up(token_file, wait=120):
    began = time.monotonic()
    while time.monotonic() - began < wait:
        with socket.socket() as probe:
            if token_file.exists() and probe.connect_ex(('127.0.0.1', PORT)) == 0:
                return {'passed': True, 'session': Studio(token_file.read_text(encoding='utf-8').strip()).get('/api/session')['mode']}
        time.sleep(1)
    return {'passed': False, 'reason': f'no Studio on {PORT} after {wait} s'}


class Studio:
    """The Studio's action API as its page calls it: the launch token on every call, CSRF and the origin on a write."""

    def __init__(self, token):
        self.base, self.token = f'http://127.0.0.1:{PORT}', token
        self.csrf = self.get('/api/session')['csrf']

    def _call(self, method, path, body=None):
        headers = {'X-EAOS-Token': self.token, 'Origin': self.base, 'Content-Type': 'application/json'}
        if method == 'POST': headers['X-EAOS-CSRF'] = self.csrf
        request = urllib.request.Request(self.base + path, json.dumps(body).encode() if body is not None else None, headers, method=method)
        with urllib.request.urlopen(request, timeout=120) as answer: return json.loads(answer.read() or b'{}')

    def get(self, path): return self._call('GET', path)

    def post(self, path, body): return self._call('POST', path, body)

    def use(self, run):
        """What the assistant of a run used, as the Studio's usage page reads it."""
        return next((row['usage'] for row in self.get('/api/usage')['runs'] if row['id'] == run), None)

    def run(self, body, until=()):
        """A run started and followed to its end, or to one of the states `until`; its record."""
        from eaos.core.project.runs import TERMINAL
        run, began = self.post('/api/runs', body)['run'], time.monotonic()
        while run['state'] not in TERMINAL + tuple(until) and time.monotonic() - began < RUN_LIMIT:
            time.sleep(5)
            run = self.get(f"/api/runs/{run['id']}")['run']
        return run


def build(scratch):
    journey = Journey(scratch, 'build')
    app = journey.folder / 'app'
    app.mkdir(exist_ok=True)
    (journey.folder / 'PRD.md').write_text(PRD, encoding='utf-8')
    prompt = (f'Use the eaos tools, always with project="{app}", to build the product of the plan {journey.folder / "PRD.md"}. '
              'blueprint_start with that source, write the spec and blueprint_spec until it is complete (nobody is here to ask: '
              'take your own recommendation for every choice and question), blueprint_design, then build_start with '
              'person_agreed=true (the person agreed by starting this proof). Build every card of the first milestone with '
              'build_read and build_edit (build_skip only a card that cannot pass its gates), then build_finish; when it holds '
              'the milestone back, fix what it says with build_edit card="FIX" and call it again. Stop when build_finish '
              'delivers the first milestone: do not start the second.')
    def first_milestone():
        use, said = assistant(prompt, app, journey.folder, 'm9-proof-build')
        from eaos.journeys.build_from_plan import steps
        state = steps.status(str(app)) if (Path(os.environ['EAOS_HOME'])).exists() else {}
        built = [b for b in branches(app) if b.startswith('eaos/build')]
        return {'passed': bool(built), 'branch': built, 'status': str(state)[:600], 'cost_usd': cost(use), 'said': said[-500:],
                **({} if built else {'reason': f'no milestone delivered: {said[-400:]}'})}
    journey.step('first milestone', first_milestone)
    return journey


def assistant(prompt, app, folder, run):
    """Claude Code, headless, on the EAOS MCP server as a Studio run starts it (eaos/ai/assistant/headless.py), until it
    ends; (its use, what it said last)."""
    from eaos.ai.assistant.headless import ClaudeCode
    from eaos.core.system.usage import from_stream
    stream = folder / f'{run}.jsonl'
    with open(stream, 'w', encoding='utf-8') as out:
        subprocess.run(ClaudeCode().argv(prompt, run, folder), cwd=app, stdout=out, stderr=subprocess.STDOUT,
                       stdin=subprocess.DEVNULL, timeout=RUN_LIMIT)
    lines = stream.read_text(encoding='utf-8').splitlines()
    last = next((json.loads(line).get('result') for line in reversed(lines) if line.startswith('{') and '"type":"result"' in line), '')
    return from_stream(lines), str(last or (lines[-1] if lines else ''))


def runtime(scratch, home=None):
    """The M1 runtime of a full check, as tools/metrics.py measures it, and its largest folders."""
    journey = Journey(scratch, 'runtime-measure')
    journey.name, journey.path = 'runtime', journey.path.with_name('runtime.json')
    def measure():
        project_home = Path(home) if home else next((Path(scratch) / 'repair-cli' / 'home' / 'projects').iterdir())
        folder = project_home / 'runtime'
        mb, files = size(folder)
        top = sorted(((size(child)[0] if child.is_dir() else child.stat().st_size // MB, child.name) for child in folder.iterdir()), reverse=True)[:6]
        return {'passed': mb <= 100, 'project_home': str(project_home), 'runtime_mb': mb, 'files': files, 'target_mb': 100,
                'largest_mb': {name: value for value, name in top}, **({} if mb <= 100 else {'reason': f'{mb} MB over the 100 MB target'})}
    journey.step('runtime', measure)
    return journey


JOURNEYS = {'repair-cli': repair_cli, 'extend': extend, 'repair-studio': repair_studio, 'extend-studio': extend_studio, 'build': build,
            'runtime': runtime}


def results(scratch):
    """Every journey's recorded steps, without the failures' tracebacks."""
    found = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((scratch / 'results').glob('*.json'))]
    return [{**r, 'steps': [{k: v for k, v in step.items() if k != 'trace'} for step in r['steps']]} for r in found]


def main(scratch, names):
    scratch, asked = Path(scratch).resolve(), dict(a.partition('=')[::2] for a in names)
    for name in [n for n in JOURNEYS if n in asked]:
        JOURNEYS[name](scratch, *([asked[name] or None] if name == 'runtime' else []))
    found = results(scratch)
    print(json.dumps(found, indent=1))
    return 0 if all(step['passed'] for r in found for step in r['steps']) else 1


if __name__ == '__main__':
    if len(sys.argv) < 3 or not set(a.split('=')[0] for a in sys.argv[2:]) <= set(JOURNEYS): sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2:]))

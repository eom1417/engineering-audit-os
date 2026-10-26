"""The tidy, proved (M9.5): on three corpus apps of different kinds, the move batch (M8.5) and the context batch (M8.6)
made through their gates on an isolated copy, and an assistant asked the same ten questions about each app before and
after, scored right or wrong, with the files it read and the tokens it spent.

    python tools/tidy_proof.py [name ...] [--scratch DIR] [--model MODEL] [--no-ask] [--out FILE]

Each app (tools/corpus.json) is fetched at its pinned commit into DIR (default $EAOS_CORPUS/tidy), checked
(`eaos check --path look --run-app --assistant none`: its run set up, its screens recorded), then:
  moves     move_batch.proposal, every move the tool can make, made by move_batch.make (the move gate: the public
            surface, every test back by name, the checks, nothing newly broken, the behaviour lock); merged or refused
  context   context_batch.proposal, then context_batch.make; merged, refused, or nothing to trim
  ask       each question asked of the Claude CLI (Read, Grep and Glob only, in a clean export of the app: no run left
            behind), once on the pinned commit, once on the commit the batches left; the expected paths mapped through
            the moves. Right when the answer names an expected path; files read are the distinct paths it Read; tokens
            are the result line's input (cache included) and output tokens.
The results land in DIR/tidy-proof.json and as a Markdown table (--out). Run it as a background job: it takes minutes.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
os.environ['EAOS_HEADLESS'] = '1'
from dev_paths import CORPUS  # noqa: E402
import corpus  # noqa: E402

EAOS = Path(sys.executable).parent / 'eaos'

# Ten questions per app, each with the paths that answer it at the pinned commit (any one of them is right).
QUESTIONS = {
    'flaskr': [
        ('Where is it checked that a user is signed in before a view runs?', ['flaskr/auth.py']),
        ('Which file opens the database connection?', ['flaskr/db.py']),
        ('Where is the database schema (the tables) defined?', ['flaskr/schema.sql']),
        ('Which file handles the endpoint that creates a new blog post?', ['flaskr/blog.py']),
        ('Where is the sign-in (login) endpoint implemented?', ['flaskr/auth.py']),
        ('Where are the configuration values (SECRET_KEY, the database path) set?', ['flaskr/__init__.py']),
        ('Which file creates the Flask application (the app factory)?', ['flaskr/__init__.py']),
        ('Which test file tests registration and login?', ['tests/test_auth.py']),
        ('Where are the shared test fixtures (the test app and client) defined?', ['tests/conftest.py']),
        ('Which template renders the sign-in form?', ['flaskr/templates/auth/login.html']),
    ],
    'task-api': [
        ('Where is it checked that a request carries a valid sign-in token?', ['authMiddleware.js']),
        ('Which file opens the SQLite database and creates its table?', ['db.js']),
        ('Where is the Supabase client created?', ['supabaseClient.js']),
        ('Which file handles the endpoint POST /tasks?', ['index.js']),
        ('Where is the sign-in endpoint (POST /auth/login) implemented?', ['index.js']),
        ('Which file defines the triage endpoint?', ['src/routes/triage.js']),
        ('Where is the LLM client configured (its base URL and API key)?', ['src/llm/client.js']),
        ('Where is the API contract (OpenAPI) of the service?', ['openapi.json']),
        ('Where are the evaluation cases of the triage prompt?', ['evals/cases.json']),
        ('Where is the JSON schema of the triage output defined?', ['src/llm/schema.js']),
    ],
    'next-dashboard': [
        ('Where is sign-in configured (the authentication provider)?', ['lib/auth.ts']),
        ('Which file decides which pages require sign-in (the middleware)?', ['middleware.ts']),
        ('Which file connects to the database and defines the products table?', ['lib/db.ts']),
        ('Where is the server action that deletes a product?', ['app/(dashboard)/actions.ts']),
        ('Which API route seeds the database?', ['app/api/seed/route.ts']),
        ('Which route handles the sign-in callbacks of the auth library?', ['app/api/auth/[...nextauth]/route.ts']),
        ('Which page shows the sign-in screen?', ['app/login/page.tsx']),
        ('Which component renders the table of products?', ['app/(dashboard)/products-table.tsx']),
        ('Where is the Next.js configuration (allowed image hosts)?', ['next.config.ts']),
        ('Which file holds the shared className helper (cn)?', ['lib/utils.ts']),
    ],
}
SCHEMA = {'type': 'object', 'properties': {'answer_paths': {'type': 'array', 'items': {'type': 'string'}},
                                           'files_read': {'type': 'integer'}}, 'required': ['answer_paths', 'files_read']}
PROMPT = ('You are reading the code of the project in the current folder. Answer this question about where things are:\n\n'
          '{question}\n\nanswer_paths: the file(s) that answer it, as paths relative to the current folder, the most specific '
          'first, at most three. files_read: how many files you opened. Look at the code; do not guess.')


def run(argv, cwd, env=None, timeout=1800):
    return subprocess.run([str(a) for a in argv], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)


def git(cwd, *argv):
    return run(['git', *argv], cwd).stdout.strip()


# ---------------------------------------------------------------- the batches

def check(app, folder):
    """The app fetched at its commit, checked, set up and its screens recorded: the guided state."""
    from eaos.journeys import guided
    from eaos.live.app import setup as live_setup
    corpus.fetch(app, folder)
    # --run-app is the person's agreement to run the app in a copy (as tools/corpus.py checks): the run is set up
    run([EAOS, 'check', '--path', 'look', '--run-app', '--assistant', 'none', '--lang', 'en', '--watch'], folder / 'app', timeout=2700)
    state = guided.load(str(folder / 'app'))
    if not guided.set_up(state):
        live_setup.authorize(guided.source(state), guided.runtime_of(state), 'tidy proof')
        ran = live_setup.setup(guided.source(state), guided.runtime_of(state), report=guided.report_of(state), provider=None, say=lambda *_: None)
        state['setup'] = {'commit': guided.tip(state), 'ok': ran['ok'], 'attempts': ran['attempts'], 'limitations': ran['limitations']}
        guided.save(state)
    return state


def batches(state):
    """{moves: {proposed, made, merged, refused, mapping, root}, context: {...}}: both batches through their gates."""
    from eaos.journeys import guided
    from eaos.journeys.fix import context_batch, move_batch
    target, runtime, report = guided.source(state), guided.runtime_of(state), guided.report_of(state)
    drawn = move_batch.proposal(report, target)
    makeable = [m for m in drawn['moves'] if not m['refused']]
    moves = {'proposed': len(drawn['moves']), 'cannot': [f"{m['from']}: {m['refused']}" for m in drawn['moves'] if m['refused']],
             'made': [{'from': m['from'], 'to': m['to'], 'rule': m['rule']} for m in makeable], 'merged': False, 'refused': [],
             'mapping': {}, 'root': None, 'setup_ok': (state.get('setup') or {}).get('ok'),
             'lock': (guided.runtime_of(state) / 'behavior-lock').is_dir()}
    if makeable:
        summary = move_batch.make({'report': report, 'target': target, 'runtime': runtime, 'number': 1, 'moves': makeable})
        moves.update(merged=bool(summary['kept']), refused=summary['refused'], root=summary['root'],
                     mapping={m['from']: m['to'] for m in makeable} if summary['kept'] else {})
    trim = context_batch.proposal(target)
    context = {'files': trim['files'], 'tokens_before': trim['tokens_before'], 'tokens_after': trim['tokens_after'],
               'merged': False, 'refused': [], 'patch': None}
    summary = context_batch.make({'target': target, 'runtime': runtime, 'number': 1})
    context.update(merged=bool(summary['kept']), refused=summary['refused'])
    if summary['kept']: context['patch'] = git(summary['root'], 'format-patch', '--stdout', f"{summary['base']}..HEAD")
    return {'moves': moves, 'context': context}


def exports(folder, state, made):
    """Two clean trees (git archive, nothing a run left): `before` at the pinned commit, `after` with both batches."""
    from eaos.journeys import guided
    source = guided.source(state)
    trees = {}
    for name, repo in (('before', source), ('after', made['moves']['root'] if made['moves']['merged'] else source)):
        tree = folder / name
        shutil.rmtree(tree, ignore_errors=True)
        tree.mkdir()
        subprocess.run(f'git -C "{repo}" archive HEAD | tar -x -C "{tree}"', shell=True, check=True)  # nosec -- our own paths
        trees[name] = tree
    if made['context']['patch']:
        done = subprocess.run(['git', 'apply', '-'], cwd=trees['after'], input=made['context']['patch'], text=True, capture_output=True)
        made['context']['applied_after'] = done.returncode == 0
    return trees


# ---------------------------------------------------------------- the questions

def ask(question, tree, model, log):
    """One question to the Claude CLI in `tree`: {paths, files_read, said_read, tokens, cost, seconds}."""
    argv = ['claude', '-p', PROMPT.format(question=question), '--output-format', 'stream-json', '--verbose', '--model', model,
            '--json-schema', json.dumps(SCHEMA), '--tools', 'Read,Grep,Glob', '--allowedTools', 'Read', 'Grep', 'Glob',
            '--permission-mode', 'dontAsk', '--strict-mcp-config', '--no-session-persistence']
    began = time.monotonic()
    done = run(argv, tree, timeout=600)
    log.write_text(done.stdout, encoding='utf-8')
    read, tools, result = set(), 0, {}
    for line in done.stdout.splitlines():
        try: event = json.loads(line)
        except ValueError: continue
        if event.get('type') == 'assistant':
            for block in (event.get('message') or {}).get('content') or []:
                if block.get('type') == 'tool_use' and block.get('name') in ('Read', 'Grep', 'Glob'):
                    tools += 1
                    if block['name'] == 'Read': read.add(_relative(block['input'].get('file_path', ''), tree))
        elif event.get('type') == 'result': result = event
    usage = result.get('usage') or {}
    answer = result.get('structured_output') or {}
    return {'paths': [_relative(p, tree) for p in answer.get('answer_paths') or []], 'said_read': answer.get('files_read'),
            'files_read': len(read), 'tool_calls': tools, 'cost': result.get('total_cost_usd'), 'seconds': round(time.monotonic() - began),
            'tokens': sum(usage.get(k) or 0 for k in ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens')),
            'error': '' if result.get('subtype') == 'success' else (result.get('subtype') or done.stderr[-200:])}


def _relative(path, tree):
    path = str(path).strip()
    for prefix in (str(tree) + '/', str(Path(tree).resolve()) + '/', './'):
        if path.startswith(prefix): path = path[len(prefix):]
    return path.lstrip('/')


def expected(paths, mapping):
    """The expected paths after the moves: each mapped through the move mapping."""
    return [mapping.get(p, p) for p in paths]


def score(name, trees, mapping, model, folder):
    rows = []
    for number, (question, paths) in enumerate(QUESTIONS[name], 1):
        row = {'question': question}
        for when in ('before', 'after'):
            want = expected(paths, mapping) if when == 'after' else paths
            got = ask(question, trees[when], model, folder / f'ask-{when}-{number}.jsonl')
            row[when] = {**got, 'expected': want, 'right': any(p in got['paths'] for p in want)}
            print(f"  {name} Q{number} {when}: {'right' if row[when]['right'] else 'WRONG'} read={got['files_read']} tokens={got['tokens']}", flush=True)
        rows.append(row)
    return rows


# ---------------------------------------------------------------- the table

def totals(rows, when):
    return {'right': sum(r[when]['right'] for r in rows), 'files': sum(r[when]['files_read'] for r in rows),
            'tools': sum(r[when]['tool_calls'] for r in rows), 'tokens': sum(r[when]['tokens'] for r in rows),
            'cost': round(sum(r[when]['cost'] or 0 for r in rows), 3)}


def table(results, model):
    lines = ['| App | Kind | Moves proposed / made | Move batch | Context batch | Right before → after | Files read before → after '
             '| Tool calls before → after | Tokens before → after |', '|---|---|---|---|---|---|---|---|---|']
    for name, done in results.items():
        moves, context = done['moves'], done['context']
        merged = 'merged' if moves['merged'] else ('nothing to move' if not moves['made'] else 'refused: ' + '; '.join(moves['refused'])[:160])
        trimmed = 'merged' if context['merged'] else 'refused: ' + '; '.join(context['refused'])[:120]
        row = f"| {name} | {done['stack']} | {moves['proposed']} / {len(moves['made'])} | {merged} | {trimmed} |"
        if done.get('questions'):
            b, a = totals(done['questions'], 'before'), totals(done['questions'], 'after')
            row += (f" {b['right']}/10 → {a['right']}/10 | {b['files']} → {a['files']} | {b['tools']} → {a['tools']} "
                    f"| {b['tokens']:,} → {a['tokens']:,} |")
        else: row += ' - | - | - | - |'
        lines.append(row)
    return '\n'.join(lines) + f'\n\nAssistant: Claude Code CLI, model `{model}`, Read/Grep/Glob only, one fresh session per question.\n'


def main(argv):
    names = [a for a in argv if not a.startswith('--')] or list(QUESTIONS)
    option = lambda flag, default: argv[argv.index(flag) + 1] if flag in argv else default  # noqa: E731
    scratch, model = Path(option('--scratch', CORPUS / 'tidy')), option('--model', 'sonnet')
    names = [n for n in names if n not in (option('--scratch', ''), option('--model', ''), option('--out', ''))]
    catalog = {app['name']: app for app in json.loads(corpus.CATALOG.read_text(encoding='utf-8'))['apps']}
    scratch.mkdir(parents=True, exist_ok=True)
    results = {}
    for name in names:
        folder = scratch / name
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir()
        os.environ.update(EAOS_HOME=str(folder / 'home'), EAOS_OUTPUT=str(folder / 'output'))
        began = time.monotonic()
        state = check(catalog[name], folder)
        made = batches(state)
        print(f"{name}: moves {made['moves']['proposed']} proposed, {len(made['moves']['made'])} made, merged={made['moves']['merged']} "
              f"{made['moves']['refused']}; context merged={made['context']['merged']} {made['context']['refused']}", flush=True)
        results[name] = {'stack': catalog[name]['stack'], **made}
        if '--no-ask' not in argv:
            results[name]['questions'] = score(name, exports(folder, state, made), made['moves']['mapping'], model, folder)
        results[name]['seconds'] = round(time.monotonic() - began)
        (scratch / 'tidy-proof.json').write_text(json.dumps(results, indent=1, default=str) + '\n', encoding='utf-8')
    text = table(results, model)
    print(text)
    if '--out' in argv: Path(option('--out', '')).write_text(text, encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

"""What live setup (eaos/live_setup.py) tells the person's assistant when the app does not start: the rules of a
proposal, the project's own setup documents, the code that raised the failure, and the messages that carry them."""
import json
import re
from pathlib import Path

ENV_EXAMPLES = ('.env.example', '.env.sample', '.env.template', '.env.local.example', '.env.development.example', 'example.env')


def read_json(path):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}


ASSIST_SYSTEM = """You set up a web app to run on this computer for automated checks, in an isolated copy, with a
local database EAOS provides. You do not change the app. You answer with one JSON object:
{"action": "final", "result": {"reason": "<one sentence>",
  "env": {"NAME": "value"}, "start": ["argv", "..."] or null, "install": [["argv"]] or null,
  "prepare": [["argv"]] or null, "database": "postgres" or "none" or null,
  "seed_script": "<a Node.js script>" or null, "fixtures": {"E2E_NAME": "value"} or null}}
"env" is the complete environment: it replaces the current one, so keep what still applies. For "start",
"install" and "prepare", null keeps the current value and [] removes it (no prepare commands at all).
"database": "none" when the app runs without one locally; "postgres" gives it EAOS's local PostgreSQL.
The app may be written in any language: JavaScript, or Python (a server it starts itself, its own command line, or
uvicorn and gunicorn). When the current profile starts nothing ("start": ["true"]), EAOS found no JavaScript web
app: read the documentation and say how to install and start the app's web server, on 127.0.0.1 and the profile's
"port". Rules, each one enforced: every address is http://127.0.0.1 or http://localhost; no real secret (generate
values); no command that deploys, publishes, or reaches a hosted service; every command starts with npm, npx, pnpm,
yarn, bun, node, corepack, python, python3, pip, pip3, uv, poetry, uvicorn or gunicorn; commands run in the app's
folder.
Use "{database_url}" for the local database's address, and "{run_dir}" (an empty folder of the run's own,
outside the app, made for you) for any folder the app needs outside its code: backups, uploads, data. Never
create folders with commands. The seed script runs with Node after the app starts,
with BASE_URL and EAOS_STORAGE_STATE in its environment; require('playwright') is available. It signs in the
way the app itself allows locally (a development sign-in the docs describe, or signing up through the page),
adds a little sample data if the app is empty, and saves the browser state with
context.storageState({ path: process.env.EAOS_STORAGE_STATE }). Its console output ends with one JSON line of
fixture values it created, for example {"E2E_PROFILEID": "..."}, when the checks need them."""

DOCS = ('README.md', 'README', 'CLAUDE.md', 'AGENTS.md', 'CONTRIBUTING.md', 'docs/DEVELOPMENT.md', 'docs/SETUP.md',
        'docs/development.md', 'docs/setup.md', 'docs/LOCAL.md')


def _excerpt(project, folder, limit=40000):
    parts, used = [], 0
    for base in dict.fromkeys((Path(project), Path(project) / folder)):
        for name in DOCS + ENV_EXAMPLES:
            path = base / name
            if path.is_file() and used < limit:
                text = path.read_text(encoding='utf-8', errors='replace')[:min(12000, limit - used)]
                parts.append(f'=== {path.relative_to(project)}\n{text}')
                used += len(text)
    return '\n\n'.join(parts)


BASELINE_NOTE = """This time the app runs as it does in production, for a load test: built (the "build" commands), then
started from the build ("start"), with NODE_ENV=production, on the port the profile names. The fields you return
(env, start, install, prepare, database, and also "build": [["argv"]]) apply to that production run only. The
load test opens the pages without signing in, so no seed script is needed. The database, when the app needs one
in production, is EAOS's local PostgreSQL; its user is the superuser "postgres", and a prepare step may create the
roles the app requires with the app's own scripts."""


SOURCE_SUFFIXES = ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.json', '.vue', '.svelte', '.py')


def relevant_source(project, folder, failure, limit=3, context=60):
    """The code that raised the failure: each distinctive phrase of the error, looked up in the project's own
    source (never its build output or libraries), with the lines around it. The assistant fixes what it can see."""
    root = Path(project) / folder
    # Error lines, and the page's own words ("Where are you working?"): both are written somewhere in the code.
    phrases = sorted({p.strip(' .:-') for p in re.split(r'[\n|]| - |: |\s{2,}', failure or '') if len(p.strip()) >= 16},
                     key=len, reverse=True)[:16]                    # the most distinctive first
    found, seen = [], set()
    files = [f for f in root.rglob('*') if f.suffix in SOURCE_SUFFIXES and f.is_file()
             and not any(part in ('node_modules', 'dist', 'dist-server', 'build', '.next', 'coverage', '.venv', '__pycache__') for part in f.parts)][:6000]
    for phrase in phrases:
        needle = phrase[:60]
        for path in files:
            text = path.read_text(encoding='utf-8', errors='replace')
            at = text.find(needle)
            if at < 0 or path in seen: continue
            seen.add(path)
            lines = text.splitlines()
            line = text.count('\n', 0, at)
            start, end = max(0, line - context), min(len(lines), line + context)
            found.append(f'=== {path.relative_to(Path(project))} (lines {start + 1}-{end})\n' + '\n'.join(lines[start:end]))
            break
        if len(found) >= limit: break
    return '\n\n'.join(found)


def assist_messages(project, runtime, detected, failure, needs, mode='lock'):
    folder = detected['profile']['app']
    package = read_json(Path(project) / folder / 'package.json')
    profile = json.loads((Path(runtime) / 'run.json').read_text(encoding='utf-8'))
    if mode == 'baseline': profile = {**{k: v for k, v in profile.items() if k != 'baseline'}, **(profile.get('baseline') or {})}
    brief = {'what_failed': failure, 'current_profile': profile,
             'detected': detected['facts'], 'scripts': package.get('scripts'), 'fixtures_the_checks_need': needs}
    return [{'role': 'system', 'content': ASSIST_SYSTEM + ('\n\n' + BASELINE_NOTE if mode == 'baseline' else '')},
            {'role': 'user', 'content': 'The situation:\n' + json.dumps(brief, ensure_ascii=False, indent=1)
             + '\n\nThe project documentation:\n' + _excerpt(project, folder)
             + ('\n\nThe code that raised the failure:\n' + source if (source := relevant_source(project, folder, failure)) else '')}]

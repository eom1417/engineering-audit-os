"""The readiness kit: a Goss file for what a running release must show, and a checklist where every item is a command.

  handover/readiness/goss.yaml       the port the application listens on, its health route answering 200,
                                     its process, and the files a start needs. Judged by `goss render`.
  handover/readiness/checklist.json  the items of eaos/rules/readiness-checklist.json that apply to this project,
                                     each with the command NS16 runs in the sandbox. An item without a command
                                     is refused here, not skipped later. Its shape is checked by eaos.emit.shape.
"""
import json
import re
import sys
from pathlib import Path

from .base import Emitted
from .project import profile
from .yamltext import dump

RULES = Path(__file__).resolve().parent.parent / 'rules/readiness-checklist.json'
# The port a start command listens on when the project does not say otherwise (each tool's documented default).
PORTS = (('vite preview', 4173), ('vite dev', 5173), ('vite', 5173), ('next start', 3000), ('next dev', 3000),
         ('streamlit', 8501), ('uvicorn', 8000), ('fastapi', 8000), ('django', 8000), ('flask', 5000))


def start(p):
    """(start command, the text that says which server runs, process name)."""
    scripts = p['scripts']
    if p['js']:
        script = next((name for name in ('preview', 'start', 'dev') if name in scripts), None)
        runner = 'bun run' if p['package_manager'] == 'bun' else f"{p['package_manager']} run"
        return (f'{runner} {script}' if script else None), scripts.get(script, ''), 'bun' if p['package_manager'] == 'bun' else 'node'
    if p['python'] and p['root']:
        text = ' '.join((p['root'] / name).read_text(encoding='utf-8', errors='ignore')
                        for name in ('pyproject.toml', 'requirements.txt') if (p['root'] / name).is_file()).lower()
        entry = next((name for name in ('run_app.py', 'app.py', 'main.py', 'manage.py') if name in p['files']), None)
        return (f'python {entry}' if entry else None), text, 'python'
    return None, '', None


def port_of(server_text):
    lowered = server_text.lower()
    return next((port for word, port in PORTS if word in lowered), None)


def health_route(p):
    routes = [s for f in p['features'] for s in f.get('surfaces') or [] if isinstance(s, str) and s.startswith('/')]
    return next((r for r in routes if 'health' in r.lower() and '$' not in r and ':' not in r), '/')


def goss(p):
    command, server, process = start(p)
    port = port_of(server)
    spec = {}
    if port:
        spec['port'] = {f'tcp:{port}': {'listening': True}}
        spec['http'] = {f'http://localhost:{port}{health_route(p)}': {'status': 200, 'timeout': 5000}}
    if process: spec['process'] = {process: {'running': True}}
    needed = ['package.json'] if p['js'] else [name for name in ('pyproject.toml', 'requirements.txt') if name in p['files']]
    if p['js'] and 'build' in p['scripts']: needed.append('dist/index.html')
    if needed: spec['file'] = {name: {'exists': True} for name in needed}
    note = (f'Start the application first ({command}), then: goss -g readiness/goss.yaml validate\n'
            f'Port {port} is the default of the start command; change it here if the project sets another.' if port else
            'The start command does not name a known server: add its port and health route here.')
    return dump(spec, 'What a running release must show, written by EAOS for Goss.\n' + note)


def commands(p):
    lock_js = 'npx playwright test --config behavior-lock/playwright.config.ts'
    lock_py = 'python -m pytest behavior-lock/approvals'
    runner = 'bun run' if p['package_manager'] == 'bun' else f"{p['package_manager']} run"
    build = (f'{runner} build' if p['js'] and 'build' in p['scripts'] else
             'pip install -e .' if p['pyproject'] else 'pip install -r requirements.txt' if p['requirements'] else None)
    return {'build': build, 'safety_net': lock_js if p['js'] else lock_py if p['python'] else None}


def applies(rule, p, report):
    """Whether a checklist item concerns this project, from the facts: its data clients and its own files."""
    if rule == 'all': return True
    if rule == 'postgres':
        from .nfr import _facts
        clients = {(fact.get('value') or {}).get('client') for fact in _facts(report, 'data_access')}
        return 'supabase' in clients or any(f.startswith('supabase/') for f in p['files'])
    if rule == 'sqlite':
        return p['python'] and any(re.search(r'^\s*(import|from)\s+sqlite3\b', (p['root'] / f).read_text(encoding='utf-8', errors='ignore'), re.M)
                                   for f in p['files'] if f.endswith('.py'))
    if rule == 'docker': return any(f.endswith('Dockerfile') or f.startswith('docker-compose') for f in p['files'])
    return False


def checklist(p, report):
    values = commands(p)
    items = []
    for item in json.loads(RULES.read_text(encoding='utf-8'))['items']:
        if not applies(item['applies'], p, report): continue
        needed = set(re.findall(r'\{(\w+)\}', item['command']))
        if any(values.get(name) is None for name in needed): continue
        command = item['command'].format(**values)
        if not command.strip(): raise ValueError(f"{item['id']}: a readiness item without a command is refused")
        items.append({'id': item['id'], 'title': item['title'], 'command': command, 'why': item['why'], 'status': 'not_run'})
    return {'schema_version': 1, 'project': p['name'], 'items': items}


def write(report):
    report = Path(report)
    p = profile(report)
    if p['root'] is None: return []
    folder = report / 'handover/readiness'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'goss.yaml').write_text(goss(p), encoding='utf-8')
    (folder / 'checklist.json').write_text(json.dumps(checklist(p, report), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return [Emitted('handover/readiness/goss.yaml', 'goss', ('goss', '-g', '{path}', 'render')),
            Emitted('handover/readiness/checklist.json', 'schema', (sys.executable, '-m', 'eaos.emit.shape', 'checklist', '{path}'))]

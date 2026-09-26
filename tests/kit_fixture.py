"""A small project and its report, enough for the handover emitters: a Vite SPA or a Python desktop app."""
import json
from pathlib import Path


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if isinstance(text, str) else json.dumps(text), encoding='utf-8')


def build(root, stack='js'):
    """(project, report) under root."""
    root = Path(root)
    project, report = root / 'project', root / 'report'
    if stack == 'js':
        write(project / 'package.json', {'name': 'demo', 'scripts': {'build': 'vite build', 'preview': 'vite preview', 'test': 'vitest run'}})
        write(project / 'bun.lock', '')
        write(project / 'tsconfig.json', '{}')
        write(project / 'src/pages/Home.tsx', "import { get } from '../lib/Api';\nexport const Home = () => get('/x');\n")
        write(project / 'src/lib/Api.ts', 'export const get = (u: string) => fetch(u);\n')
        write(project / 'src/lib/format.ts', "import { get } from './Api';\nexport const f = get;\n")
        reference = 'react-vite-spa-rest'
        write(report / 'facts/data.json', {'facts': [{'kind': 'data_access', 'value': {'client': 'supabase'}, 'location': {'path': 'src/lib/Api.ts'}}]})
    else:
        write(project / 'pyproject.toml', '[project]\nname = "demo"\ndependencies = ["streamlit"]\n')
        write(project / 'run_app.py', 'import views.main\n')
        write(project / 'views/main.py', 'from core.database import connect\n')
        write(project / 'core/database.py', 'import sqlite3\ndef connect():\n    return sqlite3.connect("x.db")\n')
        write(project / 'core/models.py', 'from services.prices import price\n')
        write(project / 'services/prices.py', 'def price():\n    return 1\n')
        write(project / 'tests/test_x.py', 'def test_x():\n    assert True\n')
        reference = 'python-desktop'
    write(report / 'dossier.json', {'provenance': {'target': str(project), 'tool_version': '3.0.0', 'generated_at': 'now'}, 'claims': []})
    write(report / 'target-architecture.json', {'reference': reference, 'target_components': [
        {'name': 'pages', 'layer': 'pages', 'files': 1, 'responsibility': 'screens'},
        {'name': 'api-client', 'layer': 'api-client', 'files': 1, 'responsibility': 'the only code that knows endpoints'}]})
    write(report / 'intake.json', {'run_command': 'bun run preview' if stack == 'js' else None, 'questions': [
        {'id': 'hosting', 'answer': 'Vercel'}], 'scenarios': [
        {'id': 'QS-001', 'kind': 'load', 'stimulus': '100 users', 'response': 'answered in time', 'source': 'default',
         'measure': {'metric': 'p95_ms', 'threshold': 800, 'unit': 'ms'}},
        {'id': 'QS-002', 'kind': 'latency', 'stimulus': '100 users', 'response': 'few errors', 'source': 'default',
         'measure': {'metric': 'error_rate', 'threshold': 0.01, 'unit': 'ratio'}},
        {'id': 'QS-003', 'kind': 'availability', 'stimulus': 'a month', 'response': 'up', 'source': 'answer',
         'measure': {'metric': 'availability', 'threshold': 99.5, 'unit': 'percent'}}]})
    write(report / 'features.json', {'features': [
        {'name': 'home', 'critical': True, 'surfaces': ['/', '/health']},
        {'name': 'admin', 'critical': False, 'surfaces': ['/admin']}]})
    for name in ('CURRENT-STATE.md', 'TARGET-STATE.md', 'GAP-AND-STRATEGY.md', 'EXECUTION-PLAN.md'):
        write(report / name, f'# {name[:-3]}\n\nSee [the roadmap](ROADMAP.md), [the first decision](adr/ADR-001.md) '
                             f'and [the guide](EXECUTION-GUIDE.md).\n')
    write(report / 'ROADMAP.md', '# Roadmap\n\nBack to [the plan](EXECUTION-PLAN.md).\n')
    write(report / 'adr/ADR-001.md', '# ADR-001: One API client\n\nSee [ADR-002](ADR-002.md).\n')
    write(report / 'adr/ADR-002.md', '# ADR-002: Layers\n\nText.\n')
    return project, report

"""The system map (pages, APIs, server handlers, parts, data), the work log, the version stamp and the error banner."""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos import c4, human_report, system_map
from eaos.human_report import readability_problems
from test_human_report import report, section
from test_report_maps import CHIEF, facts as map_facts, ledger


def fact(kind, path, value, symbol=None):
    return {'kind': kind, 'location': {'path': path, 'symbol': symbol}, 'value': value}


def system(out):
    """Two pages; /users calls its own APIs and, with /settings, the shared web/shared/api.ts; one API has no handler.
    GET and POST /api/users are file-routed (server/routes/users.ts exports GET and POST); GET /api/me is a declared
    route; both reach server/data/users-db.ts (tables users, sessions), which imports pg. A test file's call is left out."""
    out = Path(out)
    (out / 'facts').mkdir(exist_ok=True)
    rows = {
        'entrypoints': [fact('entry_point', 'web/App.tsx', {'surface': 'page', 'route': '/users', 'handler': 'UsersPage'}),
                        fact('entry_point', 'web/App.tsx', {'surface': 'page', 'route': '/settings', 'handler': 'Settings'}),
                        fact('entry_point', 'server/routes/me.ts', {'surface': 'http', 'route': '/api/me', 'http_method': 'GET', 'handler': 'getMe'}),
                        fact('data_access', 'web/pages/UsersPage.tsx', {'client': 'http', 'target': '/api/users', 'operation': 'get', 'category': 'source'}),
                        fact('data_access', 'web/pages/UsersPage.tsx', {'client': 'http', 'target': '/api/users?page=${n}', 'operation': 'post', 'category': 'source'}),
                        fact('data_access', 'web/shared/api.ts', {'client': 'http', 'target': '/api/me', 'operation': 'get', 'category': 'source'}),
                        fact('data_access', 'web/pages/Settings.tsx', {'client': 'http', 'target': '/api/nowhere', 'operation': 'get', 'category': 'source'}),
                        fact('data_access', 'tests/users.test.ts', {'client': 'http', 'target': '/api/users', 'operation': 'delete', 'category': 'test'})],
        'syntax': [fact('symbol', 'web/pages/UsersPage.tsx', {'name': 'UsersPage', 'exported': True, 'kind': 'function'}),
                   fact('symbol', 'web/pages/Settings.tsx', {'name': 'Settings', 'exported': True, 'kind': 'function'}),
                   fact('symbol', 'server/routes/users.ts', {'name': 'GET', 'exported': True, 'kind': 'function'}),
                   fact('symbol', 'server/routes/users.ts', {'name': 'POST', 'exported': True, 'kind': 'function'}),
                   fact('import_edge', 'server/db.ts', {'module': 'pg', 'style': 'absolute'})],
        'graph': [fact('graph_node', p, {'depends_on': d}) for p, d in (
            ('web/App.tsx', ['web/pages/UsersPage.tsx', 'web/pages/Settings.tsx']), ('web/pages/UsersPage.tsx', ['web/shared/api.ts']),
            ('web/pages/Settings.tsx', ['web/shared/api.ts']), ('web/shared/api.ts', []),
            ('server/routes/users.ts', ['server/data/users-db.ts']), ('server/routes/me.ts', ['server/data/users-db.ts']),
            ('server/data/users-db.ts', ['server/db.ts']), ('server/db.ts', []))],
        'domain': [fact('data_table', 'server/data/users-db.ts', {'name': n}) for n in ('users', 'sessions', 'IF')],
    }
    for name, records in rows.items():
        (out / 'facts' / f'{name}.json').write_text(json.dumps({'facts': records}), encoding='utf-8')
    (out / 'features.json').write_text(json.dumps({'features': [
        {'name': 'users', 'surfaces': ['/users'], 'endpoints': ['GET /api/users', 'POST /api/users', 'GET /api/me'], 'files': []},
        {'name': 'settings', 'surfaces': ['/settings'], 'endpoints': ['GET /api/me'], 'files': []}]}), encoding='utf-8')
    target = json.loads((out / 'target-architecture.json').read_text(encoding='utf-8'))
    target['current_components'] += [
        {'id': 'T-web', 'name': 'web', 'relation': 'modify', 'files': 4, 'paths': ['web/App.tsx', 'web/pages/UsersPage.tsx', 'web/pages/Settings.tsx', 'web/shared/api.ts']},
        {'id': 'T-routes', 'name': 'server/routes', 'relation': 'retain', 'files': 2, 'paths': ['server/routes/users.ts', 'server/routes/me.ts']},
        {'id': 'T-data', 'name': 'server/data', 'relation': 'retain', 'files': 2, 'paths': ['server/data/users-db.ts', 'server/db.ts']}]
    (out / 'target-architecture.json').write_text(json.dumps(target), encoding='utf-8')
    return out


HANDOVER = {'branch': 'main', 'last_assistant': 'Codex', 'last_activity': '2026-09-29T14:02:11+00:00', 'running_job': None,
            'open_work': {'kind': 'fix batch', 'number': 3, 'kept': ['TASK-1'], 'not_kept': {'TASK-4': 'the tests failed'}, 'left': ['TASK-6'],
                          'resume': 'batch 3 is open'},
            'waiting_for_the_person': None, 'progress': {'total': 7, 'closed': 2}, 'person_already_answered': [],
            'last_steps': [{'at': '2026-09-29T13:40:00+00:00', 'by': 'Claude Code', 'tool': 'audit', 'outcome': 'done'},
                           {'at': '2026-09-29T14:02:11+00:00', 'by': 'Codex', 'tool': 'fix_edit', 'card': 'TASK-4', 'outcome': 'not kept: the tests failed'}],
            'notes': [{'at': '2026-09-29T14:02:30+00:00', 'by': 'Codex', 'card': 'TASK-4', 'note': 'The export test needs fixture data.'}],
            'in_progress': {'card': 'TASK-6', 'since': '2026-09-29T14:03:00+00:00', 'by': 'Codex', 'files_read': ['src/api/users.ts'], 'last_try': 'the check failed: 1 test'},
            'how_to_continue': 'Continue exactly where this stopped.'}
EAOS = {'version': '0.0.1', 'commit': 'c992b28abcdef99', 'digest': 'sha256-9f8e7d6c5b4a', 'built': '2026-09-29T14:05:00+00:00'}


class SystemMapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = system(report(self.tmp.name))
        self.sm = system_map.build(self.out)

    def test_a_project_with_no_page_and_no_api_says_so_instead_of_leaving_a_gap(self):
        """EAOS's own audit (a command-line tool): no page, no API. The section says what the project is and where its
        links are drawn; it is not missing and it is not 'not available'."""
        (Path(self.tmp.name) / 'library').mkdir()
        bare = report(Path(self.tmp.name) / 'library')
        for name in ('features.json', 'facts/entrypoints.json', 'facts/flows.json'):
            (bare / name).unlink(missing_ok=True)
        page = human_report.write(bare, 'ar', 'library').read_text(encoding='utf-8')
        self.assertIn('data-part="system-map"', page)
        self.assertIn('لم نجد في هذا المشروع صفحات ويب ولا نقاط API', page)
        self.assertEqual(readability_problems(page), [])

    def test_each_api_is_mapped_to_the_server_code_that_answers_it(self):
        apis = {a['key']: a for a in self.sm['apis']}
        self.assertEqual(set(apis), {'GET /api/users', 'POST /api/users', 'GET /api/me', 'GET /api/nowhere'})
        self.assertEqual(apis['GET /api/users']['handlers'], [{'path': 'server/routes/users.ts', 'function': 'GET', 'how': 'file routing'}])
        self.assertEqual(apis['POST /api/users']['handlers'][0]['function'], 'POST', 'the query and template are cut off the call')
        self.assertEqual(apis['GET /api/me']['handlers'], [{'path': 'server/routes/me.ts', 'function': 'getMe', 'how': 'entry point'}])
        self.assertEqual((apis['GET /api/nowhere']['handlers'], self.sm['unknown']), ([], 1))
        self.assertEqual(apis['GET /api/users']['callers'], ['web/pages/UsersPage.tsx'], 'a test file is not a caller')
        self.assertEqual(apis['GET /api/users']['tables'], ['sessions', 'users'], 'IF is a word of SQL, not a table')
        self.assertEqual(system_map.route_of_file('app/server/routes/auth/google-start.ts'), 'auth/google-start')
        self.assertTrue(system_map.same_route('/api/users/:id', '/api/users/[id]'))

    def test_a_page_lights_every_api_handler_and_table_it_reaches(self):
        users = set(self.sm['related']['P:/users UsersPage'])
        self.assertLessEqual({'A:GET /api/users', 'A:POST /api/users', 'C:web/shared/api.ts', 'A:GET /api/me', 'H:server/routes/users.ts',
                              'H:server/routes/me.ts', 'M:T-data', 'T:users', 'T:sessions', 'S:PostgreSQL database'}, users)
        settings = set(self.sm['related']['P:/settings Settings'])
        self.assertIn('T:users', settings, 'through the shared file and GET /api/me')
        self.assertNotIn('A:GET /api/users', settings)
        self.assertLessEqual({'P:/users UsersPage', 'P:/settings Settings', 'A:GET /api/me'}, set(self.sm['related']['T:users']))
        kinds = {(e['from'], e['to']): e['kind'] for e in self.sm['edges']}
        self.assertEqual(kinds[('P:/users UsersPage', 'A:GET /api/users')], 'call')
        self.assertEqual(kinds[('P:/users UsersPage', 'C:web/shared/api.ts')], 'uses')
        self.assertEqual(kinds[('C:web/shared/api.ts', 'A:GET /api/me')], 'call')
        self.assertEqual(kinds[('M:T-data', 'T:users')], 'data')

    def test_the_layout_keeps_every_column_apart(self):
        lay = system_map.layout(self.sm)
        by_column = {}
        for column, y in lay['place'].values(): by_column.setdefault(column, []).append(y)
        for ys in by_column.values():
            ys.sort()
            self.assertTrue(all(b - a >= system_map.BOX_H for a, b in zip(ys, ys[1:])), ys)
            self.assertLessEqual(ys[-1] + system_map.BOX_H, lay['height'])

    def test_the_page_draws_the_system_map_and_reads_well(self):
        page = human_report.write(self.out, 'ar').read_text(encoding='utf-8')
        self.assertEqual(readability_problems(page), [])
        part = section(page, 'system')
        self.assertIn('data-part="system-map"', part)
        self.assertEqual(part.count('class="chart smap'), 2, 'one drawing per reading direction')
        self.assertIn('data-node="A:GET /api/nowhere"', part)
        data = json.loads(re.search(r'<script type="application/json" id="eaos-system">(.*?)</script>', page, re.S).group(1))
        self.assertIn('T:users', data['rel']['P:/users UsersPage'])
        self.assertIn('unknown: no server route or file matches it', part)
        self.assertEqual(json.loads((self.out / 'human' / 'errors.json').read_text(encoding='utf-8')), [])

    def test_missing_or_broken_records_leave_the_map_out_not_the_page(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assertIsNone(system_map.build(empty))
        (self.out / 'facts' / 'entrypoints.json').write_text('{"facts": [7, {"kind": "data_access"}]', encoding='utf-8')
        sm = system_map.build(self.out)
        self.assertEqual({a['key'] for a in sm['apis']}, {'GET /api/users', 'POST /api/users', 'GET /api/me'}, 'the features still name them')
        page = human_report.write(self.out, 'en').read_text(encoding='utf-8')
        self.assertEqual(readability_problems(page), [])


class WorkLogStampErrorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = report(self.tmp.name)

    def test_the_work_log_says_where_the_work_stopped_and_who_did_what(self):
        page = human_report.write(self.out, 'en', progress={'handover': HANDOVER, 'ledger': ledger()}).read_text(encoding='utf-8')
        self.assertEqual(readability_problems(page), [])
        log = re.search(r'data-part="work-log".*?</section>', section(page, 'plan'), re.S).group(0)
        for words in ('Codex', 'Claude Code', 'fixed a card and checked it', 'checked the whole project', 'TASK-6', 'the tests failed',
                      'The export test needs fixture data.', 'Was working on card', 'src/api/users.ts', 'the check failed: 1 test', 'Finish card', '2026-09-29 14:02'):
            self.assertIn(words, log)
        self.assertLess(log.index('fixed a card and checked it'), log.index('checked the whole project'), 'newest first')

    def test_with_no_handover_the_work_log_says_nothing_has_started(self):
        page = human_report.write(self.out, 'ar').read_text(encoding='utf-8')
        self.assertIn('data-part="work-log"', page)
        self.assertIn('لم يبدأ أي عمل بعد', page)
        self.assertEqual(readability_problems(page), [])

    def test_the_stamp_and_the_errors_the_caller_names_are_shown(self):
        page = human_report.write(self.out, 'ar', progress={'eaos': EAOS, 'report_errors': ['the ledger could not be read: 3 lines broken']}).read_text(encoding='utf-8')
        self.assertEqual(readability_problems(page), [])
        stamp = re.search(r'<div class="stamp[^"]*" data-part="stamp">.*?</div>', page).group(0)
        for words in ('بنته نسخة EAOS', '0.0.1', 'c992b28abcde', 'sha256-9f8e7', '2026-09-29 14:05'):
            self.assertIn(words, stamp)
        self.assertIn('class="stamp-foot', page)
        self.assertIn('data-part="report-errors"', page)
        self.assertIn('the ledger could not be read: 3 lines broken', page)
        clean = human_report.write(self.out, 'ar').read_text(encoding='utf-8')
        self.assertNotIn('data-part="report-errors"', clean)
        self.assertNotIn('data-part="stamp"', clean)

    def test_a_section_that_fails_is_named_on_the_page_and_in_errors_json(self):
        with mock.patch('eaos.human_report.section_target', side_effect=RuntimeError('a broken record')):
            page = human_report.write(self.out, 'en').read_text(encoding='utf-8')
        self.assertEqual(json.loads((self.out / 'human' / 'errors.json').read_text(encoding='utf-8')),
                         [{'section': 'target', 'error': 'RuntimeError: a broken record'}])
        self.assertIn('data-part="report-errors"', page)
        self.assertIn('Not available in this report.', section(page, 'target'))
        self.assertIn('data-report="plan"', page, 'the rest of the page is built')
        self.assertEqual(readability_problems(page), [])
        with mock.patch('eaos.system_map.build', side_effect=ValueError('bad facts')):
            human_report.write(self.out, 'en')
        self.assertEqual(json.loads((self.out / 'human' / 'errors.json').read_text(encoding='utf-8')),
                         [{'section': 'system map', 'error': 'ValueError: bad facts'}])


class MermaidTests(unittest.TestCase):
    def test_the_diagrams_group_parts_label_links_and_draw_loops_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = system(report(tmp))
            map_facts(out)
            graph = json.loads((out / 'facts' / 'graph.json').read_text(encoding='utf-8'))
            c4.write(out)
            current = (out / 'architecture/current/diagram.mmd').read_text(encoding='utf-8')
            target = (out / 'architecture/target/diagram.mmd').read_text(encoding='utf-8')
            text = (out / 'architecture/system.mmd').read_text(encoding='utf-8')
        self.assertTrue(graph['facts'])
        self.assertTrue(current.startswith('flowchart LR'))
        self.assertRegex(current, r'subgraph g\d+\["lib"\]')
        self.assertRegex(current, r'c\d+ -->\|1 imports\| c\d+')
        self.assertRegex(current, r'linkStyle [\d,]+ stroke:#d03b3b', 'the loop between src and src/api is red')
        self.assertIn('subgraph', target)
        self.assertIn('subgraph apis["APIs"]', text)
        self.assertRegex(text, r'-->\|answers\|')

    def test_a_crowded_diagram_keeps_the_strongest_links_and_says_so(self):
        names = [f'p{i}' for i in range(30)]
        edges = [(a, b, i * 30 + j) for i, a in enumerate(names) for j, b in enumerate(names) if a != b]
        text = c4.readable(names, edges, {}, limit=150)
        self.assertEqual(text.count('-->'), 150)
        self.assertIn('%% 720 of the 870 links are left out', text)
        first = next(line for line in text.splitlines() if '-->' in line)
        self.assertIn(f'|{max(n for _, _, n in edges)} imports|', first, 'the strongest link comes first')


@unittest.skipUnless((CHIEF / 'facts' / 'entrypoints.json').is_file(), 'the chief-ops report is not on this machine')
class ChiefOpsSystemTests(unittest.TestCase):
    def test_the_real_report_maps_its_apis_to_its_route_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / 'facts').mkdir()
            for name in ('plan.json', 'dossier.json', 'debt-register.json', 'run-manifest.json', 'target-architecture.json', 'gap-matrix.json', 'features.json'):
                shutil.copy(CHIEF / name, out / name)
            for name in ('graph', 'flows', 'structure', 'entrypoints', 'domain', 'syntax'):
                shutil.copy(CHIEF / 'facts' / f'{name}.json', out / 'facts' / f'{name}.json')
            sm = system_map.build(out)
            page = human_report.write(out, 'ar', progress={'ledger': ledger(), 'handover': HANDOVER, 'eaos': EAOS}).read_text(encoding='utf-8')
        apis = {a['key']: a for a in sm['apis']}
        handler = lambda key: [(h['path'], h['function']) for h in apis[key]['handlers']]
        self.assertEqual(handler('GET /api/users'), [('app/server/routes/users.ts', 'GET')])
        self.assertEqual(handler('POST /api/workspace-restore/commit'), [('app/server/routes/workspace-restore-commit.ts', 'POST')])
        self.assertEqual(handler('GET /api/support-access'), [('app/server/routes/support-access.ts', 'GET')], 'not support/access.ts')
        self.assertEqual(handler('GET /api/audit'), [('app/server/routes/audit.ts', 'GET')], 'the template in the URL is cut off')
        self.assertLessEqual(sm['unknown'], 3)
        self.assertIn('T:roles', sm['related']['A:POST /api/roles'])
        self.assertEqual(readability_problems(page), [])
        self.assertNotRegex(page, r'<!-- \w+ -->', 'no section fell back to "not available"')
        self.assertNotIn('data-part="report-errors"', page)


if __name__ == '__main__':
    unittest.main()

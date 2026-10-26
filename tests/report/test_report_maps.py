"""The report's maps: today's parts and their imports, files, functions and pages; the target; the gap closed; every card;
the system map (pages, APIs, server handlers, parts, data), the work log, the version stamp and the error banner."""
import json
import re
import shutil
from unittest import mock
import tempfile
import unittest
from pathlib import Path

from eaos.analysis.maps import architecture as arch_map, c4, system_drawing, system as system_map
from eaos.report.blueprint import design as blueprint, view as blueprint_view
from eaos.report import human_report
from report.test_human_report import report, section

def node(path, depends, group=None):
    return {'kind': 'graph_node', 'location': {'path': path},
            'value': {'depends_on': depends, 'fan_in': 0, 'fan_out': len(depends), 'cycle_group': group}}


def facts(out):
    """Imports: src/a <-> src/api/users (a loop across two parts), src/b -> src/a; functions and calls; one page."""
    (out / 'facts').mkdir(exist_ok=True)
    graph = [node('src/a.ts', ['src/api/users.ts'], 0), node('src/api/users.ts', ['src/a.ts'], 0),
             node('src/b.ts', ['src/a.ts']), node('src/old.ts', []),
             {'kind': 'graph_cycle', 'location': {'path': 'src/a.ts'}, 'value': {'members': ['src/a.ts', 'src/api/users.ts']}}]
    scopes = [('src/a.ts', 'helper'), ('src/a.ts', 'save'), ('src/api/users.ts', 'listUsers'), ('src/b.ts', 'main')]
    structure = [{'kind': 'scope', 'location': {'path': p, 'symbol': f'<module>.{n}'}, 'value': {'name': n, 'kind': 'function'}} for p, n in scopes]
    structure += [{'kind': 'call_site', 'location': {'path': p, 'symbol': s}, 'value': {'callee': c, 'attribute': False}}
                  for p, s, c in (('src/b.ts', '<module>.main', 'save'), ('src/a.ts', '<module>.<module>.save.<anon>', 'helper'),
                                  ('src/a.ts', '<module>.save', 'listUsers'), ('src/b.ts', '<module>.main', 'nowhere'))]
    flow = {'kind': 'flow', 'location': {'path': 'src/api/users.ts', 'symbol': 'listUsers'},
            'value': {'flow_id': 'FLOW-001', 'entry': {'surface': 'endpoint', 'route': '/users', 'http_method': 'GET',
                                                       'path': 'src/api/users.ts', 'handler': 'listUsers'},
                      'steps': [{'from': 'listUsers', 'from_path': 'src/api/users.ts', 'callee': 'save', 'resolution': 'imported',
                                 'to_path': 'src/a.ts', 'to_symbol': 'save', 'depth': 0},
                                {'from': 'save', 'from_path': 'src/a.ts', 'callee': 'mystery', 'resolution': 'unresolved',
                                 'to_path': None, 'to_symbol': None, 'depth': 1}]}}
    for name, rows in (('graph', graph), ('structure', structure), ('flows', [flow])):
        (out / 'facts' / f'{name}.json').write_text(json.dumps({'facts': rows}), encoding='utf-8')


def ledger():
    cards = [{'key': 'k1', 'id': 'TASK-1', 'title': 't1', 'pattern': 'upgrade_dependency', 'milestone': 'M01', 'paths': ['package-lock.json'],
              'state': 'done', 'new': False, 'batch': 1, 'at': '2026-09-28T10:00:00+00:00', 'why': '', 'commit': 'abc1234'},
             {'key': 'k3', 'id': 'TASK-3', 'title': 't3', 'pattern': 'remove_dead', 'milestone': 'M01', 'paths': ['src/old.ts'],
              'state': 'on_branch', 'new': False, 'batch': 2, 'at': None, 'why': '', 'commit': None},
             {'key': 'k6', 'id': 'TASK-6', 'title': 't6', 'pattern': 'hotspot', 'milestone': 'M02', 'paths': ['src/api/users.ts'],
              'state': 'skipped', 'new': False, 'batch': None, 'at': None, 'why': 'a public name changes', 'commit': None},
             {'key': 'gone0001', 'id': None, 'title': 'Unused helper removed from src/gone.ts', 'pattern': 'remove_dead', 'milestone': 'M01',
              'paths': ['src/gone.ts'], 'state': 'resolved', 'new': False, 'batch': None, 'at': '2026-09-27T09:00:00+00:00', 'why': '', 'commit': None}]
    return {'schema_version': 1, 'updated': '2026-09-29T10:00:00+00:00', 'commit': 'abc',
            'totals': {'total': 7, 'closed': 2, 'done': 1, 'resolved': 1, 'on_branch': 1, 'in_batch': 0, 'open': 4, 'skipped': 1, 'new': 0, 'percent': 28.6},
            'cards': cards, 'history': [{'at': '2026-09-20T10:00:00+00:00', 'event': 'baseline', 'closed': 0, 'total': 6, 'percent': 0.0, 'batch': None},
                                        {'at': '2026-09-29T10:00:00+00:00', 'event': 'merged', 'closed': 2, 'total': 7, 'percent': 28.6, 'batch': 1}]}


def overlaps(nodes, width, height):
    return [(a['id'], b['id']) for i, a in enumerate(nodes) for b in nodes[i + 1:]
            if a['x'] < b['x'] + width and b['x'] < a['x'] + width and a['y'] < b['y'] + height and b['y'] < a['y'] + height]


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


class MapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = report(self.tmp.name)
        facts(self.out)

    def test_parts_files_and_flows_are_drawn_from_the_facts(self):
        cmap = arch_map.component_map(self.out)
        self.assertEqual(overlaps(cmap['nodes'], arch_map.NODE_W, arch_map.NODE_H), [])
        edges = {(e['from'], e['to']): e for e in cmap['edges']}
        self.assertTrue(edges[('T-src', 'T-api')]['cycle'] and edges[('T-api', 'T-src')]['cycle'])
        self.assertEqual(sum(e['back'] for e in cmap['edges']), 1, 'one edge of the loop is set aside to layer the rest')
        src = next(n for n in cmap['nodes'] if n['id'] == 'T-src')
        self.assertEqual((src['inside'], src['ce'], src['cohesion']), (1, 1, 50))
        # The drill-down resolves calls by name and skips what it cannot; a flow is drawn to where the trace stops.
        drill = arch_map.drill_data(self.out, arch_map.component_map(self.out))
        files = drill['files']
        calls = {(files[a], f, files[b], g) for a, f, b, g, _ in drill['calls']}
        self.assertEqual(calls, {('src/b.ts', 'main', 'src/a.ts', 'save'), ('src/a.ts', 'save', 'src/a.ts', 'helper'),
                                 ('src/a.ts', 'save', 'src/api/users.ts', 'listUsers')})
        flow = arch_map.flow_charts(self.out)[0]
        kinds = [n['kind'] for n in flow['nodes']]
        self.assertEqual(kinds, ['entry', 'handler', 'fn', 'stop'])
        self.assertEqual(len({(n['x'], n['y']) for n in flow['nodes']}), 4)

    def test_the_page_embeds_the_maps_and_every_card_and_only_closed_cards_close_a_milestone(self):
        page = human_report.write(self.out, 'ar', progress={'waves': [], 'ledger': ledger()}).read_text(encoding='utf-8')
        for part in ('cards', 'arch-map', 'arch-drill', 'flows', 'target-map', 'target-mapping', 'progress-history'):
            self.assertIn(f'data-part="{part}"', page)
        drill = json.loads(re.search(r'<script type="application/json" id="eaos-drill">(.*?)</script>', page, re.S).group(1))
        self.assertEqual(len(drill['comps']), 2)
        json.loads(re.search(r'<script type="application/json" id="eaos-flows">(.*?)</script>', page, re.S).group(1))
        self.assertRegex(page, r'<details class="card allcards" id="allcards" data-part="cards">')
        cards = section(page, 'plan')
        self.assertNotIn('Unused helper removed from src/gone.ts', cards, 'a ledger row without a plan card is not a card')
        self.assertIn('a public name changes', cards)
        self.assertIn('>29%<', section(page, 'summary'), 'the ledger percent, in whole percents above ten')
        self.assertIn('class="edge cyc', section(page, 'structure'))
        page = human_report.write(self.out, 'en', progress={'waves': [], 'ledger': ledger()}).read_text(encoding='utf-8')
        plan = section(page, 'plan')
        # M01: TASK-1 done of three cards; TASK-3 is only on a branch; a ledger-only row is no card
        self.assertIn('aria-valuenow="33"', plan)

    def test_the_page_works_without_a_ledger_and_with_nothing(self):
        page = human_report.write(self.out, 'en').read_text(encoding='utf-8')
        self.assertIn('data-part="cards"', page)
        text = human_report.render(human_report.empty(), 'shop', 'en')
        self.assertNotIn('<!-- ', text)
        shutil.rmtree(self.out / 'facts')
        page = human_report.write(self.out, 'en').read_text(encoding='utf-8')
        self.assertIn('Not available in this report.', section(page, 'structure'))


class BlueprintMapTests(unittest.TestCase):
    def test_the_blueprint_draws_its_layers_and_lists_every_card_with_its_state(self):
        from journeys.test_blueprint import spec
        stack = blueprint.choose_stack(spec())
        built = blueprint.design(spec(), stack)
        ids = [c['id'] for c in built['plan']['tasks']]
        text = blueprint_view.page(spec(), stack, built, [{'number': 1, 'milestone': 'M01', 'branch': 'eaos/build-1', 'kept': ids[:1], 'skipped': {ids[1]: 'refused'}}])
        self.assertIn('data-part="target-map"', text)
        self.assertEqual(text.count('class="tcard"'), len(ids))
        self.assertEqual(text.count('data-state="done"'), 2, 'the built card, and its chip')
        self.assertIn('refused', text)


class SystemMapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = system(report(self.tmp.name))
        self.sm = system_map.build(self.out)

    def test_each_api_is_mapped_to_its_server_code_and_a_page_lights_all_it_reaches(self):
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
        # The layout keeps every column apart.
        lay = system_drawing.layout(self.sm)
        by_column = {}
        for column, y in lay['place'].values(): by_column.setdefault(column, []).append(y)
        for ys in by_column.values():
            ys.sort()
            self.assertTrue(all(b - a >= system_drawing.BOX_H for a, b in zip(ys, ys[1:])), ys)
            self.assertLessEqual(ys[-1] + system_drawing.BOX_H, lay['height'])

    def test_the_page_draws_the_system_map_or_says_why_there_is_none(self):
        page = human_report.write(self.out, 'ar').read_text(encoding='utf-8')
        part = section(page, 'system')
        self.assertIn('data-part="system-map"', part)
        self.assertEqual(part.count('class="chart smap'), 2, 'one drawing per reading direction')
        self.assertIn('data-node="A:GET /api/nowhere"', part)
        data = json.loads(re.search(r'<script type="application/json" id="eaos-system">(.*?)</script>', page, re.S).group(1))
        self.assertIn('T:users', data['rel']['P:/users UsersPage'])
        self.assertIn('unknown: no server route or file matches it', part)
        self.assertEqual(json.loads((self.out / 'human' / 'errors.json').read_text(encoding='utf-8')), [])
        # Missing or broken records leave the map out, not the page.
        with tempfile.TemporaryDirectory() as empty:
            self.assertIsNone(system_map.build(empty))
        (self.out / 'facts' / 'entrypoints.json').write_text('{"facts": [7, {"kind": "data_access"}]', encoding='utf-8')
        sm = system_map.build(self.out)
        self.assertEqual({a['key'] for a in sm['apis']}, {'GET /api/users', 'POST /api/users', 'GET /api/me'}, 'the features still name them')
        page = human_report.write(self.out, 'en').read_text(encoding='utf-8')
        # A project with no page and no API (a command-line tool) says so instead of leaving a gap.
        (Path(self.tmp.name) / 'library').mkdir()
        bare = report(Path(self.tmp.name) / 'library')
        for name in ('features.json', 'facts/entrypoints.json', 'facts/flows.json'):
            (bare / name).unlink(missing_ok=True)
        page = human_report.write(bare, 'ar', 'library').read_text(encoding='utf-8')
        self.assertIn('data-part="system-map"', page)
        self.assertIn('لم نجد في هذا المشروع صفحات ويب ولا نقاط API', page)


class WorkLogStampErrorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = report(self.tmp.name)

    def test_the_work_log_stamp_and_errors_say_where_the_work_stopped_and_what_failed(self):
        page = human_report.write(self.out, 'en', progress={'handover': HANDOVER, 'ledger': ledger()}).read_text(encoding='utf-8')
        log = re.search(r'data-part="work-log".*?</section>', section(page, 'plan'), re.S).group(0)
        for words in ('Codex', 'Claude Code', 'fixed a card and checked it', 'checked the whole project', 'TASK-6', 'the tests failed',
                      'The export test needs fixture data.', 'Was working on card', 'src/api/users.ts', 'the check failed: 1 test', 'Finish card', '2026-09-29 14:02'):
            self.assertIn(words, log)
        self.assertLess(log.index('fixed a card and checked it'), log.index('checked the whole project'), 'newest first')
        page = human_report.write(self.out, 'ar').read_text(encoding='utf-8')
        self.assertIn('data-part="work-log"', page)
        self.assertIn('لم يبدأ أي عمل بعد', page)
        # The stamp and every error are shown, and a failing section costs only itself.
        page = human_report.write(self.out, 'ar', progress={'eaos': EAOS, 'report_errors': ['the ledger could not be read: 3 lines broken']}).read_text(encoding='utf-8')
        stamp = re.search(r'<div class="stamp[^"]*" data-part="stamp">.*?</div>', page).group(0)
        for words in ('بنته نسخة EAOS', '0.0.1', 'c992b28abcde', 'sha256-9f8e7', '2026-09-29 14:05'):
            self.assertIn(words, stamp)
        self.assertIn('class="stamp-foot', page)
        self.assertIn('data-part="report-errors"', page)
        self.assertIn('the ledger could not be read: 3 lines broken', page)
        clean = human_report.write(self.out, 'ar').read_text(encoding='utf-8')
        self.assertNotIn('data-part="report-errors"', clean)
        self.assertNotIn('data-part="stamp"', clean)
        with mock.patch('eaos.report.human_report.page.section_target', side_effect=RuntimeError('a broken record')):
            page = human_report.write(self.out, 'en').read_text(encoding='utf-8')
        self.assertEqual(json.loads((self.out / 'human' / 'errors.json').read_text(encoding='utf-8')),
                         [{'section': 'target', 'error': 'RuntimeError: a broken record'}])
        self.assertIn('data-part="report-errors"', page)
        self.assertIn('Not available in this report.', section(page, 'target'))
        self.assertIn('data-report="plan"', page, 'the rest of the page is built')
        with mock.patch('eaos.analysis.maps.system.build', side_effect=ValueError('bad facts')):
            human_report.write(self.out, 'en')
        self.assertEqual(json.loads((self.out / 'human' / 'errors.json').read_text(encoding='utf-8')),
                         [{'section': 'system map', 'error': 'ValueError: bad facts'}])


class MermaidTests(unittest.TestCase):
    def test_the_diagrams_group_parts_label_links_and_draw_loops_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = system(report(tmp))
            facts(out)
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


if __name__ == '__main__':
    unittest.main()

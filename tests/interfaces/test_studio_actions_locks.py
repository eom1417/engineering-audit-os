"""The run engine (eaos/features/studio/journey/runs): the locks, the selection of cards, and the handoff."""
import json
import os
import subprocess
import time
import unittest
from unittest import mock
from eaos.features.studio.journey.runs import handoff
from eaos.kernel.system import studio_access as security
from eaos.features.guided.journey import selection  # noqa: E402
from eaos.kernel.project import state as project_state
from tests.interfaces._studio_actions_fixture import Base, card


class Locks(Base):
    def test_every_request_needs_the_token_and_a_post_the_csrf_token_and_the_studio_origin_and_refusals_are_logged_without_them(self):
        self.app.handle('GET', f'/api/runs?token=wrong-{self.app.token[:5]}', {'Host': '127.0.0.1:8765'}, None)
        self.app.handle('POST', '/api/runs', {**self.headers(), 'X-EAOS-CSRF': 'bad'}, {})
        text = (self.app.store.folder / 'refused.jsonl').read_text()
        rows = [json.loads(line) for line in text.splitlines()]
        self.assertEqual([(r['method'], r['path']) for r in rows], [('GET', '/api/runs'), ('POST', '/api/runs')])
        self.assertIn('CSRF', rows[1]['reason'])
        self.assertNotIn(self.app.token, text)
        self.assertNotIn(self.app.token[:5], text)
        good = self.headers()
        self.assertEqual(self.app.handle('POST', '/api/runs/reorder', good, {'order': []})[0], 200)
        for change, status in (({'X-EAOS-Token': None}, 401), ({'X-EAOS-Token': 'x'}, 401),
                               ({'X-EAOS-CSRF': None}, 403),
                               ({'X-EAOS-CSRF': self.app.token}, 403), ({'Origin': 'http://127.0.0.1:9999'}, 403),
                               ({'Origin': 'null'}, 403), ({'Host': 'attacker.test:8765'}, 421),
                               ({'Host': '0.0.0.0:8765'}, 421)):
            headers = {k: v for k, v in {**good, **change}.items() if v is not None}
            self.assertEqual(self.app.handle('POST', '/api/runs/reorder', headers, {'order': []})[0], status, change)
        referer = {k: v for k, v in good.items() if k != 'Origin'}
        self.assertEqual(self.app.handle('POST', '/api/runs/reorder',
                                         {**referer, 'Referer': 'http://localhost:8765/#/runs'}, {'order': []})[0], 200)
        self.assertEqual(self.app.handle('POST', '/api/runs/reorder', referer, {'order': []})[0], 403)
        host = {'Host': 'localhost:8765'}
        self.assertEqual(self.app.handle('GET', f'/api/session?token={self.app.token}', host, None)[0], 200,
                         'a GET may carry it in the query')
        self.assertEqual(self.app.handle('GET', '/api/session?token=nope', host, None)[0], 401)
        self.assertEqual(self.app.handle('POST', f'/api/runs/reorder?token={self.app.token}',
                                         {**host, 'X-EAOS-CSRF': self.app.csrf, 'Origin': 'http://localhost:8765'},
                                         {})[0], 401)

    def test_a_confirmation_is_single_use_bound_and_expires_and_a_fix_without_one_is_refused(self):
        locks = security.Locks(8765)
        token = locks.confirm('accept', None, '/p')['token']
        self.assertFalse(locks.spend(token, 'undo', None, '/p'))
        self.assertFalse(locks.spend(token, 'accept', None, '/other'))
        self.assertTrue(locks.spend(token, 'accept', None, '/p'))
        self.assertFalse(locks.spend(token, 'accept', None, '/p'))
        late = locks.confirm('fix', {'kind': 'card'}, '/p')['token']
        with mock.patch('time.time', return_value=time.time() + security.CONFIRM_SECONDS + 5):
            self.assertFalse(locks.spend(late, 'fix', {'kind': 'card'}, '/p'))
        self.assertFalse(security.Locks(8765).spend(locks.confirm('accept', None, '/p')['token'], 'accept', None, '/p'))
        self.assertFalse(locks.spend('not.a.token', 'accept', None, '/p'))
        status, payload = self.post('/api/runs', {'action': 'fix', 'verb': 'fix',
                                                  'selection': {'kind': 'card', 'cards': ['TASK-001']}})
        self.assertEqual((status, payload.get('needs')), (403, 'confirm'))
        self.assertEqual(self.app.store.all(), [])
        self.assertEqual(self.post('/api/runs', {'action': 'accept', 'inputs': {'person_agreed': True}})[0], 403)
        # A Fix shows and pins where it builds: a branch that moves after the preview is refused, never built on
        # silently
        commit = lambda: subprocess.run(['git', '-C', str(self.project), '-c', 'user.name=a', '-c', 'user.email=a@b',
                                         'commit', '-q', '--allow-empty', '-m', 'm'], check=True)
        commit()
        subprocess.run(['git', '-C', str(self.project), 'checkout', '-q', '-b', 'dev'], check=True)
        selection = {'kind': 'card', 'cards': ['TASK-001']}
        where = self.post('/api/actions/fix/preview', {'verb': 'fix', 'selection': selection})[1]['where']
        self.assertEqual((where['base']['branch'], where['deliver_as'], where['merge_into'], where['problem']),
                         ('dev', 'eaos/dev/wave-1', 'dev', None))
        main = next(b for b in where['branches'] if b['name'] != 'dev')
        self.assertEqual(main['blocked']['code'], 'main_name',
                         'a protected branch that is not open takes no merge from here')
        preview = self.post('/api/actions/fix/preview',
                            {'verb': 'fix', 'selection': selection, 'where': {'merge_into': main['name']}})[1]
        self.assertEqual((preview['where']['problem']['code'], preview['confirm']), ('protected_target', None))
        preview = self.post('/api/actions/fix/preview',
                            {'verb': 'fix', 'selection': selection, 'where': {'deliver_as': 'eaos/mine'}})[1]
        commit()
        status, payload = self.post('/api/runs', {'action': 'fix', 'verb': 'fix', 'selection': selection,
                                                  'confirm': preview['confirm']['token'],
                                                  'where': {'deliver_as': 'eaos/mine', 'base': 'dev',
                                                            'base_commit': preview['where']['base']['commit']}})
        self.assertEqual((status, payload.get('needs')), (409, 'preview'), payload)
        self.assertIn('moved', payload['error'])
        preview = self.post('/api/actions/fix/preview',
                            {'verb': 'fix', 'selection': selection, 'where': {'deliver_as': 'eaos/mine'}})[1]
        status, payload = self.post('/api/runs', {'action': 'fix', 'verb': 'fix', 'selection': selection,
                                                  'confirm': preview['confirm']['token'],
                                                  'where': {'deliver_as': 'eaos/mine',
                                                            'base_commit': preview['where']['base']['commit']}})
        self.assertEqual((status, payload['run']['where']['deliver_as']), (200, 'eaos/mine'), payload)
        self.assertIn('deliver_as="eaos/mine"', self.app.manager.prompt_of(self.app.store.load(payload['run']['id'])))


    def test_speed_mode_is_offered_in_a_fixs_preview_kept_for_the_project_and_given_to_its_assistant(self):
        from eaos.features.guided.interface import agent_tools
        from eaos.features.guided.journey import check_choices
        from eaos.features.guided import journey as guided
        from eaos.features.check.journey import schedule
        guided.save(agent_tools.state_of(str(self.project)))              # a project checked once: its fixes come after
        subprocess.run(['git', '-C', str(self.project), '-c', 'user.name=a', '-c', 'user.email=a@b', 'commit', '-q',
                        '--allow-empty', '-m', 'm'], check=True)
        selection = {'kind': 'cards', 'cards': ['TASK-001', 'TASK-002']}
        with mock.patch.object(schedule, 'capacity',
                               return_value=(8, 2 ** 34, 2 ** 34)):           # room for five assistants
            preview = self.post('/api/actions/fix/preview', {'verb': 'fix', 'selection': selection})[1]
            self.assertEqual(preview['speed'], {'on': False, 'assistants': 5, 'lanes': 1},
                             'no plan yet: the cards are not split')
            status, payload = self.post('/api/runs',
                                        {'action': 'fix', 'verb': 'fix', 'selection': selection,
                                         'confirm': preview['confirm']['token'],
                                         'inputs': {'speed': True},
                                         'where': {'base_commit': preview['where']['base']['commit']}})
        self.assertEqual((status, payload['run']['where']['assistants']), (200, 5), payload)
        self.assertIn(', assistants=5. ', self.app.manager.prompt_of(self.app.store.load(payload['run']['id'])))
        self.assertEqual(check_choices.kept(project_state.load(self.project))['mode'], 'speed',
                         "kept, as the check's speed mode")


class Selection(Base):
    def test_every_kind_of_selection_resolves_to_open_cards_is_refused_with_its_reason_or_previewed(self):
        (self.studio / 'gaps.json').write_text(json.dumps({'gaps': [{'id': 'g1', 'component': 'orders',
                                                                     'cards': ['TASK-002', 'TASK-003']}]}))
        (self.studio / 'operations.json').write_text(json.dumps({'operations': [{'id': 'op1', 'cards': ['TASK-004']}]}))
        ids = lambda s: [c['id'] for c in selection.resolve(s, self.studio, 'fix')[0]]
        for chosen, expected in ((('severity', 'high'), ['TASK-001', 'TASK-004']), (('area', 'security'), ['TASK-002']),
                                 (('component', 'orders'), ['TASK-002']), (('gap', 'g1'), ['TASK-002']),
                                 (('operation', 'op1'), ['TASK-004'])):
            self.assertEqual(ids({'kind': 'group', 'group': {'by': chosen[0], 'value': chosen[1]}}), expected, chosen)
        self.assertEqual(ids({'kind': 'step', 'step': 'M2'}), ['TASK-004'])
        self.assertEqual(ids({'kind': 'card', 'cards': ['TASK-002', 'TASK-001']}), ['TASK-002'])
        _, left = selection.resolve({'kind': 'cards', 'cards': ['TASK-001', 'TASK-003']}, self.studio, 'fix')
        self.assertEqual(left, [{'id': 'TASK-003', 'why': 'already done', 'why_ar': 'متعامل معها: انحلّت'}])
        (self.studio / 'gaps.json').unlink()
        for bad, why in (({'kind': 'cards', 'cards': ['NOPE']}, 'no card named'),
                         ({'kind': 'cards', 'cards': ['TASK-003']}, 'can run now'),
                         ({'kind': 'group', 'group': {'by': 'gap', 'value': 'g'}}, 'gap register'),
                         ({'kind': 'x'}, 'kind'),
                         ({'kind': 'step', 'step': 'M9'}, 'names no card')):
            with self.assertRaisesRegex(selection.SelectionError, why): selection.resolve(bad, self.studio, 'fix')
        self.assertEqual(self.post('/api/actions/fix/preview',
                                   {'verb': 'fix', 'selection': {'kind': 'cards', 'cards': ['NOPE']}})[0], 400)
        (self.studio / 'cards.json').write_text(json.dumps({'cards': [card(f'TASK-{n:03d}') for n in range(10, 32)]}))
        status, preview = self.post('/api/actions/fix/preview',
                                    {'verb': 'fix',
                                     'selection': {'kind': 'group', 'group': {'by': 'severity', 'value': 'high'}}})
        self.assertEqual(status, 200, preview)
        self.assertEqual([len(b['cards']) for b in preview['batches']], [10, 10, 2])
        self.assertEqual((len(preview['files']), preview['risk']['level'], preview['assistant']['name']),
                         (22, 'high', 'Claude Code'))
        self.assertLess(preview['estimate']['minutes_low'], preview['estimate']['minutes_high'])
        self.assertTrue(preview['confirm']['token'] and preview['on_failure']['ar'])
        status, preview = self.post('/api/actions/explain/preview',
                                    {'verb': 'explain', 'selection': {'kind': 'card', 'cards': ['TASK-010']}})
        self.assertEqual((preview['risk']['level'], preview['confirm'], preview['batches']), ('low', None, []))
        (self.studio / 'cards.json').write_text(json.dumps({'cards': [card('TASK-001'),
                                                                      card('TASK-002', kind='repository_craft')]}))
        fixing, left = selection.resolve({'kind': 'cards', 'cards': ['TASK-001', 'TASK-002']}, self.studio, 'fix')
        self.assertEqual(([c['id'] for c in fixing], [c['id'] for c in left]), (['TASK-001'], ['TASK-002']))
        self.assertIn('its own batch', left[0]['why'])
        self.assertEqual(len(selection.resolve({'kind': 'cards', 'cards': ['TASK-001', 'TASK-002']}, self.studio,
                                               'explain')[0]), 2)


class Handoff(Base):
    def test_with_no_assistant_the_next_status_call_takes_the_request_and_a_note_closes_it(self):
        app = self.make(adapters_={})
        run = self.start('fix', app=app)
        self.assertEqual(app.wait(run, ('waiting_for_person',), 10)['state'], 'waiting_for_person')
        self.assertIn('studio-request', app.store.load(run)['handoff']['en'])
        self.assertEqual([r['run'] for r in handoff.pending(self.project)], [run])
        self.assertEqual(list(self.project.rglob('studio-requests.json')), [],
                         'the request waits in the EAOS workspace, never the project')
        [written] = list((self.base / 'home').rglob('studio-requests.json'))
        self.assertIn(f'studio-request {run} done', json.loads(written.read_text())[0]['request']['en'])
        from eaos.doors.mcp_server import server as mcp_server
        with mock.patch('eaos.features.guided.interface.agent_tools.status',
                        side_effect=lambda project: {'next': 'audit'}), mock.patch.dict(os.environ,
                                                                                        {'EAOS_ASSISTANT': 'Codex'}):
            answer = mcp_server._status(str(self.project))
            self.assertEqual(mcp_server._status(str(self.project)), {'next': 'audit'})
        self.assertEqual(answer['studio_request']['id'], run)
        self.assertIn('TASK-001', answer['studio_request']['request'])
        self.assertEqual(app.wait(run, ('running',), 10)['state'], 'running')
        self.assertIsNone(handoff.close(self.project, 'studio-request other done'))
        self.assertEqual(handoff.close(self.project, f'studio-request {run} done: fixed TASK-001'), run)
        self.assertEqual(app.wait(run, ('done',), 10)['result']['answer'], 'fixed TASK-001')
        self.assertEqual(handoff.pending(self.project), [])

    def test_the_studios_own_calls_neither_take_the_request_nor_use_the_person_only_tools(self):
        handoff.add(self.project, 'r1', 'do it', {'en': 'x', 'ar': 'x'})
        from eaos.doors.mcp_server import server as mcp_server
        with mock.patch('eaos.features.guided.interface.agent_tools.status', return_value={}), \
                mock.patch.dict(os.environ, {'EAOS_ASSISTANT': mcp_server.STUDIO}):
            self.assertEqual(mcp_server._status(str(self.project)), {})
        self.assertEqual(len(handoff.pending(self.project)), 1)
        with mock.patch.dict(os.environ, {'EAOS_STUDIO_RUN': 'r1'}):
            for tool in (name for name in mcp_server.PERSON_ONLY if name in mcp_server.functions()):
                answer = json.loads(mcp_server.functions()[tool](project=str(self.project),
                                                                 **({'branch': 'x'} if tool == 'choose_branch'
                                                                    else {})))
                self.assertIn('the person', answer['error'])


if __name__ == '__main__':
    unittest.main()

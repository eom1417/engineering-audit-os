"""The kinds of users of an app (eaos/roles.py): read from its code with real evidence, each opened as itself, and the
coverage saying which kinds a check saw and who opened another kind's page."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos import roles

KINDS = [{'id': 'admin', 'name': 'Administrator', 'pages': ['/admin', '/admin/users']},
         {'id': 'support', 'name': 'Support', 'pages': ['/support']},
         {'id': 'customer', 'name': 'Customer', 'pages': ['/account']}]


class Roles(unittest.TestCase):
    def test_an_answer_must_cite_a_real_line_and_name_pages_of_the_code(self):
        with tempfile.TemporaryDirectory() as target:
            (Path(target) / 'server.js').write_text('one\ntwo\n')
            good = {'roles': [{'id': 'admin', 'evidence': 'server.js:2', 'enter': 'account', 'pages': ['/admin']},
                              {'id': 'programs', 'evidence': 'server.js:1', 'enter': 'switch', 'switch': 'server.js:2', 'pages': []}]}
            self.assertEqual(roles.errors(good, target, ['/admin']), [])
            wrong = roles.errors({'roles': [{'id': 'admin', 'evidence': 'server.js:9', 'enter': 'account', 'pages': ['/nowhere']},
                                            {'id': 'programs', 'evidence': 'server.js:1', 'enter': 'switch', 'switch': 'server.js:7'},
                                            {'id': 'Admin!', 'evidence': 'x:1'}]}, target, ['/admin'])
            self.assertEqual(len(wrong), 4, wrong)

    def test_the_coverage_says_why_a_kind_was_not_seen(self):
        seen = {'/support'}
        by_hand = {row['id']: row.get('why') for row in roles.coverage(KINDS, None, seen)}
        self.assertEqual(by_hand, {'admin': 'no_access', 'support': None, 'customer': 'no_access'})
        local = {row['id']: row.get('why') for row in roles.coverage(KINDS, {'admin', 'support'}, seen)}
        self.assertEqual(local, {'admin': 'not_opened', 'support': None, 'customer': 'no_test_user'})

    def test_a_page_of_one_kind_opened_by_another_is_a_breach(self):
        base = 'http://127.0.0.1:3000'
        gone = {'path': roles.NOWHERE, 'text': 'Page not found'}
        look = lambda state, paths: {'text': 'Home', 'others': [
            {'path': p, 'url': base + p, 'status': 200 if (state, p) == ('c', '/admin/users') else 403, 'text': p} for p in paths[:-1]]
            + [gone]}
        found = roles.breaches(KINDS, [('admin', 'a'), ('customer', 'c')], look)
        self.assertEqual(found, [{'kind': 'customer', 'page': '/admin/users', 'of': 'admin'}])
        self.assertFalse(roles.opened('/admin', base + '/login'), 'sent to the sign-in is not opened')

    def test_each_kind_pictures_its_own_pages_and_the_first_one_the_shared_ones(self):
        groups = {p: [p] for p in ('/', '/admin', '/support', '/help')}
        self.assertEqual(set(roles.share(KINDS, groups, 'support', False)), {'/', '/support'})
        self.assertEqual(set(roles.share(KINDS, groups, 'admin', True)), {'/', '/admin', '/help'})
        self.assertEqual(roles.share(KINDS, groups, None, True), groups)

    def test_a_page_of_another_profile_showing_the_apps_not_found_is_not_seen_never_a_missing_page(self):
        # chief-ops (2026-10-20): signed in to the administration profile only, the check opened the programs profile's
        # pages by their address, pictured the app's "not found" (answered 200), and asked whether to delete or build them
        base = 'http://127.0.0.1:3000'
        gone = roles.nowhere_of({'text': 'Home\nWelcome back', 'others': [
            {'text': 'Page not found\nThe page /eaos-no-such-page-7f3a does not exist. Back home'}]})
        programs = 'Page not found\nThe page /programs/plans does not exist. Back home'
        self.assertFalse(roles.opened('/programs/plans', base + '/programs/plans', 200, 0, programs, gone))
        self.assertTrue(roles.opened('/admin', base + '/admin', 200, 0, 'Administration\nUsers 12 Programs 3', gone))
        # the second check of chief-ops: the app draws its "not found" inside its menus, which the page of an address it
        # does not have lacks, and the whole pages were too unlike for the "not found" to be told
        within = 'Chief Ops\nCommand centre\nPrograms\nRota\nSettings\nSupport team\nPage not found\nThe page /rota does not exist. Back home'
        self.assertFalse(roles.opened('/rota', base + '/rota', 200, 0, within, gone), 'its "not found" inside the menus')
        self.assertTrue(roles.opened('/rota', base + '/rota', 200, 0, 'Chief Ops\nCommand centre\nRota\nWeek 43\nBack home', gone))
        self.assertEqual(roles.nowhere_of({'text': 'Home\nWelcome', 'others': [{'text': 'Home\nWelcome'}]})['missing'], [],
                         'an app drawing its first page at any address says nothing by it')
        # an app with two "not found" pages: a bare 404 for an address it does not have, and its own inside its menus
        bare = roles.nowhere_of({'text': 'Chief Ops\nCommand centre\nRota\nWelcome, manager.', 'others': [{'text': '404\nThis page could not be found.'}]})
        own = 'Chief Ops\nCommand centre\nRota\nPage not found\nThe page /tickets does not exist.'
        self.assertFalse(roles.opened('/tickets', base + '/tickets', 200, 0, own, bare))
        self.assertTrue(roles.opened('/rota', base + '/rota', 200, 0, 'Chief Ops\nCommand centre\nRota\nRota\nWeek 43: 12 shifts.', bare))
        self.assertTrue(roles.opened('/settings', base + '/settings', 200, 0, 'Chief Ops\nSettings\nPermissions\n' + 'A rule. ' * 30, bare),
                        'a page about permissions is a page')
        views = KINDS + [{'id': 'programs', 'enter': 'switch', 'pages': ['/programs/plans']}]
        groups = {p: [p] for p in ('/', '/admin', '/programs/plans')}
        self.assertEqual(set(roles.share(views, groups, None, True, held={'programs'})), {'/', '/admin'},
                         "the person's one session never opens a view another session holds")
        shown = lambda state, paths: {'text': 'Home', 'others': [{'path': p, 'url': base + p, 'status': 200,
                                                     'text': f'Page not found\nThe page {p} does not exist. Back home'} for p in paths[:-1]]
                                      + [{'path': roles.NOWHERE, 'text': 'Page not found\nThe page /eaos-no-such-page-7f3a does not exist. Back home'}]}
        self.assertEqual(roles.breaches(views, [('nurse', 'n')], shown), [], "another profile's not-found page is no breach")
        opens = lambda state, paths: {'text': 'Home', 'others': [{'path': p, 'url': base + p, 'status': 200, 'text': p} for p in paths]}
        self.assertEqual(roles.breaches(views, [('programs', 'p')], opens), [], 'a switch is the same account: its pages are its own')
        rows = [{'url': base + '/programs/plans', 'kind': None, 'unseen': True}, {'url': base + '/admin', 'kind': None}]
        self.assertEqual(roles.unseen({'rows': rows}), [{'page': base + '/programs/plans', 'view': None}])
        from eaos.studio.nodes import visual_reviewer
        with tempfile.TemporaryDirectory() as report:
            (Path(report) / 'live').mkdir()
            for name in ('a.png', 'b.png'): (Path(report) / name).write_bytes(b'png')
            pictured = [{**rows[0], 'screenshot': 'a.png'}, {**rows[1], 'screenshot': 'b.png'}]
            (Path(report) / 'live/screens.json').write_text(json.dumps({'rows': pictured}))
            self.assertEqual([page['page'] for page in visual_reviewer.inputs(report)['pages']], [base + '/admin'],
                             'a page not seen is never judged')


    def test_a_view_the_running_app_shows_missing_is_added_as_checked_and_a_redirect_to_its_own_page_is_reached(self):
        # chief-ops (2026-10-20): only the support pages were pictured; the reading of the code had missed the programs
        from unittest import mock
        from eaos import test_users
        with tempfile.TemporaryDirectory() as target, tempfile.TemporaryDirectory() as out:
            (Path(target) / 'workplace.js').write_text('one\ntwo\nthree\n')
            roles._write(out, [{'id': 'support', 'enter': 'account', 'evidence': 'workplace.js:1', 'pages': ['/tickets']}])
            with mock.patch.object(roles, 'pages_of', return_value=['/tickets', '/rota']):
                refused = roles.add(out, target, [{'id': 'program', 'name': {'en': 'Program', 'ar': 'البرنامج'}, 'evidence': 'workplace.js:2',
                                                    'enter': 'switch', 'switch': 'workplace.js:3', 'pages': ['/rota']},
                                                   {'id': 'ghost', 'evidence': 'workplace.js:99', 'enter': 'account', 'pages': ['/nowhere']}])
            self.assertEqual(len(refused), 2, refused)
            self.assertEqual([(view['id'], view.get('found')) for view in roles.read(out)], [('support', None), ('program', 'app')])
        nowhere = roles.nowhere_of({'text': 'Home', 'others': [{'text': '404'}]})
        base = 'http://127.0.0.1:3000'
        self.assertTrue(test_users._reached({'path': '/settings', 'url': base + '/settings/profile', 'status': 200, 'text': 'Profile'}, nowhere))
        self.assertFalse(test_users._reached({'path': '/rota', 'url': base + '/', 'status': 200, 'text': 'Home'}, nowhere), 'sent home')
        self.assertFalse(test_users._reached({'path': '/rota', 'url': base + '/rota', 'status': 200, 'text': 'Home\nPage not found'}, nowhere))

    def test_every_page_no_session_opens_is_either_owned_by_the_view_that_opens_it_or_proved_unreachable(self):
        # chief-ops (2026-10-21): pages of the program skipped silently; a page a session found went to the wrong one
        from unittest import mock
        from eaos import test_users
        with tempfile.TemporaryDirectory() as target, tempfile.TemporaryDirectory() as out:
            (Path(target) / 'routes.js').write_text('one\ntwo\n')
            roles._write(out, [{'id': 'program', 'enter': 'switch', 'evidence': 'routes.js:1', 'pages': ['/rota']}])
            with mock.patch.object(roles, 'pages_of', return_value=['/', '/rota', '/access', '/legacy']):
                refused = roles.prove(out, target, [{'page': '/legacy', 'why': 'refuses every user', 'evidence': 'routes.js:2'},
                                                    {'page': '/access', 'why': 'no one comes here'}])
                roles.claim(out, {'program': ['/access']})
                roles.claim(out, {'program': ['/access']})
                self.assertNotIn('/legacy', test_users._tried(out))
            self.assertEqual(len(refused), 1, 'a verdict without a line of the code is refused')
            self.assertEqual(roles.proven(out), {'/legacy': 'refuses every user'})
            self.assertEqual(roles.read(out)[0]['pages'], ['/rota', '/access'])
            roles._write(out, roles.read(out))
            self.assertEqual(roles.proven(out), {'/legacy': 'refuses every user'}, 'a verdict outlives the views written again')

    def test_a_lack_on_the_running_app_goes_back_to_the_reading_which_adds_views_and_never_drops_one(self):
        # the owner, 2026-10-21: a loop back to the node that owns the views until every page opens
        from unittest import mock
        from eaos import test_users
        with tempfile.TemporaryDirectory() as target, tempfile.TemporaryDirectory() as out:
            (Path(target) / 'routes.js').write_text('one\ntwo\nthree\n')
            roles._write(out, [{'id': 'support', 'enter': 'account', 'evidence': 'routes.js:1', 'pages': ['/cases']}],
                         strategy='one_account', sign_in='a development sign-in, routes.js:1')
            asked = []
            provider = mock.Mock(complete=lambda messages, **how: (asked.append((messages[-1]['content'], how)) or {
                'roles': [{'id': 'program', 'evidence': 'routes.js:2', 'enter': 'switch', 'switch': 'routes.js:3', 'pages': ['/rota']}]}, {}))
            with mock.patch.object(roles, 'pages_of', return_value=['/cases', '/rota']):
                roles.find(target, out, provider, lacking='/rota opens with no session')
            self.assertIn('/rota opens with no session', asked[0][0])
            self.assertEqual(asked[0][1], {'stage': 'roles', 'reads': target, 'deep': True}, 'it reads the code itself')
            self.assertEqual([k['id'] for k in roles.read(out)], ['support', 'program'])
            self.assertEqual(roles.way_in(out)['strategy'], 'one_account', 'an answer without the way in keeps it')
            self.assertIn('"strategy"', ' '.join(roles.errors({'roles': [], 'strategy': 'every'}, target, [])))
        rounds = []
        with mock.patch.object(test_users, 'lacking', return_value='/rota'), \
                mock.patch.object(test_users, '_round', side_effect=lambda *a: rounds.append('round') or ('/rota' if rounds.count('round') < 3 else '')), \
                mock.patch('eaos.roles.find', side_effect=lambda *a: rounds.append(('find', a[3]))):
            self.assertEqual(test_users.make('p', None, 'b', 's', 'r', 'provider'), '')
        self.assertEqual(rounds, ['round', ('find', '/rota'), 'round', ('find', '/rota'), 'round'])
        nowhere = roles.nowhere_of({'text': 'Home', 'others': [{'text': '404'}]})
        self.assertFalse(test_users._reached({'path': '/admin', 'url': 'http://h/dashboard', 'status': 200, 'text': 'Dashboard'}, nowhere),
                         'sent to another page is not the page')


if __name__ == '__main__':
    unittest.main()

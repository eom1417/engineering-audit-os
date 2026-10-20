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
        look = lambda state, paths: [{'path': p, 'url': base + p, 'status': 200 if (state, p) == ('c', '/admin/users') else 403}
                                     for p in paths]
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
        base, gone = 'http://127.0.0.1:3000', 'Page not found\nThe page /eaos-no-such-page-7f3a does not exist. Back home'
        programs = 'Page not found\nThe page /programs/plans does not exist. Back home'
        self.assertFalse(roles.opened('/programs/plans', base + '/programs/plans', 200, 0, programs, gone))
        self.assertTrue(roles.opened('/admin', base + '/admin', 200, 0, 'Administration\nUsers 12 Programs 3', gone))
        self.assertIsNone(roles.nowhere_of({'text': 'Home\nWelcome', 'others': [{'text': 'Home\nWelcome'}]}),
                          'an app drawing its first page at any address says nothing by it')
        views = KINDS + [{'id': 'programs', 'enter': 'switch', 'pages': ['/programs/plans']}]
        groups = {p: [p] for p in ('/', '/admin', '/programs/plans')}
        self.assertEqual(set(roles.share(views, groups, None, True, held={'programs'})), {'/', '/admin'},
                         "the person's one session never opens a view another session holds")
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


if __name__ == '__main__':
    unittest.main()

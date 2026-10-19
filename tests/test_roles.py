"""The kinds of users of an app (eaos/roles.py): read from its code with real evidence, each opened as itself, and the
coverage saying which kinds a check saw and who opened another kind's page."""
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
            good = {'roles': [{'id': 'admin', 'evidence': 'server.js:2', 'pages': ['/admin']}]}
            self.assertEqual(roles.errors(good, target, ['/admin']), [])
            wrong = roles.errors({'roles': [{'id': 'admin', 'evidence': 'server.js:9', 'pages': ['/nowhere']},
                                            {'id': 'Admin!', 'evidence': 'x:1'}]}, target, ['/admin'])
            self.assertEqual(len(wrong), 3, wrong)

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


if __name__ == '__main__':
    unittest.main()

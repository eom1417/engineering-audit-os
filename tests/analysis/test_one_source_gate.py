"""The gate of one source per pattern (M15.9, closed 2026-10-28): a detector not proven safe never refuses a sound change,
code copied word for word still does, and each row is what the change wrote, not where it sits nor how many there are."""
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from eaos.analysis.claims.ledger import VERDICTS
from eaos.analysis.repair import one_source_gate as gate
from eaos.facts.code import metrics
from shared_fixture import scratch

M15 = ('one_source:near_copy', 'one_source:idiom:request_state', 'one_source:idiom:json_read', 'one_source:ui_pattern', 'one_source:look')


def near(first, second, digest, kind='similar', lines=12):
    return {'id': f'N-{first}-{second}-{digest}', 'kind': 'symbol_metric_external', 'location': {'path': first[0], 'line': first[1]},
            'value': {'record': 'near_copy', 'kind': kind, 'similarity': 0.9, 'lines': lines, 'end_line': first[1] + lines - 1,
                      'digest': digest, 'other': {'path': second[0], 'line': second[1], 'end_line': second[1] + lines - 1}}}


def idiom(path, line, form='request_state'):
    return {'id': f'I-{path}-{line}', 'kind': 'symbol_metric_external', 'location': {'path': path, 'line': line},
            'value': {'record': 'idiom', 'form': form, 'rule': form}}


def look(value, *places):
    return {'id': f'L-{value}', 'kind': 'look_value', 'location': {'path': places[0]},
            'value': {'kind': 'color', 'value': value, 'count': len(places), 'places': [{'path': p, 'line': 3} for p in places]}}


def screen(*places):
    members = [{'path': p, 'line': 5, 'end_line': 20, 'tag': 'div', 'elements': 9} for p in places]
    return {'id': 'U-1', 'kind': 'ui_pattern', 'location': {'path': places[0]}, 'value': {'members': members, 'similarity': 0.9}}


def clone(digest, *places):
    return {'id': f'C-{digest}', 'kind': 'clone_cluster', 'input_sha': digest, 'location': {'path': places[0]},
            'value': {'occurrences': [{'path': p, 'start_line': 1, 'end_line': 6} for p in places]}}


def check(external=(), patterns=(), clones=(), ran=('jscpd', 'ast-grep'), read_patterns=True):
    """A check's fact sets as `record(name)` reads them."""
    sets = {'external': {'facts': list(external), 'summary': {'engines_observed': list(ran)}},
            'patterns': {'facts': list(patterns)} if read_patterns else None, 'metrics': {'facts': list(clones)}}
    return lambda name: sets.get(name)


def added(before, after, paths, kinds=None):
    """The rows the change added, as gates.debt counts them (the check before it says what it measured)."""
    kinds = gate.measured(before) if kinds is None else kinds
    had = gate.rows(before, paths, kinds)
    return [row['what'] for key, row in gate.rows(after, paths, kinds).items() if key not in had]


class Verdicts:
    """The detector verdicts in force: `hidden` the detectors under their bar, `refuses` those proven safe to refuse."""
    def __init__(self, hidden=(), refuses=()):
        self.file = Path(scratch('eaos-gate-verdicts-')) / 'verdicts.json'
        self.file.write_text(json.dumps({'hidden': {name: 'under the bar' for name in hidden}}), encoding='utf-8')
        self.patches = [mock.patch.dict(os.environ, {'EAOS_DETECTOR_VERDICTS': str(self.file)}),
                        mock.patch.object(gate, 'REFUSES', frozenset(refuses))]

    def __enter__(self):
        for patch in self.patches: patch.start()

    def __exit__(self, *_):
        for patch in self.patches: patch.stop()


# The change of each case: before it two places of each pattern, after it a third in src/pages/C.jsx.
BEFORE = check([near(('src/pages/A.jsx', 30), ('src/pages/B.jsx', 30), 'd1'), idiom('src/pages/A.jsx', 5), idiom('src/pages/B.jsx', 5)],
               [look('#123456', 'src/pages/A.jsx', 'src/pages/B.jsx'), screen('src/pages/A.jsx', 'src/pages/B.jsx')])
AFTER = check([near(('src/pages/A.jsx', 30), ('src/pages/B.jsx', 30), 'd1'), near(('src/pages/A.jsx', 30), ('src/pages/C.jsx', 30), 'd1'),
               idiom('src/pages/A.jsx', 5), idiom('src/pages/B.jsx', 5), idiom('src/pages/C.jsx', 5)],
              [look('#123456', 'src/pages/A.jsx', 'src/pages/B.jsx', 'src/pages/C.jsx'),
               screen('src/pages/A.jsx', 'src/pages/B.jsx', 'src/pages/C.jsx')])
CHANGED = {'src/pages/C.jsx'}


class Trust(unittest.TestCase):
    def test_a_likeness_from_a_detector_under_its_bar_never_refuses_a_change(self):
        hidden = json.loads(VERDICTS.read_text(encoding='utf-8'))['hidden']
        self.assertTrue(set(M15) <= set(hidden), 'the packaged verdicts keep every detector of M15 under its bar')
        with Verdicts(hidden=M15, refuses=M15):
            self.assertEqual(added(BEFORE, AFTER, CHANGED), [], 'case C: hidden, so not even a proven refusal applies')

    def test_a_detector_over_its_bar_refuses_only_once_its_refusals_are_proven_safe(self):
        with Verdicts():
            self.assertEqual(added(BEFORE, AFTER, CHANGED), [], 'shown, its precision alone refuses nothing')
        with Verdicts(refuses=M15):
            found = added(BEFORE, AFTER, CHANGED)
        for what in ('same code is written again at src/pages/C.jsx', 'request state', '<div>', '#123456'):
            self.assertTrue(any(what in row for row in found), (what, found))

    def test_two_responsibilities_alike_in_one_folder_are_never_refused_on_likeness(self):
        # case A: a tax and a fee worked out alike, added beside each other: a likeness, not a breach
        with Verdicts():
            self.assertEqual(added(check(), check([near(('src/lib/tax.js', 1), ('src/lib/fee.js', 1), 'd9')]), {'src/lib/fee.js'}), [])

    def test_code_copied_word_for_word_is_refused_whatever_the_verdicts(self):
        # case B: the same six lines written again by the change
        after = check(clones=[clone('w1', 'src/lib/tax.js', 'src/lib/fee.js')])
        for verdicts in (Verdicts(hidden=M15), Verdicts()):
            with verdicts:
                self.assertEqual(len(added(check(), after, {'src/lib/fee.js'})), 1)

    def test_a_third_word_for_word_copy_in_a_file_that_had_one_is_refused_and_a_move_is_not(self):
        two = check(clones=[clone('w1', 'src/lib/tax.js', 'src/lib/fee.js')])
        three = check(clones=[{**clone('w1', 'src/lib/tax.js', 'src/lib/fee.js'), 'value': {'occurrences': [
            {'path': 'src/lib/tax.js', 'start_line': 1}, {'path': 'src/lib/fee.js', 'start_line': 1}, {'path': 'src/lib/fee.js', 'start_line': 40}]}}])
        with Verdicts():
            self.assertEqual(len(added(two, three, {'src/lib/fee.js'})), 1, 'one more copy of the same lines')
            moved = check(clones=[clone('w1', 'src/lib/tax.js', 'src/lib/charge.js')])
            self.assertEqual(added(two, moved, {'src/lib/fee.js', 'src/lib/charge.js'}), [], 'a copy moved between the changed files')

    def test_a_copy_kept_on_purpose_with_its_reason_is_no_clone(self):
        body = [f'    total_{i} = price * quantity + tax_{i}' for i in range(8)]
        kept = ['def one():', '    # jscpd:ignore-start -- each MCP tool is its own signature', *body, '    # jscpd:ignore-end']
        self.assertEqual(metrics._windows_of('a.py', kept), [])
        self.assertEqual(len(metrics._windows_of('a.py', ['def one():', *body])), len(body) - metrics.WINDOW + 1)


class BeforeAfter(unittest.TestCase):
    """Every detector proven safe here, so each row is seen: what the change added, and only that."""
    def setUp(self):
        self.verdicts = Verdicts(refuses=M15)
        self.verdicts.__enter__()
        self.addCleanup(self.verdicts.__exit__)

    def test_a_new_copy_is_refused_and_a_removed_one_is_not(self):
        one = check([near(('src/a.js', 1), ('src/b.js', 1), 'd1')])
        self.assertEqual(len(added(check(), one, {'src/b.js'})), 1)
        self.assertEqual(added(one, check(), {'src/b.js'}), [])

    def test_code_moved_between_the_changed_files_adds_nothing(self):
        paths = {'src/b.js', 'src/c.js'}
        self.assertEqual(added(check([near(('src/a.js', 1), ('src/b.js', 1), 'd1')]),
                               check([near(('src/a.js', 1), ('src/c.js', 1), 'd1')]), paths), [])
        self.assertEqual(added(check([idiom('src/x.js', 1), idiom('src/y.js', 1), idiom('src/b.js', 1)]),
                               check([idiom('src/x.js', 1), idiom('src/y.js', 1), idiom('src/c.js', 9)]), paths), [])

    def test_a_second_copy_between_the_same_two_files_is_its_own(self):
        one = near(('src/a.js', 1), ('src/b.js', 1), 'd1')
        two = near(('src/a.js', 40), ('src/b.js', 40), 'd2')
        self.assertEqual(len(added(check([one]), check([one, two]), {'src/b.js'})), 1)

    def test_a_different_copy_where_another_left_is_new_though_the_count_is_the_same(self):
        paths = {'src/b.js', 'src/c.js'}
        self.assertEqual(len(added(check([near(('src/a.js', 1), ('src/b.js', 1), 'd1')]),
                                   check([near(('src/a.js', 60), ('src/c.js', 1), 'd2')]), paths)), 1)
        self.assertEqual(len(added(check(patterns=[look('#111111', 'src/x.css', 'src/b.js')]),
                                   check(patterns=[look('#222222', 'src/x.css', 'src/c.js')]), paths)), 1)
        three = [idiom('src/x.js', 1), idiom('src/y.js', 1)]
        self.assertEqual(len(added(check([*three, idiom('src/b.js', 1), idiom('src/q.js', 1, 'json_read'), idiom('src/r.js', 1, 'json_read')]),
                                   check([*three, idiom('src/q.js', 1, 'json_read'), idiom('src/r.js', 1, 'json_read'),
                                          idiom('src/c.js', 1, 'json_read')]), paths)), 1, 'one request state left, a JSON read came')

    def test_what_the_check_before_did_not_measure_holds_nothing_against_the_change(self):
        older = check([near(('src/x.js', 1), ('src/y.js', 1), None)])       # near copies without their digest (0.0.88)
        for before, kind in ((check(ran=()), 'near_copy'), (older, 'near_copy'), (check(ran=()), 'idiom'), (check(read_patterns=False), 'look')):
            self.assertNotIn(kind, gate.measured(before))
        self.assertEqual(added(check(ran=(), read_patterns=False), AFTER, CHANGED), [])
        self.assertEqual(gate.measured(check(ran=(), read_patterns=False)), {'clone'}, 'EAOS\'s own metrics always run')


if __name__ == '__main__':
    unittest.main()

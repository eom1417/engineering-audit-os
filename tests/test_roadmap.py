"""Every card sized, owned by one section, and in exactly one milestone, in the blueprint's order."""
import unittest

from eaos.analysis.roadmap import effort, milestones, section, sections


def task(tid, pattern, paths=('src/a.ts',), priority=1.0, **extra):
    return {'id': tid, 'pattern': pattern, 'paths': list(paths), 'priority': priority, 'title': tid, **extra}


class RoadmapTests(unittest.TestCase):
    def test_cards_are_sized_and_placed_in_the_first_section_that_holds(self):
        self.assertEqual(effort(['a', 'b'], 5), ('S', {'files': 2, 'dependents': 5}))
        # Size needs both measures small: one file with 129 dependents (the self-audit's workspace.py) is large.
        self.assertEqual(effort(['a', 'b', 'c'], 20)[0], 'M')
        self.assertEqual(effort(['eaos/core/workspace.py'], 129)[0], 'L')
        self.assertEqual(effort([str(i) for i in range(9)], 21)[0], 'L')
        cases = [(task('1', 'upgrade_dependency', ['package-lock.json']), 'security'),
                 (task('2', 'generic', ['.github/workflows/ci.yml']), 'infrastructure'),
                 (task('3', 'generic', ['supabase/migrations/1.sql']), 'data'),
                 (task('4', 'generic', ['src/server/x.ts']), 'backend'),
                 (task('5', 'trace_gap'), 'quality'), (task('6', 'hotspot'), 'frontend'),
                 # No default section: a Python module is back end, a card with no file is general.
                 (task('7', 'hotspot', ['eaos/facts/secrets.py']), 'backend'), (task('8', 'generic', []), 'general'),
                 (task('9', 'hotspot', ['studio/src/App.tsx']), 'frontend')]
        for card, expected in cases:
            with self.subTest(expected):
                self.assertEqual(section(card), expected)
        rows = {row['section']: row for row in sections([
            dict(task('T1', 'generic'), section='data'),
            dict(task('T2', 'generic', prerequisites=[{'task_id': 'T1', 'reason': 'schema first'}]), section='frontend')])}
        self.assertEqual(rows['frontend']['depends_on'], ['data'])

    def test_milestones_keep_the_blueprint_order_and_each_card_is_in_exactly_one(self):
        tasks = [task('T1', 'load_blocker'), task('T2', 'remove_dead'), task('T3', 'hotspot', ['src/a.ts']),
                 task('T4', 'import_cycle'), task('T5', 'trace_gap'), task('T6', 'hotspot', ['src/b.ts'], priority=3)]
        plan = milestones(tasks, {'src/a.ts': 'feature:a', 'src/b.ts': 'feature:b'}, {'feature:b': 'rebuild'})
        self.assertEqual([m['name'] for m in plan],
                         ['stabilize', 'safety_net', 'boundaries', 'build:feature:b', 'build:feature:a', 'hardening'])
        self.assertEqual(sorted(tid for m in plan for tid in m['tasks']), sorted(t['id'] for t in tasks))
        self.assertTrue(next(m for m in plan if m['name'] == 'build:feature:b')['strangler'])
        self.assertTrue(all(m['goal'] and m['exit'] and m['goal_ar'] and m['exit_ar'] for m in plan))
        many = [task(f'T{i}', 'hotspot', [f'src/{i}.ts']) for i in range(12)]
        plan = milestones(many, {f'src/{i}.ts': f'feature:{i}' for i in range(12)})
        self.assertLess(len(plan), 10)
        self.assertTrue(all(m['tasks'] for m in plan))

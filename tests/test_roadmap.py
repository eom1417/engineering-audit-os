"""Every card sized, owned by one section, and in exactly one milestone, in the blueprint's order."""
from shared_fixture import Workspace

from eaos.roadmap import effort, milestones, section, sections


def task(tid, pattern, paths=('src/a.ts',), priority=1.0, **extra):
    return {'id': tid, 'pattern': pattern, 'paths': list(paths), 'priority': priority, 'title': tid, **extra}


class RoadmapTests(Workspace):
    def test_size_follows_files_and_dependents(self):
        self.assertEqual(effort(['a', 'b'], 5), ('S', {'files': 2, 'dependents': 5}))
        self.assertEqual(effort(['a', 'b', 'c'], 30)[0], 'M')
        self.assertEqual(effort([str(i) for i in range(9)], 21)[0], 'L')

    def test_the_first_section_rule_that_holds_wins(self):
        self.assertEqual(section(task('1', 'upgrade_dependency', ['package-lock.json'])), 'security')
        self.assertEqual(section(task('2', 'generic', ['.github/workflows/ci.yml'])), 'infrastructure')
        self.assertEqual(section(task('3', 'generic', ['supabase/migrations/1.sql'])), 'data')
        self.assertEqual(section(task('4', 'generic', ['src/server/x.ts'])), 'backend')
        self.assertEqual(section(task('5', 'trace_gap')), 'quality')
        self.assertEqual(section(task('6', 'hotspot')), 'frontend')

    def test_milestones_keep_the_blueprint_order_and_each_card_is_in_exactly_one(self):
        tasks = [task('T1', 'load_blocker'), task('T2', 'remove_dead'), task('T3', 'hotspot', ['src/a.ts']),
                 task('T4', 'import_cycle'), task('T5', 'trace_gap'), task('T6', 'hotspot', ['src/b.ts'], priority=3)]
        plan = milestones(tasks, {'src/a.ts': 'feature:a', 'src/b.ts': 'feature:b'}, {'feature:b': 'rebuild'})
        self.assertEqual([m['name'] for m in plan], ['stabilize', 'safety_net', 'boundaries', 'build:feature:b', 'build:feature:a', 'hardening'])
        ids = [tid for m in plan for tid in m['tasks']]
        self.assertEqual(sorted(ids), sorted(t['id'] for t in tasks))
        self.assertTrue(next(m for m in plan if m['name'] == 'build:feature:b')['strangler'])
        self.assertTrue(all(m['goal'] and m['exit'] and m['goal_ar'] and m['exit_ar'] for m in plan))

    def test_fewer_than_ten_milestones_and_no_empty_one(self):
        tasks = [task(f'T{i}', 'hotspot', [f'src/{i}.ts']) for i in range(12)]
        plan = milestones(tasks, {f'src/{i}.ts': f'feature:{i}' for i in range(12)})
        self.assertLess(len(plan), 10)
        self.assertTrue(all(m['tasks'] for m in plan))

    def test_a_section_waits_for_the_sections_its_prerequisites_are_in(self):
        tasks = [dict(task('T1', 'generic'), section='data'),
                 dict(task('T2', 'generic', prerequisites=[{'task_id': 'T1', 'reason': 'schema first'}]), section='frontend')]
        rows = {row['section']: row for row in sections(tasks)}
        self.assertEqual(rows['frontend']['depends_on'], ['data'])

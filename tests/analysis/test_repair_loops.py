"""A loop of imports is the change's only when the change made it (second strangers' round, 2026-11-05: removing one
import of a large loop in a monorepo showed a smaller loop it held, and the sound fix was refused for it)."""
import json
import unittest
from pathlib import Path

from eaos.analysis.repair import gates
from shared_fixture import scratch


def check(*loops):
    folder = Path(scratch())
    (folder / 'facts').mkdir()
    facts = [{'kind': 'graph_cycle', 'location': {'path': members[0]}, 'value': {'members': list(members)}} for members in loops]
    (folder / 'facts/graph.json').write_text(json.dumps({'facts': facts}), encoding='utf-8')
    return folder


class LoopTests(unittest.TestCase):
    def test_a_smaller_loop_a_large_one_held_is_not_the_changes_and_a_new_one_is(self):
        before = check(('common/a.ts', 'common/b.ts', 'common/c.ts', 'math/d.ts'))
        self.assertEqual(gates.structure(before, check(('common/a.ts', 'common/b.ts'))), [])
        found = gates.structure(before, check(('common/a.ts', 'common/b.ts'), ('math/d.ts', 'math/e.ts')))
        self.assertEqual([row['where'] for row in found], ['math/d.ts'])


if __name__ == '__main__':
    unittest.main()

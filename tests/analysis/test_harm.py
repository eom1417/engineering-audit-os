"""A size measure is a card only with a sign of harm: a flat run of defaults and a cohesive unit are not worth a fix,
a deeply nested function is."""
import unittest

from eaos.features.claims.analysis.harm import mark
from eaos.kernel.contracts.decisions import decide


def metric(path, symbol, nesting):
    return {'kind': 'metric', 'location': {'path': path, 'symbol': symbol},
            'value': {'scope': 'method', 'lines': 80, 'complexity': 18, 'max_nesting': nesting}}


def claim(key, **params):
    return {'id': 'CLM-001', 'statement': 's', 'claim_type': 'structure', 'confidence': 'CONFIRMED', 'falsifier': 'f',
            'render': {'key': key, 'params': params}, 'disposition': {'kind': 'investigate', 'reason': 'Ranked.'}}


def sets(metrics, commits=0, fixes=None):
    churn = [{'kind': 'history_churn', 'location': {'path': path}, 'value': {'commits': n, 'fix_commits': n}}
             for path, n in (fixes or {}).items()]
    return {'metrics': {'facts': metrics}, 'history': {'summary': {'commits_analysed': commits}, 'facts': churn}}


class SizeNeedsHarm(unittest.TestCase):
    def kinds(self, rows, facts):
        mark(rows, facts)
        return [decide(row)['kind'] for row in rows]

    def test_a_flat_function_past_the_limit_is_kept_as_a_measure(self):
        # complexity 17 from a flat run of bindValue defaults, nesting 3
        facts = sets([metric('app/Models/FeedDAO.php', 'addFeed', 3)])
        row = claim('hotspot', path='app/Models/FeedDAO.php', symbol='addFeed')
        self.assertEqual(self.kinds([row], facts), ['retain'])
        self.assertIn('Measured only', decide(row)['reason'])

    def test_a_deep_function_stays_a_card(self):
        # nesting 8, the kind of function both judges wanted fixed
        facts = sets([metric('app/Controllers/entryController.php', 'readAction', 8)])
        row = claim('hotspot', path='app/Controllers/entryController.php', symbol='readAction')
        self.assertNotEqual(self.kinds([row], facts), ['retain'])

    def test_a_file_fixed_often_earns_its_cards_flat_or_long(self):
        facts = sets([metric('src/a.ts', 'f', 2)], commits=40, fixes={'src/a.ts': 3})
        rows = [claim('hotspot', path='src/a.ts', symbol='f'), claim('large_module', path='src/a.ts')]
        self.assertNotIn('retain', self.kinds(rows, facts))

    def test_a_long_cohesive_module_is_kept_and_a_short_history_says_nothing(self):
        # a message list of one cohesive 1523-line unit; its fixes are unknown with one commit read
        facts = sets([metric('lib/model/message_list.dart', 'f', 6)], commits=1,
                     fixes={'lib/model/message_list.dart': 5})
        self.assertEqual(self.kinds([claim('large_module', path='lib/model/message_list.dart')], facts), ['retain'])

    def test_an_engine_complexity_at_a_file_follows_its_deepest_function(self):
        flat, deep = sets([metric('lib/favicons.php', 'a', 3)]), sets([metric('lib/favicons.php', 'a', 7)])
        row = lambda: claim('engine_cluster', place='lib/favicons.php', kind='complexity')
        self.assertEqual(self.kinds([row()], flat), ['retain'])
        self.assertNotEqual(self.kinds([row()], deep), ['retain'])

    def test_other_claims_are_left_alone(self):
        row = claim('command_injection', path='server.js')
        mark([row], sets([]))
        self.assertEqual(row['disposition']['kind'], 'investigate')



class NestingTests(unittest.TestCase):
    def test_only_a_block_is_a_level_an_object_or_a_jsx_value_is_not(self):
        # only a block is a level: counting every brace would read most complex functions five deep
        from eaos.features.code_reading.facts.code.metrics import nesting_depth
        script = ['function f(a) {', '  const o = { x: { y: 1 } };', '  if (a) {', '    for (const b of a) {',
                  '      call({ k: () => { return 1; } });', '    }', '  } else {', '    return <div>{a}</div>;', '  }',
                  '}']
        self.assertEqual(nesting_depth(script, 'typescript'), 4)          # f, if, for, the arrow's body
        self.assertEqual(nesting_depth(['    def f(self):', '        if a:', '            return 1'], 'python'), 2)

if __name__ == '__main__':
    unittest.main()

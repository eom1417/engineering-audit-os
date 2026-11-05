"""A size measure is a card only with a sign of harm (M17.3, 2026-11-05: two judges found 30 of 40 sampled cards true
sizes and branch counts, all but one not worth fixing; the one kept nested eight deep)."""
import unittest

from eaos.analysis.claims.harm import mark
from eaos.core.contracts.decisions import decide


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
        # FreshRSS's FeedDAO.addFeed: complexity 17 from a flat run of bindValue defaults, nesting 3.
        facts = sets([metric('app/Models/FeedDAO.php', 'addFeed', 3)])
        row = claim('hotspot', path='app/Models/FeedDAO.php', symbol='addFeed')
        self.assertEqual(self.kinds([row], facts), ['retain'])
        self.assertIn('Measured only', decide(row)['reason'])

    def test_a_deep_function_stays_a_card(self):
        # FreshRSS's entryController.readAction: nesting 8, the one both judges wanted fixed.
        facts = sets([metric('app/Controllers/entryController.php', 'readAction', 8)])
        row = claim('hotspot', path='app/Controllers/entryController.php', symbol='readAction')
        self.assertNotEqual(self.kinds([row], facts), ['retain'])

    def test_a_file_fixed_often_earns_its_cards_flat_or_long(self):
        facts = sets([metric('src/a.ts', 'f', 2)], commits=40, fixes={'src/a.ts': 3})
        rows = [claim('hotspot', path='src/a.ts', symbol='f'), claim('large_module', path='src/a.ts')]
        self.assertNotIn('retain', self.kinds(rows, facts))

    def test_a_long_cohesive_module_is_kept_and_a_short_history_says_nothing(self):
        # zulip-flutter's message list: one cohesive 1523-line unit; its fixes unknown with one commit read.
        facts = sets([metric('lib/model/message_list.dart', 'f', 6)], commits=1, fixes={'lib/model/message_list.dart': 5})
        self.assertEqual(self.kinds([claim('large_module', path='lib/model/message_list.dart')], facts), ['retain'])

    def test_an_engine_complexity_at_a_file_follows_its_deepest_function(self):
        flat, deep = sets([metric('lib/favicons.php', 'a', 3)]), sets([metric('lib/favicons.php', 'a', 6)])
        row = lambda: claim('engine_cluster', place='lib/favicons.php', kind='complexity')
        self.assertEqual(self.kinds([row()], flat), ['retain'])
        self.assertNotEqual(self.kinds([row()], deep), ['retain'])

    def test_other_claims_are_left_alone(self):
        row = claim('command_injection', path='server.js')
        mark([row], sets([]))
        self.assertEqual(row['disposition']['kind'], 'investigate')


if __name__ == '__main__':
    unittest.main()

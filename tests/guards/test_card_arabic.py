"""Every card reads in Arabic for an Arabic reader: its why is never the English scenario when the card carries its fix
in Arabic (a stranger's Rust tool showed "Split it by job..." under Arabic, 2026-11-04), and every rule of the
repository's craft and of the layers says its sentence and its fix in both languages."""
import json
import re
import unittest
from pathlib import Path
from eaos.core.language.words import impact_of
from eaos.facts.repository.catalog import RULES

ARABIC = re.compile('[؀-ۿ]')
SAVED = Path(__file__).resolve().parents[1] / 'fixtures/saved-project/0.0.90/output/technical/dossier.json'


class CardArabicTests(unittest.TestCase):
    def test_a_card_with_an_arabic_fix_says_it_in_arabic(self):
        claim = {'render': {'key': 'repository_finding', 'params': {'fix_en': 'Split it by job.', 'fix_ar': 'قسّمه حسب الوظيفة.'}},
                 'impact': {'scenario': 'Split it by job.'}}
        self.assertEqual(impact_of(claim, 'ar'), 'قسّمه حسب الوظيفة.')

    def test_every_craft_rule_is_said_in_arabic(self):
        for rule, (_, ar, _, fix_ar) in RULES.items():
            with self.subTest(rule): self.assertTrue(ARABIC.search(ar) and ARABIC.search(fix_ar))

    def test_every_saved_card_reads_in_arabic(self):
        claims = json.loads(SAVED.read_text(encoding='utf-8'))['claims']
        english = [c['id'] for c in claims if impact_of(c, 'ar') != '—' and not ARABIC.search(impact_of(c, 'ar'))]
        self.assertEqual(english, [])

    def test_an_upgrade_with_no_fixed_version_asks_to_replace_the_package(self):
        from eaos.core.language.words import statement_of
        claim = {'render': {'key': 'vulnerable_dependency', 'params': {'package': 'bincode', 'installed': '1.3.3', 'count': 1,
                                                                       'ids': 'RUSTSEC-2025-0141', 'severity': 'medium', 'fixed': '—'}}}
        self.assertIn('replace it', statement_of(claim, 'en'))
        self.assertIn('القرار لك', impact_of(claim, 'ar'))


if __name__ == '__main__':
    unittest.main()

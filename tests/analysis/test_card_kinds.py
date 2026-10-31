"""One definition of each card kind (eaos/core/contracts/card_kinds.py): a kind nobody registered is refused when a claim is
built, so it can never reach a person as a generic card with its detector and its own fix lost."""
import ast
import unittest
from pathlib import Path
from unittest import mock

from eaos.analysis.claims import ledger
from eaos.analysis.presentation.model import PATTERNS as AREAS
from eaos.analysis.repair import one_source_gate, remediation
from eaos.core.contracts.card_kinds import KINDS
from eaos.core.language.words import TEMPLATES, statement_of

ROOT = Path(__file__).resolve().parents[2]
# Written out here, not read from the table: a row that loses its field must disagree with something.
JUDGED_AS = {'engine_cluster': 'engine_cluster:X', 'layer_finding': 'layer:X', 'repository_finding': 'repository:X',
             'logic_flaw': 'logic:X', 'experience_difficulty': 'experience:X', 'real_data': 'real_data:X',
             'old_engine': 'old_engine:X', 'data_keeping': 'data_keeping:X', 'one_source': 'one_source:X'}
OWN_FIX_AND_WORDS = ('layer_finding', 'repository_finding', 'logic_flaw', 'experience_difficulty', 'real_data', 'old_engine',
                     'data_keeping', 'one_source', 'person_rule')
OWN_PATTERN = ('old_engine', 'data_keeping', 'one_source', 'person_rule')
SUBTYPE = {'kind': 'X', 'rule': 'X', 'class': 'X'}


def claim(key=None, **params):
    row = {'id': 'CLM-001', 'statement': 'A finding', 'claim_type': 'risk', 'confidence': 'LIKELY', 'method': ['static_fact'],
           'evidence_ids': ['E1'], 'falsifier': 'It is gone', 'presented_in': ['A1'], 'status': 'open'}
    return {**row, 'render': {'key': key, 'params': params}} if key else row


class NewClaims(unittest.TestCase):
    def test_a_card_kind_nobody_registered_is_refused_by_name(self):
        problems = ledger.errors([claim('never_registered', ar='x', en='y')])
        self.assertTrue(any('never_registered' in problem for problem in problems), problems)

    def test_a_registered_kind_and_a_claim_with_no_card_kind_are_not(self):
        for row in (claim('one_source', kind='near_copy', ar='x', en='y'), claim()):
            self.assertFalse([p for p in ledger.errors([row]) if 'card kind' in p], row)


class Withholding(unittest.TestCase):
    def test_a_card_of_a_hidden_detector_is_withheld_for_every_kind_judged_per_subtype(self):
        for key, name in JUDGED_AS.items():
            with self.subTest(key), mock.patch.object(ledger, 'hidden_detectors', return_value={name: 'under its bar'}):
                shown, withheld = ledger.withhold([{**claim(key, **SUBTYPE)}])
                self.assertEqual((shown, withheld[0]['withheld']['detector']), ([], name))

    def test_a_kind_with_no_subtype_is_judged_by_its_key_and_shown_when_not_hidden(self):
        with mock.patch.object(ledger, 'hidden_detectors', return_value={'dead_code': 'under its bar'}):
            self.assertEqual(ledger.withhold([claim('dead_code')])[0], [])
            self.assertEqual(len(ledger.withhold([claim('hotspot')])[0]), 1)

    def test_the_gate_judges_a_finding_as_the_ledger_judges_its_card(self):
        for finding, kind in (({'kind': 'near_copy', 'evidence': {}}, 'near_copy'),
                              ({'kind': 'idiom', 'evidence': {'form': 'json-read'}}, 'idiom:json-read')):
            self.assertEqual(one_source_gate.detector(finding), ledger.detector_of(claim('one_source', kind=kind)))


class Remediation(unittest.TestCase):
    def test_a_card_with_its_own_fix_keeps_it(self):
        for key in OWN_FIX_AND_WORDS:
            with self.subTest(key):
                self.assertEqual(remediation.pattern_for(claim(key, fix_ar='its own fix'))['change'], 'its own fix')

    def test_a_kind_that_is_its_own_pattern_is_never_generic_with_or_without_a_probe(self):
        for key in OWN_PATTERN:
            with self.subTest(key):
                self.assertEqual(remediation.classify(claim(key)), key)
                for table in (remediation.PATTERNS, AREAS): self.assertIn(key, table)
                self.assertTrue(remediation.cost_of_inaction(key))

    def test_an_unknown_subtype_inside_a_known_kind_stays_generic_and_is_not_refused(self):
        card = {**claim('engine_cluster', kind='no_such_subtype'),
                'probe_spec': {'probe_type': 'graph_query', 'specification': {'query': 'engine_cluster_present', 'kind': 'no_such_subtype'}}}
        self.assertEqual(remediation.classify(card), 'generic')
        self.assertFalse([p for p in ledger.errors([card]) if 'card kind' in p])

    def test_a_saved_card_of_a_kind_since_retired_still_reads(self):
        old = claim('a_kind_since_retired', ar='x', en='y')
        self.assertEqual(remediation.pattern_for(old)['name'], 'generic')
        self.assertEqual(statement_of(old, 'en'), old['statement'])
        self.assertEqual(ledger.detector_of(old), 'a_kind_since_retired')


class Words(unittest.TestCase):
    def test_a_card_with_its_own_words_says_them_in_each_language(self):
        for key in OWN_FIX_AND_WORDS:
            with self.subTest(key):
                card = claim(key, ar='بالعربي', en='in English')
                self.assertEqual((statement_of(card, 'ar'), statement_of(card, 'en')), ('بالعربي', 'in English'))

    def test_every_other_kind_has_its_sentence_in_both_languages(self):
        for key, kind in KINDS.items():
            for language in ('ar', 'en'): self.assertIn(key, TEMPLATES[language], (key, language))


class TheTable(unittest.TestCase):
    def test_every_card_kind_written_in_the_code_is_registered(self):
        written = set()
        for path in (ROOT / 'eaos').rglob('*.py'):
            if path.parent.name == 'templates' or 'rules' in path.parts and 'semgrep' in path.parts: continue
            written |= {key for key in _render_keys(path.read_text(encoding='utf-8'))}
        self.assertTrue({'one_source', 'cochange', 'dead_code_review'} <= written, 'the scan still finds what it looks for')
        self.assertEqual(written - set(KINDS), set())


def _render_keys(text):
    """The literal `render={'key': ...}`, `'render': {'key': ...}` and `['render']['key'] = ...` of one module."""
    found = set()
    for node in ast.walk(ast.parse(text)):
        rendered = [node.value] if isinstance(node, ast.keyword) and node.arg == 'render' else []
        if isinstance(node, ast.Dict):
            rendered += [v for k, v in zip(node.keys, node.values) if isinstance(k, ast.Constant) and k.value == 'render']
        for value in rendered:
            if isinstance(value, ast.Dict):
                found |= {v.value for k, v in zip(value.keys, value.values)
                          if isinstance(k, ast.Constant) and k.value == 'key' and isinstance(v, ast.Constant)}
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and "['render']['key']" in ast.unparse(node.targets[0]):
            found.add(node.value.value)
    return found


if __name__ == '__main__':
    unittest.main()

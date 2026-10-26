"""The JSON records carry the meaning; the two languages render the same thing from them."""
import json
import re
import shutil
import unittest
import shared_fixture  # noqa: F401  (runs without measured detector verdicts)
from pathlib import Path

from eaos.core.contracts.artifacts import DOCUMENTS
from eaos.core.language.words import FALSIFIERS, IMPACTS, TEMPLATES, falsifier_of, statement_of
from eaos.pipeline import execute
from shared_fixture import scratch

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/sustainability'
ARABIC = re.compile(r'[؀-ۿ]{3,}')
LATIN_WORD = re.compile(r'\b[A-Za-z]{4,}\b')


class ParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = scratch()
        cls.arabic = Path(cls.directory) / 'ar'
        cls.english = Path(cls.directory) / 'en'
        execute(FIXTURE, cls.arabic, skip=('engines',), language='ar')
        # A document a check before M1.4 wrote and none writes now goes, or both languages would not list the same files.
        cls.english.mkdir(parents=True)
        (cls.english / 'DECISION-BRIEF.md').write_text('# Decision brief\n', encoding='utf-8')
        execute(FIXTURE, cls.english, skip=('engines',), language='en')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.directory, ignore_errors=True)

    def test_both_languages_produce_every_document_and_neither_mixes_in_the_other(self):
        self.assertEqual({p.name for p in self.arabic.glob('*.md')}, {p.name for p in self.english.glob('*.md')})
        for artifact in DOCUMENTS:
            if not artifact.required or artifact.name == 'index.html':
                continue
            for root in (self.arabic, self.english):
                self.assertTrue((root / artifact.name).is_file(), f'{artifact.name} missing from {root.name}')
        leaking = {}
        for path in sorted(self.english.glob('*.md')):
            text = path.read_text(encoding='utf-8')
            self.assertTrue(text.lstrip().startswith('#'), f'{path.name} has no heading')
            if ARABIC.findall(text):
                leaking[path.name] = ARABIC.findall(text)[:3]
        self.assertEqual(leaking, {}, 'the reader asked for English')
        text = (self.arabic / 'CURRENT-STATE.md').read_text(encoding='utf-8')
        self.assertTrue(LATIN_WORD.search(text), 'symbol and path names must not be translated')

    def test_both_languages_render_the_same_records(self):
        arabic, english = (json.loads((root / 'dossier.json').read_text(encoding='utf-8')) for root in (self.arabic, self.english))
        self.assertEqual(sorted(c['claim_type'] for c in arabic['claims']), sorted(c['claim_type'] for c in english['claims']))
        arabic, english = (json.loads((root / 'plan.json').read_text(encoding='utf-8')) for root in (self.arabic, self.english))
        self.assertEqual(sorted(arabic), sorted(english))
        self.assertEqual(len(arabic['tasks']), len(english['tasks']))

    def test_every_card_and_every_index_link_is_there(self):
        plan = json.loads((self.english / 'plan.json').read_text(encoding='utf-8'))
        self.assertEqual(len(list((self.english / 'PLAN').glob('TASK-*.md'))), len(plan['tasks']))
        targets = re.findall(r'\]\(([^)]+)\)', (self.english / 'README.md').read_text(encoding='utf-8'))
        self.assertTrue(targets)
        optional = {artifact.name for artifact in DOCUMENTS if not artifact.required}
        missing = [t for t in targets if not t.startswith(('http', '#')) and not (self.english / t).exists() and t not in optional]
        self.assertEqual(missing, [], 'the index points at documents that were never produced')


class LabelCatalogueTests(unittest.TestCase):
    """Both languages describe the same claim, or the reader gets the other one's words."""

    def test_both_languages_describe_the_same_claim(self):
        for catalogue, name in ((IMPACTS, 'IMPACTS'), (TEMPLATES, 'TEMPLATES'),
                                (FALSIFIERS, 'FALSIFIERS')):
            arabic, english = set(catalogue['ar']), set(catalogue['en'])
            with self.subTest(catalogue=name):
                self.assertEqual(arabic - english, set(),
                                 f'{name}: these keys fall back to Arabic in an English report')
        # The ledger stores one English sentence per claim kind. Printing it under an Arabic
        # heading gave the reader half a line in each language.
        for key in FALSIFIERS['ar']:
            with self.subTest(key=key):
                claim = {'falsifier': 'An English sentence.', 'render': {'key': key}}
                self.assertNotEqual(falsifier_of(claim, 'ar'), 'An English sentence.')
                self.assertEqual(falsifier_of(claim, 'en'), 'An English sentence.')
        # A kind with no entry keeps the stored sentence rather than losing it.
        unknown = {'falsifier': 'Stored.', 'render': {'key': 'not-a-key'}}
        self.assertEqual(falsifier_of(unknown, 'ar'), 'Stored.')
        claim = {'statement': 'مسار: ينادي خدمة خارجية',
                 'render': {'key': 'load_blocker',
                            'params': {'where': 'route', 'kind': 'timeout', 'statement': 'ينادي خدمة خارجية'},
                            'params_en': {'where': 'route', 'kind': 'timeout', 'statement': 'calls an external service'}}}
        self.assertNotRegex(statement_of(claim, 'en'), ARABIC)
        self.assertIn('calls an external service', statement_of(claim, 'en'))

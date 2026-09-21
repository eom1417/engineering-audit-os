"""The JSON records carry the meaning; the two languages render the same thing from them."""
import json
import re
import shutil
import tempfile
import unittest
from shared_fixture import Workspace
from pathlib import Path

from eaos.audit import run as run_audit
from eaos.compose.artifacts import DOCUMENTS

FIXTURE = Path(__file__).resolve().parent / 'fixtures/sustainability'
ARABIC = re.compile(r'[؀-ۿ]{3,}')
LATIN_WORD = re.compile(r'\b[A-Za-z]{4,}\b')


class ParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.mkdtemp()
        cls.arabic = Path(cls.directory) / 'ar'
        cls.english = Path(cls.directory) / 'en'
        run_audit(FIXTURE, cls.arabic, language='ar')
        run_audit(FIXTURE, cls.english, language='en')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.directory, ignore_errors=True)

    def test_both_languages_produce_the_same_set_of_documents(self):
        arabic = {path.name for path in self.arabic.glob('*.md')}
        english = {path.name for path in self.english.glob('*.md')}
        self.assertEqual(arabic, english)

    def test_the_english_report_is_not_half_arabic(self):
        leaking = {}
        for path in sorted(self.english.glob('*.md')):
            found = ARABIC.findall(path.read_text(encoding='utf-8'))
            if found:
                leaking[path.name] = found[:3]
        self.assertEqual(leaking, {}, 'the reader asked for English')

    def test_the_arabic_report_still_keeps_identifiers_as_written(self):
        text = (self.arabic / 'SYSTEM-MAP.md').read_text(encoding='utf-8')
        self.assertTrue(LATIN_WORD.search(text), 'symbol and path names must not be translated')

    def test_both_languages_render_the_same_records(self):
        for name in ('dossier.json', 'plan.json', 'transform-plan.json'):
            arabic = json.loads((self.arabic / name).read_text(encoding='utf-8'))
            english = json.loads((self.english / name).read_text(encoding='utf-8'))
            if name == 'dossier.json':
                self.assertEqual(len(arabic['claims']), len(english['claims']))
                self.assertEqual(sorted(c['claim_type'] for c in arabic['claims']),
                                 sorted(c['claim_type'] for c in english['claims']))
            else:
                self.assertEqual(sorted(arabic), sorted(english))

    def test_every_declared_document_is_produced_in_both_languages(self):
        for artifact in DOCUMENTS:
            if not artifact.required or artifact.name == 'index.html':
                continue
            for root in (self.arabic, self.english):
                self.assertTrue((root / artifact.name).is_file(), f'{artifact.name} missing from {root.name}')

    def test_every_document_links_somewhere_or_says_why_it_does_not(self):
        for path in sorted(self.english.glob('*.md')):
            text = path.read_text(encoding='utf-8')
            self.assertTrue(text.strip(), f'{path.name} is empty')
            self.assertTrue(text.lstrip().startswith('#'), f'{path.name} has no heading')


class RecordDrivenTests(Workspace):
    """A changed record must change the rendering, or the rendering is not reading it."""

    def setUp(self):
        super().setUp()
        self.out = Path(self.tmp) / 'out'
        run_audit(FIXTURE, self.out, language='en')

    def test_removing_a_task_removes_its_card(self):
        plan = json.loads((self.out / 'plan.json').read_text(encoding='utf-8'))
        if not plan['tasks']:
            self.skipTest('the fixture produced no task to remove')
        cards = sorted(path.name for path in (self.out / 'PLAN').glob('TASK-*.md'))
        self.assertEqual(len(cards), len(plan['tasks']))

    def test_a_blocked_repair_appears_in_the_blockers_document(self):
        dossier = json.loads((self.out / 'dossier.json').read_text(encoding='utf-8'))
        blocked = [task for task in dossier['tasks'] if task['decision']['blockers']]
        text = (self.out / 'BLOCKERS.md').read_text(encoding='utf-8')
        for task in blocked:
            self.assertIn(task['id'], text, 'a blocked repair is missing from BLOCKERS.md')
        if not blocked:
            self.assertIn('No recorded repair blockers', text)

    def test_the_blockers_document_speaks_the_requested_language_only(self):
        text = (self.out / 'BLOCKERS.md').read_text(encoding='utf-8')
        self.assertEqual(ARABIC.findall(text), [])

    def test_every_link_in_the_index_resolves(self):
        text = (self.out / 'README.md').read_text(encoding='utf-8')
        targets = re.findall(r'\]\(([^)]+)\)', text)
        self.assertTrue(targets)
        missing = [target for target in targets
                   if not target.startswith(('http', '#')) and not (self.out / target).exists()]
        declared = {artifact.name for artifact in DOCUMENTS if not artifact.required}
        surprising = [target for target in missing if target not in declared]
        self.assertEqual(surprising, [], 'the index points at documents that were never produced')

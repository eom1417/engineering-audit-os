"""studio/: the cards, evidence, decisions and history a check writes, and what the fix verbs, the problems filter and
`eaos waiting` read of them; the evidence excerpts never show a secret or a file outside the project."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.shared_fixture import Workspace

from eaos.journeys.fix import selection
from eaos.report.records import cards, evidence, model, write


def task(number, pattern, kind='remediate', **extra):
    return {'id': f'TASK-{number}', 'title': f'card {number}', 'pattern': pattern, 'kind': kind,
            'paths': [f'src/m{number}.py'],
            'claim_id': f'CLM-{number}', 'decision': {'readiness': 'ready'}, **extra}


class Records(Workspace):
    def setUp(self):
        super().setUp()
        self.out = Path(self.tmp)
        self.project = str(self.out / 'shop')
        self.tasks = [task(1, 'dead_code'), task(2, 'security_weakness', 'investigate'), task(3, 'import_cycle')]
        self.save()

    def save(self):
        (self.out / 'plan.json').write_text(json.dumps({'tasks': self.tasks,
                                                        'milestones': [{'id': 'M01', 'tasks': ['TASK-1', 'TASK-2']}]}))
        (self.out / 'dossier.json').write_text(json.dumps({'coverage': {'source_files': 10},
                                                           'claims': [{'id': f'CLM-{n}', 'confidence': 'CONFIRMED'}
                                                                      for n in (1, 2, 3)]}))

    def load(self, name):
        return json.loads((self.out / 'studio' / f'{name}.json').read_text(encoding='utf-8'))

    def test_the_verbs_select_the_cards_the_check_wrote_and_the_inbox_offers_the_investigations(self):
        result = write.write(self.out, 'en', self.project)
        self.assertEqual((result['written'], result['errors']), (['cards', 'evidence', 'decisions', 'history'], []))
        run, left = selection.resolve({'kind': 'group', 'group': {'by': 'area', 'value': 'quality'}},
                                      self.out / 'studio', 'fix')
        self.assertEqual(([c['id'] for c in run], left), (['TASK-1'], []))
        self.assertEqual(selection.cards_in(self.out / 'studio', 'severity', 'high'), {'TASK-2'})
        self.assertEqual([c['milestone'] for c in self.load('cards')['cards']], ['M01', 'M01', None])
        decisions = self.load('decisions')['decisions']
        self.assertEqual([(d['id'], d['blocks'], d['recommended_option']) for d in decisions],
                         [('investigations', ['TASK-2'], 'yes')])
        scans = self.load('history')['scans']
        self.assertEqual((len(scans), scans[0]['open_total'], scans[0]['total']), (1, 3, 3))
        self.assertEqual(self.load('manifest')['project'], {'name': 'shop'})

    def test_the_inbox_asks_only_what_the_assistant_left_to_the_person_and_each_card_says_what_it_decided(self):
        self.tasks[1]['resolution'] = {'resolution': 'owner', 'by': 'assistant',
                                       'question': 'Show prices with tax?', 'options': ['Yes', 'No'],
                                       'recommendation': 'Yes', 'why': 'a product choice',
                                       'words': 'decided by your assistant'}
        self.tasks[2]['resolution'] = {'resolution': 'fix', 'by': 'assistant', 'change': 'Split the handler',
                                       'capped': True, 'words': 'w'}
        self.save()
        (self.out / 'cards.json').write_text(json.dumps(
            {'set_aside': [{'card': 'TASK-9', 'title': 'a rule card', 'why': 'contradicted'}]}))
        write.write(self.out, 'en', self.project)
        decisions = self.load('decisions')['decisions']
        self.assertEqual([(d['id'], d['state'], d['recommended_option'], d['answer']) for d in decisions],
                         [('card:TASK-2', 'waiting', 'o1', None), ('disagree-TASK-9', 'answered', None, 'assistant')])
        shown = {c['id']: c for c in self.load('cards')['cards']}
        self.assertEqual((shown['TASK-3']['needs_decision'], shown['TASK-3']['resolution']['change']),
                         (False, 'Split the handler'))
        self.assertEqual((shown['TASK-2']['needs_decision'], shown['TASK-2']['resolution']['options']),
                         (True, ['Yes', 'No']))

    def test_records_that_cannot_be_read_are_named_and_leave_no_manifest(self):
        write.write(self.out, 'en', self.project)
        with mock.patch.object(model, 'records', side_effect=OSError('disk gone')):
            result = write.write(self.out, 'en', self.project)
        self.assertEqual(result, {'written': [], 'errors': [{'section': 'records', 'error': 'OSError: disk gone'}]})
        self.assertFalse((self.out / 'studio/manifest.json').exists())


class Evidence(unittest.TestCase):
    """A card says why it matters in both languages; a fact carries the code around its line, never a secret."""

    TEXT = 'import a\n\nconst KEY = "sk_live_123"\nfunction f() {\n  return 1\n}\n'

    def source(self, path):
        return {'src/a.ts': self.TEXT, 'bin.dat': 'x\0y'}.get(path)

    def test_the_code_around_a_line_is_written_with_its_numbers_and_a_secret_line_never(self):
        code = evidence.code_excerpt(self.source, 'src/a.ts', 5, 'complexity')
        self.assertEqual(code, {'start': 3, 'line': 5,
                                'lines': ['const KEY = "sk_live_123"', 'function f() {', '  return 1', '}'],
                                'hidden': []})
        self.assertEqual(len(evidence.code_excerpt(lambda path: 'x' * 1000, 'min.js', 1, 'complexity')['lines'][0]),
                         evidence.CODE_WIDTH)
        for args in (('src/a.ts', 3, 'secret'), ('src/a.ts', None, 'complexity'), ('src/a.ts', 99, 'complexity'),
                     ('gone.ts', 1, 'complexity'), ('bin.dat', 1, 'complexity')):
            self.assertIsNone(evidence.code_excerpt(self.source, *args), args)
        code = evidence.code_excerpt(self.source, 'src/a.ts', 4, 'complexity', {('src/a.ts', 3)})
        self.assertEqual(code['hidden'], [3])
        self.assertNotIn('sk_live', ''.join(code['lines']))

    def test_the_evidence_hides_secret_lines_and_a_card_says_why_in_both_languages(self):
        facts = [{'id': 'F1', 'kind': 'engine_finding', 'location': {'path': 'src/a.ts', 'line': 4},
                  'value': {'kind': 'complexity', 'message': 'complex'}},
                 {'id': 'F2', 'kind': 'engine_finding', 'location': {'path': 'src/a.ts'},
                  'value': {'kind': 'secret', 'sites': [{'path': 'src/a.ts', 'line': 3}]}}]
        from eaos.facts.store import write_set
        with tempfile.TemporaryDirectory() as report:
            write_set(report, 'external', 'external', '1', [], {'facts': facts, 'input_sha': 'sha'})
            rows = {f['id']: f for f in evidence.evidence(report, {'F1', 'F2'}, self.source)}
        self.assertEqual((rows['F1']['line'], rows['F1']['code']['hidden']), (4, [3]))
        self.assertIsNone(rows['F2']['code'])
        self.assertNotIn('sk_live', json.dumps(rows))
        why = cards.why_of({'impact': 'Code nobody runs is still read.',
                            'impact_render': {'key': 'dead_code', 'params': {}}})['why']
        self.assertEqual(set(why), {'ar', 'en'})
        self.assertRegex(why['ar'], '[؀-ۿ]')
        self.assertEqual(cards.why_of({}), {})

    def test_files_are_read_at_the_scanned_commit_and_never_outside_the_project(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / 'p'
            (project / 'src').mkdir(parents=True)
            (Path(folder) / 'outside.txt').write_text('secret', encoding='utf-8')
            (project / 'src/a.ts').write_text('old\n', encoding='utf-8')
            git = lambda *a: subprocess.run(['git', '-C', str(project), *a], check=True,
                                            capture_output=True, text=True).stdout.strip()
            git('init', '-q'); git('add', '.'); git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'one')
            commit = git('rev-parse', 'HEAD')
            (project / 'src/a.ts').write_text('new\n', encoding='utf-8')
            self.assertEqual(evidence.sources(project, commit)('src/a.ts'), 'old\n')
            self.assertEqual(evidence.sources(project, None)('src/a.ts'), 'new\n')
            self.assertIsNone(evidence.sources(project, None)('../outside.txt'))
            self.assertIsNone(evidence.sources(None, None)('src/a.ts'))

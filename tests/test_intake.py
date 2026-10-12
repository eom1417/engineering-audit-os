"""The intake: every question answered or on a declared default, and every scenario number with a source."""
import json
from pathlib import Path

from shared_fixture import Workspace

from eaos import intake
from eaos.artifact_contracts import contracts, validate


class IntakeTests(Workspace):
    def setUp(self):
        super().setUp()
        self.target, self.out = Path(self.tmp) / 'project', Path(self.tmp) / 'out'
        (self.out / 'facts').mkdir(parents=True)
        self.target.mkdir()
        self.features([('Login', True), ('Reports', False)])

    def features(self, rows):
        (self.out / 'features.json').write_text(json.dumps({'features': [{'name': n, 'critical': c} for n, c in rows]}))

    def model(self, path, name, text, start_line=1):
        (self.target / path).parent.mkdir(parents=True, exist_ok=True)
        (self.target / path).write_text(text)
        facts = self.out / 'facts/domain.json'
        rows = json.loads(facts.read_text())['facts'] if facts.is_file() else []
        rows.append({'kind': 'data_model', 'location': {'path': path, 'start_line': start_line}, 'value': {'name': name}})
        facts.write_text(json.dumps({'facts': rows}))

    def questions(self, answers=None):
        return {row['id']: row for row in intake.build(self.target, self.out, answers)['questions']}

    def test_without_answers_every_question_is_a_declared_default_and_the_record_keeps_its_contract(self):
        record = intake.build(self.target, self.out)
        self.assertEqual(validate(record, contracts()['intake']), [])
        for row in record['questions']:
            self.assertEqual(row['status'], 'default')
            self.assertTrue(row['default_reason'], row['id'])
        self.assertEqual(self.questions()['critical_features']['answer'], ['Login'])

    def test_an_answer_is_used_with_its_source_and_an_unknown_id_is_reported(self):
        record = intake.build(self.target, self.out, {'concurrent_users': 10000, 'colour': 'blue'})
        row = next(q for q in record['questions'] if q['id'] == 'concurrent_users')
        self.assertEqual((row['answer'], row['status']), (10000, 'answered'))
        self.assertEqual(record['unknown_answers'], ['colour'])
        load = next(s for s in record['scenarios'] if s['kind'] == 'load')
        self.assertIn('10000 users', load['stimulus'])
        self.assertEqual((load['source'], load['question_id']), ('answer', 'concurrent_users'))
        availability = next(s for s in record['scenarios'] if s['kind'] == 'availability')
        self.assertEqual((availability['source'], availability['measure']['threshold']), ('default', 99.5))

    def test_personal_data_is_found_on_a_person_and_the_reason_says_where(self):
        # A definition ends where the next one starts; a name is personal only on a person.
        self.model('src/types.ts', 'Category', 'export interface Category {\n  id: string;\n}\nexport interface Vendor {\n  email: string;\n}\n')
        self.model('src/category.ts', 'Category', 'export interface Category {\n  name: string;\n}\n')
        self.assertIs(self.questions()['personal_data']['answer'], False)
        self.model('src/vendor.ts', 'Vendor', 'export interface Vendor {\n  id: string;\n  email: string;\n}\n')
        self.assertIn('src/vendor.ts:3', self.questions()['personal_data']['default_reason'])
        self.assertIn('privacy', [s['kind'] for s in intake.build(self.target, self.out)['scenarios']])
        (self.out / 'facts/domain.json').unlink()
        self.model('src/driver.ts', 'Driver', 'export interface Driver {\n  name: string;\n}\n')
        self.assertIs(self.questions()['personal_data']['answer'], True)

    def test_the_run_command_follows_the_lockfile_and_prefers_preview(self):
        self.assertIsNone(intake.run_command(self.target))
        (self.target / 'package.json').write_text(json.dumps({'scripts': {'dev': 'vite', 'preview': 'vite preview'}}))
        self.assertEqual(intake.run_command(self.target), 'npm run preview')
        (self.target / 'bun.lock').write_text('')
        self.assertEqual(intake.run_command(self.target), 'bun run preview')

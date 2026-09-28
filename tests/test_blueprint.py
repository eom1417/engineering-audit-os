"""Building a project from its plan (docs/BUILD-FROM-PLAN.md): any plan read, the spec checked, the target and the
build drawn, the gates that keep copies, cycles, layer breaks and stray vendors out, and the build handed over."""
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from eaos import blueprint, build_tools, guided


def spec(**changes):
    base = {'name': 'Clinic', 'summary': 'Book clinic visits.',
            'modules': [{'id': 'appointments', 'name': 'Appointments', 'responsibility': 'booking visits'},
                        {'id': 'patients', 'name': 'Patients', 'responsibility': 'who the patients are'}],
            'entities': [{'id': 'patient', 'name': 'Patient', 'module': 'patients', 'fields': [{'name': 'name', 'type': 'text'}]},
                         {'id': 'appointment', 'name': 'Appointment', 'module': 'appointments', 'fields': [{'name': 'at', 'type': 'date'}]}],
            'features': [{'id': 'F1', 'name': 'Register a patient', 'module': 'patients', 'entities': ['patient'], 'roles': ['staff'],
                          'acceptance': ['a saved patient appears in the list']},
                         {'id': 'F2', 'name': 'Book a visit', 'module': 'appointments', 'entities': ['appointment', 'patient'],
                          'roles': ['staff'], 'acceptance': ['a booked visit shows on its day']}],
            'roles': [{'id': 'staff', 'name': 'Staff', 'can': ['F1', 'F2']}],
            'flows': [{'id': 'FL1', 'name': 'First booking', 'actor': 'staff', 'features': ['F1', 'F2'], 'steps': ['add', 'book']}]}
    base.update(changes)
    return base


class SourceTests(unittest.TestCase):
    def test_any_plan_is_read_as_text_pasted_markdown_html_or_word(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(blueprint.read_source(text='  a pasted plan  '), 'a pasted plan')
            (Path(tmp) / 'plan.md').write_text('# Plan\n\nBook visits.\n')
            self.assertIn('Book visits.', blueprint.read_source(Path(tmp) / 'plan.md'))
            (Path(tmp) / 'plan.html').write_text('<html><style>x{}</style><h1>Plan</h1><p>Book&nbsp;visits</p></html>')
            self.assertEqual(blueprint.read_source(Path(tmp) / 'plan.html').split(), ['Plan', 'Book', 'visits'])
            with zipfile.ZipFile(Path(tmp) / 'plan.docx', 'w') as word:
                word.writestr('word/document.xml', '<w:document><w:body><w:p><w:r><w:t>حجز المواعيد</w:t></w:r></w:p>'
                                                   '<w:p><w:r><w:t>Staff book visits</w:t></w:r></w:p></w:body></w:document>')
            self.assertEqual(blueprint.read_source(Path(tmp) / 'plan.docx').splitlines(), ['حجز المواعيد', 'Staff book visits'])
            with self.assertRaises(ValueError): blueprint.read_source(Path(tmp) / 'missing.pdf')


class SpecTests(unittest.TestCase):
    def test_a_complete_spec_has_no_problem(self):
        self.assertEqual(blueprint.validate_spec(spec()), ([], []))

    def test_what_makes_a_spec_unbuildable_is_named(self):
        broken = spec(features=[{'id': 'F1', 'name': 'x', 'module': 'patients', 'entities': ['patient', 'ghost'], 'acceptance': []}],
                      entities=spec()['entities'] + [{'id': 'orphan', 'name': 'O', 'module': 'nowhere', 'fields': []}])
        problems, _ = blueprint.validate_spec(broken)
        text = '\n'.join(problems)
        for expected in ('no acceptance criterion', 'uses ghost, which is not an entity', 'entity orphan: its owning module',
                         'entity orphan: no feature uses it', 'module appointments: no feature belongs to it'):
            self.assertIn(expected, text)

    def test_an_open_decision_and_an_unknown_technology_become_questions_with_a_recommendation(self):
        _, questions = blueprint.validate_spec(spec(stack_preferences={'database': 'mongodb'},
                                                    decisions=[{'id': 'D1', 'question': 'Reminders by SMS or e-mail?',
                                                                'options': ['sms', 'email'], 'recommendation': 'email'}]))
        by_id = {q['id']: q for q in questions}
        self.assertEqual(by_id['stack-database']['recommendation'], 'postgres-drizzle')
        self.assertEqual((by_id['D1']['kind'], by_id['D1']['recommendation']), ('choice', 'email'))


class DesignTests(unittest.TestCase):
    def test_the_stack_follows_the_person_then_the_recommendation_and_leaves_out_what_the_plan_does_not_need(self):
        self.assertEqual(blueprint.choose_stack(spec(), {'database': 'supabase'})['database']['id'], 'supabase')
        self.assertEqual(blueprint.choose_stack(spec())['database']['id'], 'postgres-drizzle')
        bare = blueprint.choose_stack(spec(entities=[], roles=[], features=[{'id': 'F1', 'module': 'patients'}]))
        self.assertEqual((bare['database']['id'], bare['auth']['id']), ('none', 'none'))
        self.assertTrue(blueprint.choose_stack(spec())['database']['switch'], 'every choice says how to change it later')

    def test_the_build_goes_skeleton_foundations_then_each_module_after_the_data_it_uses_then_the_journeys(self):
        built = blueprint.design(spec(), blueprint.choose_stack(spec()))
        names = [m['name'] for m in built['plan']['milestones']]
        self.assertEqual(names, ['The skeleton', 'Shared foundations', 'Patients', 'Appointments', 'Journeys end to end'],
                         'appointments use patients, so patients are built first')
        cards = {c['id']: c for c in built['plan']['tasks']}
        feature = next(c for c in cards.values() if c['feature'] == 'F2')
        self.assertEqual(feature['acceptance'], ['a booked visit shows on its day'])
        self.assertTrue(all(cards[d]['milestone'] <= feature['milestone'] for d in feature['depends_on']))
        self.assertIn('server/src/infrastructure/database/', built['policy']['vendors']['database']['only_in'])
        rules = {rule['allow_only']['from']: rule['allow_only']['to'] for rule in built['policy']['rules']}
        self.assertEqual(rules['domain'], ['shared'], 'business rules use nothing but the shared types')

    def test_the_target_reads_like_an_audits_target(self):
        built = blueprint.design(spec(), blueprint.choose_stack(spec()))
        target = built['architecture']
        self.assertEqual({c['name'] for c in target['target_components'] if c['kind'] == 'module'}, {'Patients', 'Appointments'})
        self.assertTrue(all(d['how_to_change_later'] for d in target['decisions']))


def write(root, files):
    for name, text in files.items():
        (Path(root) / name).parent.mkdir(parents=True, exist_ok=True)
        (Path(root) / name).write_text(text)


class GateTests(unittest.TestCase):
    def test_layer_breaks_stray_files_vendors_outside_their_adapter_cycles_and_copies_are_refused(self):
        from eaos.facts.run import collect
        stack = blueprint.choose_stack(spec())
        rules = blueprint.policy(stack)
        copied = ''.join(f'  const v{i} = input.values[{i}] * rate + offset - {i};\n' for i in range(9))
        with tempfile.TemporaryDirectory() as tmp:
            root, out = Path(tmp) / 'p', Path(tmp) / 'out'
            write(root, {
                'package.json': '{"name": "p", "dependencies": {"drizzle-orm": "1"}}',
                'server/src/domain/patients/rules.ts': 'import { db } from "../../infrastructure/database/db";\nexport const r = db;\n',
                'server/src/infrastructure/database/db.ts': 'import { drizzle } from "drizzle-orm";\nexport const db = drizzle;\n',
                'server/src/application/patients/list.ts': 'import { drizzle } from "drizzle-orm";\nexport const l = drizzle;\n',
                'server/src/application/patients/a.ts': 'import { b } from "./b";\nexport const a = () => b;\n',
                'server/src/application/patients/b.ts': 'import { a } from "./a";\nexport const b = () => a;\n',
                'server/src/application/patients/one.ts': f'export function one(input, rate, offset) {{\n{copied}  return 0;\n}}\n',
                'server/src/application/patients/two.ts': f'export function two(input, rate, offset) {{\n{copied}  return 1;\n}}\n',
                'server/src/stray/thing.ts': 'export const t = 1;\n'})
            collect(root.resolve(), out)
            gates = {problem['gate'] for problem in blueprint.build_problems(root, out, rules)}
        self.assertTrue({'layers', 'structure', 'vendor', 'cycle', 'copy'} <= gates, gates)


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp.name) / 'home')})
        patcher.start(); self.addCleanup(patcher.stop)
        self.project = str(Path(self.tmp.name) / 'clinic')

    def test_from_a_pasted_plan_to_a_designed_blueprint_in_an_empty_folder(self):
        answer = build_tools.blueprint_start(text='A clinic books visits for its patients.', project=self.project)
        self.assertIn('features', answer['spec_format'])
        self.assertTrue(Path(self.project).is_dir(), 'a new project folder is made')
        self.assertEqual(build_tools.status(self.project)['next']['tool'], 'blueprint_spec')
        self.assertEqual(build_tools.blueprint_spec(spec(), self.project)['problems'], [])
        designed = build_tools.blueprint_design(project=self.project)
        self.assertEqual(designed['status'], 'designed')
        self.assertTrue(Path(designed['blueprint']).is_file())
        page = Path(designed['for_the_person']).read_text()
        self.assertIn('Register a patient', page)
        self.assertIn('To change it later', page, 'every technology says how to change it later')
        self.assertTrue(build_tools.open_blueprint(self.project, show=False)['blueprint_for_people'].endswith('BLUEPRINT.html'))
        self.assertEqual(build_tools.status(self.project)['next']['tool'], 'build_start')
        self.assertEqual(build_tools.build_start(self.project)['status'], 'needs_agreement')
        self.assertFalse((Path(self.project) / '.git').exists(), 'nothing is made before the person agrees')

    def test_a_card_is_kept_only_through_its_gates_and_a_milestone_arrives_as_a_stacked_branch(self):
        build_tools.blueprint_start(text='plan', project=self.project)
        build_tools.blueprint_spec(spec(), self.project)
        build_tools.blueprint_design(project=self.project)
        opened = build_tools.build_start(self.project, person_agreed=True)
        self.assertEqual(opened['milestone']['id'], 'M01')
        root = Path(opened['copy'])
        self.assertTrue((root / 'eaos.policy.json').is_file() and (root / 'docs/blueprint/BLUEPRINT.md').is_file())
        edit = {'card': 'BLD-001', 'edits': [{'path': 'package.json', 'content': '{"name": "clinic"}\n'}]}
        with mock.patch.object(build_tools, '_gates', return_value=[{'gate': 'copy', 'where': 'a.ts', 'what': 'copied'}]):
            refused = build_tools._build_edit_job(self.project, edit, lambda *_: None)
        self.assertFalse(refused['kept'])
        self.assertFalse((root / 'package.json').exists(), 'a refused card is taken back')
        with mock.patch.object(build_tools, '_gates', return_value=[]):
            kept = build_tools._build_edit_job(self.project, edit, lambda *_: None)
            self.assertTrue(kept['kept'])
            finished = build_tools._build_finish_job(self.project, {}, lambda *_: None)
        self.assertEqual((finished['delivered'], finished['branch']), (True, 'eaos/build-1'))
        branches = subprocess.run(['git', '-C', self.project, 'branch', '--list', 'eaos/*'], capture_output=True, text=True).stdout
        self.assertIn('eaos/build-1', branches)
        self.assertEqual(finished['milestones_left'][0], 'M02')
        nxt = build_tools.build_start(self.project)
        self.assertEqual(nxt['milestone']['id'], 'M02', 'the next milestone needs no second agreement')
        self.assertTrue((Path(nxt['copy']) / 'package.json').is_file(), 'it starts where the last milestone ended')
        state = guided.load(Path(self.project).resolve())
        self.assertEqual([w['status'] for w in state['waves']], ['applied'])


if __name__ == '__main__':
    unittest.main()

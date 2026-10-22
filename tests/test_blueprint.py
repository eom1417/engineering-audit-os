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

from eaos import blueprint, build_tools, guided, plan_source


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
            'flows': [{'id': 'FL1', 'name': 'First booking', 'actor': 'staff', 'features': ['F1', 'F2'], 'steps': ['add', 'book']}],
            'look': {'theme': 'light', 'colors': {'primary': '#0F766E'}, 'fonts': ['IBM Plex Sans Arabic'], 'components': ['button', 'table'],
                     'design_md': '# Clinic\n\nCalm teal on white, IBM Plex Sans Arabic.',
                     'screens': [{'id': 'S1', 'name': 'Visits', 'features': ['F2'], 'picture': 'screens/visits.png'}]}}
    base.update(changes)
    return base


class SpecTests(unittest.TestCase):
    def test_any_plan_is_read_and_what_makes_its_spec_unbuildable_or_open_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(plan_source.read_source(text='  a pasted plan  '), 'a pasted plan')
            (Path(tmp) / 'plan.md').write_text('# Plan\n\nBook visits.\n')
            self.assertIn('Book visits.', plan_source.read_source(Path(tmp) / 'plan.md'))
            (Path(tmp) / 'plan.html').write_text('<html><style>x{}</style><h1>Plan</h1><p>Book&nbsp;visits</p></html>')
            self.assertEqual(plan_source.read_source(Path(tmp) / 'plan.html').split(), ['Plan', 'Book', 'visits'])
            with zipfile.ZipFile(Path(tmp) / 'plan.docx', 'w') as word:
                word.writestr('word/document.xml', '<w:document><w:body><w:p><w:r><w:t>حجز المواعيد</w:t></w:r></w:p>'
                                                   '<w:p><w:r><w:t>Staff book visits</w:t></w:r></w:p></w:body></w:document>')
            self.assertEqual(plan_source.read_source(Path(tmp) / 'plan.docx').splitlines(), ['حجز المواعيد', 'Staff book visits'])
            with self.assertRaises(ValueError): plan_source.read_source(Path(tmp) / 'missing.pdf')
            # A folder of them, with the pictures of its screens kept as files for the assistant to look at.
            (Path(tmp) / 'screens').mkdir()
            (Path(tmp) / 'screens/visits.png').write_bytes(b'png')
            text, pictures = plan_source.read_plan(tmp)
            self.assertIn('Book visits.', text)
            self.assertEqual(pictures, [str(Path(tmp) / 'screens/visits.png')])
        self.assertEqual(blueprint.validate_spec(spec()), ([], []))
        broken = spec(features=[{'id': 'F1', 'name': 'x', 'module': 'patients', 'entities': ['patient', 'ghost'], 'acceptance': []}],
                      entities=spec()['entities'] + [{'id': 'orphan', 'name': 'O', 'module': 'nowhere', 'fields': []}])
        problems, _ = blueprint.validate_spec(broken)
        text = '\n'.join(problems)
        for expected in ('no acceptance criterion', 'uses ghost, which is not an entity', 'entity orphan: its owning module',
                         'entity orphan: no feature uses it', 'module appointments: no feature belongs to it'):
            self.assertIn(expected, text)
        self.assertIn('`look` is empty', '\n'.join(blueprint.validate_spec(spec(look=None))[0]))
        _, questions = blueprint.validate_spec(spec(stack_preferences={'database': 'mongodb'},
                                                    decisions=[{'id': 'D1', 'question': 'Reminders by SMS or e-mail?',
                                                                'options': ['sms', 'email'], 'recommendation': 'email'}]))
        by_id = {q['id']: q for q in questions}
        self.assertEqual(by_id['stack-database']['recommendation'], 'postgres-drizzle')
        self.assertEqual((by_id['D1']['kind'], by_id['D1']['recommendation']), ('choice', 'email'))

class DesignTests(unittest.TestCase):
    def test_the_stack_follows_the_person_and_the_build_goes_skeleton_foundations_modules_then_journeys(self):
        self.assertEqual(blueprint.choose_stack(spec(), {'database': 'supabase'})['database']['id'], 'supabase')
        self.assertEqual(blueprint.choose_stack(spec())['database']['id'], 'postgres-drizzle')
        bare = blueprint.choose_stack(spec(entities=[], roles=[], features=[{'id': 'F1', 'module': 'patients'}]))
        self.assertEqual((bare['database']['id'], bare['auth']['id']), ('none', 'none'))
        self.assertTrue(blueprint.choose_stack(spec())['database']['switch'], 'every choice says how to change it later')
        built = blueprint.design(spec(), blueprint.choose_stack(spec()))
        names = [m['name'] for m in built['plan']['milestones']]
        self.assertEqual(names, ['The skeleton', 'Shared foundations', 'Patients', 'Appointments', 'Journeys end to end', 'Ready to release'],
                         'appointments use patients, so patients are built first')
        cards = {c['id']: c for c in built['plan']['tasks']}
        feature = next(c for c in cards.values() if c['feature'] == 'F2')
        self.assertEqual(feature['acceptance'], ['a booked visit shows on its day',
                                                 'the screen Visits follows its picture screens/visits.png, with the shared look only'])
        self.assertTrue(all(cards[d]['milestone'] <= feature['milestone'] for d in feature['depends_on']))
        self.assertIn('server/src/infrastructure/database/', built['policy']['vendors']['database']['only_in'])
        rules = {rule['allow_only']['from']: rule['allow_only']['to'] for rule in built['policy']['rules']}
        self.assertEqual(rules['domain'], ['shared'], 'business rules use nothing but the shared types')
        target = built['architecture']
        self.assertEqual({c['name'] for c in target['parts'] if c['kind'] == 'module'}, {'Patients', 'Appointments'})
        self.assertIn('domain', {c['layer'] for c in target['target_components']}, "the target's parts are its layers, as a check's are")
        self.assertTrue(all(d['how_to_change_later'] for d in target['decisions']))


    def test_the_cards_every_product_needs_come_from_its_facts_and_every_requirement_is_built_by_something(self):
        # HungerLab: an assistant added about 50 such cards by hand, and nothing proved each requirement was built.
        facts = spec(nonfunctional={'languages': ['ar', 'en'], 'data_sensitivity': 'health', 'platforms': ['mobile web'], 'expected_users': 5000},
                     integrations=[{'id': 'sms', 'name': 'Twilio', 'purpose': 'reminders'}],
                     requirements=[{'id': 'FR-1', 'text': 'book a visit', 'covered_by': ['F2']},
                                   {'id': 'NFR-3', 'text': 'Arabic first', 'covered_by': ['languages']}])
        self.assertEqual(blueprint.validate_spec(facts), ([], []))
        built = blueprint.design(facts, blueprint.choose_stack(facts))
        by_source = {c['source']: c for c in built['plan']['tasks']}
        self.assertLessEqual({'languages', 'privacy', 'offline', 'integration:sms', 'security', 'errors', 'accessibility', 'speed',
                              'load', 'release'}, set(by_source))
        self.assertEqual(by_source['integration:sms']['paths'], ['server/src/infrastructure/sms/'])
        self.assertEqual({by_source[k]['milestone'] for k in ('languages', 'privacy', 'security')}, {'M02'})
        self.assertEqual(built['plan']['milestones'][-1]['name'], 'Ready to release')
        self.assertEqual((by_source['F2']['covers'], by_source['languages']['covers']), (['FR-1'], ['NFR-3']))
        bare = {c['source'] for c in blueprint.design(spec(), blueprint.choose_stack(spec()))['plan']['tasks']}
        self.assertFalse(bare & {'languages', 'privacy', 'offline', 'load'}, 'only what the facts call for')
        problems = '\n'.join(blueprint.validate_spec(spec(requirements=[{'id': 'FR-9', 'text': 'pay', 'covered_by': []},
                                                                        {'id': 'FR-8', 'text': 'x', 'covered_by': ['payments']}]))[0])
        self.assertIn('requirement FR-9: nothing builds it', problems)
        self.assertIn('requirement FR-8: payments is not a feature', problems)


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
            from eaos.gates import found
            gates = {problem['gate'] for problem in found(None, out, [p.relative_to(root).as_posix() for p in root.rglob('*.ts')], rules)}
        self.assertTrue({'layers', 'structure', 'vendor', 'cycle', 'copy'} <= gates, gates)

    def test_a_shape_too_small_to_hold_a_rule_is_not_a_copy(self):
        # A real build: `() => x.y()` in several files was refused as copied code.
        from eaos.facts.run import collect
        from eaos.gates import found
        with tempfile.TemporaryDirectory() as tmp:
            root, out = Path(tmp) / 'p', Path(tmp) / 'out'
            write(root, {f'server/src/application/m{i}/use.ts': f'import {{ db{i} }} from "./db";\nexport const close{i} = () => db{i}.end();\n'
                         for i in range(8)})
            collect(root.resolve(), out)
            problems = found(None, out, [p.relative_to(root).as_posix() for p in root.rglob('*.ts')], blueprint.policy(blueprint.choose_stack(spec())))
        self.assertNotIn('copy', {problem['gate'] for problem in problems})


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(self.tmp.name) / 'home')})
        patcher.start(); self.addCleanup(patcher.stop)
        self.project = str(Path(self.tmp.name) / 'clinic')

    def test_a_blueprint_drawn_outside_the_studio_shows_there_its_build_plan_its_questions_and_its_next_step(self):
        # The incident (HungerLab): the blueprint was drawn from the person's own assistant session; the Studio showed
        # no build card, none of its four questions, and "check the project" with no score.
        from eaos.studio import actions
        build_tools.blueprint_start(text='A clinic books visits for its patients.', project=self.project)
        asked = spec(decisions=[{'id': 'D1', 'question': 'Reminders by SMS or e-mail?', 'options': ['SMS', 'E-mail'],
                                 'recommendation': 'E-mail', 'why': 'e-mail costs nothing'}], flows=[])
        build_tools.blueprint_spec(asked, self.project)
        build_tools.blueprint_design(project=self.project)
        studio = guided.report_of(guided.load(Path(self.project).resolve())) / 'studio'
        read = lambda name: json.loads((studio / f'{name}.json').read_text())
        built = next(p for p in read('plans')['plans'] if p['kind'] == 'build')
        cards = [t for s in built['steps'] for t in s['tasks']]
        self.assertEqual(len(cards), len(build_tools._plan(guided.load(Path(self.project).resolve()))['tasks']))
        self.assertIn('a booked visit shows on its day', '\n'.join(t['acceptance'] for t in cards))
        question = next(d for d in read('decisions')['decisions'] if d['id'] == 'blueprint:D1')
        self.assertEqual(([o['label'] for o in question['options']], question['recommended_option']), (['SMS', 'E-mail'], 'o2'))
        self.assertEqual(read('head')['next']['tool'], 'blueprint_answer')
        self.assertEqual({d['state'] for d in read('decisions')['decisions'] if d['id'].startswith('blueprint:')}, {'waiting'},
                         'a check\'s share of questions never answers a blueprint question for the person')
        app = actions.Actions(Path(self.project), port=8765, adapters={})
        self.addCleanup(app.close)
        row = next(r for r in app.report_decisions() if r['id'] == 'blueprint:D1')
        self.assertEqual(app.answer_decision('blueprint:D1', {'scope': row['scope'], 'option': 'o1'})['response']['status'], 'applied')
        kept = json.loads((build_tools.folder(guided.load(Path(self.project).resolve())) / 'product-spec.json').read_text())
        self.assertEqual(kept['decisions'][0]['chosen'], 'SMS', 'the answer is in the spec, with no assistant run to review it')
        self.assertFalse(app.store.all())
        self.assertEqual([d['id'] for d in read('decisions')['decisions']], ['blueprint:flows'])
        build_tools.blueprint_answer('flows', 'yes', self.project)
        self.assertEqual((read('head')['next']['tool'], read('head')['next']['milestone']), ('build_start', 'M01'))

    def test_the_last_milestone_waits_for_every_requirement_and_for_usable_screens(self):
        build_tools.blueprint_start(text='plan', project=self.project)
        build_tools.blueprint_spec(spec(requirements=[{'id': 'FR-1', 'text': 'book a visit', 'covered_by': ['F2']}]), self.project)
        build_tools.blueprint_design(project=self.project)
        state = guided.load(Path(self.project).resolve())
        card = next(c['id'] for c in build_tools._plan(state)['tasks'] if c['covers'] == ['FR-1'])
        self.assertEqual([p['where'] for p in build_tools._unbuilt(state, {'kept': {}})], ['FR-1'], 'skipped or never built')
        self.assertEqual(build_tools._unbuilt(state, {'kept': {card: 'abc'}}), [])
        look = {'screen_problems': [{'page': '/', 'width': 375, 'problems': ['axe: color-contrast (serious, 2)']}],
                'speed': {'performance': 40, 'accessibility': 80, 'best-practices': 95}}
        self.assertEqual([p['what'] for p in build_tools._unusable(look)],
                         ['axe: color-contrast (serious, 2)', 'Lighthouse accessibility is 80, under 90'],
                         'the copy runs in development mode: its speed never stops a delivery')

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
        with mock.patch.object(build_tools, '_gates', return_value=[]), \
                mock.patch.object(build_tools, '_look', return_value={'screens': 2, 'departures': []}) as looked:
            kept = build_tools._build_edit_job(self.project, edit, lambda *_: None)
            self.assertTrue(kept['kept'])
            finished = build_tools._build_finish_job(self.project, {}, lambda *_: None)
        self.assertEqual((finished['delivered'], finished['branch']), (True, 'eaos/build-1'))
        self.assertEqual((looked.call_count, finished['look']['screens']), (1, 2), "a milestone with screens has them pictured and reviewed")
        self.assertTrue((guided.report_of(guided.load(Path(self.project).resolve())).parent / 'DESIGN.md').is_file(), "the spec's look is kept where the review reads it")
        branches = subprocess.run(['git', '-C', self.project, 'branch', '--list', 'eaos/*'], capture_output=True, text=True).stdout
        self.assertIn('eaos/build-1', branches)
        self.assertEqual(finished['milestones_left'][0], 'M02')
        nxt = build_tools.build_start(self.project)
        self.assertEqual(nxt['milestone']['id'], 'M02', 'the next milestone needs no second agreement')
        self.assertTrue((Path(nxt['copy']) / 'package.json').is_file(), 'it starts where the last milestone ended')
        state = guided.load(Path(self.project).resolve())
        self.assertEqual([w['status'] for w in state['waves']], ['applied'])
        from eaos import journeys, progress
        steps = {s['id']: s for s in journeys.journey(state)}
        self.assertEqual(list(steps), ['plan', 'spec', 'blueprint', 'build', 'accept'], 'the build journey, as declared')
        self.assertTrue(steps['blueprint']['done'] and not steps['build']['done'])
        self.assertEqual(steps['build']['state'], 'running', 'a build no process holds is not judged gone')
        drawn = {s['name']: s for s in progress.fold(progress.read(guided.runtime_of(state), 'build'))['stages']}
        self.assertEqual((drawn['M01']['state'], drawn['M02']['state']), ('ok', 'running'))
        self.assertEqual([(c['name'], c['status']) for c in drawn['M01']['steps']], [('BLD-001', 'ok')])
        journeys.draw_build(state)
        again = progress.fold(progress.read(guided.runtime_of(state), 'build'))
        self.assertEqual((again['started_at'], {s['name']: s['started_at'] for s in again['stages']}['M02']),
                         (state['built'][0]['began'], state['open_build']['began']), 'drawn again, the build keeps its own times')


if __name__ == '__main__':
    unittest.main()


class LookTests(unittest.TestCase):
    def test_a_chosen_design_is_kept_beside_the_report_and_the_screen_review_judges_against_it(self):
        from eaos import design
        from eaos.studio.nodes import visual_reviewer
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {'EAOS_ENGINE_TOOLS': tmp}):
            self.assertIn('tools install --only ui-ux-pro-max', design.brief()['sources']['ui-ux-pro-max']['install'],
                          'a source not fetched says how to fetch it')
            report = Path(tmp) / 'out' / 'technical'
            (report / 'live/screens').mkdir(parents=True)
            (report / 'live/screens/home.png').write_bytes(b'png')
            (report / 'live/screens.json').write_text('{"rows": [{"url": "/", "screenshot": "live/screens/home.png", '
                                                      '"viewport": "phone", "variant": "light"}]}', encoding='utf-8')
            with self.assertRaises(ValueError): design.choose(report, 'no title')
            design.choose(report, '# Clinic\n\nCalm teal on white.')
            self.assertEqual(visual_reviewer.inputs(report)['design'], '# Clinic\n\nCalm teal on white.\n')


class ExtendTests(unittest.TestCase):
    def test_a_feature_is_planned_into_the_checked_project_reusing_it_and_built_as_a_batch(self):
        import json
        from eaos import agent_tools, decisions, extend
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {'EAOS_HOME': str(Path(tmp) / 'home')}):
            project = Path(tmp) / 'shop'
            (project / 'src/domain').mkdir(parents=True)
            (project / 'src/domain/money.ts').write_text('export const formatMoney = (n: number) => n.toFixed(2)\n')
            (project / 'eaos.policy.json').write_text(json.dumps({'schema_version': 1, 'layers': {
                'domain': ['src/domain/**'], 'ui': ['src/ui/**']}, 'rules': [
                {'allow_only': {'from': 'domain', 'to': []}, 'reason': 'rules are pure'}]}))
            subprocess.run(['git', 'init', '-q', str(project)], check=True)
            state = agent_tools.project_state(str(project))
            report = guided.report_of(state)
            (report / 'studio').mkdir(parents=True)
            (report / 'plan.json').write_text(json.dumps({'tasks': [], 'milestones': []}))
            (report / 'studio/functions.json').write_text(json.dumps({'functions': [
                {'id': 'src/domain/money.ts#formatMoney', 'name': 'formatMoney', 'module': 'src/domain/money.ts', 'kind': 'function'}]}))
            started = extend.extend_start(state, report, text='Show the cart total on every page.')
            self.assertEqual(started['project']['functions'][0]['id'], 'src/domain/money.ts#formatMoney')
            feature = {'id': 'F1', 'name': 'Cart total', 'module': 'cart', 'acceptance': ['the total shows on every page'],
                       'paths': ['src/ui/total.tsx', 'web/total.tsx'], 'functions': ['formatMoney'], 'reuses': ['src/x.ts#nope']}
            wanted = spec(modules=[{'id': 'cart', 'name': 'Cart', 'responsibility': 'what is bought'}], entities=[], roles=[],
                          flows=[{'id': 'FL1', 'name': 'Buy', 'features': ['F1']}], features=[feature], look=None)
            problems = '\n'.join(extend.extend_plan(state, report, wanted)['problems'])
            for expected in ('web/total.tsx is in no layer', 'formatMoney already exists', 'src/x.ts#nope is not a function'):
                self.assertIn(expected, problems)
            feature.update(paths=['src/domain/total.ts'], functions=['cartTotal'], reuses=[], tests=['src/domain/total.test.ts'])
            planned = extend.extend_plan(state, report, wanted)
            self.assertEqual(planned['status'], 'planned', planned)
            cards = json.loads((report / 'plan.json').read_text())['tasks']
            self.assertEqual([(c['id'], c['milestone'], decisions.ready(c)) for c in cards], [('EXT-001', 'X01', True)])
            (report / 'plan.json').write_text(json.dumps({'tasks': [], 'milestones': []}))     # a new check
            self.assertEqual(extend.carry(project, report), 1, 'a card not built yet is kept by the next check')

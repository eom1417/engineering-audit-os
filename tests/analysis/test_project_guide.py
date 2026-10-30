"""A project's extension guide (M18.3): its recipes come from how the project really grew, and only what the project has
gets one; written between EAOS's markers with one pointer line in the context files, what the person wrote stays."""
import json
import subprocess
from pathlib import Path
from unittest import mock

from shared_fixture import Workspace

from eaos.analysis.repair import moves, project_guide
from eaos.analysis.understanding import extending
from eaos.facts.code.history import additions
from eaos.facts.repository import craft
from eaos.facts.repository.catalog import limits


def git(root, *argv):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=t', '-c', 'user.email=t@t', *argv], check=True, capture_output=True, text=True).stdout


LAYERS = {'layers': [{'name': 'ui', 'role': 'screen', 'allowed': ['data'], 'files': 2}, {'name': 'data', 'role': 'data', 'allowed': [], 'files': 1}],
          'map': [{'path': 'src/pages/Home.tsx', 'layer': 'ui', 'side': 'browser'}, {'path': 'src/pages/About.tsx', 'layer': 'ui', 'side': 'browser'},
                  {'path': 'src/data/client.ts', 'layer': 'data', 'side': 'server'}, {'path': 'src/router.tsx', 'layer': 'ui', 'side': 'browser'}],
          'gaps': [], 'endpoints': []}


class ProjectGuideTests(Workspace):
    def repo(self):
        root = Path(self.tmp) / 'shop'
        root.mkdir()
        git(root, 'init', '-q', '-b', 'main')
        self.commit(root, {'src/router.tsx': 'r1', 'src/data/client.ts': 'c', 'package.json': json.dumps({'scripts': {'lint': 'x', 'test': 'y'}})}, 'start')
        self.commit(root, {'src/pages/Home.tsx': 'h', 'src/router.tsx': 'r2', 'src/pages/Home.test.tsx': 't'}, 'home page')
        self.commit(root, {'src/pages/About.tsx': 'a', 'src/router.tsx': 'r3', 'README.md': 'x'}, 'about page')
        (Path(self.tmp) / 'report').mkdir()
        (Path(self.tmp) / 'report' / 'layers.json').write_text(json.dumps(LAYERS), encoding='utf-8')
        return root

    def commit(self, root, files, message):
        for name, text in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text, encoding='utf-8')
        git(root, 'add', '-A')
        git(root, 'commit', '-qm', message)

    def drawn(self, root):
        return project_guide.drawn_from_report(root, Path(self.tmp) / 'report')

    def test_a_recipe_comes_from_the_commits_that_added_one_and_a_kind_the_project_lacks_gets_none(self):
        drawn = self.drawn(self.repo())
        page = next(r for r in drawn['recipes'] if r['id'] == 'page')
        self.assertEqual(page['example'], 'src/pages/About.tsx')
        self.assertIn('src/router.tsx', page['touch'])
        self.assertNotIn('README.md', page['touch'])
        self.assertEqual(page['test'], 'src/pages/Home.test.tsx')
        self.assertEqual(drawn['checks'], ['npm run lint', 'npm run test'])
        self.assertIn('A background job', drawn['missing'])
        self.assertFalse(any(r['id'] == 'job' for r in drawn['recipes']))

    def test_what_wires_a_kind_in_comes_from_the_imports_when_the_history_is_one_mass_commit(self):
        root = Path(self.tmp) / 'one'
        root.mkdir()
        git(root, 'init', '-q', '-b', 'main')
        self.commit(root, {'src/App.tsx': 'a', 'src/pages/A.tsx': 'a', 'src/pages/B.tsx': 'b', **{f'x/{n}.ts': 'x' for n in range(60)}}, 'all at once')
        report = Path(self.tmp) / 'report'
        (report / 'facts').mkdir(parents=True)
        (report / 'facts/graph.json').write_text(json.dumps({'facts': [{'kind': 'module', 'location': {'path': 'src/App.tsx'}, 'value': {'depends_on': ['src/pages/A.tsx', 'src/pages/B.tsx']}}]}))
        (report / 'layers.json').write_text(json.dumps(LAYERS))
        page = next(r for r in project_guide.drawn_from_report(root, report)['recipes'] if r['id'] == 'page')
        self.assertIsNone(page['commit'])
        self.assertIn('src/App.tsx', page['touch'])

    def test_a_file_that_changes_with_anything_is_no_sign_of_a_kind(self):
        root = self.repo()
        for n in range(12): self.commit(root, {'src/hub.ts': str(n)}, f'work {n}')
        self.commit(root, {'src/pages/C.tsx': 'c', 'src/router.tsx': 'r9', 'src/hub.ts': 'hub'}, 'a page')
        (Path(self.tmp) / 'report' / 'layers.json').write_text(json.dumps(LAYERS))
        page = next(r for r in self.drawn(root)['recipes'] if r['id'] == 'page')
        self.assertIn('src/router.tsx', page['touch'])
        self.assertNotIn('src/hub.ts', page['touch'])

    def test_a_mass_commit_says_nothing_of_what_changes_together(self):
        root = self.repo()
        self.commit(root, {f'src/mass/{n}.ts': 'x' for n in range(60)}, 'mass')
        self.assertFalse(any('src/mass/0.ts' in commit['changed'] for commit in additions(root)))

    def test_written_with_one_pointer_line_again_and_again_the_same_and_what_the_person_wrote_stays(self):
        root = self.repo()
        self.commit(root, {'AGENTS.md': '# Ours\n'}, 'context')
        written = project_guide.write(root, self.drawn(root))
        self.assertEqual(sorted(written), ['AGENTS.md', 'docs/EXTENDING.md'])
        agents = (root / 'AGENTS.md').read_text(encoding='utf-8')
        self.assertEqual(agents.count('docs/EXTENDING.md'), 1)
        self.assertNotIn('## Recipes', agents)
        with (root / 'docs/EXTENDING.md').open('a', encoding='utf-8') as guide: guide.write('My own note.\n')
        git(root, 'add', '-A')
        git(root, 'commit', '-qm', 'guide')
        self.assertEqual(project_guide.write(root, self.drawn(root)), [])
        self.assertIn('My own note.', (root / 'docs/EXTENDING.md').read_text(encoding='utf-8'))

    def test_no_context_file_makes_agents_and_a_claude_that_reads_it(self):
        root = self.repo()
        project_guide.write(root, self.drawn(root))
        self.assertEqual((root / 'CLAUDE.md').read_text(encoding='utf-8'), '@AGENTS.md\n')
        self.assertIn(project_guide.POINTER_BEGIN, (root / 'AGENTS.md').read_text(encoding='utf-8'))

    def test_a_moved_home_is_followed_and_a_gone_file_is_a_stale_path(self):
        root = self.repo()
        project_guide.write(root, self.drawn(root))
        git(root, 'add', '-A')
        git(root, 'commit', '-qm', 'guide')
        moves.apply(root, [{'from': 'src/router.tsx', 'to': 'src/core/router.tsx'}])
        text = (root / 'docs/EXTENDING.md').read_text(encoding='utf-8')
        self.assertIn('`src/core/router.tsx`', text)
        self.assertNotIn('`src/router.tsx`', text)
        gone = craft._stale_in(type('S', (), {'text': lambda self, p: '`src/pages/Gone.tsx`'})(), 'docs/EXTENDING.md', craft._tree(['src/pages/Home.tsx']))
        self.assertEqual([f['rule'] for f in gone], ['stale-doc-path'])

    def test_the_card_asks_for_a_guide_only_of_a_project_large_enough_without_one(self):
        rules = limits()
        many = [f'src/m{n}.py' for n in range(rules['guide_min_files'])]
        self.assertEqual([f['rule'] for f in craft.no_guide(many, set(many), rules)], ['no-extending-guide'])
        self.assertEqual(craft.no_guide(many[:-1], set(many), rules), [])
        self.assertEqual(craft.no_guide(many, {*many, 'docs/EXTENDING.md'}, rules), [])

    def test_a_build_is_born_with_it_and_its_milestone_proof_commits_it_only_when_nothing_holds_it_back(self):
        from eaos.journeys.build_from_plan import checks
        root = self.repo()
        out = Path(self.tmp) / 'report'
        state = {'project': str(root)}
        with mock.patch('eaos.analysis.layers.check', return_value=LAYERS), mock.patch.object(checks, '_milestone_tidy', return_value=[]), \
                mock.patch.object(project_guide, 'pinned_ids', return_value=[]):
            checks._milestone_proof(state, root, out, ('CARD-1', False), [])
            self.assertFalse((root / 'docs/EXTENDING.md').exists(), 'a card is no proof')
            self.assertEqual(checks._milestone_proof(state, root, out, (None, False), [{'gate': 'x'}]), [{'gate': 'x'}])
            self.assertFalse((root / 'docs/EXTENDING.md').exists(), 'held back')
            checks._milestone_proof(state, root, out, (None, False), [])
        self.assertIn('docs/EXTENDING.md', git(root, 'show', '--name-only', '--format=', 'HEAD'))
        self.assertEqual(git(root, 'status', '--porcelain'), '')

    def test_a_project_that_declares_its_layers_is_mapped_by_them_and_says_what_each_must_not_use(self):
        from eaos.analysis.layers import record
        root = Path(self.tmp) / 'declared'
        root.mkdir()
        (root / 'eaos.policy.json').write_text(json.dumps({'layers': {'core': ['core/**'], 'web': ['web/**']}, 'rules': [{'deny': {'from': 'core', 'to': 'web'}, 'reason': 'down only'}]}))
        layers = record._layers({'declared_policy': True, 'rows': [{'layer': 'core'}, {'layer': 'core'}, {'layer': 'web'}], 'reference': None}, root)
        self.assertEqual([(l['name'], l['files'], l['denied']) for l in layers], [('core', 2, ['web']), ('web', 1, [])])

    def test_an_endpoint_the_record_found_is_told_by_it_not_by_a_folder_called_api(self):
        root = self.repo()
        self.commit(root, {'src/api/client.ts': 'x', 'server/routes.ts': 'y'}, 'both')
        report = Path(self.tmp) / 'report'
        (report / 'layers.json').write_text(json.dumps({**LAYERS, 'endpoints': [{'path': 'server/routes.ts'}]}))
        endpoint = next(r for r in project_guide.drawn_from_report(root, report)['recipes'] if r['id'] == 'endpoint')
        self.assertEqual(endpoint['example'], 'server/routes.ts')

    def test_the_guide_has_what_a_person_needs_to_add_a_feature_from_what_the_check_read(self):
        root = self.repo()
        report = Path(self.tmp) / 'report'
        (report / 'facts').mkdir()
        (report / 'facts/graph.json').write_text(json.dumps({'facts': [{'kind': 'graph_node', 'location': {'path': 'src/data/client.ts'}, 'value': {'fan_in': 9, 'depends_on': []}}]}))
        (report / 'architecture').mkdir()
        (report / 'architecture/map.json').write_text(json.dumps({'digest': {'hotspots': [{'path': 'src/router.tsx', 'commits': 3, 'complexity': 40}],
                                                                             'clusters': [{'members': ['src/data/client.ts', 'src/data/x.ts']}]}}))
        (report / 'features.json').write_text(json.dumps({'features': [{'name': 'orders', 'surfaces': ['src/pages/Home.tsx'], 'tables': ['orders']}]}))
        (report / 'layers.json').write_text(json.dumps({**LAYERS, 'findings': [{'severity': 'high', 'en': 'A screen reads the database.'}]}))
        text = project_guide.text(project_guide.drawn_from_report(root, report), 'shop')
        for said in ('## Where new code goes', '## Reuse first', '`src/data/client.ts` (9 files use it)', '## Sensitive files', '## Features today', '| orders |',
                     '## Add a new feature', 'A feature is finished when', '**What must stay true:**', '## Known departures', 'A screen reads the database.',
                     '## The areas', '| src/data |', 'Before merging: `npm run lint`'):
            self.assertIn(said, text)

    def test_a_fix_batch_carries_the_guide_as_its_own_commit_and_only_when_it_changed(self):
        from eaos.journeys.fix.regenerate import keep_guide
        root = self.repo()
        report = Path(self.tmp) / 'report'
        with mock.patch.object(project_guide, 'pinned_ids', return_value=[]):
            self.assertTrue(keep_guide(root, report, str(root), 1))
            self.assertIn('docs/EXTENDING.md', git(root, 'show', '--name-only', '--format=', 'HEAD'))
            self.assertIsNone(keep_guide(root, report, str(root), 2))
            self.assertIsNone(keep_guide(root, Path(self.tmp) / 'no-check', str(root), 3))

    def test_the_commands_are_the_projects_own(self):
        root = Path(self.tmp)
        self.assertEqual(extending.commands(root, {'manage.py', 'go.mod'}), ['python manage.py test', 'go test ./...'])

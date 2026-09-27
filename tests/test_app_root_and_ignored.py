"""An application in app/, a Node server beside a React client, and files the project's .gitignore keeps out."""
import json
import subprocess
from pathlib import Path

from shared_fixture import Workspace

from eaos.facts.scope import declared_exclusions, exclusion_reasons, git_ignored
from eaos.reference_architecture import layer_of, locate, rooted, by_id


def write(path, text=''):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if isinstance(text, str) else json.dumps(text))


class GitIgnoredTests(Workspace):
    def test_what_gitignore_keeps_out_is_excluded_with_its_reason(self):
        root = Path(self.tmp)
        write(root / '.gitignore', 'release/\n.data/\n')
        write(root / 'app.ts', 'export const a = 1;\n')
        write(root / 'release/app.ts', 'export const a = 1;\n')   # a build copy of the same code
        write(root / '.data/dump.json', '{}')
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        self.assertEqual(git_ignored(root), ['.data', 'release'])
        self.assertIn('release', declared_exclusions(root))
        self.assertIn(".gitignore", exclusion_reasons(root)['release'])

    def test_without_git_nothing_is_excluded_on_that_ground(self):
        write(Path(self.tmp) / 'release/app.ts', 'x')
        self.assertEqual(git_ignored(self.tmp), [])


class AppRootTests(Workspace):
    def fullstack(self, root, folder=''):
        base = root / folder if folder else root
        write(base / 'package.json', {'dependencies': {'react': '19', 'pg': '8'}, 'devDependencies': {'vite': '7'}})
        (base / 'server').mkdir(parents=True, exist_ok=True)

    def test_a_react_client_with_its_own_node_server_and_database_is_the_node_api_type(self):
        root = Path(self.tmp)
        self.fullstack(root)
        self.assertEqual(locate(root), ('react-vite-node-api', ''))

    def test_an_app_kept_in_app_is_found_and_its_layers_follow_it(self):
        root = Path(self.tmp)
        self.fullstack(root, 'app')
        reference_id, prefix = locate(root)
        self.assertEqual((reference_id, prefix), ('react-vite-node-api', 'app/'))
        reference = rooted(by_id(reference_id), prefix)
        self.assertEqual(layer_of('app/server/routes/users.ts', reference)[0], 'routes')
        self.assertEqual(layer_of('app/server/infrastructure/postgres.ts', reference)[0], 'data-access')
        self.assertEqual(layer_of('app/server/infrastructure/logging.ts', reference)[0], 'infrastructure')
        self.assertEqual(layer_of('app/src/blueprint/rules.ts', reference)[0], 'engine')

    def test_a_server_folder_declares_its_own_database_driver(self):
        root = Path(self.tmp)
        write(root / 'package.json', {'dependencies': {'react': '19'}, 'devDependencies': {'vite': '7'}})
        write(root / 'server/package.json', {'dependencies': {'drizzle-orm': '0.40', 'postgres': '3'}})
        self.assertEqual(locate(root)[0], 'react-vite-node-api')

    def test_one_python_test_does_not_make_a_node_project_a_python_tool(self):
        root = Path(self.tmp)
        write(root / 'package.json', {'dependencies': {'pg': '8'}})
        write(root / 'server.mjs', 'export {}\n')
        write(root / 'tests/e2e/test_app.py', 'def test(): pass\n')
        self.assertEqual(locate(root)[0], 'generic-layered')   # not python-cli


class CatalogueCoverageTests(Workspace):
    """Every project with source gets a target: a specific type when one fits, the layered fallback otherwise."""

    def test_a_workspace_monorepo_separates_applications_from_packages(self):
        root = Path(self.tmp)
        write(root / 'pnpm-workspace.yaml', 'packages:\n  - "apps/*"\n  - "packages/*"\n')
        write(root / 'package.json', {'name': 'mono'})
        reference_id, prefix = locate(root)
        self.assertEqual(reference_id, 'workspace-monorepo')
        reference = by_id(reference_id)
        self.assertEqual(layer_of('apps/api/src/app.module.ts', reference)[0], 'server-apps')
        self.assertEqual(layer_of('apps/mobile/app/index.tsx', reference)[0], 'client-apps')
        self.assertEqual(layer_of('packages/config/index.ts', reference)[0], 'core-packages')
        layers = {layer['name']: layer for layer in reference['layers']}
        self.assertNotIn('server-apps', layers['packages']['allowed_dependencies'])
        self.assertNotIn('client-apps', layers['packages']['allowed_dependencies'])

    def test_a_project_no_specific_type_fits_still_gets_a_layered_target(self):
        root = Path(self.tmp)
        write(root / 'package.json', {'dependencies': {'pg': '8'}})
        write(root / 'src/domain/plan.ts', 'export const x = 1;\n')
        write(root / 'src/sync/queue.ts', 'export const y = 1;\n')
        reference_id, _ = locate(root)
        self.assertEqual(reference_id, 'generic-layered')
        reference = by_id(reference_id)
        self.assertEqual(layer_of('src/domain/plan.ts', reference)[0], 'domain')
        self.assertEqual(layer_of('src/sync/queue.ts', reference)[0], 'infrastructure')

    def test_a_specific_type_in_app_wins_over_the_fallback_at_the_root(self):
        root = Path(self.tmp)
        write(root / 'README.md', '# x')
        write(root / 'tools/x.ts', 'export {}\n')
        write(root / 'app/package.json', {'dependencies': {'react': '19', 'pg': '8'}, 'devDependencies': {'vite': '7'}})
        (root / 'app/server').mkdir(parents=True)
        self.assertEqual(locate(root), ('react-vite-node-api', 'app/'))

    def test_nothing_to_read_gets_no_type(self):
        write(Path(self.tmp) / 'README.md', '# only prose')
        self.assertEqual(locate(self.tmp), (None, ''))

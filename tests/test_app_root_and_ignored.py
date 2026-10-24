"""An application in app/, a Node server beside a React client, and files the project's .gitignore keeps out."""
import json
import subprocess
from pathlib import Path

from shared_fixture import Workspace

from eaos.facts.scope import declared_exclusions, exclusion_reasons, git_ignored
from eaos.analysis.reference_architecture import layer_of, locate, rooted, by_id


def write(path, text=''):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if isinstance(text, str) else json.dumps(text))


FULLSTACK = {'dependencies': {'react': '19', 'pg': '8'}, 'devDependencies': {'vite': '7'}}


class GitIgnoredTests(Workspace):
    def test_what_gitignore_keeps_out_is_excluded_with_its_reason_only_under_git(self):
        root = Path(self.tmp)
        write(root / '.gitignore', 'release/\n.data/\n')
        write(root / 'app.ts', 'export const a = 1;\n')
        write(root / 'release/app.ts', 'export const a = 1;\n')   # a build copy of the same code
        write(root / '.data/dump.json', '{}')
        self.assertEqual(git_ignored(root), [], 'without git nothing is excluded on that ground')
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        self.assertEqual(git_ignored(root), ['.data', 'release'])
        self.assertIn('release', declared_exclusions(root))
        self.assertIn('.gitignore', exclusion_reasons(root)['release'])


class AppRootTests(Workspace):
    def test_a_react_client_with_its_own_node_server_is_the_node_api_type_at_the_root_or_in_app(self):
        root = Path(self.tmp)
        write(root / 'one/package.json', FULLSTACK); (root / 'one/server').mkdir()
        self.assertEqual(locate(root / 'one'), ('react-vite-node-api', ''))
        # A server folder may declare its own database driver.
        write(root / 'two/package.json', {'dependencies': {'react': '19'}, 'devDependencies': {'vite': '7'}})
        write(root / 'two/server/package.json', {'dependencies': {'drizzle-orm': '0.40', 'postgres': '3'}})
        self.assertEqual(locate(root / 'two')[0], 'react-vite-node-api')
        # A specific type in app/ wins over the layered fallback at the root, and the layers follow it.
        write(root / 'three/README.md', '# x')
        write(root / 'three/tools/x.ts', 'export {}\n')
        write(root / 'three/app/package.json', FULLSTACK); (root / 'three/app/server').mkdir()
        reference_id, prefix = locate(root / 'three')
        self.assertEqual((reference_id, prefix), ('react-vite-node-api', 'app/'))
        reference = rooted(by_id(reference_id), prefix)
        for path, layer in [('app/server/routes/users.ts', 'routes'), ('app/server/infrastructure/postgres.ts', 'data-access'),
                            ('app/server/infrastructure/logging.ts', 'infrastructure'), ('app/src/blueprint/rules.ts', 'engine')]:
            self.assertEqual(layer_of(path, reference)[0], layer, path)

    def test_a_project_no_specific_type_fits_gets_the_layered_fallback_and_prose_gets_none(self):
        root = Path(self.tmp)
        write(root / 'node/package.json', {'dependencies': {'pg': '8'}})
        write(root / 'node/server.mjs', 'export {}\n')
        write(root / 'node/src/domain/plan.ts', 'export const x = 1;\n')
        write(root / 'node/src/sync/queue.ts', 'export const y = 1;\n')
        write(root / 'node/tests/e2e/test_app.py', 'def test(): pass\n')   # one python test: not a python tool
        reference_id, _ = locate(root / 'node')
        self.assertEqual(reference_id, 'generic-layered')
        reference = by_id(reference_id)
        self.assertEqual(layer_of('src/domain/plan.ts', reference)[0], 'domain')
        self.assertEqual(layer_of('src/sync/queue.ts', reference)[0], 'infrastructure')
        write(root / 'prose/README.md', '# only prose')
        self.assertEqual(locate(root / 'prose'), (None, ''))

    def test_a_workspace_monorepo_separates_applications_from_packages(self):
        root = Path(self.tmp)
        write(root / 'pnpm-workspace.yaml', 'packages:\n  - "apps/*"\n  - "packages/*"\n')
        write(root / 'package.json', {'name': 'mono'})
        reference_id, _ = locate(root)
        self.assertEqual(reference_id, 'workspace-monorepo')
        reference = by_id(reference_id)
        self.assertEqual(layer_of('apps/api/src/app.module.ts', reference)[0], 'server-apps')
        self.assertEqual(layer_of('apps/mobile/app/index.tsx', reference)[0], 'client-apps')
        self.assertEqual(layer_of('packages/config/index.ts', reference)[0], 'core-packages')
        layers = {layer['name']: layer for layer in reference['layers']}
        self.assertNotIn('server-apps', layers['packages']['allowed_dependencies'])
        self.assertNotIn('client-apps', layers['packages']['allowed_dependencies'])

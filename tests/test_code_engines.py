"""The code-understanding engines: ast-grep, Lizard, knip and react-docgen.

tests/fixtures/code_engines plants one thing each engine must find: a tangled Python function (`tariff`),
an unused helper and import, a React component reached only through an `@/` alias (`VehicleCard`), one no
file imports (`Orphan`), an unused export, an unused dependency (`left-pad`) and a `useEffect` that only
copies state. Each engine's real output on that project is pinned in tests/contracts/<engine>.json and fed
through its adapter offline; where the pinned tool is installed, the adapter also runs it for real.
"""
import json
from pathlib import Path
from unittest import mock

from shared_fixture import Workspace

from eaos.engines import ADAPTERS, ast_grep, knip, lizard, react_docgen, tool
from eaos.engines.contract import KINDS, OBSERVED, UNAVAILABLE
from eaos.engines.process import run, which

CONTRACTS = Path(__file__).resolve().parent / 'contracts'
FIXTURE = Path(__file__).resolve().parent / 'fixtures/code_engines'
ENGINES = {'ast-grep': ast_grep, 'lizard': lizard, 'knip': knip, 'react-docgen': react_docgen}


def sample(name):
    return json.loads((CONTRACTS / f'{name}.json').read_text(encoding='utf-8'))


def installed(module):
    return module.version() == module.PINNED


def rules_of(report):
    return {(item['rule'], item['subject']['path'], item['subject']['key']) for item in report.findings}


class EveryEngineTests(Workspace):
    def test_each_is_registered_pinned_sampled_and_a_missing_tool_is_unavailable_never_raised(self):
        for name, module in ENGINES.items():
            self.assertIs(ADAPTERS[name], module)
            self.assertEqual(module.PINNED, tool.pinned(name))
            self.assertEqual(sample(name)['pinned_version'], module.PINNED, name)
            for capability in module.capabilities(): self.assertIn(capability.kind, KINDS)
        with mock.patch.object(tool, 'which', return_value=None):
            for name, module in ENGINES.items():
                self.assertIsNone(module.version(), name)
                report = module.analyze(FIXTURE, Path(self.tmp) / 'work')
                self.assertEqual(report.status, UNAVAILABLE, name)
                self.assertIn(f'--only {name}', report.reason)
                self.assertEqual((report.findings, report.metrics), ([], []))
        # An adapter reads its own version when the binary prints none.
        with mock.patch.object(tool, 'version', return_value=None), \
                mock.patch('eaos.toolchain.applies', return_value=(True, 'react')):
            self.assertIsNone(tool.declined('react-docgen', 'react-docgen', self.tmp, probe=lambda: '3.0.7'))
            self.assertEqual(tool.declined('react-docgen', 'react-docgen', self.tmp, probe=lambda: None).status, UNAVAILABLE)

    def test_an_exclusion_matches_whole_segments_below_the_target_never_the_folders_it_sits_in(self):
        self.assertTrue(tool.excluded('src/components/ui/button.tsx', ['components/ui']))
        self.assertTrue(tool.excluded('dist/app.js', ['dist']))
        self.assertFalse(tool.excluded('src/components/uikit/x.tsx', ['components/ui']))
        self.assertFalse(tool.excluded('build_trial.py', ['build']))
        root = Path(self.tmp) / 'build' / 'proj[1]'
        root.mkdir(parents=True)
        for path in ('src/components/ui/Button.tsx', 'src/pages/Home.tsx'):
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_text('export const A = () => <div/>;\n')
        self.assertEqual(react_docgen.sources(root, ('components/ui',)), (['src/pages/Home.tsx'], []))


class OfflineAdapterTests(Workspace):
    """Each engine's pinned output fed through its adapter, with no engine installed."""

    def test_ast_grep_records_components_and_derived_state_effects_and_every_rule_has_examples(self):
        rows = sample('ast-grep')['ast-grep.jsonl']
        metrics, findings, by_rule = ast_grep.normalise(rows, ast_grep.PINNED)
        self.assertEqual(findings, [])
        components = {(m['path'], m['symbol']) for m in metrics if m['measurements']['record'] == 'react_component'}
        self.assertEqual(components, {('src/main.tsx', 'App'), ('src/components/VehicleCard.tsx', 'VehicleCard'),
                                      ('src/components/Orphan.tsx', 'Orphan')})
        effect = next(m for m in metrics if m['measurements']['record'] == 'react_effect_derived_state')
        self.assertEqual((effect['path'], effect['line'], effect['symbol']), ('src/components/VehicleCard.tsx', 8, 'setLabel'))
        self.assertEqual(sum(by_rule.values()), len(rows))
        # A rule naming a shared kind becomes a finding.
        metrics, findings, _ = ast_grep.normalise([dict(rows[0], metadata={'kind': 'dead_code'})], ast_grep.PINNED)
        self.assertEqual((len(metrics), [f['kind'] for f in findings]), (0, ['dead_code']))
        tests = ''.join(p.read_text(encoding='utf-8') for p in (ast_grep.RULES / 'rule-tests').glob('*.yml'))
        for rule, _ in ast_grep.rules(): self.assertIn(f'id: {rule}\n', tests)

    def test_lizard_measures_every_function_and_only_the_tangled_one_is_a_finding(self):
        parsed, skipped = lizard.rows(sample('lizard')['lizard.csv'] + 'a,short,row\n')
        self.assertEqual(skipped, 1)
        metrics, findings = lizard.normalise(parsed, lizard.PINNED)
        self.assertTrue({('billing.py', 'unused_helper'), ('src/lib/format.ts', 'plate')} <= {(m['path'], m['symbol']) for m in metrics})
        self.assertEqual(rules_of(type('R', (), {'findings': findings})), {('ccn', 'billing.py', 'billing.py::tariff')})
        self.assertEqual(findings[0]['measurements'][0], {'name': 'cyclomatic_complexity', 'value': 22, 'threshold': 15, 'unit': None})
        with mock.patch.object(lizard.tool, 'declined', return_value=None), mock.patch.object(lizard, 'version', return_value=lizard.PINNED), \
                mock.patch.object(lizard, 'which', return_value='lizard'), \
                mock.patch.object(lizard, 'run', return_value=(0, sample('lizard')['lizard.csv'], '', 0.1)):
            report = lizard.analyze(self.tmp, Path(self.tmp) / 'work')
        self.assertEqual((report.status, report.coverage['over_threshold']), (OBSERVED, 1))
        self.assertFalse([m for m in report.metrics if m['path'].startswith(('.', '/'))], 'paths are relative')

    def test_knip_reports_unused_files_exports_and_dependencies_with_every_plugin_off(self):
        findings, counted = knip.normalise(sample('knip')['knip.json'], knip.PINNED)
        self.assertEqual(rules_of(type('R', (), {'findings': findings})), KNIP_EXPECTED)
        self.assertEqual(({f['kind'] for f in findings}, counted), ({'dead_code', 'unused_dependency'}, {}))
        report = {'issues': [{'file': 'package.json', 'devDependencies': [{'name': 'vitest'}], 'unlisted': [{'name': 'x'}]}]}
        self.assertEqual(knip.normalise(report, knip.PINNED), ([], {'devDependencies': 1, 'unlisted': 1}),
                         'dev dependencies are counted, not reported')
        # Every plugin is switched off so no project configuration runs; without its plugin list it refuses to run.
        config = knip.configuration(['vite', 'eslint'], exclude=('legacy',))
        self.assertEqual((config['vite'], config['eslint']), (False, False))
        self.assertIn('**/legacy/**', config['ignore'])
        with mock.patch.object(knip.tool, 'declined', return_value=None), mock.patch.object(knip, 'version', return_value=knip.PINNED), \
                mock.patch.object(knip, 'which', return_value='/nowhere/bin/knip'), mock.patch.object(knip, 'run') as ran:
            self.assertEqual(knip.analyze(self.tmp, Path(self.tmp) / 'work').status, 'error')
        ran.assert_not_called()

    def test_react_docgen_records_props_and_isolates_a_failing_file(self):
        rows = {row['symbol']: row['measurements'] for row in react_docgen.records(sample('react-docgen')['react-docgen.json'])}
        self.assertEqual(set(rows), {'App', 'VehicleCard', 'Orphan'})
        self.assertEqual(rows['VehicleCard']['props'], [{'name': 'compact', 'type': 'boolean', 'required': False},
                                                        {'name': 'vehicle', 'type': 'Vehicle', 'required': True}])
        self.assertEqual(rows['VehicleCard']['referenced_types'], ['Vehicle'])
        self.assertEqual(rows['App']['prop_count'], 0)
        parsed = sample('react-docgen')['react-docgen.json']
        def fake_run(command, **_):
            files = command[command.index('find-all-exported-components') + 1:]
            if 'src/main.tsx' in files: return 1, '', 'SyntaxError', 0.1
            Path(command[command.index('--out') + 1]).write_text(json.dumps({f: parsed[f] for f in files}))
            return 0, '', '', 0.1
        with mock.patch.object(react_docgen.tool, 'declined', return_value=None), \
                mock.patch.object(react_docgen, 'version', return_value=react_docgen.PINNED), \
                mock.patch.object(react_docgen, 'which', return_value='react-docgen'), mock.patch.object(react_docgen, 'run', fake_run):
            report = react_docgen.analyze(FIXTURE / 'web', Path(self.tmp) / 'work')
        self.assertEqual((report.status, report.coverage['unparsed_files']), (OBSERVED, ['src/main.tsx']))
        self.assertEqual({m['symbol'] for m in report.metrics}, {'VehicleCard', 'Orphan'})
        self.assertEqual(react_docgen.GLOB_SPECIAL.sub(r'\\\1', 'app/(auth)/[id]/page.tsx'), r'app/\(auth\)/\[id\]/page.tsx')


KNIP_EXPECTED = {('files', 'src/components/Orphan.tsx', 'src/components/Orphan.tsx'),
                 ('exports', 'src/lib/format.ts', 'src/lib/format.ts:unusedFormat'),
                 ('dependencies', 'package.json', 'left-pad')}


class LiveRunTests(Workspace):
    """Where the pinned tool is installed, the adapter runs it for real on the planted fixture."""

    def test_each_installed_engine_finds_what_was_planted(self):
        work = lambda name: Path(self.tmp) / name
        with self.subTest(engine='ast-grep'):
            if not installed(ast_grep): self.skipTest('ast-grep is not installed at its pin')
            code, out, error, _ = run([which('ast-grep'), 'test', '--config', str(ast_grep.RULES / 'sgconfig.yml'),
                                       '--skip-snapshot-tests'], cwd=ast_grep.RULES)
            self.assertEqual(code, 0, out + error)
            report = ast_grep.analyze(FIXTURE / 'web', work('ast'))
            self.assertEqual(report.status, OBSERVED, report.reason)
            self.assertEqual(report.metrics, ast_grep.normalise(sample('ast-grep')['ast-grep.jsonl'], ast_grep.PINNED)[0])
        with self.subTest(engine='lizard'):
            if not installed(lizard): self.skipTest('lizard is not installed at its pin')
            self.assertEqual(rules_of(lizard.analyze(FIXTURE / 'py', work('lizard'))), {('ccn', 'billing.py', 'billing.py::tariff')})
        with self.subTest(engine='knip'):
            if not installed(knip): self.skipTest('knip is not installed at its pin')
            # VehicleCard is imported only as `@/components/VehicleCard`: were the alias not resolved it would be unused.
            report = knip.analyze(FIXTURE / 'web', work('knip'))
            self.assertEqual(report.status, OBSERVED, report.reason)
            self.assertEqual(rules_of(report), KNIP_EXPECTED)
        with self.subTest(engine='react-docgen'):
            if not installed(react_docgen): self.skipTest('react-docgen is not installed at its pin')
            report = react_docgen.analyze(FIXTURE / 'web', work('docgen'))
            self.assertEqual(report.status, OBSERVED, report.reason)
            self.assertEqual(report.metrics, react_docgen.records(sample('react-docgen')['react-docgen.json']))

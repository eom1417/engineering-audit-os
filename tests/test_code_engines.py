"""The code-understanding engines: ast-grep, Lizard, complexipy, vulture, knip and react-docgen.

tests/fixtures/code_engines plants one thing each engine must find: a tangled Python function (`tariff`),
an unused helper and import, a React component reached only through an `@/` alias (`VehicleCard`), one no
file imports (`Orphan`), an unused export, an unused dependency (`left-pad`) and a `useEffect` that only
copies state. Each engine's real output on that project is pinned in tests/contracts/<engine>.json and fed
through its adapter offline; where the pinned tool is installed, the adapter also runs it for real.
"""
import json
import re
import unittest
from pathlib import Path
from unittest import mock

from shared_fixture import Workspace

from eaos.engines import ADAPTERS, ast_grep, complexipy, knip, lizard, react_docgen, tool, vulture
from eaos.engines.contract import KINDS, NOT_APPLICABLE, OBSERVED, UNAVAILABLE
from eaos.engines.process import run, which

CONTRACTS = Path(__file__).resolve().parent / 'contracts'
FIXTURE = Path(__file__).resolve().parent / 'fixtures/code_engines'
ENGINES = {'ast-grep': ast_grep, 'lizard': lizard, 'complexipy': complexipy, 'vulture': vulture, 'knip': knip,
           'react-docgen': react_docgen}


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
        with mock.patch.object(tool, 'which', return_value='vulture'), \
                mock.patch.object(tool, 'run', return_value=(0, 'vulture 2.16\n', '', 0.1)):
            self.assertEqual(vulture.version(), '2.16', 'a two-part version is read')

    def test_an_exclusion_matches_whole_segments_below_the_target_never_the_folders_it_sits_in(self):
        self.assertTrue(tool.excluded('src/components/ui/button.tsx', ['components/ui']))
        self.assertTrue(tool.excluded('dist/app.js', ['dist']))
        self.assertFalse(tool.excluded('src/components/uikit/x.tsx', ['components/ui']))
        self.assertFalse(tool.excluded('build_trial.py', ['build']))
        root = Path(self.tmp) / 'build' / 'proj[1]'
        root.mkdir(parents=True)
        patterns = vulture.exclusions(root, ('components/ui',)).split(',')
        anchor = str(root.resolve()).replace('[1]', '[[]1[]]')
        self.assertTrue(all(p.startswith(anchor + '/') for p in patterns))
        from fnmatch import fnmatch
        self.assertFalse(any(fnmatch(str(root.resolve() / 'app.py'), p) for p in patterns))
        self.assertTrue(any(fnmatch(str(root.resolve() / 'src/components/ui/a.py'), p) for p in patterns))
        self.assertTrue(any(fnmatch(str(root.resolve() / 'build/a.py'), p) for p in patterns))
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

    def test_complexipy_reads_its_output_file_names_unparsed_files_and_no_output_is_an_error(self):
        def fake_run(command, cwd=None, **_):
            Path(command[command.index('--output') + 1]).write_text(json.dumps(sample('complexipy')['complexipy.json']))
            return 1, f'\x1b[31merror\x1b[0m: Failed to process \x1b[37m{cwd}/legacy/broken.py\x1b[0m - Please check file/folder exists or check syntax', '', 0.1
        def analyze(run):
            with mock.patch.object(complexipy.tool, 'declined', return_value=None), \
                    mock.patch.object(complexipy, 'version', return_value=complexipy.PINNED), \
                    mock.patch.object(complexipy, 'which', return_value='complexipy'), mock.patch.object(complexipy, 'run', run):
                return complexipy.analyze(self.tmp, Path(self.tmp) / 'work')
        report = analyze(fake_run)
        self.assertEqual((report.status, report.coverage['unparsed_files']), (OBSERVED, ['legacy/broken.py']))
        self.assertEqual({m['symbol']: m['measurements']['cognitive_complexity'] for m in report.metrics},
                         {'tariff': 25, 'total': 1, 'unused_helper': 0})
        self.assertEqual(rules_of(report), {('cognitive', 'billing.py', 'billing.py::tariff')})
        self.assertEqual(analyze(mock.Mock(return_value=(2, '', 'boom', 0.1))).status, 'error')

    def test_vulture_lines_become_dead_code_findings_and_variables_and_tests_are_only_counted(self):
        rows = vulture.candidates(sample('vulture')['vulture.txt'] + 'not a vulture line\n')
        self.assertEqual(len(rows), 3)
        findings, by_type, in_tests, _ = vulture.normalise(rows, vulture.PINNED)
        self.assertEqual((by_type, in_tests), ({'function': 2, 'import': 1}, 0))
        messages = sorted(f['message'] for f in findings)
        self.assertIn('unused import `os` (90% confidence)', messages)
        self.assertTrue(all(re.search(r'`\w+`', m) for m in messages))
        self.assertEqual({f['engine_confidence'] for f in findings}, {0.9, 0.6})
        rows = vulture.candidates("app.py:3: unused variable 'x' (60% confidence)\n"
                                  "tests/test_app.py:9: unused function 'test_it' (60% confidence)\n")
        self.assertEqual(vulture.normalise(rows, vulture.PINNED)[:3], ([], {'function': 1, 'variable': 1}, 1))

    FRAMEWORK = (
        'import html.parser\n'
        'from urllib.request import HTTPRedirectHandler\n\n\n'
        'def build(server):\n'
        '    @server.prompt(name="audit")\n'
        '    def audit_prompt():\n'
        '        return "audit"\n'
        '    return server\n\n\n'
        'class Reader(html.parser.HTMLParser):\n'
        '    def handle_starttag(self, tag, attrs):\n'
        '        pass\n\n'
        '    def forgotten(self):\n'
        '        pass\n\n\n'
        'class NoRedirect(HTTPRedirectHandler):\n'
        '    def redirect_request(self, *args):\n'
        '        return None\n\n\n'
        '@property\n'
        'def lonely():\n'
        '    return 1\n')

    def test_what_a_framework_calls_is_not_reported_as_dead_and_an_unreadable_file_keeps_its_candidates(self):
        root = Path(self.tmp)
        (root / 'app.py').write_text(self.FRAMEWORK)
        rows = vulture.candidates("app.py:6: unused function 'audit_prompt' (60% confidence)\n"
                                  "app.py:13: unused method 'handle_starttag' (60% confidence)\n"
                                  "app.py:16: unused method 'forgotten' (60% confidence)\n"
                                  "app.py:21: unused method 'redirect_request' (60% confidence)\n"
                                  "app.py:25: unused function 'lonely' (60% confidence)\n")
        findings, _, _, framework = vulture.normalise(rows, vulture.PINNED, root)
        self.assertEqual(framework, ['app.py:6:audit_prompt', 'app.py:13:handle_starttag', 'app.py:21:redirect_request'])
        self.assertEqual(sorted(f['message'].split('`')[1] for f in findings), ['forgotten', 'lonely'])
        (root / 'broken.py').write_text('@app.route("/")\ndef index(:\n')
        rows = vulture.candidates("broken.py:1: unused function 'index' (60% confidence)\n"
                                  "missing.py:1: unused function 'gone' (60% confidence)\n")
        findings, _, _, framework = vulture.normalise(rows, vulture.PINNED, root)
        self.assertEqual((len(findings), framework), (2, []))

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
        with self.subTest(engine='complexipy'):
            if not installed(complexipy): self.skipTest('complexipy is not installed at its pin')
            self.assertEqual(complexipy.analyze(FIXTURE / 'web', work('c1')).status, NOT_APPLICABLE)
            self.assertEqual(rules_of(complexipy.analyze(FIXTURE / 'py', work('c2'))), {('cognitive', 'billing.py', 'billing.py::tariff')})
            project = work('project'); project.mkdir()
            (project / 'ok.py').write_text('def ok():\n    return 1\n')
            (project / 'broken.py').write_text('def broken(:\n')
            report = complexipy.analyze(project, work('c3'))
            self.assertEqual((report.coverage['unparsed_files'], [m['symbol'] for m in report.metrics]), (['broken.py'], ['ok']))
        with self.subTest(engine='vulture'):
            if not installed(vulture): self.skipTest('vulture is not installed at its pin')
            self.assertTrue({('unused_import', 'billing.py', 'billing.py:os'),
                             ('unused_function', 'billing.py', 'billing.py:unused_helper')}
                            <= rules_of(vulture.analyze(FIXTURE / 'py', work('v1'))))
            # A project that lives under an excluded name is kept; its own excluded folder is not.
            root = work('build') / 'proj'
            (root / 'fixtures').mkdir(parents=True)
            (root / 'billing.py').write_text((FIXTURE / 'py/billing.py').read_text(encoding='utf-8'))
            (root / 'fixtures/sample.py').write_text('import os\n\n\ndef sample():\n    return 1\n')
            report = vulture.analyze(root, work('v2'), exclude=('fixtures',))
            self.assertIn(('unused_import', 'billing.py', 'billing.py:os'), rules_of(report))
            self.assertFalse(any(f['subject']['path'].startswith('fixtures/') for f in report.findings))
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

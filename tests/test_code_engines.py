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
    def test_each_is_registered_pinned_and_sampled_at_its_pin(self):
        for name, module in ENGINES.items():
            self.assertIs(ADAPTERS[name], module)
            self.assertEqual(module.PINNED, tool.pinned(name))
            self.assertEqual(sample(name)['pinned_version'], module.PINNED, name)
            for capability in module.capabilities(): self.assertIn(capability.kind, KINDS)

    def test_an_adapter_reads_its_own_version_when_the_binary_prints_none(self):
        with mock.patch.object(tool, 'version', return_value=None), \
                mock.patch('eaos.toolchain.applies', return_value=(True, 'react')):
            self.assertIsNone(tool.declined('react-docgen', 'react-docgen', self.tmp, probe=lambda: '3.0.7'))
            self.assertEqual(tool.declined('react-docgen', 'react-docgen', self.tmp, probe=lambda: None).status, UNAVAILABLE)

    def test_a_missing_tool_is_reported_unavailable_with_its_install_command_never_raised(self):
        with mock.patch.object(tool, 'which', return_value=None):
            for name, module in ENGINES.items():
                self.assertIsNone(module.version(), name)
                report = module.analyze(FIXTURE, Path(self.tmp) / 'work')
                self.assertEqual(report.status, UNAVAILABLE, name)
                self.assertIn(f'--only {name}', report.reason)
                self.assertEqual((report.findings, report.metrics), ([], []))


class ExclusionTests(Workspace):
    """An exclusion is a directory name or a relative path, matched at any depth below the target and never
    against the folders the target itself sits in (a project under `build/` or `.claude/worktrees/`)."""

    def test_a_relative_path_entry_matches_at_any_depth_and_only_whole_segments(self):
        self.assertTrue(tool.excluded('src/components/ui/button.tsx', ['components/ui']))
        self.assertTrue(tool.excluded('dist/app.js', ['dist']))
        self.assertFalse(tool.excluded('src/components/uikit/x.tsx', ['components/ui']))
        self.assertFalse(tool.excluded('build_trial.py', ['build']))

    def test_vulture_patterns_are_anchored_at_the_target(self):
        root = Path(self.tmp) / 'build' / 'proj[1]'
        root.mkdir(parents=True)
        patterns = vulture.exclusions(root, ('components/ui',)).split(',')
        anchor = str(root.resolve()).replace('[1]', '[[]1[]]')
        self.assertTrue(all(p.startswith(anchor + '/') for p in patterns))
        from fnmatch import fnmatch
        inside = str(root.resolve() / 'app.py')
        self.assertFalse(any(fnmatch(inside, p) for p in patterns))
        self.assertTrue(any(fnmatch(str(root.resolve() / 'src/components/ui/a.py'), p) for p in patterns))
        self.assertTrue(any(fnmatch(str(root.resolve() / 'build/a.py'), p) for p in patterns))

    def test_react_docgen_skips_a_relative_path_entry(self):
        root = Path(self.tmp)
        for path in ('src/components/ui/Button.tsx', 'src/pages/Home.tsx'):
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_text('export const A = () => <div/>;\n')
        self.assertEqual(react_docgen.sources(root, ('components/ui',)), (['src/pages/Home.tsx'], []))

    @unittest.skipUnless(installed(vulture) and installed(complexipy), 'vulture and complexipy are not installed at their pins')
    def test_live_runs_keep_a_project_that_lives_under_an_excluded_name(self):
        root = Path(self.tmp) / 'build' / 'proj'
        (root / 'fixtures').mkdir(parents=True)
        (root / 'billing.py').write_text((FIXTURE / 'py/billing.py').read_text(encoding='utf-8'))
        (root / 'fixtures/sample.py').write_text('import os\n\n\ndef sample():\n    return 1\n')
        report = vulture.analyze(root, Path(self.tmp) / 'v', exclude=('fixtures',))
        self.assertIn(('unused_import', 'billing.py', 'billing.py:os'), rules_of(report))
        self.assertFalse(any(f['subject']['path'].startswith('fixtures/') for f in report.findings))
        measured = complexipy.analyze(root, Path(self.tmp) / 'c', exclude=('fixtures',))
        self.assertEqual({m['path'] for m in measured.metrics}, {'billing.py'})


class AstGrepTests(Workspace):
    def test_records_components_by_their_binding_name_and_derived_state_effects(self):
        rows = sample('ast-grep')['ast-grep.jsonl']
        metrics, findings, by_rule = ast_grep.normalise(rows, ast_grep.PINNED)
        self.assertEqual(findings, [])
        components = {(m['path'], m['symbol']) for m in metrics if m['measurements']['record'] == 'react_component'}
        self.assertEqual(components, {('src/main.tsx', 'App'), ('src/components/VehicleCard.tsx', 'VehicleCard'),
                                      ('src/components/Orphan.tsx', 'Orphan')})
        effect = next(m for m in metrics if m['measurements']['record'] == 'react_effect_derived_state')
        self.assertEqual((effect['path'], effect['line'], effect['symbol']), ('src/components/VehicleCard.tsx', 8, 'setLabel'))
        self.assertEqual(sum(by_rule.values()), len(rows))

    def test_a_rule_naming_a_shared_kind_becomes_a_finding(self):
        row = dict(sample('ast-grep')['ast-grep.jsonl'][0], metadata={'kind': 'dead_code'})
        metrics, findings, _ = ast_grep.normalise([row], ast_grep.PINNED)
        self.assertEqual((len(metrics), [f['kind'] for f in findings]), (0, ['dead_code']))

    def test_every_rule_in_the_pack_has_examples(self):
        tests = ''.join(p.read_text(encoding='utf-8') for p in (ast_grep.RULES / 'rule-tests').glob('*.yml'))
        for rule, _ in ast_grep.rules(): self.assertIn(f'id: {rule}\n', tests)

    @unittest.skipUnless(installed(ast_grep), 'ast-grep is not installed at its pin')
    def test_the_pack_passes_its_own_examples(self):
        code, out, error, _ = run([which('ast-grep'), 'test', '--config', str(ast_grep.RULES / 'sgconfig.yml'),
                                   '--skip-snapshot-tests'], cwd=ast_grep.RULES)
        self.assertEqual(code, 0, out + error)

    @unittest.skipUnless(installed(ast_grep), 'ast-grep is not installed at its pin')
    def test_live_run_matches_the_sample(self):
        report = ast_grep.analyze(FIXTURE / 'web', Path(self.tmp) / 'work')
        self.assertEqual(report.status, OBSERVED, report.reason)
        self.assertEqual(report.metrics, ast_grep.normalise(sample('ast-grep')['ast-grep.jsonl'], ast_grep.PINNED)[0])


class LizardTests(Workspace):
    def test_every_function_is_measured_and_only_the_tangled_one_is_a_finding(self):
        parsed, skipped = lizard.rows(sample('lizard')['lizard.csv'] + 'a,short,row\n')
        self.assertEqual(skipped, 1)
        metrics, findings = lizard.normalise(parsed, lizard.PINNED)
        self.assertIn(('billing.py', 'unused_helper'), {(m['path'], m['symbol']) for m in metrics})
        self.assertIn(('src/lib/format.ts', 'plate'), {(m['path'], m['symbol']) for m in metrics})
        self.assertEqual(rules_of(type('R', (), {'findings': findings})), {('ccn', 'billing.py', 'billing.py::tariff')})
        self.assertEqual(findings[0]['measurements'][0], {'name': 'cyclomatic_complexity', 'value': 22, 'threshold': 15, 'unit': None})

    def test_the_csv_is_read_from_its_stdout_with_relative_paths(self):
        with mock.patch.object(lizard.tool, 'declined', return_value=None), mock.patch.object(lizard, 'version', return_value=lizard.PINNED), \
                mock.patch.object(lizard, 'which', return_value='lizard'), \
                mock.patch.object(lizard, 'run', return_value=(0, sample('lizard')['lizard.csv'], '', 0.1)):
            report = lizard.analyze(self.tmp, Path(self.tmp) / 'work')
        self.assertEqual((report.status, report.coverage['over_threshold']), (OBSERVED, 1))
        self.assertFalse([m for m in report.metrics if m['path'].startswith(('.', '/'))])

    @unittest.skipUnless(installed(lizard), 'lizard is not installed at its pin')
    def test_live_run_finds_the_tangled_function(self):
        report = lizard.analyze(FIXTURE / 'py', Path(self.tmp) / 'work')
        self.assertEqual(rules_of(report), {('ccn', 'billing.py', 'billing.py::tariff')})


class ComplexipyTests(Workspace):
    def test_reads_cognitive_complexity_from_the_file_it_writes(self):
        def fake_run(command, **_):
            Path(command[command.index('--output') + 1]).write_text(json.dumps(sample('complexipy')['complexipy.json']))
            return 0, '', '', 0.1
        with mock.patch.object(complexipy.tool, 'declined', return_value=None), \
                mock.patch.object(complexipy, 'version', return_value=complexipy.PINNED), \
                mock.patch.object(complexipy, 'which', return_value='complexipy'), mock.patch.object(complexipy, 'run', fake_run):
            report = complexipy.analyze(self.tmp, Path(self.tmp) / 'work')
        self.assertEqual(report.status, OBSERVED)
        self.assertEqual({m['symbol']: m['measurements']['cognitive_complexity'] for m in report.metrics},
                         {'tariff': 25, 'total': 1, 'unused_helper': 0})
        self.assertEqual(rules_of(report), {('cognitive', 'billing.py', 'billing.py::tariff')})

    def test_no_output_file_is_an_error_not_a_clean_result(self):
        with mock.patch.object(complexipy.tool, 'declined', return_value=None), \
                mock.patch.object(complexipy, 'version', return_value=complexipy.PINNED), \
                mock.patch.object(complexipy, 'which', return_value='complexipy'), \
                mock.patch.object(complexipy, 'run', return_value=(2, '', 'boom', 0.1)):
            self.assertEqual(complexipy.analyze(self.tmp, Path(self.tmp) / 'work').status, 'error')

    def test_a_file_it_cannot_parse_is_named_and_the_rest_is_still_measured(self):
        def fake_run(command, cwd=None, **_):
            Path(command[command.index('--output') + 1]).write_text(json.dumps(sample('complexipy')['complexipy.json']))
            return 1, f'\x1b[31merror\x1b[0m: Failed to process \x1b[37m{cwd}/legacy/broken.py\x1b[0m - Please check file/folder exists or check syntax', '', 0.1
        with mock.patch.object(complexipy.tool, 'declined', return_value=None), \
                mock.patch.object(complexipy, 'version', return_value=complexipy.PINNED), \
                mock.patch.object(complexipy, 'which', return_value='complexipy'), mock.patch.object(complexipy, 'run', fake_run):
            report = complexipy.analyze(self.tmp, Path(self.tmp) / 'work')
        self.assertEqual((report.status, report.coverage['unparsed_files'], len(report.metrics)), (OBSERVED, ['legacy/broken.py'], 3))

    @unittest.skipUnless(installed(complexipy), 'complexipy is not installed at its pin')
    def test_live_run_names_a_file_it_cannot_parse(self):
        project = Path(self.tmp) / 'project'
        project.mkdir()
        (project / 'ok.py').write_text('def ok():\n    return 1\n')
        (project / 'broken.py').write_text('def broken(:\n')
        report = complexipy.analyze(project, Path(self.tmp) / 'work')
        self.assertEqual((report.coverage['unparsed_files'], [m['symbol'] for m in report.metrics]), (['broken.py'], ['ok']))

    @unittest.skipUnless(installed(complexipy), 'complexipy is not installed at its pin')
    def test_live_run_does_not_apply_without_python_and_finds_the_tangled_function(self):
        self.assertEqual(complexipy.analyze(FIXTURE / 'web', Path(self.tmp) / 'a').status, NOT_APPLICABLE)
        self.assertEqual(rules_of(complexipy.analyze(FIXTURE / 'py', Path(self.tmp) / 'b')),
                         {('cognitive', 'billing.py', 'billing.py::tariff')})


class VultureTests(Workspace):
    def test_text_lines_become_dead_code_findings_with_the_name_in_backticks(self):
        rows = vulture.candidates(sample('vulture')['vulture.txt'] + 'not a vulture line\n')
        self.assertEqual(len(rows), 3)
        findings, by_type, in_tests, _ = vulture.normalise(rows, vulture.PINNED)
        self.assertEqual((by_type, in_tests), ({'function': 2, 'import': 1}, 0))
        messages = sorted(f['message'] for f in findings)
        self.assertIn('unused import `os` (90% confidence)', messages)
        self.assertTrue(all(re.search(r'`\w+`', m) for m in messages))
        self.assertEqual({f['engine_confidence'] for f in findings}, {0.9, 0.6})

    def test_variables_and_test_files_are_counted_not_reported(self):
        rows = vulture.candidates("app.py:3: unused variable 'x' (60% confidence)\n"
                                  "tests/test_app.py:9: unused function 'test_it' (60% confidence)\n")
        findings, by_type, in_tests, _ = vulture.normalise(rows, vulture.PINNED)
        self.assertEqual((findings, by_type, in_tests), ([], {'function': 1, 'variable': 1}, 1))

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

    def test_what_a_framework_calls_is_counted_not_reported_and_the_rest_still_is(self):
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

    def test_an_unreadable_file_leaves_the_candidate_reported(self):
        (Path(self.tmp) / 'broken.py').write_text('@app.route("/")\ndef index(:\n')
        rows = vulture.candidates("broken.py:1: unused function 'index' (60% confidence)\n"
                                  "missing.py:1: unused function 'gone' (60% confidence)\n")
        findings, _, _, framework = vulture.normalise(rows, vulture.PINNED, Path(self.tmp))
        self.assertEqual((len(findings), framework), (2, []))

    def test_its_two_part_version_is_read(self):
        with mock.patch.object(tool, 'which', return_value='vulture'), \
                mock.patch.object(tool, 'run', return_value=(0, 'vulture 2.16\n', '', 0.1)):
            self.assertEqual(vulture.version(), '2.16')

    @unittest.skipUnless(installed(vulture), 'vulture is not installed at its pin')
    def test_live_run_finds_the_unused_import_and_helper(self):
        report = vulture.analyze(FIXTURE / 'py', Path(self.tmp) / 'work')
        self.assertTrue({('unused_import', 'billing.py', 'billing.py:os'),
                         ('unused_function', 'billing.py', 'billing.py:unused_helper')} <= rules_of(report))


class KnipTests(Workspace):
    EXPECTED = {('files', 'src/components/Orphan.tsx', 'src/components/Orphan.tsx'),
                ('exports', 'src/lib/format.ts', 'src/lib/format.ts:unusedFormat'),
                ('dependencies', 'package.json', 'left-pad')}

    def test_unused_files_exports_and_dependencies_become_findings(self):
        findings, counted = knip.normalise(sample('knip')['knip.json'], knip.PINNED)
        self.assertEqual(rules_of(type('R', (), {'findings': findings})), self.EXPECTED)
        self.assertEqual({f['kind'] for f in findings}, {'dead_code', 'unused_dependency'})
        self.assertEqual(counted, {})

    def test_dev_dependencies_are_counted_not_reported(self):
        report = {'issues': [{'file': 'package.json', 'devDependencies': [{'name': 'vitest'}], 'unlisted': [{'name': 'x'}]}]}
        self.assertEqual(knip.normalise(report, knip.PINNED), ([], {'devDependencies': 1, 'unlisted': 1}))

    def test_every_plugin_is_switched_off_so_no_project_configuration_runs(self):
        config = knip.configuration(['vite', 'eslint'], exclude=('legacy',))
        self.assertEqual((config['vite'], config['eslint']), (False, False))
        self.assertIn('**/legacy/**', config['ignore'])

    def test_without_its_plugin_list_it_refuses_to_run(self):
        with mock.patch.object(knip.tool, 'declined', return_value=None), mock.patch.object(knip, 'version', return_value=knip.PINNED), \
                mock.patch.object(knip, 'which', return_value='/nowhere/bin/knip'), mock.patch.object(knip, 'run') as ran:
            report = knip.analyze(self.tmp, Path(self.tmp) / 'work')
        self.assertEqual(report.status, 'error')
        ran.assert_not_called()

    @unittest.skipUnless(installed(knip), 'knip is not installed at its pin')
    def test_live_run_resolves_the_alias_and_finds_only_what_is_unused(self):
        # VehicleCard is imported only as `@/components/VehicleCard`: were the alias not resolved it would be unused.
        report = knip.analyze(FIXTURE / 'web', Path(self.tmp) / 'work')
        self.assertEqual(report.status, OBSERVED, report.reason)
        self.assertEqual(rules_of(report), self.EXPECTED)


class ReactDocgenTests(Workspace):
    def test_components_carry_their_props_and_the_types_they_name(self):
        rows = {row['symbol']: row['measurements'] for row in react_docgen.records(sample('react-docgen')['react-docgen.json'])}
        self.assertEqual(set(rows), {'App', 'VehicleCard', 'Orphan'})
        self.assertEqual(rows['VehicleCard']['props'], [{'name': 'compact', 'type': 'boolean', 'required': False},
                                                        {'name': 'vehicle', 'type': 'Vehicle', 'required': True}])
        self.assertEqual(rows['VehicleCard']['referenced_types'], ['Vehicle'])
        self.assertEqual(rows['App']['prop_count'], 0)

    def test_a_failing_file_is_isolated_and_named_and_the_rest_is_read(self):
        parsed = sample('react-docgen')['react-docgen.json']
        def fake_run(command, **_):
            files = command[command.index('find-all-exported-components') + 1:]
            if 'src/main.tsx' in files: return 1, '', 'SyntaxError', 0.1
            out = Path(command[command.index('--out') + 1])
            out.write_text(json.dumps({f: parsed[f] for f in files}))
            return 0, '', '', 0.1
        with mock.patch.object(react_docgen.tool, 'declined', return_value=None), \
                mock.patch.object(react_docgen, 'version', return_value=react_docgen.PINNED), \
                mock.patch.object(react_docgen, 'which', return_value='react-docgen'), mock.patch.object(react_docgen, 'run', fake_run):
            report = react_docgen.analyze(FIXTURE / 'web', Path(self.tmp) / 'work')
        self.assertEqual(report.status, OBSERVED)
        self.assertEqual(report.coverage['unparsed_files'], ['src/main.tsx'])
        self.assertEqual({m['symbol'] for m in report.metrics}, {'VehicleCard', 'Orphan'})

    def test_glob_characters_in_a_path_are_escaped(self):
        self.assertEqual(react_docgen.GLOB_SPECIAL.sub(r'\\\1', 'app/(auth)/[id]/page.tsx'), r'app/\(auth\)/\[id\]/page.tsx')

    @unittest.skipUnless(installed(react_docgen), 'react-docgen is not installed at its pin')
    def test_live_run_matches_the_sample(self):
        report = react_docgen.analyze(FIXTURE / 'web', Path(self.tmp) / 'work')
        self.assertEqual(report.status, OBSERVED, report.reason)
        self.assertEqual(report.metrics, react_docgen.records(sample('react-docgen')['react-docgen.json']))


if __name__ == '__main__':
    unittest.main()

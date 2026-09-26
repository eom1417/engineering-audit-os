"""The static-analysis adapters: each reads its tool's real output shape, and nothing it cannot map is lost."""
import json
from pathlib import Path
from unittest import mock

from shared_fixture import Workspace

from eaos.engines import scc

CONTRACTS = Path(__file__).resolve().parent / 'contracts'


def sample(name):
    return json.loads((CONTRACTS / f'{name}.json').read_text(encoding='utf-8'))


class SccTests(Workspace):
    def test_the_sample_is_pinned_and_carries_what_the_adapter_reads(self):
        payload = sample('scc')
        self.assertEqual(payload['pinned_version'], scc.PINNED)
        for language in payload['scc.json']:
            for field in ('Name', 'Count', 'Code', 'Complexity'): self.assertIn(field, language)
            for row in language['Files']:
                for field in ('Location', 'Language', 'Lines', 'Code', 'Comment', 'Blank', 'Complexity'): self.assertIn(field, row)

    def test_every_file_becomes_a_measurement_with_a_project_relative_path(self):
        out = Path(self.tmp) / 'work/scc/scc.json'
        out.parent.mkdir(parents=True)
        text = json.dumps(sample('scc')['scc.json']).replace('/project', str(Path(self.tmp) / 'project'))
        (Path(self.tmp) / 'project').mkdir()
        def fake_run(command, **_):
            out.write_text(text)
            return 0, '', '', 0.1
        with mock.patch.object(scc.tool, 'declined', return_value=None), mock.patch.object(scc, 'version', return_value=scc.PINNED), \
                mock.patch.object(scc, 'run', fake_run), mock.patch.object(scc, 'which', return_value='scc'):
            report = scc.analyze(Path(self.tmp) / 'project', Path(self.tmp) / 'work')
        self.assertEqual(report.findings, [])
        self.assertTrue(report.metrics)
        for row in report.metrics:
            self.assertFalse(row['path'].startswith('/'), row['path'])
            self.assertIn('code', row['measurements'])

    def test_measurements_become_metric_facts_that_never_reach_correlation(self):
        from eaos.correlate import _findings
        from eaos.facts import external
        manifest = {'engines': {'scc': {'version': '4.1.0', 'metrics': [
            {'path': 'a.py', 'granularity': 'file', 'measurements': {'code': 10}}]}}, 'findings': [],
                    'coverage': {'scc': {'status': 'observed', 'evaluated_kinds': {}}}, 'target_unchanged': True}
        source = mock.Mock(exclude=(), fingerprint='f')
        with mock.patch('eaos.engines.analyze', return_value=manifest):
            result = external.run(self.tmp, source, out=self.tmp)
        kinds = {fact['kind'] for fact in result['facts']}
        self.assertEqual(kinds, {'symbol_metric_external'})
        self.assertEqual(_findings({'external': {'facts': result['facts']}}), [])


class SemgrepTests(Workspace):
    RULES = Path(__file__).resolve().parents[1] / 'eaos/rules/semgrep'

    def own_rules(self):
        """(id, kind) of every EAOS rule, read from the rule text (EAOS carries no YAML parser)."""
        import re
        rules = []
        for path in sorted(self.RULES.glob('*.yml')):
            for block in re.split(r'\n\s*- id: ', '\n' + path.read_text())[1:]:
                rules.append({'id': block.split()[0], 'metadata': {'kind': re.search(r'\bkind: (\w+)', block).group(1)}})
        return rules

    def test_every_own_rule_is_in_the_eaos_namespace_with_a_kind_an_example_and_a_mapping(self):
        from eaos.engines.contract import KINDS
        from eaos.engines.sarif import RULES
        from fnmatch import fnmatch
        rows = json.loads(RULES.read_text())['semgrep']
        examples = ''.join(p.read_text() for p in self.RULES.iterdir() if p.suffix in ('.ts', '.py'))
        for rule in self.own_rules():
            self.assertTrue(rule['id'].startswith('eaos.'), rule['id'])
            self.assertIn(rule['metadata']['kind'], KINDS, rule['id'])
            self.assertIn(f"ruleid: {rule['id']}", examples, rule['id'])
            self.assertIn(f"ok: {rule['id']}", examples, rule['id'])
            mapped = next((row['kind'] for row in rows if fnmatch(rule['id'], row['match'])), None)
            self.assertEqual(mapped, rule['metadata']['kind'], rule['id'])

    def test_the_rules_catch_their_examples_and_spare_the_correct_code(self):
        from eaos.engines import semgrep
        if semgrep.version() is None: self.skipTest('semgrep is not installed')
        import subprocess
        done = subprocess.run([semgrep.which('semgrep'), '--test', '--disable-version-check', str(self.RULES)],
                              capture_output=True, text=True, timeout=600)
        self.assertEqual(done.returncode, 0, done.stdout[-2000:] + done.stderr[-2000:])

    def test_the_official_library_is_never_in_this_repository(self):
        root = Path(__file__).resolve().parents[1]
        for path in (root / 'eaos').rglob('*.y*ml'):
            self.assertNotIn('semgrep.dev/legal/rules-license', path.read_text(errors='replace'), path)
        self.assertFalse((root / 'eaos/rules/semgrep-rules').exists())

    def test_rule_ids_and_paths_do_not_depend_on_where_things_are_installed(self):
        from eaos.engines import semgrep
        sarif = Path(self.tmp) / 'out.sarif'
        sarif.write_text(json.dumps({'runs': [{'tool': {'driver': {'rules': [{'id': 'rules.official.python.lang.security.x'}]}},
                                               'results': [{'ruleId': 'rules.eaos.eaos.security.y', 'locations': [
                                                   {'physicalLocation': {'artifactLocation': {'uri': f'{self.tmp}/app/db.py'}}}]}]}]}))
        semgrep.normalise(sarif, self.tmp)
        run = json.loads(sarif.read_text())['runs'][0]
        self.assertEqual(run['tool']['driver']['rules'][0]['id'], 'python.lang.security.x')
        self.assertEqual(run['results'][0]['ruleId'], 'eaos.security.y')
        self.assertEqual(run['results'][0]['locations'][0]['physicalLocation']['artifactLocation']['uri'], 'app/db.py')

    def test_the_sample_is_pinned_and_maps_completely(self):
        from eaos.engines import sarif, semgrep
        payload = sample('semgrep')
        self.assertEqual(payload['pinned_version'], semgrep.PINNED)
        path = Path(self.tmp) / 'semgrep.sarif'
        path.write_text(json.dumps(payload['semgrep.sarif']))
        findings, unmapped = sarif.read(path, 'semgrep', semgrep.PINNED)
        self.assertEqual(unmapped, {})
        self.assertTrue(findings)


class TrivyTests(Workspace):
    def test_no_secret_value_or_masked_match_survives_in_the_raw_file(self):
        from eaos.engines import trivy
        path = Path(self.tmp) / 'trivy.sarif'
        path.write_text(json.dumps({'runs': [{'tool': {'driver': {'rules': [
            {'id': 'jwt-token', 'name': 'Secret', 'shortDescription': {'text': 'JWT token'},
             'fullDescription': {'text': 'KEY="eyJhbGciOi.real.token"'}, 'help': {'text': 'KEY="eyJ"', 'markdown': 'KEY'}}]}},
            'results': [{'ruleId': 'jwt-token', 'message': {'text': 'Artifact: .env\nMatch: KEY="eyJhbGciOi.real.token"'},
                         'locations': [{'physicalLocation': {'artifactLocation': {'uri': '.env'}, 'region': {'startLine': 2}}}]}]}]}))
        trivy.redact(path)
        text = path.read_text()
        self.assertNotIn('eyJ', text)
        self.assertNotIn('KEY=', text)
        self.assertIn('Match: [not recorded]', text)

    def test_the_sample_is_pinned_redacted_and_maps_completely(self):
        from eaos.engines import sarif, trivy
        payload = sample('trivy')
        self.assertEqual(payload['pinned_version'], trivy.PINNED)
        self.assertNotRegex(json.dumps(payload), r'\*{6,}')
        path = Path(self.tmp) / 'trivy.sarif'
        path.write_text(json.dumps(payload['trivy.sarif']))
        findings, unmapped = sarif.read(path, 'trivy', trivy.PINNED)
        self.assertEqual(unmapped, {})
        self.assertEqual({f['kind'] for f in findings} >= {'vulnerability', 'secret'}, True)

    def test_a_second_scanner_on_a_vulnerable_package_is_a_witness_not_a_second_claim(self):
        from eaos.claims import from_engines
        facts = [{'id': f'F{i}', 'kind': 'engine_finding', 'location': {'path': 'package-lock.json', 'line': None},
                  'value': {'engine': engine, 'kind': 'vulnerability', 'rule': 'r', 'message': 'm', 'measurements': [],
                            'sites': [{'path': 'package-lock.json', 'line': None}]}}
                 for i, engine in enumerate(('osv-scanner', 'trivy'))]
        sets = {'external': {'facts': facts, 'summary': {'evaluated_kinds': {
            'osv-scanner': {'vulnerability': {'status': 'observed', 'granularity': 'package'}},
            'trivy': {'vulnerability': {'status': 'observed', 'granularity': 'package'}}}}}}
        self.assertEqual(from_engines(sets), [])


class CheckovTests(Workspace):
    def test_the_sample_is_pinned_and_maps_completely(self):
        from eaos.engines import checkov, sarif
        payload = sample('checkov')
        self.assertEqual(payload['pinned_version'], checkov.PINNED)
        path = Path(self.tmp) / 'results.sarif'
        path.write_text(json.dumps(payload['results_sarif.sarif']))
        findings, unmapped = sarif.read(path, 'checkov', checkov.PINNED)
        self.assertEqual(unmapped, {})
        self.assertEqual({f['kind'] for f in findings}, {'misconfiguration'})


class SarifLocationTests(Workspace):
    def test_every_way_a_tool_writes_a_location_becomes_a_project_relative_path(self):
        from eaos.engines.sarif import relative
        root = Path(self.tmp) / 'project'
        (root / 'app').mkdir(parents=True)
        (root / 'Dockerfile').write_text('FROM x\n')
        self.assertEqual(relative(f'{root}/app/db.py', root), 'app/db.py')
        self.assertEqual(relative(f'file://{root}/app/db.py', root), 'app/db.py')
        self.assertEqual(relative('project/Dockerfile', root), 'Dockerfile')
        self.assertEqual(relative('project/missing.txt', root), 'project/missing.txt')
        self.assertEqual(relative('.env', root), '.env')


class DependencyCruiserTests(Workspace):
    def test_the_sample_carries_what_the_adapter_reads(self):
        from eaos.engines import dependency_cruiser
        payload = sample('dependency-cruiser')
        self.assertEqual(payload['pinned_version'], dependency_cruiser.PINNED)
        summary = payload['depcruise.json']['summary']
        self.assertIn('totalCruised', summary)
        for violation in summary['violations']:
            self.assertIn('from', violation)
            self.assertIn('rule', violation)
            for step in violation['cycle']: self.assertIn('name', step)

    def test_a_policy_deny_becomes_a_forbidden_rule_written_outside_the_project(self):
        from eaos.engines.dependency_cruiser import configuration, glob_regex
        (Path(self.tmp) / 'eaos.policy.json').write_text(json.dumps({
            'layers': {'ui': ['src/ui/**'], 'db': ['src/db/*.ts']},
            'rules': [{'deny': {'from': 'ui', 'to': 'db'}, 'reason': 'screens go through services'}]}))
        rules, declared = configuration(self.tmp)
        self.assertEqual(declared, 1)
        self.assertEqual(rules['forbidden'][1]['from']['path'], '^src/ui/.*')
        self.assertEqual(rules['forbidden'][1]['to']['path'], '^src/db/[^/]*\\.ts$')
        import re
        self.assertTrue(re.match(glob_regex('src/db/*.ts'), 'src/db/users.ts'))
        self.assertFalse(re.match(glob_regex('src/db/*.ts'), 'src/db/deep/users.ts'))

    def test_a_cycle_closed_only_by_import_type_is_coupling_not_a_runtime_cycle(self):
        from eaos.engines import dependency_cruiser
        if dependency_cruiser.version() is None: self.skipTest('dependency-cruiser is not installed')
        root = Path(self.tmp) / 'project'
        (root / 'src').mkdir(parents=True)
        (root / 'src/a.ts').write_text('import { b } from "./b";\nexport const a = () => b();\n')
        (root / 'src/b.ts').write_text('import { a } from "./a";\nexport const b = () => a();\n')
        (root / 'src/page.ts').write_text('import { render } from "./child";\nexport interface Message { text: string }\nrender();\n')
        (root / 'src/child.ts').write_text('import type { Message } from "./page";\nexport const render = (m?: Message) => m;\n')
        from eaos.engines.process import state_digest
        before = state_digest(root)
        report = dependency_cruiser.analyze(root, Path(self.tmp) / 'work')
        self.assertEqual(state_digest(root), before)
        self.assertEqual(sorted(p.name for p in root.iterdir()), ['src'])
        self.assertEqual(report.status, 'observed', report.reason)
        self.assertEqual([sorted(p for p, _ in f['sites']) for f in report.findings], [['src/a.ts', 'src/b.ts']])
        self.assertEqual(len(report.coverage['type_only_cycles']), 1)
        self.assertIn('src/child.ts', report.coverage['type_only_cycles'][0])

    def test_a_run_that_examined_nothing_is_an_error_not_a_clean_graph(self):
        from eaos.engines import dependency_cruiser
        def fake_run(command, **_):
            out = Path(command[command.index('--output-to') + 1])
            out.write_text(json.dumps({'summary': {'totalCruised': 0, 'violations': [],
                                                   'environment': {'issues': [{'name': 'missing-typescript-transpiler'}]}}}))
            return 0, '', '', 0.1
        (Path(self.tmp) / 'a.ts').write_text('export const a = 1;\n')
        with mock.patch.object(dependency_cruiser.tool, 'declined', return_value=None), \
                mock.patch.object(dependency_cruiser, 'version', return_value='18.4.0'), \
                mock.patch.object(dependency_cruiser, 'run', fake_run), mock.patch.object(dependency_cruiser, 'which', return_value='depcruise'):
            report = dependency_cruiser.analyze(self.tmp, Path(self.tmp) / 'work')
        self.assertEqual(report.status, 'error')
        self.assertIn('missing-typescript-transpiler', report.reason)


class SqlfluffTests(Workspace):
    def test_the_sample_carries_what_the_adapter_reads(self):
        from eaos.engines import sqlfluff
        payload = sample('sqlfluff')
        self.assertEqual(payload['pinned_version'], sqlfluff.PINNED)
        for entry in payload['sqlfluff.json']:
            self.assertIn('filepath', entry)
            for violation in entry['violations']:
                for field in ('code', 'start_line_no', 'description'): self.assertIn(field, violation)

    def test_style_is_counted_but_only_risk_families_become_findings(self):
        from eaos.engines import sqlfluff
        payload = sample('sqlfluff')['sqlfluff.json']
        def fake_run(command, **_):
            Path(command[command.index('--write-output') + 1]).write_text(json.dumps(payload))
            return 0, '', '', 0.1
        with mock.patch.object(sqlfluff.tool, 'declined', return_value=None), mock.patch.object(sqlfluff, 'version', return_value='4.3.0'), \
                mock.patch.object(sqlfluff, 'run', fake_run), mock.patch.object(sqlfluff, 'which', return_value='sqlfluff'):
            report = sqlfluff.analyze(self.tmp, Path(self.tmp) / 'work')
        codes = [v['code'] for entry in payload for v in entry['violations']]
        self.assertEqual(sum(report.coverage['violations_by_code'].values()), len(codes))
        self.assertEqual({f['rule'] for f in report.findings}, {c for c in codes if not sqlfluff.style(c)})
        self.assertEqual(report.coverage['style_only_not_findings'], sum(1 for c in codes if sqlfluff.style(c)))


class OpenApiTests(Workspace):
    V1 = ('openapi: 3.0.3\ninfo: {title: Fleet, version: 1.0.0}\npaths:\n'
          '  /vehicles:\n    get:\n      responses: {"200": {description: ok}}\n'
          '  /drivers:\n    get:\n      responses: {"200": {description: ok}}\n')

    def project(self):
        import subprocess
        root = Path(self.tmp) / 'project'
        root.mkdir()
        git = lambda *a: subprocess.run(['git', '-C', str(root), *a], check=True, capture_output=True)
        (root / 'openapi.yaml').write_text(self.V1)
        git('init', '-q'); git('add', '.'); git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'v1')
        (root / 'openapi.yaml').write_text(self.V1.split('  /drivers:')[0])
        git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qam', 'v2')
        return root

    def test_the_samples_carry_what_the_adapters_read(self):
        from eaos.engines import oasdiff, sarif, spectral
        self.assertEqual(sample('spectral')['pinned_version'], spectral.PINNED)
        self.assertEqual(sample('oasdiff')['pinned_version'], oasdiff.PINNED)
        path = Path(self.tmp) / 's.sarif'
        path.write_text(json.dumps(sample('spectral')['spectral.sarif']))
        findings, unmapped = sarif.read(path, 'spectral', spectral.PINNED)
        self.assertEqual((unmapped, {f['kind'] for f in findings}), ({}, {'api_contract'}))
        for change in sample('oasdiff')['breaking.json']:
            for field in ('id', 'text', 'level', 'path'): self.assertIn(field, change)

    def test_a_removed_path_is_a_breaking_change_against_the_previous_version(self):
        from eaos.engines import oasdiff
        from eaos.engines.process import state_digest
        if oasdiff.version() is None: self.skipTest('oasdiff is not installed')
        root = self.project()
        before = state_digest(root)
        report = oasdiff.analyze(root, Path(self.tmp) / 'work')
        self.assertEqual(state_digest(root), before)
        self.assertEqual([f['rule'] for f in report.findings], ['api-path-removed-without-deprecation'])
        self.assertIn('/drivers', report.findings[0]['message'])

    def test_a_specification_with_no_history_is_examined_with_nothing_to_compare(self):
        from eaos.engines import oasdiff
        if oasdiff.version() is None: self.skipTest('oasdiff is not installed')
        root = Path(self.tmp) / 'fresh'
        root.mkdir()
        (root / 'openapi.yaml').write_text(self.V1)
        report = oasdiff.analyze(root, Path(self.tmp) / 'work')
        self.assertEqual((report.status, report.findings), ('observed', []))
        self.assertEqual(report.coverage['specifications'], {'openapi.yaml': 'no earlier version in history'})


class GitNexusTests(Workspace):
    def test_the_sample_carries_what_the_adapter_reads(self):
        from eaos.engines import gitnexus
        payload = sample('gitnexus')
        self.assertEqual(payload['pinned_version'], gitnexus.PINNED)
        for cycle in payload['check-cycles.json']['cycles']: self.assertIn('files', cycle)
        rows = gitnexus.table(payload['cypher-imports.json']['markdown'])
        self.assertTrue(rows)
        self.assertTrue(all(len(row) == 2 for row in rows))

    def test_excluded_paths_match_whole_segments(self):
        from eaos.engines.gitnexus import excluded
        self.assertTrue(excluded('src/components/ui/button.tsx', ['components/ui']))
        self.assertFalse(excluded('src/components/uikit/button.tsx', ['components/ui']))

    def test_it_runs_on_a_copy_and_leaves_the_project_and_the_home_untouched(self):
        from eaos.engines import gitnexus
        from eaos.engines.process import state_digest
        if gitnexus.version() is None: self.skipTest('gitnexus is not installed')
        root = Path(self.tmp) / 'project'
        (root / 'src').mkdir(parents=True)
        (root / 'src/a.ts').write_text('import { b } from "./b";\nexport const a = () => b();\n')
        (root / 'src/b.ts').write_text('import { a } from "./a";\nexport const b = () => a();\n')
        (root / 'AGENTS.md').write_text('# the owner\'s own file\n')
        before = state_digest(root)
        home = Path.home() / '.gitnexus'
        existed = home.exists()
        report = gitnexus.analyze(root, Path(self.tmp) / 'work')
        self.assertEqual(report.status, 'observed', report.reason)
        self.assertEqual(state_digest(root), before)
        self.assertEqual((root / 'AGENTS.md').read_text(), '# the owner\'s own file\n')
        self.assertFalse((root / 'CLAUDE.md').exists())
        self.assertEqual(home.exists(), existed)
        self.assertEqual([sorted(p for p, _ in f['sites']) for f in report.findings if f['kind'] == 'cycle'],
                         [['src/a.ts', 'src/b.ts']])


class CheckovCoverageTests(Workspace):
    def test_a_clean_run_records_how_many_checks_passed(self):
        from eaos.engines import checkov
        def fake_run(command, **_):
            out = Path(command[command.index('--output-file-path') + 1])
            (out / 'results_sarif.sarif').write_text(json.dumps({'runs': [{'tool': {'driver': {'rules': []}}, 'results': []}]}))
            (out / 'results_json.json').write_text(json.dumps({'check_type': 'github_actions',
                                                               'summary': {'passed': 116, 'failed': 0, 'skipped': 0}}))
            return 0, '', '', 0.1
        with mock.patch.object(checkov.tool, 'declined', return_value=None), mock.patch.object(checkov, 'version', return_value='3.3.19'), \
                mock.patch.object(checkov, 'run', fake_run), mock.patch.object(checkov, 'which', return_value='checkov'):
            report = checkov.analyze(self.tmp, Path(self.tmp) / 'work')
        self.assertEqual((report.status, report.findings), ('observed', []))
        self.assertEqual(report.coverage['frameworks'], {'github_actions': {'passed': 116, 'failed': 0, 'skipped': 0}})


class GitNexusPagingTests(Workspace):
    def run_with(self, pages):
        from eaos.engines import gitnexus
        calls = []
        def fake_run(command, **_):
            calls.append(command)
            if command[1] == 'analyze': return 0, '', '', 0.1
            if command[1] == 'check': return 0, json.dumps({'cycles': []}), '', 0.1
            query = command[-1]
            offset = int(query.split(' SKIP ')[1].split()[0])
            rows = pages(query, offset)
            header = '| x | y |\n| --- | --- |\n'
            return 0, json.dumps({'markdown': header + ''.join(f'| {a} | {b} |\n' for a, b in rows)}), '', 0.1
        (Path(self.tmp) / 'p').mkdir()
        with mock.patch.object(gitnexus.tool, 'declined', return_value=None), mock.patch.object(gitnexus, 'version', return_value='1.6.12'), \
                mock.patch.object(gitnexus, 'run', fake_run), mock.patch.object(gitnexus, 'which', return_value='gitnexus'):
            return gitnexus.analyze(Path(self.tmp) / 'p', Path(self.tmp) / 'work'), calls

    def test_every_page_is_read_until_a_short_one(self):
        from eaos.engines import gitnexus
        total = gitnexus.PAGE + 7
        def pages(query, offset):
            if 'IMPORTS' in query: return [(f'f{i}.ts', 'hub.ts') for i in range(offset, min(total, offset + gitnexus.PAGE))]
            return []
        report, calls = self.run_with(pages)
        self.assertEqual(report.coverage['import_edges'], total)

    def test_a_page_at_the_output_limit_is_an_error_not_a_shorter_answer(self):
        from eaos.engines import gitnexus
        def pages(query, offset):
            return [('x' * 200, 'y' * 200)] * 200 if 'IMPORTS' in query else []
        report, _ = self.run_with(pages)
        self.assertEqual(report.status, 'error')
        self.assertIn('output limit', report.reason)


class MirrorTests(Workspace):
    def test_a_copy_without_hardlinks_cannot_reach_the_project(self):
        from eaos.engines.process import mirror
        root = Path(self.tmp) / 'project'
        root.mkdir()
        (root / 'AGENTS.md').write_text('original\n')
        copy, how = mirror(root, Path(self.tmp) / 'work', hardlink=False)
        self.assertEqual(how, 'copy')
        with open(copy / 'AGENTS.md', 'r+') as handle:
            handle.write('changed')
        self.assertEqual((root / 'AGENTS.md').read_text(), 'original\n')

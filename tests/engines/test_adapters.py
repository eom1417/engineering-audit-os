"""The static-analysis adapters: each reads its tool's real output shape, and nothing it cannot map is lost."""
import json
from pathlib import Path
from unittest import mock

from shared_fixture import Workspace

from eaos.engines.code import scc

CONTRACTS = Path(__file__).resolve().parents[1] / 'contracts'


def sample(name):
    return json.loads((CONTRACTS / f'{name}.json').read_text(encoding='utf-8'))


class SampleTests(Workspace):
    def test_each_sample_is_pinned_and_maps_everything_and_no_secret_survives(self):
        from eaos.engines.security import checkov, semgrep, trivy
        from eaos.engines.code import dependency_cruiser, gitnexus, sqlfluff
        from eaos.engines.api import oasdiff, spectral
        from eaos.engines import sarif
        for module, name, file, kinds in ((semgrep, 'semgrep', 'semgrep.sarif', None), (trivy, 'trivy', 'trivy.sarif', {'secret'}),
                                          (checkov, 'checkov', 'results_sarif.sarif', {'misconfiguration'}),
                                          (spectral, 'spectral', 'spectral.sarif', {'api_contract'})):
            with self.subTest(engine=name):
                payload = sample(name)                       # its pin: test_engine_contracts
                path = Path(self.tmp) / f'{name}.sarif'
                path.write_text(json.dumps(payload[file]))
                findings, unmapped = sarif.read(path, name, module.PINNED)
                self.assertEqual(unmapped, {})
                self.assertTrue(findings)
                if kinds: self.assertLessEqual(kinds, {f['kind'] for f in findings})
        self.assertNotRegex(json.dumps(sample('trivy')), r'\*{6,}', 'the trivy sample is redacted')
        payload = sample('scc')
        for language in payload['scc.json']:
            for field in ('Name', 'Count', 'Code', 'Complexity'): self.assertIn(field, language)
            for row in language['Files']:
                for field in ('Location', 'Language', 'Lines', 'Code', 'Comment', 'Blank', 'Complexity'): self.assertIn(field, row)
        payload = sample('dependency-cruiser')
        self.assertEqual(payload['pinned_version'], dependency_cruiser.PINNED)
        self.assertIn('totalCruised', payload['depcruise.json']['summary'])
        for violation in payload['depcruise.json']['summary']['violations']:
            self.assertLessEqual({'from', 'rule'}, set(violation))
            for step in violation['cycle']: self.assertIn('name', step)
        payload = sample('sqlfluff')
        self.assertEqual(payload['pinned_version'], sqlfluff.PINNED)
        for entry in payload['sqlfluff.json']:
            self.assertIn('filepath', entry)
            for violation in entry['violations']: self.assertLessEqual({'code', 'start_line_no', 'description'}, set(violation))
        self.assertEqual(sample('oasdiff')['pinned_version'], oasdiff.PINNED)
        for change in sample('oasdiff')['breaking.json']: self.assertLessEqual({'id', 'text', 'level', 'path'}, set(change))
        payload = sample('gitnexus')
        self.assertEqual(payload['pinned_version'], gitnexus.PINNED)
        for cycle in payload['check-cycles.json']['cycles']: self.assertIn('files', cycle)
        rows = gitnexus.table(payload['cypher-imports.json']['markdown'])
        self.assertTrue(rows and all(len(row) == 2 for row in rows))
        from eaos.engines.security import trivy
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


class SemgrepTests(Workspace):
    RULES = Path(__file__).resolve().parents[2] / 'eaos/rules/semgrep'

    def own_rules(self):
        """(id, kind) of every EAOS rule, read from the rule text (EAOS carries no YAML parser)."""
        import re
        rules = []
        for path in sorted(self.RULES.glob('*.yml')):
            for block in re.split(r'\n\s*- id: ', '\n' + path.read_text())[1:]:
                rules.append({'id': block.split()[0], 'metadata': {'kind': re.search(r'\bkind: (\w+)', block).group(1)}})
        return rules

    def test_every_own_rule_is_in_the_eaos_namespace_with_a_kind_an_example_and_a_mapping_and_no_official_rule_is_here(self):
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
        root = Path(__file__).resolve().parents[2]
        for path in (root / 'eaos').rglob('*.y*ml'):
            self.assertNotIn('semgrep.dev/legal/rules-license', path.read_text(errors='replace'), path)
        self.assertFalse((root / 'eaos/rules/semgrep-rules').exists())

    def test_the_rules_catch_their_examples_and_spare_the_correct_code(self):
        from eaos.engines.security import semgrep
        if semgrep.version() is None: self.skipTest('semgrep is not installed')
        import subprocess
        done = subprocess.run([semgrep.which('semgrep'), '--test', '--disable-version-check', str(self.RULES)],
                              capture_output=True, text=True, timeout=600)
        self.assertEqual(done.returncode, 0, done.stdout[-2000:] + done.stderr[-2000:])

    def test_the_silenced_official_rules_are_left_out_and_the_other_security_rules_kept(self):
        from eaos.engines.security import semgrep
        checkout = Path(self.tmp) / 'official'
        for name in (*semgrep.SILENCED, 'javascript/browser/security/insecure-innerhtml.yaml', 'javascript/lang/style/x.yaml'):
            (checkout / name).parent.mkdir(parents=True, exist_ok=True)
            (checkout / name).write_text('rules: []\n')
        with mock.patch.object(semgrep, 'official_checkout', return_value=(checkout, 'c' * 40)):
            semgrep.assemble(Path(self.tmp))
        copied = {p.relative_to(Path(self.tmp) / 'rules/official').as_posix() for p in (Path(self.tmp) / 'rules/official').rglob('*.yaml')}
        self.assertEqual(copied, {'javascript/browser/security/insecure-innerhtml.yaml'})

    def test_rule_ids_and_paths_do_not_depend_on_where_things_are_installed(self):
        from eaos.engines.security import semgrep
        sarif = Path(self.tmp) / 'out.sarif'
        sarif.write_text(json.dumps({'runs': [{'tool': {'driver': {'rules': [{'id': 'rules.official.python.lang.security.x'}]}},
                                               'results': [{'ruleId': 'rules.eaos.eaos.security.y', 'locations': [
                                                   {'physicalLocation': {'artifactLocation': {'uri': f'{self.tmp}/app/db.py'}}}]}]}]}))
        semgrep.normalise(sarif, self.tmp)
        run = json.loads(sarif.read_text())['runs'][0]
        self.assertEqual(run['tool']['driver']['rules'][0]['id'], 'python.lang.security.x')
        self.assertEqual(run['results'][0]['ruleId'], 'eaos.security.y')
        self.assertEqual(run['results'][0]['locations'][0]['physicalLocation']['artifactLocation']['uri'], 'app/db.py')
        from eaos.engines.sarif import relative
        root = Path(self.tmp) / 'project'
        (root / 'app').mkdir(parents=True)
        (root / 'Dockerfile').write_text('FROM x\n')
        for written, expected in ((f'{root}/app/db.py', 'app/db.py'), (f'file://{root}/app/db.py', 'app/db.py'),
                                  ('project/Dockerfile', 'Dockerfile'), ('project/missing.txt', 'project/missing.txt'), ('.env', '.env')):
            self.assertEqual(relative(written, root), expected, written)


class DependencyCruiserTests(Workspace):
    def test_a_policy_deny_becomes_a_forbidden_rule_written_outside_the_project(self):
        from eaos.engines.code.dependency_cruiser import configuration, glob_regex
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
        from eaos.engines.code import dependency_cruiser
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


class ReportedRunTests(Workspace):
    """What a run of a tool reports beyond its findings: what it examined, what passed, what is only style, every page."""

    def test_measurements_stay_metrics_style_is_not_a_finding_a_clean_run_counts_what_passed_and_an_empty_one_is_an_error(self):
        out = Path(self.tmp) / 'work/scc/scc.json'
        out.parent.mkdir(parents=True)
        text = json.dumps(sample('scc')['scc.json']).replace('/project', str(Path(self.tmp) / 'project'))
        (Path(self.tmp) / 'project').mkdir()
        def fake_run(command, **_):
            out.write_text(text)
            return 0, '', '', 0.1
        with mock.patch.object(scc.tool, 'started', return_value=(None, scc.PINNED)), \
                mock.patch.object(scc, 'run', fake_run), mock.patch.object(scc, 'which', return_value='scc'):
            report = scc.analyze(Path(self.tmp) / 'project', Path(self.tmp) / 'work')
        self.assertEqual(report.findings, [])
        self.assertTrue(report.metrics)
        for row in report.metrics:
            self.assertFalse(row['path'].startswith('/'), row['path'])
            self.assertIn('code', row['measurements'])
        from eaos.analysis.claims.correlate import _findings
        from eaos.facts import engine_findings as external
        manifest = {'engines': {'scc': {'version': '4.1.0', 'metrics': [
            {'path': 'a.py', 'granularity': 'file', 'measurements': {'code': 10}}]}}, 'findings': [],
                    'coverage': {'scc': {'status': 'observed', 'evaluated_kinds': {}}}, 'target_unchanged': True}
        source = mock.Mock(exclude=(), content_fingerprint='f')
        with mock.patch('eaos.engines.analyze', return_value=manifest):
            result = external.run(self.tmp, source, out=self.tmp)
        kinds = {fact['kind'] for fact in result['facts']}
        self.assertEqual(kinds, {'symbol_metric_external'})
        self.assertEqual(_findings({'external': {'facts': result['facts']}}), [])
        from eaos.engines.code import sqlfluff
        payload = sample('sqlfluff')['sqlfluff.json']
        def fake_run(command, **_):
            Path(command[command.index('--write-output') + 1]).write_text(json.dumps(payload))
            return 0, '', '', 0.1
        with mock.patch.object(sqlfluff.tool, 'started', return_value=(None, '4.3.0')), \
                mock.patch.object(sqlfluff, 'run', fake_run), mock.patch.object(sqlfluff, 'which', return_value='sqlfluff'):
            report = sqlfluff.analyze(self.tmp, Path(self.tmp) / 'work')
        codes = [v['code'] for entry in payload for v in entry['violations']]
        self.assertEqual(sum(report.coverage['violations_by_code'].values()), len(codes))
        self.assertEqual({f['rule'] for f in report.findings}, {c for c in codes if not sqlfluff.style(c)})
        self.assertEqual(report.coverage['style_only_not_findings'], sum(1 for c in codes if sqlfluff.style(c)))
        from eaos.engines.security import checkov
        def fake_run(command, **_):
            out = Path(command[command.index('--output-file-path') + 1])
            (out / 'results_sarif.sarif').write_text(json.dumps({'runs': [{'tool': {'driver': {'rules': []}}, 'results': []}]}))
            (out / 'results_json.json').write_text(json.dumps({'check_type': 'github_actions',
                                                               'summary': {'passed': 116, 'failed': 0, 'skipped': 0}}))
            return 0, '', '', 0.1
        with mock.patch.object(checkov.tool, 'started', return_value=(None, '3.3.19')), \
                mock.patch.object(checkov, 'run', fake_run), mock.patch.object(checkov, 'which', return_value='checkov'):
            report = checkov.analyze(self.tmp, Path(self.tmp) / 'work')
        self.assertEqual((report.status, report.findings), ('observed', []))
        self.assertEqual(report.coverage['frameworks'], {'github_actions': {'passed': 116, 'failed': 0, 'skipped': 0}})
        from eaos.engines.code import dependency_cruiser
        def fake_run(command, **_):
            out = Path(command[command.index('--output-to') + 1])
            out.write_text(json.dumps({'summary': {'totalCruised': 0, 'violations': [],
                                                   'environment': {'issues': [{'name': 'missing-typescript-transpiler'}]}}}))
            return 0, '', '', 0.1
        (Path(self.tmp) / 'a.ts').write_text('export const a = 1;\n')
        with mock.patch.object(dependency_cruiser.tool, 'started', return_value=(None, '18.4.0')), \
                mock.patch.object(dependency_cruiser, 'run', fake_run), mock.patch.object(dependency_cruiser, 'which', return_value='depcruise'):
            report = dependency_cruiser.analyze(self.tmp, Path(self.tmp) / 'work-depcruise')
        self.assertEqual(report.status, 'error')
        self.assertIn('missing-typescript-transpiler', report.reason)

    def run_with(self, pages):
        from eaos.engines.code import gitnexus
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
        (Path(self.tmp) / 'p').mkdir(exist_ok=True)
        with mock.patch.object(gitnexus.tool, 'started', return_value=(None, '1.6.12')), \
                mock.patch.object(gitnexus, 'run', fake_run), mock.patch.object(gitnexus, 'which', return_value='gitnexus'):
            return gitnexus.analyze(Path(self.tmp) / 'p', Path(self.tmp) / 'work'), calls

    def test_its_misreadings_of_python_are_no_cycle_and_a_real_cycle_stays(self):
        # EAOS, 2026-10-24: all six of GitNexus's cycles were `from . import core` and `import html` misread
        from eaos.engines.code import gitnexus
        copy = Path(self.tmp) / 'copy'
        (copy / 'core').mkdir(parents=True)
        (copy / 'core/markup.py').write_text('import html\nfrom . import words\n')
        (copy / 'a.py').write_text('import b\n')
        self.assertTrue(gitnexus.misread(['nodes/__init__.py', 'nodes/triage.py', 'nodes/__init__.py'], copy))
        self.assertTrue(gitnexus.misread(['core/markup.py', 'report/html.py'], copy))
        self.assertFalse(gitnexus.misread(['a.py', 'b.py'], copy))
        self.assertFalse(gitnexus.misread(['core/markup.py', 'core/words.py'], copy))

    def test_every_page_is_read_until_a_short_one_and_a_page_at_the_output_limit_is_an_error(self):
        from eaos.engines.code import gitnexus
        total = gitnexus.PAGE + 7
        def pages(query, offset):
            if 'IMPORTS' in query: return [(f'f{i}.ts', 'hub.ts') for i in range(offset, min(total, offset + gitnexus.PAGE))]
            return []
        report, calls = self.run_with(pages)
        self.assertEqual(report.coverage['import_edges'], total)
        report, _ = self.run_with(lambda query, offset: [('x' * 200, 'y' * 200)] * 200 if 'IMPORTS' in query else [])
        self.assertEqual(report.status, 'error')
        self.assertIn('output limit', report.reason)
        from eaos.engines.code.gitnexus import excluded
        self.assertTrue(excluded('src/components/ui/button.tsx', ['components/ui']), 'excluded paths match whole segments')
        self.assertFalse(excluded('src/components/uikit/button.tsx', ['components/ui']))


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

    def test_a_removed_path_is_a_breaking_change_and_a_specification_with_no_history_has_nothing_to_compare(self):
        from eaos.engines.api import oasdiff
        from eaos.engines.process import state_digest
        if oasdiff.version() is None: self.skipTest('oasdiff is not installed')
        root = self.project()
        before = state_digest(root)
        report = oasdiff.analyze(root, Path(self.tmp) / 'work')
        self.assertEqual(state_digest(root), before)
        self.assertEqual([f['rule'] for f in report.findings], ['api-path-removed-without-deprecation'])
        self.assertIn('/drivers', report.findings[0]['message'])
        root = Path(self.tmp) / 'fresh'
        root.mkdir()
        (root / 'openapi.yaml').write_text(self.V1)
        report = oasdiff.analyze(root, Path(self.tmp) / 'work2')
        self.assertEqual((report.status, report.findings), ('observed', []))
        self.assertEqual(report.coverage['specifications'], {'openapi.yaml': 'no earlier version in history'})


class GitNexusTests(Workspace):
    def test_it_runs_on_a_copy_and_leaves_the_project_and_the_home_untouched(self):
        from eaos.engines.code import gitnexus
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

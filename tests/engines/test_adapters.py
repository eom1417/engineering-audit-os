"""The static-analysis adapters: each reads its tool's real output shape, and nothing it cannot map is lost."""
import json
from pathlib import Path
from unittest import mock

from shared_fixture import Workspace

from eaos.engines.tool import version_of

CONTRACTS = Path(__file__).resolve().parents[1] / 'contracts'


def sample(name):
    return json.loads((CONTRACTS / f'{name}.json').read_text(encoding='utf-8'))


class SampleTests(Workspace):
    def test_each_sample_is_pinned_and_maps_everything_and_no_secret_survives(self):
        from eaos.engines.security import semgrep
        from eaos.engines.code import dependency_cruiser
        from eaos.engines import sarif
        for module, name, file, kinds in ((semgrep, 'semgrep', 'semgrep.sarif', None),):
            with self.subTest(engine=name):
                payload = sample(name)                       # its pin: test_engine_contracts
                path = Path(self.tmp) / f'{name}.sarif'
                path.write_text(json.dumps(payload[file]))
                findings, unmapped = sarif.read(path, name, module.PINNED)
                self.assertEqual(unmapped, {})
                self.assertTrue(findings)
                if kinds: self.assertLessEqual(kinds, {f['kind'] for f in findings})
        payload = sample('dependency-cruiser')
        self.assertEqual(payload['pinned_version'], dependency_cruiser.PINNED)
        self.assertIn('totalCruised', payload['depcruise.json']['summary'])
        for violation in payload['depcruise.json']['summary']['violations']:
            self.assertLessEqual({'from', 'rule'}, set(violation))
            for step in violation['cycle']: self.assertIn('name', step)


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
        if version_of(semgrep) is None: self.skipTest('semgrep is not installed')
        import subprocess
        done = subprocess.run([semgrep.which('semgrep'), '--test', '--disable-version-check', str(self.RULES)],
                              capture_output=True, text=True, timeout=600)
        self.assertEqual(done.returncode, 0, done.stdout[-2000:] + done.stderr[-2000:])

    def test_the_silenced_official_rules_are_left_out_and_the_other_security_rules_kept(self):
        from eaos.engines.security import semgrep
        checkout = Path(self.tmp) / 'official'
        for name in (*semgrep.SILENCED, 'javascript/browser/security/insecure-innerhtml.yaml', 'javascript/lang/style/x.yaml',
                     'php/lang/security/injection.yaml', 'php/lang/style/x.yaml'):
            (checkout / name).parent.mkdir(parents=True, exist_ok=True)
            (checkout / name).write_text('rules: []\n')
        with mock.patch.object(semgrep, 'official_checkout', return_value=(checkout, 'c' * 40)):
            semgrep.assemble(Path(self.tmp))
        copied = {p.relative_to(Path(self.tmp) / 'rules/official').as_posix() for p in (Path(self.tmp) / 'rules/official').rglob('*.yaml')}
        self.assertEqual(copied, {'javascript/browser/security/insecure-innerhtml.yaml', 'php/lang/security/injection.yaml'})

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
        if version_of(dependency_cruiser) is None: self.skipTest('dependency-cruiser is not installed')
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
    """What a run of a tool reports beyond its findings: what it examined, what passed, what is only style, pages."""

    def test_measurements_stay_metrics_and_an_empty_run_is_an_error(self):
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

"""Syft and OSV-Scanner: a complete inventory, every vulnerable version found once, and a repair that is checked."""
import json
import subprocess
from pathlib import Path
from unittest import mock

from shared_fixture import Workspace

from eaos.engines import ordered
from eaos.engines import osv_scanner, syft, tool
from eaos.engines.contract import KINDS, NOT_APPLICABLE

CONTRACTS = Path(__file__).resolve().parent / 'contracts'


def sample(name):
    return json.loads((CONTRACTS / f'{name}.json').read_text(encoding='utf-8'))


class ContractTests(Workspace):
    def test_the_samples_are_pinned_to_the_versions_the_toolchain_installs(self):
        for module in (syft, osv_scanner):
            self.assertEqual(sample(module.NAME)['pinned_version'], module.PINNED, module.NAME)

    def test_the_sbom_is_cyclonedx_with_named_components(self):
        sbom = sample('syft')['sbom.cdx.json']
        self.assertEqual(sbom['bomFormat'], 'CycloneDX')
        for component in sbom['components']:
            self.assertIn('name', component)

    def test_osv_output_still_carries_what_the_adapter_reads(self):
        for result in sample('osv-scanner')['osv.json']['results']:
            self.assertIn('path', result['source'])
            for package in result['packages']:
                self.assertLessEqual({'name', 'version', 'ecosystem'}, set(package['package']))
                for vulnerability in package['vulnerabilities']:
                    self.assertIn('id', vulnerability)
                    self.assertIn('affected', vulnerability)
                for group in package.get('groups') or []:
                    self.assertIn('ids', group)


class NormaliseTests(Workspace):
    def findings(self):
        return osv_scanner.normalise(sample('osv-scanner')['osv.json'], Path('/project'), '2.6.0')

    def test_a_package_found_in_several_sources_is_one_finding_with_its_lockfile_as_site(self):
        findings = self.findings()
        keys = [f['subject']['key'] for f in findings]
        self.assertEqual(len(keys), len(set(keys)))
        for finding in findings:
            self.assertIn(finding['kind'], KINDS)
            self.assertEqual(finding['method'], 'deterministic')
            paths = [path for path, _ in finding['sites']]
            if len(paths) > 1: self.assertNotIn('sbom.cdx.json', paths)

    def test_every_finding_names_its_severity_advisories_and_fix(self):
        for finding in self.findings():
            numbers = {m['name']: m['value'] for m in finding['measurements']}
            self.assertIn(numbers['severity'], osv_scanner.SEVERITIES)
            self.assertEqual(numbers['advisories'], len(numbers['advisory_ids']))
            self.assertIn('fixed_in', numbers)

    def test_the_fix_is_the_lowest_fixed_version_above_the_installed_one(self):
        advisory = {'affected': [{'package': {'name': 'p'}, 'ranges': [{'type': 'SEMVER', 'events': [
            {'introduced': '0'}, {'fixed': '1.2.3'}, {'introduced': '2.0.0'}, {'fixed': '2.0.5'}]}]}]}
        self.assertEqual(osv_scanner.fixed_in(advisory, 'p', '1.0.0'), '1.2.3')
        self.assertEqual(osv_scanner.fixed_in(advisory, 'p', '2.0.1'), '2.0.5')
        self.assertIsNone(osv_scanner.fixed_in(advisory, 'p', '1.5.0'))
        self.assertIsNone(osv_scanner.fixed_in(advisory, 'p', '1.10.0-rc.1'))

    def test_severity_comes_from_the_score_then_the_label(self):
        self.assertEqual([osv_scanner.score_severity(s) for s in ('9.8', '7.5', '5.0', '3.1', None)],
                         ['critical', 'high', 'medium', 'low', None])
        self.assertEqual(osv_scanner.label_severity('MODERATE'), 'medium')


class InventoryTests(Workspace):
    def test_declared_python_ranges_complete_the_sbom_and_say_they_are_not_locked(self):
        root = Path(self.tmp)
        (root / 'pyproject.toml').write_text('[project]\nname = "x"\ndependencies = ["pandas>=2.2", "Streamlit_Extras"]\n')
        (root / 'requirements.txt').write_text('# pinned\nrequests==2.31.0\n-r other.txt\npandas\n')
        sbom = {'components': [{'name': 'requests', 'version': '2.31.0'}]}
        self.assertEqual(syft.complete(sbom, root), 2)
        added = {c['name']: {p['name']: p['value'] for p in c['properties']} for c in sbom['components'][1:]}
        self.assertEqual(added['pandas'], {'eaos:declared': '>=2.2', 'eaos:source': 'pyproject.toml [project.dependencies]'})
        self.assertIn('streamlit-extras', added)


class RegistryTests(Workspace):
    def test_an_engine_runs_after_the_engines_it_reads(self):
        self.assertEqual(ordered(['osv-scanner', 'jscpd', 'syft']), ['jscpd', 'syft', 'osv-scanner'])

    def test_a_tool_with_nothing_to_read_is_not_applicable_not_absent(self):
        (Path(self.tmp) / 'app.py').write_text('print(1)\n')
        with mock.patch.object(tool, 'version', return_value='4.3.0'):
            report = tool.declined('sqlfluff', 'sqlfluff', self.tmp)
        self.assertEqual(report.status, NOT_APPLICABLE)
        with mock.patch.object(tool, 'version', return_value=None):
            self.assertEqual(tool.declined('sqlfluff', 'sqlfluff', self.tmp).status, 'unavailable')


class UpgradeCheckTests(Workspace):
    LOCK = {'name': 'f', 'version': '1.0.0', 'lockfileVersion': 3, 'requires': True,
            'packages': {'': {'name': 'f', 'version': '1.0.0', 'dependencies': {'picomatch': '2.3.1'}},
                         'node_modules/picomatch': {'version': '2.3.1', 'license': 'MIT'}}}

    def test_the_check_fails_before_the_upgrade_and_passes_after(self):
        if osv_scanner.version() is None or syft.version() is None: self.skipTest('syft and osv-scanner are not installed')
        from eaos.dependency_assessment import _check_argv
        root = Path(self.tmp)
        (root / 'package.json').write_text(json.dumps({'name': 'f', 'dependencies': {'picomatch': '2.3.1'}}))
        (root / 'package-lock.json').write_text(json.dumps(self.LOCK))
        argv = _check_argv('npm', 'picomatch', ['GHSA-3v7f-55p6-f55p', 'GHSA-c2c7-rcm5-vvqj'])
        before = subprocess.run(argv, cwd=root, capture_output=True).returncode
        if before == 2: self.skipTest('OSV database unreachable (no network)')
        self.assertEqual(before, 1)
        (root / 'package-lock.json').write_text(json.dumps(self.LOCK).replace('2.3.1', '2.3.2'))
        self.assertEqual(subprocess.run(argv, cwd=root, capture_output=True).returncode, 0)


class ClaimTests(Workspace):
    FACT = {'id': 'FACT-1', 'kind': 'engine_finding',
            'location': {'path': 'package-lock.json', 'line': None, 'symbol': 'npm:picomatch@2.3.1'},
            'value': {'engine': 'osv-scanner', 'kind': 'vulnerability', 'rule': 'osv.vulnerable_dependency',
                      'message': 'picomatch@2.3.1 (npm) has 2 known vulnerabilities, highest high; fixed in 2.3.2',
                      'measurements': [{'name': 'severity', 'value': 'high'}, {'name': 'fixed_in', 'value': '2.3.2'},
                                       {'name': 'advisory_ids', 'value': ['GHSA-a', 'GHSA-b']},
                                       {'name': 'advisories', 'value': 2}]}}

    def claims(self):
        from eaos.claims import from_facts
        return [c for c in from_facts({'external': {'facts': [self.FACT]}}, target=self.tmp)
                if (c.get('render') or {}).get('key') == 'vulnerable_dependency']

    def test_a_fixable_vulnerable_dependency_is_a_claim_whose_reviewer_is_the_rule(self):
        [claim] = self.claims()
        self.assertEqual(claim['confidence'], 'CONFIRMED')
        self.assertTrue(claim['assessment']['reviewed_by'].startswith('engagement rule upgrade_vulnerable_dependencies'))
        self.assertEqual(claim['checks'][0]['expected_exit'], 0)

    def test_the_claim_says_reachability_is_not_shown(self):
        from eaos.compose.labels import IMPACTS
        self.assertIn('not yet shown', IMPACTS['en']['vulnerable_dependency'])
        self.assertIn('لم يُثبت', IMPACTS['ar']['vulnerable_dependency'])

    def test_the_owner_can_turn_the_upgrade_rule_off(self):
        (Path(self.tmp) / 'eaos.engagement.json').write_text(json.dumps({'rules': {'upgrade_vulnerable_dependencies': False}}))
        [claim] = self.claims()
        self.assertNotIn('assessment', claim)

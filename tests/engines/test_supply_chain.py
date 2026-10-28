"""Syft and OSV-Scanner: a complete inventory, every vulnerable version found once, and a repair that is checked."""
import json
import subprocess
from pathlib import Path

from shared_fixture import Workspace

from eaos.engines import ordered
from eaos.engines.security import osv_scanner, syft
from eaos.engines.contract import KINDS
from eaos.engines.tool import version_of

CONTRACTS = Path(__file__).resolve().parents[1] / 'contracts'


def sample(name):
    return json.loads((CONTRACTS / f'{name}.json').read_text(encoding='utf-8'))


class OsvTests(Workspace):
    def test_the_pinned_samples_still_carry_what_the_adapters_read_and_each_package_is_one_finding(self):
        for module in (syft, osv_scanner):
            self.assertEqual(sample(module.NAME)['pinned_version'], module.PINNED, module.NAME)
        sbom = sample('syft')['sbom.cdx.json']
        self.assertEqual(sbom['bomFormat'], 'CycloneDX')
        self.assertTrue(all('name' in component for component in sbom['components']))
        for result in sample('osv-scanner')['osv.json']['results']:
            self.assertIn('path', result['source'])
            for package in result['packages']:
                self.assertLessEqual({'name', 'version', 'ecosystem'}, set(package['package']))
                for vulnerability in package['vulnerabilities']:
                    self.assertLessEqual({'id', 'affected'}, set(vulnerability))
        findings = osv_scanner.normalise(sample('osv-scanner')['osv.json'], Path('/project'), '2.6.0')
        keys = [f['subject']['key'] for f in findings]
        self.assertEqual(len(keys), len(set(keys)), 'a package found in several sources is one finding')
        for finding in findings:
            self.assertIn(finding['kind'], KINDS)
            self.assertEqual(finding['method'], 'deterministic')
            paths = [path for path, _ in finding['sites']]
            if len(paths) > 1: self.assertNotIn('sbom.cdx.json', paths)
            numbers = {m['name']: m['value'] for m in finding['measurements']}
            self.assertIn(numbers['severity'], osv_scanner.SEVERITIES)
            self.assertEqual(numbers['advisories'], len(numbers['advisory_ids']))
            self.assertIn('fixed_in', numbers)

    def test_the_fix_is_the_lowest_fixed_version_above_the_installed_one_and_severity_is_scored(self):
        advisory = {'affected': [{'package': {'name': 'p'}, 'ranges': [{'type': 'SEMVER', 'events': [
            {'introduced': '0'}, {'fixed': '1.2.3'}, {'introduced': '2.0.0'}, {'fixed': '2.0.5'}]}]}]}
        self.assertEqual(osv_scanner.fixed_in(advisory, 'p', '1.0.0'), '1.2.3')
        self.assertEqual(osv_scanner.fixed_in(advisory, 'p', '2.0.1'), '2.0.5')
        self.assertIsNone(osv_scanner.fixed_in(advisory, 'p', '1.5.0'))
        self.assertIsNone(osv_scanner.fixed_in(advisory, 'p', '1.10.0-rc.1'))
        self.assertEqual([osv_scanner.score_severity(s) for s in ('9.8', '7.5', '5.0', '3.1', None)],
                         ['critical', 'high', 'medium', 'low', None])
        self.assertEqual(osv_scanner.label_severity('MODERATE'), 'medium')


class InventoryTests(Workspace):
    def test_declared_python_ranges_complete_the_sbom_and_engines_run_in_the_order_they_read(self):
        root = Path(self.tmp)
        (root / 'pyproject.toml').write_text('[project]\nname = "x"\ndependencies = ["pandas>=2.2", "Streamlit_Extras"]\n')
        (root / 'requirements.txt').write_text('# pinned\nrequests==2.31.0\n-r other.txt\npandas\n')
        sbom = {'components': [{'name': 'requests', 'version': '2.31.0'}]}
        self.assertEqual(syft.complete(sbom, root), 2)
        added = {c['name']: {p['name']: p['value'] for p in c['properties']} for c in sbom['components'][1:]}
        self.assertEqual(added['pandas'], {'eaos:declared': '>=2.2', 'eaos:source': 'pyproject.toml [project.dependencies]'})
        self.assertIn('streamlit-extras', added)
        self.assertEqual(ordered(['osv-scanner', 'jscpd', 'syft']), ['jscpd', 'syft', 'osv-scanner'])


class UpgradeCheckTests(Workspace):
    LOCK = {'name': 'f', 'version': '1.0.0', 'lockfileVersion': 3, 'requires': True,
            'packages': {'': {'name': 'f', 'version': '1.0.0', 'dependencies': {'picomatch': '2.3.1'}},
                         'node_modules/picomatch': {'version': '2.3.1', 'license': 'MIT'}}}

    def test_the_check_fails_before_the_upgrade_and_passes_after(self):
        if version_of(osv_scanner) is None or version_of(syft) is None: self.skipTest('syft and osv-scanner are not installed')
        from eaos.analysis.assessments.dependencies import _check_argv
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
        from eaos.analysis.claims.ledger import from_facts
        return [c for c in from_facts({'external': {'facts': [self.FACT]}}, target=self.tmp)
                if (c.get('render') or {}).get('key') == 'vulnerable_dependency']

    def test_a_fixable_vulnerable_dependency_is_a_checked_claim_the_owner_can_turn_off(self):
        [claim] = self.claims()
        self.assertEqual(claim['confidence'], 'CONFIRMED')
        self.assertTrue(claim['assessment']['reviewed_by'].startswith('engagement rule upgrade_vulnerable_dependencies'))
        self.assertEqual(claim['checks'][0]['expected_exit'], 0)
        from eaos.core.language.words import IMPACTS
        self.assertIn('not yet shown', IMPACTS['en']['vulnerable_dependency'], 'reachability is not claimed')
        (Path(self.tmp) / 'eaos.engagement.json').write_text(json.dumps({'rules': {'upgrade_vulnerable_dependencies': False}}))
        [claim] = self.claims()
        self.assertNotIn('assessment', claim)

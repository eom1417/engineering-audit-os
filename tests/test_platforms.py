"""EAOS installs and runs on the computer it is on (a Mac as well as Linux), from its installed package alone."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos import toolchain

ROOT = Path(__file__).resolve().parents[1]


class PlatformTests(unittest.TestCase):
    def test_every_released_tool_has_a_build_for_linux_and_both_kinds_of_mac(self):
        for tool in toolchain.registry()['tools']:
            if tool['install']['method'] != 'release': continue
            platforms = tool['install'].get('platforms') or {}
            for key in ('linux-x86_64', 'darwin-arm64', 'darwin-x86_64'):
                self.assertIn(key, platforms, f"{tool['name']} has no {key} build")
                self.assertRegex(platforms[key]['sha256'], r'^[0-9a-f]{64}$', f"{tool['name']} {key}")

    def test_the_build_is_the_one_for_this_computer_and_none_is_a_skip_not_a_broken_install(self):
        syft = next(t for t in toolchain.registry()['tools'] if t['name'] == 'syft')
        with mock.patch.object(toolchain, 'platform_key', return_value='darwin-arm64'):
            self.assertIn('darwin_arm64', toolchain.release_spec(syft)['url'])
        with mock.patch.object(toolchain, 'platform_key', return_value='windows-arm64'), tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict('os.environ', {'EAOS_ENGINE_TOOLS': tmp}):
            with self.assertRaises(toolchain.Unavailable):
                toolchain.release_spec(syft)
            with mock.patch.object(toolchain, 'found_version', return_value=(None, 'not installed')):
                self.assertEqual(toolchain.install(names=['syft'], echo=lambda line: None), [], 'skipped, not failed')

    def test_tools_live_in_the_persons_home_not_a_fixed_folder(self):
        self.assertTrue(toolchain.registry()['home']['default'].startswith('~/'))
        with mock.patch.dict('os.environ', {'EAOS_ENGINE_TOOLS': ''}):
            self.assertEqual(toolchain.home(), Path.home() / '.eaos/tools')

    def test_the_engines_run_the_tools_eaos_installed(self):
        """`eaos tools install` and the engines that run the tools read the same folder."""
        from eaos.engines import process
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / 'bin/pinned-only-tool'
            binary.parent.mkdir()
            binary.write_text('#!/bin/sh\n')
            binary.chmod(0o755)
            with mock.patch.dict('os.environ', {'EAOS_ENGINE_TOOLS': tmp}):
                self.assertEqual(process.which('pinned-only-tool'), str(binary))

    def test_no_code_points_at_the_machine_eaos_was_built_on(self):
        """A clone or a fork on another computer finds everything: no path of the development server is written in code."""
        tracked = subprocess.run(['git', 'ls-files', 'eaos', 'tools', 'tests', 'acceptance', 'install.sh'], cwd=ROOT,
                                 capture_output=True, text=True, check=True).stdout.split()
        found = [name for name in tracked if name.endswith(('.py', '.sh'))
                 and '/workspace/' in (ROOT / name).read_text(encoding='utf-8', errors='replace')
                 and name != 'tests/test_platforms.py']
        self.assertEqual(found, [])


    def test_the_browser_lives_in_eaos_tools_folder_on_every_computer(self):
        with mock.patch.dict('os.environ', {'EAOS_ENGINE_TOOLS': '/opt/eaos-tools', 'PLAYWRIGHT_BROWSERS_PATH': ''}):
            self.assertEqual(toolchain.browsers(), Path('/opt/eaos-tools/browsers'))
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict('os.environ', {'EAOS_ENGINE_TOOLS': tmp, 'PLAYWRIGHT_BROWSERS_PATH': ''}):
            core = Path(tmp) / 'node/node_modules/playwright-core'
            core.mkdir(parents=True)
            (core / 'browsers.json').write_text(json.dumps({'browsers': [{'name': 'chromium', 'revision': '1243'}]}))
            self.assertEqual(toolchain.browser_missing(), 'chromium 1243 is not installed')
            (Path(tmp) / 'browsers/chromium-1243').mkdir(parents=True)
            self.assertEqual(toolchain.browser_missing(), '')

    def test_the_tool_is_found_in_any_archive_however_its_path_is_written(self):
        import io, tarfile, zipfile
        tool = {'name': 'demo', 'binary': 'demo'}
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as archive:        # reforge's Mac archive: ./demo
            info = tarfile.TarInfo('./demo'); data = b'binary'; info.size = len(data); archive.addfile(info, io.BytesIO(data))
        self.assertEqual(toolchain._member(tool, {'archive': 'tar.gz', 'member': './demo'}, buffer.getvalue()), b'binary')
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:                      # k6's Mac build is a zip
            archive.writestr('demo-v1-macos-arm64/demo', b'zipped')
        self.assertEqual(toolchain._member(tool, {'archive': 'zip', 'member': 'demo-v1-macos-arm64/demo'}, buffer.getvalue()), b'zipped')

    def test_one_tool_that_fails_never_stops_the_others(self):
        tools = [{'name': 'first', 'version': '1', 'stages': ['S01'], 'install': {'method': 'release'}},
                 {'name': 'second', 'version': '1', 'stages': ['S01'], 'install': {'method': 'pip'}}]
        installed = []
        with mock.patch.object(toolchain, 'selected', return_value=tools), tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict('os.environ', {'EAOS_ENGINE_TOOLS': tmp}), \
                mock.patch.object(toolchain, 'found_version', side_effect=lambda t: ('1', '') if t['name'] in installed else (None, '')), \
                mock.patch.object(toolchain, '_release', side_effect=KeyError('zip')), \
                mock.patch.object(toolchain, '_pip', side_effect=lambda t: installed.append(t['name'])):
            self.assertEqual(toolchain.install(echo=lambda line: None), ['first'])
        self.assertEqual(installed, ['second'])

    def test_each_npm_tool_has_its_own_folder_so_versions_never_clash(self):
        cruiser = {'name': 'dependency-cruiser'}
        self.assertEqual(toolchain.npm_prefix(cruiser).name, 'dependency-cruiser')
        self.assertNotEqual(toolchain.npm_prefix(cruiser), toolchain.npm_prefix({'name': 'renovate'}))
        self.assertEqual(toolchain.npm_prefix({'name': 'playwright'}), toolchain.home() / 'node')

    def test_a_tool_that_refuses_this_node_says_so_and_is_not_read_as_another_version(self):
        cruiser = next(t for t in toolchain.registry()['tools'] if t['name'] == 'dependency-cruiser')
        refusal = mock.Mock(returncode=1, stdout='', stderr='ERROR: node 20.20.2 is not supported; it requires ^22||^24||>=26')
        with mock.patch.object(toolchain, 'binary_path', return_value='/x/depcruise'), mock.patch.object(toolchain.subprocess, 'run', return_value=refusal):
            found, reason = toolchain.found_version(cruiser)
        self.assertIsNone(found)
        self.assertIn('needs a newer Node.js', reason)
        noisy = mock.Mock(returncode=0, stdout='node v20.20.2 detected\n18.4.0\n', stderr='')
        with mock.patch.object(toolchain, 'binary_path', return_value='/x/depcruise'), mock.patch.object(toolchain.subprocess, 'run', return_value=noisy), \
                mock.patch.object(toolchain, '_companions_missing', return_value=''):
            self.assertEqual(toolchain.found_version(cruiser), ('18.4.0', ''), 'its own version, wherever it is printed')

class VersionTests(unittest.TestCase):
    def test_one_version_everywhere_the_person_reads_it(self):
        import re
        from eaos import __version__
        package = re.search(r'^version = "([^"]+)"', (ROOT / 'pyproject.toml').read_text(encoding='utf-8'), re.M).group(1)
        changelog = re.search(r'^## (\d+\.\d+\.\d+)', (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8'), re.M).group(1)
        self.assertEqual((__version__, changelog), (package, package), 'eaos doctor, the package and the changelog say one version')


class InstalledPackageTests(unittest.TestCase):
    def test_an_installed_eaos_finds_everything_it_reads_without_the_repository(self):
        """Installed from a wheel into a fresh environment, away from this checkout: the tools list, the
        schemas and the error catalog all come from the package."""
        with tempfile.TemporaryDirectory() as tmp:
            venv = Path(tmp) / 'venv'
            # Without pip inside (ensurepip is not everywhere), filled by this pip with --python.
            subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(venv)], check=True)
            done = subprocess.run([sys.executable, '-m', 'pip', '--python', str(venv / 'bin/python'), 'install', '--quiet',
                                   '--no-deps', str(ROOT)], capture_output=True, text=True)
            if done.returncode: self.skipTest('pip could not build the package here: ' + done.stderr[-200:])
            probe = ('import json, eaos.toolchain as t, eaos.load_model as l, eaos.guided as g, eaos.artifact_contracts as a;'
                     'assert "site-packages" in str(t.REGISTRY), t.REGISTRY; print(len(t.registry()["tools"]));'
                     'l.load_schema(); g.catalog(); a.contracts()')
            ran = subprocess.run([str(venv / 'bin/python'), '-c', probe], capture_output=True, text=True, cwd=tmp)
            self.assertEqual(ran.returncode, 0, ran.stderr[-600:])
            self.assertGreater(int(ran.stdout.strip()), 20)


if __name__ == '__main__':
    unittest.main()

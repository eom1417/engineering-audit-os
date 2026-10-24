"""EAOS installs and runs on the computer it is on (a Mac as well as Linux), from its installed package alone."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.core import toolchain

ROOT = Path(__file__).resolve().parents[1]


class PlatformTests(unittest.TestCase):
    def test_every_released_tool_has_a_build_for_linux_and_mac_and_a_missing_build_is_a_skip(self):
        for tool in toolchain.registry()['tools']:
            if tool['install']['method'] != 'release': continue
            platforms = tool['install'].get('platforms') or {}
            for key in ('linux-x86_64', 'darwin-arm64', 'darwin-x86_64'):
                self.assertIn(key, platforms, f"{tool['name']} has no {key} build")
                self.assertRegex(platforms[key]['sha256'], r'^[0-9a-f]{64}$', f"{tool['name']} {key}")
        # The build is the one for this computer; none for it is a skip, not a broken install.
        syft = next(t for t in toolchain.registry()['tools'] if t['name'] == 'syft')
        with mock.patch.object(toolchain, 'platform_key', return_value='darwin-arm64'):
            self.assertIn('darwin_arm64', toolchain.release_spec(syft)['url'])
        with mock.patch.object(toolchain, 'platform_key', return_value='windows-arm64'), tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict('os.environ', {'EAOS_ENGINE_TOOLS': tmp}):
            with self.assertRaises(toolchain.Unavailable):
                toolchain.release_spec(syft)
            with mock.patch.object(toolchain, 'found_version', return_value=(None, 'not installed')):
                self.assertEqual(toolchain.install(names=['syft'], echo=lambda line: None), [], 'skipped, not failed')

    def test_tools_and_the_browser_live_in_the_persons_eaos_folder_where_the_engines_find_them(self):
        self.assertTrue(toolchain.registry()['home']['default'].startswith('~/'))
        with mock.patch.dict('os.environ', {'EAOS_ENGINE_TOOLS': ''}):
            self.assertEqual(toolchain.home(), Path.home() / '.eaos/tools')
        # `eaos tools install` and the engines that run the tools read the same folder.
        from eaos.engines import process
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / 'bin/pinned-only-tool'
            binary.parent.mkdir()
            binary.write_text('#!/bin/sh\n')
            binary.chmod(0o755)
            with mock.patch.dict('os.environ', {'EAOS_ENGINE_TOOLS': tmp}):
                self.assertEqual(process.which('pinned-only-tool'), str(binary))
        with mock.patch.dict('os.environ', {'EAOS_ENGINE_TOOLS': '/opt/eaos-tools', 'PLAYWRIGHT_BROWSERS_PATH': ''}):
            self.assertEqual(toolchain.browsers(), Path('/opt/eaos-tools/browsers'))
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict('os.environ', {'EAOS_ENGINE_TOOLS': tmp, 'PLAYWRIGHT_BROWSERS_PATH': ''}):
            core = Path(tmp) / 'node/node_modules/playwright-core'
            core.mkdir(parents=True)
            (core / 'browsers.json').write_text(json.dumps({'browsers': [{'name': 'chromium', 'revision': '1243'}]}))
            self.assertEqual(toolchain.browser_missing(), 'chromium 1243 is not installed')
            (Path(tmp) / 'browsers/chromium-1243').mkdir(parents=True)
            self.assertEqual(toolchain.browser_missing(), '')
        # Each npm tool has its own folder so versions never clash.
        cruiser = {'name': 'dependency-cruiser'}
        self.assertEqual(toolchain.npm_prefix(cruiser).name, 'dependency-cruiser')
        self.assertNotEqual(toolchain.npm_prefix(cruiser), toolchain.npm_prefix({'name': 'renovate'}))
        self.assertEqual(toolchain.npm_prefix({'name': 'playwright'}), toolchain.home() / 'node')

    def test_installing_finds_the_tool_in_any_archive_and_one_failure_never_stops_the_others(self):
        import io, tarfile, zipfile
        tool = {'name': 'demo', 'binary': 'demo'}
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as archive:        # reforge's Mac archive: ./demo
            info = tarfile.TarInfo('./demo'); data = b'binary'; info.size = len(data); archive.addfile(info, io.BytesIO(data))
        self.assertEqual(toolchain._member(tool, {'archive': 'tar.gz', 'member': './demo'}, io.BytesIO(buffer.getvalue())), b'binary')
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:                      # k6's Mac build is a zip
            archive.writestr('demo-v1-macos-arm64/demo', b'zipped')
        self.assertEqual(toolchain._member(tool, {'archive': 'zip', 'member': 'demo-v1-macos-arm64/demo'}, io.BytesIO(buffer.getvalue())), b'zipped')
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

class PortabilityTests(unittest.TestCase):
    def test_one_version_everywhere_and_no_code_points_at_the_machine_eaos_was_built_on(self):
        listed = subprocess.run(['git', 'ls-files', 'eaos', 'tools', 'tests', 'install.sh'], cwd=ROOT, capture_output=True, text=True)
        # Outside a git checkout (the check's isolated copy has no .git) the files on disk are the ones to read.
        tracked = listed.stdout.split() if listed.returncode == 0 else [
            p.relative_to(ROOT).as_posix() for folder in ('eaos', 'tools', 'tests') for p in (ROOT / folder).rglob('*')] + ['install.sh']
        found = [name for name in tracked if name.endswith(('.py', '.sh')) and (ROOT / name).is_file()
                 and '/workspace/' in (ROOT / name).read_text(encoding='utf-8', errors='replace')
                 and name != 'tests/test_platforms.py']
        self.assertEqual(found, [], 'a clone on another computer must find everything')
        import re
        from eaos import __version__
        package = re.search(r'^version = "([^"]+)"', (ROOT / 'pyproject.toml').read_text(encoding='utf-8'), re.M).group(1)
        changelog = re.search(r'^## (\d+\.\d+\.\d+)', (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8'), re.M).group(1)
        self.assertEqual((__version__, changelog), (package, package), 'eaos doctor, the package and the changelog say one version')
        badges = {name: re.findall(r'badge/version-([\d.]+)-', (ROOT / name).read_text(encoding='utf-8')) for name in ('README.md', 'README.ar.md')}
        self.assertEqual(badges, {name: [package] for name in badges}, "the READMEs' version badge (it read 0.0.28 at 0.0.35)")


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
            probe = ('import json, eaos.core.toolchain as t, eaos.analysis.load_model as l, eaos.journeys.guided as g, eaos.core.artifact_contracts as a;'
                     'assert "site-packages" in str(t.REGISTRY), t.REGISTRY; print(len(t.registry()["tools"]));'
                     'from pathlib import Path; import eaos;'
                     'assert (Path(eaos.__file__).parent / "data/schemas/load-model.schema.json").is_file();'
                     'g.catalog(); a.contracts()')
            ran = subprocess.run([str(venv / 'bin/python'), '-c', probe], capture_output=True, text=True, cwd=tmp)
            self.assertEqual(ran.returncode, 0, ran.stderr[-600:])
            self.assertGreater(int(ran.stdout.strip()), 20)


if __name__ == '__main__':
    unittest.main()

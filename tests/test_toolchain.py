"""One registry, one installer: a release is accepted only at its pinned hash, a tool only at its pinned version."""
import hashlib
import http.server
import io
import json
import os
import tarfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from shared_fixture import Workspace
from eaos.core import progress, toolchain
from eaos.engines import ADAPTERS
from eaos.pipeline.stages import ORDER, STAGES, _built_on


def tool(name, version, url, sha):
    return {'name': name, 'role': 'read', 'stages': ['S01'], 'license': 'MIT', 'repository': 'https://example.invalid',
            'version': version, 'binary': name,
            'install': {'method': 'release', 'url': url, 'sha256': sha, 'archive': 'tar.gz', 'member': name}}


class Ranged(http.server.BaseHTTPRequestHandler):
    """Serves `body`, honouring `Range: bytes=N-` as GitHub's release downloads do; records the starts asked for."""
    body, asked = b'', []

    def do_GET(self):
        start = int(self.headers.get('Range', 'bytes=0-')[6:].rstrip('-') or 0)
        type(self).asked.append(start)
        self.send_response(206 if start else 200)
        self.send_header('Content-Length', str(len(self.body) - start))
        self.end_headers()
        self.wfile.write(self.body[start:])

    def log_message(self, *args): pass


class ToolchainBase(Workspace):
    def setUp(self):
        super().setUp()
        self.home = Path(self.tmp) / 'tools'
        script = b'#!/bin/sh\necho "fake 1.2.3"\n'
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
            info = tarfile.TarInfo('fake'); info.size = len(script); info.mode = 0o755
            archive.addfile(info, io.BytesIO(script))
        self.archive = Path(self.tmp) / 'fake.tar.gz'
        self.archive.write_bytes(buffer.getvalue())
        self.sha = hashlib.sha256(buffer.getvalue()).hexdigest()
        self.registry_file = Path(self.tmp) / 'toolchain.json'
        self.saved = toolchain.pins.REGISTRY, os.environ.get('EAOS_ENGINE_TOOLS')
        toolchain.pins.REGISTRY = self.registry_file
        os.environ['EAOS_ENGINE_TOOLS'] = str(self.home)

    def tearDown(self):
        toolchain.pins.REGISTRY = self.saved[0]
        if self.saved[1] is None: os.environ.pop('EAOS_ENGINE_TOOLS', None)
        else: os.environ['EAOS_ENGINE_TOOLS'] = self.saved[1]
        super().tearDown()

    def write(self, *tools):
        self.registry_file.write_text(json.dumps({'schema_version': 1, 'home': {'env': 'EAOS_ENGINE_TOOLS', 'default': '/nowhere'},
                                                  'tools': list(tools)}))

    def fresh_home(self, name):
        self.home = Path(self.tmp) / name
        os.environ['EAOS_ENGINE_TOOLS'] = str(self.home)

    def needed(self, name, applies='all'):
        return {**tool(name, '1.2.3', self.archive.as_uri(), self.sha), 'check': 'engines', 'applies': applies}


class InstallTests(ToolchainBase):
    def test_a_release_is_installed_only_at_its_pinned_hash_and_ok_only_at_its_pinned_version(self):
        self.write(tool('fake', '1.2.3', self.archive.as_uri(), '0' * 64))
        self.assertEqual(toolchain.install(echo=lambda line: None), ['fake'])
        self.assertFalse((self.home / 'bin/fake').exists(), 'another hash is refused and nothing is installed')
        self.write(tool('fake', '1.2.3', self.archive.as_uri(), self.sha))
        self.assertEqual(toolchain.install(echo=lambda line: None), [])
        self.assertEqual([(row['name'], row['ok'], row['found']) for row in toolchain.doctor()['tools']], [('fake', True, '1.2.3')])
        self.write(tool('fake', '9.9.9', self.archive.as_uri(), self.sha))
        row = toolchain.doctor()['tools'][0]
        self.assertEqual((row['ok'], row['found']), (False, '1.2.3'))
        self.assertIn('pinned 9.9.9', row['reason'])
        # A tar.xz release is installed like a tar.gz.
        script = b'#!/bin/sh\necho "fake 1.2.3"\n'
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:xz') as archive:
            info = tarfile.TarInfo('dist/fake'); info.size = len(script); info.mode = 0o755
            archive.addfile(info, io.BytesIO(script))
        archive_path = Path(self.tmp) / 'fake.tar.xz'
        archive_path.write_bytes(buffer.getvalue())
        spec = tool('xz', '1.2.3', archive_path.as_uri(), hashlib.sha256(buffer.getvalue()).hexdigest())
        spec['install'].update(archive='tar.xz', member='fake')
        self.write(spec)
        self.assertEqual(toolchain.install(echo=lambda line: None), [])
        self.assertEqual(toolchain.doctor()['tools'][0]['found'], '1.2.3')

    def test_a_newer_version_replaces_the_older_one_on_disk(self):
        self.write(tool('fake', '1.2.3', self.archive.as_uri(), self.sha))
        self.assertEqual(toolchain.install(echo=lambda line: None), [])
        script, buffer = b'#!/bin/sh\necho "fake 2.0.0"\n', io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
            info = tarfile.TarInfo('fake'); info.size = len(script); info.mode = 0o755
            archive.addfile(info, io.BytesIO(script))
        newer = Path(self.tmp) / 'fake-2.tar.gz'
        newer.write_bytes(buffer.getvalue())
        self.write(tool('fake', '2.0.0', newer.as_uri(), hashlib.sha256(buffer.getvalue()).hexdigest()))
        self.assertEqual(toolchain.install(echo=lambda line: None), [])
        self.assertEqual(sorted(p.name for p in (self.home / 'releases').iterdir()), ['fake-2.0.0'])

    def test_a_download_goes_on_from_what_an_earlier_attempt_left(self):
        Ranged.body, Ranged.asked = self.archive.read_bytes(), []
        server = http.server.HTTPServer(('127.0.0.1', 0), Ranged)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        part = self.home / 'downloads' / 'fake-1.2.3.part'
        part.parent.mkdir(parents=True)
        part.write_bytes(Ranged.body[:40])
        self.write(tool('fake', '1.2.3', f'http://127.0.0.1:{server.server_port}/fake.tar.gz', self.sha))
        self.assertEqual(toolchain.install(echo=lambda line: None), [])
        self.assertEqual((Ranged.asked, part.exists()), ([40], False), 'only the rest was asked for, then checked whole')


class ToolEnvironment(unittest.TestCase):
    def test_a_python_tool_installs_with_its_companions_and_runs_without_the_pythonpath_of_eaos(self):
        # pip took a dependency EAOS carries as installed, so a fresh tools folder missed it (Semgrep without attrs), and
        # its version check then imported EAOS's own mcp 2 instead of Semgrep's mcp 1.
        from eaos.engines import process
        tool = {'name': 'semgrep', 'version': '1.0.0', 'binary': 'semgrep', 'install': {'method': 'pip', 'package': 'semgrep'}}
        done = mock.Mock(returncode=0, stdout='1.0.0', stderr='')
        # PYTHONSAFEPATH, set where the Studio runs, kept CodeQL's Python extractor from importing its own modules.
        with mock.patch.dict(os.environ, {'PYTHONPATH': '/eaos/site-packages', 'PYTHONSAFEPATH': '1'}), \
                mock.patch.object(toolchain.installers, 'uv', return_value=None), mock.patch.object(toolchain.installers, '_link'), \
                mock.patch.object(toolchain.versions, 'binary_path', return_value='/tools/bin/semgrep'), \
                mock.patch('subprocess.run', return_value=done) as run, mock.patch.object(process, 'run_command', run):
            toolchain.installers._pip_one(tool)
            toolchain.found_version(tool)
            process.run(['semgrep', '--version'])
        self.assertGreaterEqual(len(run.call_args_list), 3, 'pip, the version check and the engine run')
        for call in run.call_args_list:
            self.assertFalse({'PYTHONPATH', 'PYTHONSAFEPATH'} & set(call.kwargs['env']))
        # The lock's pytest needs ApprovalTests beside it in the same virtualenv.
        import tempfile
        tool = {'name': 'pytest', 'version': '9.1.1', 'binary': 'pytest',
                'install': {'method': 'pip', 'package': 'pytest', 'with': ['approvaltests==19.1.1']}}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {'EAOS_ENGINE_TOOLS': tmp}), \
                mock.patch.object(toolchain.installers, 'uv', return_value=None), mock.patch.object(toolchain.installers, '_link'), \
                mock.patch('subprocess.run') as run:
            (Path(tmp) / 'venv/bin').mkdir(parents=True)
            (Path(tmp) / 'venv/bin/python').touch()
            toolchain.installers._pip_one(tool)
            self.assertEqual(run.call_args.args[0][-2:], ['pytest==9.1.1', 'approvaltests==19.1.1'])
            packages = Path(tmp) / 'venv/lib/python3.12/site-packages'
            (packages / 'approvaltests-19.0.0.dist-info').mkdir(parents=True)
            self.assertEqual(toolchain.versions._companions_missing(tool), 'approvaltests 19.1.1 is not installed beside it (found 19.0.0)')
            (packages / 'approvaltests-19.0.0.dist-info').rename(packages / 'approvaltests-19.1.1.dist-info')
            self.assertEqual(toolchain.versions._companions_missing(tool), '')


class PreparingTests(ToolchainBase):
    """The install the Studio's "Preparing the tools" page shows, and what the check waits for."""

    def test_each_tool_is_a_stage_of_the_tools_flow_and_the_check_waits_only_for_those_it_needs_here(self):
        later = tool('later', '1.2.3', self.archive.as_uri(), self.sha)
        later['install']['member'] = 'fake'
        broken = {**self.needed('broken'), 'stages': ['S04']}
        broken['install'] = {**broken['install'], 'sha256': '0' * 64}
        self.write(later, broken, self.needed('fake', applies='python'))
        (Path(self.tmp) / 'a.py').write_text('')
        self.assertEqual(toolchain.install(echo=lambda line: None, project=self.tmp), ['broken'])
        state = progress.fold(progress.read(self.home, 'tools'))
        self.assertEqual([s['name'] for s in state['stages']], ['fake', 'broken', 'later'], "the check's first, then by stage")
        self.assertEqual({s['name']: s['state'] for s in state['stages']}, {'fake': 'ok', 'broken': 'failed', 'later': 'ok'})
        broken_row = state['stages'][1]
        self.assertIn('does not match the pinned', broken_row['reason'])
        self.assertEqual((broken_row['reason_code'], state['status'], state['stages'][0]['description']), ('tool_failed', 'INCOMPLETE', '1.2.3'))
        download, size = state['stages'][0]['steps'][0], self.archive.stat().st_size
        self.assertEqual((download['name'], download['done'], download['total']), ('download', size, size))
        # The check waits for the tools it needs here and only those.
        self.fresh_home('tools-2')
        self.write(self.needed('fake'), self.needed('knip', applies='js'), tool('later', '1.2.3', self.archive.as_uri(), self.sha))
        self.assertEqual(toolchain.readiness(['a.py'])['failed'], {'fake': 'not installed'}, 'never installed, and none runs')
        with toolchain.machine_lock():
            log = progress.ProgressLog(self.home, 'tools', pulse=False, sampler=None)
            log.started(toolchain.stages(toolchain.registry()['tools']), ['fake', 'knip', 'later'], {})
            self.assertEqual(toolchain.readiness(['a.py']), {'needed': ['fake'], 'pending': ['fake'], 'failed': {}, 'ready': False})
            log.ended({'stage': 'fake', 'status': 'ok', 'reason': '', 'seconds': 1, 'necessity': 'required', 'artifacts': []})
            self.assertTrue(toolchain.readiness(['a.py'])['ready'], "knip does not apply here, later is not the check's")
            self.assertEqual(toolchain.readiness(['a.ts'])['pending'], ['knip'])
        self.assertEqual(list(toolchain.readiness(['a.ts'])['failed']), ['knip'], 'the install is over without it')

    def test_a_second_start_installs_nothing_and_only_one_install_runs_at_a_time(self):
        self.write(self.needed('fake'))
        self.assertTrue(toolchain.stale(), 'nothing installed yet')
        toolchain.install(echo=lambda line: None)
        self.assertFalse(toolchain.stale())
        with mock.patch.object(toolchain.runs, '_spawn') as spawn:
            self.assertFalse(toolchain.prepare(self.tmp))
        spawn.assert_not_called()
        (self.home / 'bin/fake').unlink()
        self.assertTrue(toolchain.stale())
        toolchain.install(echo=lambda line: None)
        self.write(self.needed('fake') | {'version': '1.2.4'})
        self.assertTrue(toolchain.stale())
        # One install at a time on a computer; a Retry while it runs is kept for its end.
        self.fresh_home('tools-2')
        self.write(self.needed('fake'))
        child = mock.Mock(**{'poll.return_value': 0})
        with mock.patch.object(toolchain.runs, '_spawn', return_value=child) as spawn:
            with toolchain.machine_lock():
                self.assertTrue(toolchain.installing())
                self.assertFalse(toolchain.prepare(self.tmp))
            spawn.assert_not_called()
            self.assertTrue((self.home / 'install.again').exists(), 'a Retry while it runs is kept for its end')
            self.assertTrue(toolchain.prepare(self.tmp))
        self.assertEqual(spawn.call_args.args, (['tools', 'install', '--project', self.tmp], 'install.log'))
        self.assertFalse(toolchain.installing())

    def test_a_retry_asked_while_the_install_runs_tries_again_what_failed_once_it_ends(self):
        self.write(self.needed('fake'))
        attempts, real = [], toolchain.installers._release
        def flaky(tool, step):
            attempts.append(tool['name'])
            if len(attempts) == 1:
                (self.home / 'install.again').touch()           # Retry pressed while this install runs
                raise RuntimeError('no network')
            return real(tool, step)
        with mock.patch.object(toolchain.installers, '_release', side_effect=flaky):
            self.assertEqual(toolchain.install(echo=lambda line: None), [])
        self.assertEqual((attempts, (self.home / 'install.again').exists()), (['fake', 'fake'], False))
        self.assertEqual(progress.fold(progress.read(self.home, 'tools'))['status'], 'COMPLETE')

    def test_the_checks_tools_read_the_code_before_the_ai(self):
        toolchain.pins.REGISTRY = self.saved[0]
        check = {t['name']: t['check'] for t in toolchain.registry()['tools'] if t.get('check')}
        self.assertLessEqual(set(ADAPTERS), set(check), 'every engine adapter is a registered tool')
        self.assertLessEqual(set(check.values()), {'engines', 'architecture'})
        built_on = _built_on()               # an AI stage reading what the tools found comes after them
        ai = [ORDER.index(stage.name) for stage in STAGES if stage.ai and built_on[stage.name] & set(check.values())]
        self.assertTrue(ai and all(ORDER.index(stage) < min(ai) for stage in set(check.values())))


class AddedTools(ToolchainBase):
    def test_a_tool_the_person_adds_is_pinned_agreed_installed_and_runs_as_an_engine_with_no_python(self):
        # The owner (2026-10-22): the assistant must find a tool it lacks (GitHub) and add it, safely.
        from unittest import mock
        from eaos.core import tools_catalog
        from eaos.engines import sarif
        self.write()
        entry = {**tool('fake', '1.2.3', self.archive.as_uri(), self.sha), 'license': 'MIT', 'repository': 'https://github.com/o/fake',
                 'engine': {'args': ['{target}', '{output}']}}
        unsafe = {**entry, 'install': {**entry['install'], 'sha256': ''}, 'license': ''}
        self.assertEqual(tools_catalog.add(unsafe, True)['status'], 'refused', 'never without its sha256 and license')
        self.assertEqual(tools_catalog.add(entry)['status'], 'needs_agreement', 'never without the person')
        self.assertEqual(tools_catalog.add(entry, person_agreed=True)['status'], 'installed')
        self.assertEqual([t['name'] for t in toolchain.registry()['tools']], ['fake'], 'part of the one list')
        self.assertEqual(list(sarif.declared()), ['fake'])
        self.assertIn('already a tool', ' '.join(tools_catalog.problems(entry)))
        hits = {'items': [{'full_name': 'o/fake', 'html_url': 'https://github.com/o/fake', 'stargazers_count': 9, 'license': {'spdx_id': 'MIT'}}]}
        with mock.patch.object(tools_catalog, '_get', side_effect=[hits, {'tag_name': 'v1.2.3', 'assets': []}]):
            self.assertEqual(tools_catalog.find('fake checks')['candidates'][0]['license'], 'MIT')

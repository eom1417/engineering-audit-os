"""One registry, one installer: a release is accepted only at its pinned hash, a tool only at its pinned version."""
import hashlib
import io
import json
import os
import tarfile
import unittest
from pathlib import Path

from shared_fixture import Workspace
from eaos import toolchain


def tool(name, version, url, sha):
    return {'name': name, 'role': 'read', 'stages': ['S01'], 'license': 'MIT', 'repository': 'https://example.invalid',
            'version': version, 'binary': name,
            'install': {'method': 'release', 'url': url, 'sha256': sha, 'archive': 'tar.gz', 'member': name}}


class ToolchainTests(Workspace):
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
        self.saved = toolchain.REGISTRY, os.environ.get('EAOS_ENGINE_TOOLS')
        toolchain.REGISTRY = self.registry_file
        os.environ['EAOS_ENGINE_TOOLS'] = str(self.home)

    def tearDown(self):
        toolchain.REGISTRY = self.saved[0]
        if self.saved[1] is None: os.environ.pop('EAOS_ENGINE_TOOLS', None)
        else: os.environ['EAOS_ENGINE_TOOLS'] = self.saved[1]
        super().tearDown()

    def write(self, *tools):
        self.registry_file.write_text(json.dumps({'schema_version': 1, 'home': {'env': 'EAOS_ENGINE_TOOLS', 'default': '/nowhere'},
                                                  'tools': list(tools)}))

    def test_a_release_at_its_pinned_hash_is_installed_and_reported_ok(self):
        self.write(tool('fake', '1.2.3', self.archive.as_uri(), self.sha))
        self.assertEqual(toolchain.install(echo=lambda line: None), [])
        self.assertEqual([(row['name'], row['ok'], row['found']) for row in toolchain.doctor()['tools']], [('fake', True, '1.2.3')])

    def test_a_release_with_another_hash_is_refused_and_nothing_is_installed(self):
        self.write(tool('fake', '1.2.3', self.archive.as_uri(), '0' * 64))
        self.assertEqual(toolchain.install(echo=lambda line: None), ['fake'])
        self.assertFalse((self.home / 'bin/fake').exists())

    def test_a_tool_at_another_version_is_not_ok(self):
        self.write(tool('fake', '9.9.9', self.archive.as_uri(), self.sha))
        toolchain._release(tool('fake', '9.9.9', self.archive.as_uri(), self.sha))
        row = toolchain.doctor()['tools'][0]
        self.assertEqual((row['ok'], row['found']), (False, '1.2.3'))
        self.assertIn('pinned 9.9.9', row['reason'])

    def test_the_registry_names_every_adopted_adapter_and_pins_every_release(self):
        toolchain.REGISTRY = self.saved[0]
        names = {t['name'] for t in toolchain.registry()['tools']}
        record = json.loads((Path(__file__).resolve().parents[1] / 'docs/north-star.json').read_text())
        self.assertLessEqual({a['name'] for a in record['adopted_adapters']}, names)
        for row in toolchain.registry()['tools']:
            if row['install']['method'] == 'release': self.assertRegex(row['install']['sha256'], r'^[0-9a-f]{64}$', row['name'])

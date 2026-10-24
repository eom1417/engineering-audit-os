"""The eaos command: every command on the map, and the one-command check that never touches the project."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from eaos.interfaces import cli
from eaos.interfaces.command_groups import GROUPS, group_of
from eaos.pipeline import resume


def commands():
    captured = {}
    original = argparse.ArgumentParser.parse_args

    def spy(self, argv=None, namespace=None):
        captured['parser'] = self
        raise SystemExit(0)

    argparse.ArgumentParser.parse_args = spy
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(['--version'])
    except SystemExit:
        pass
    finally:
        argparse.ArgumentParser.parse_args = original
    return [a for a in captured['parser']._actions if isinstance(a, argparse._SubParsersAction)][0].choices


class CommandSurfaceTests(unittest.TestCase):
    def test_every_command_is_on_the_map_and_the_map_names_only_real_commands(self):
        known = set(commands())
        self.assertEqual(sorted(name for name in known if group_of(name) is None), [])
        for key, _, _, members in GROUPS:
            self.assertEqual(sorted(set(members) - known), [], f'group {key} lists commands that do not exist')


class AuditCommandTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.target = self.base / 'product'
        self.target.mkdir()
        (self.target / 'package.json').write_text('{"scripts":{"postinstall":"DO_NOT_EXECUTE"}}')
        (self.target / 'app.py').write_text('import store\n\n\ndef main():\n    return store.load()\n')
        (self.target / 'store.py').write_text('def load():\n    return 1\n')
        self.out = self.base / 'report'

    def call(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as printed, contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(list(args))
        return code, printed.getvalue()

    def test_the_check_reads_the_project_and_never_writes_it(self):
        before = {p.name: p.read_bytes() for p in self.target.iterdir()}
        code, printed = self.call('audit', str(self.target), '--out', str(self.out), '--skip', 'engines', '--lang', 'en')
        self.assertIn(code, (0, 2))
        summary = json.loads(printed)
        self.assertEqual(summary['stages']['claims'], 'ok')
        self.assertTrue(Path(summary['manifest']).is_file())
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.target.iterdir()})
        self.assertEqual(self.call('audit', str(self.target), '--out', str(self.target / 'audit'))[0], 2)
        self.assertFalse((self.target / 'audit').exists())

    def test_a_resume_reruns_nothing_finished_and_refuses_a_changed_project(self):
        self.call('audit', str(self.target), '--out', str(self.out), '--skip', 'engines', '--lang', 'en')
        first = json.loads((self.out / 'run-manifest.json').read_text())
        again = resume(str(self.target), str(self.out), skip=('engines',), language='en')
        self.assertEqual({n: r['status'] for n, r in again['stages'].items()}, {n: r['status'] for n, r in first['stages'].items()})
        (self.target / 'app.py').write_text('changed\n')
        with self.assertRaises(ValueError):
            resume(str(self.target), str(self.out))

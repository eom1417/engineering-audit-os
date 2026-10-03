"""Emitted files are judged by their own tool, and a missing tool is a failure, never a pass."""
import json
import shutil
import unittest
from pathlib import Path
from unittest import mock

from shared_fixture import Workspace

from eaos import emit as emitting, toolchain
from eaos.emit import Emitted, emit


def lint_available():
    home = toolchain.home()
    return (home / 'bin/markdownlint-cli2').exists() or shutil.which('markdownlint-cli2')


class EmitTests(Workspace):
    def rows(self):
        return json.loads((Path(self.tmp) / 'handover/validation.json').read_text())['files']

    def test_a_missing_validator_is_recorded_as_a_failure(self):
        with mock.patch('eaos.emit.validate.which', return_value=None):
            emit(self.tmp, validate=True)
        row = next(r for r in self.rows() if r['path'] == 'handover/README.md')
        self.assertFalse(row['ok'])
        self.assertEqual(row['reason'], 'validator unavailable: markdownlint-cli2')

    @unittest.skipUnless(lint_available(), 'markdownlint-cli2 is not installed: python -m eaos tools install')
    def test_the_handover_readme_passes_its_own_linter(self):
        (Path(self.tmp) / 'handover/k6').mkdir(parents=True)
        (Path(self.tmp) / 'handover/k6/load.js').write_text('export default function () {}\n')
        _, rows = emit(self.tmp, validate=True)
        self.assertTrue(rows[0]['ok'], rows[0])
        self.assertIn('`k6/load.js`', (Path(self.tmp) / 'handover/README.md').read_text())

    def test_the_index_runs_after_every_other_emitter(self):
        def other(report):
            (Path(report) / 'handover').mkdir(parents=True, exist_ok=True)
            (Path(report) / 'handover/otel.yaml').write_text('receivers: {}\n')
            return [Emitted('handover/otel.yaml', 'schema')]
        registry = {'handover-readme': emitting.handover_readme, 'otel': other}
        with mock.patch.dict(emitting.EMITTERS, registry, clear=True):
            written, _ = emit(self.tmp)
        self.assertEqual([item.path for item in written], ['handover/otel.yaml', 'handover/README.md'])
        self.assertIn('`otel.yaml`', (Path(self.tmp) / 'handover/README.md').read_text())

    def test_new_verdicts_replace_old_rows_and_keep_the_others(self):
        from eaos.emit.validate import record
        record(self.tmp, [{'path': 'a', 'tool': 't', 'ok': False}, {'path': 'b', 'tool': 't', 'ok': True}])
        record(self.tmp, [{'path': 'a', 'tool': 't', 'ok': True}])
        self.assertEqual([(r['path'], r['ok']) for r in self.rows()], [('a', True), ('b', True)])

    def test_only_runs_the_named_emitters(self):
        self.assertEqual(emit(self.tmp, only=['nothing'])[0], [])


if __name__ == '__main__':
    unittest.main()

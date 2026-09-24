"""NS17.T3 — EAOS writes files in a tool's own format, and that tool decides whether they are valid.

Interface this task must provide:
    python -m eaos emit REPORT_DIR [--only NAME] [--validate]        exit 0 when it ran, whatever the verdicts
      writes the files of every applicable emitter under REPORT_DIR, and with --validate runs each file's
      validator and writes REPORT_DIR/handover/validation.json (schemas/artifacts/handover-validation.schema.json)
    the first emitter is named handover-readme: it writes REPORT_DIR/handover/README.md, validated by
      markdownlint-cli2
    a validator that is not installed gives {"ok": false, "reason": "validator unavailable: <binary>"}
    binaries are looked up in $EAOS_ENGINE_TOOLS/bin first (default /workspace/engine-tools), then PATH
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))


class Emit(unittest.TestCase):
    def emit(self, report, env=None):
        return subprocess.run([sys.executable, '-m', 'eaos', 'emit', str(report), '--only', 'handover-readme', '--validate'],
                              cwd=ROOT, capture_output=True, text=True, env={**os.environ, **(env or {})})

    def validation(self, report):
        from contracts import contracts, validate
        data = json.loads((report / 'handover/validation.json').read_text(encoding='utf-8'))
        self.assertEqual(validate(data, contracts()['handover-validation']), [])
        return {row['path']: row for row in data['files']}

    def test_a_missing_validator_is_a_failure_not_a_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, tools = Path(tmp) / 'report', Path(tmp) / 'no-tools'
            report.mkdir(); (tools / 'bin').mkdir(parents=True)
            done = self.emit(report, {'EAOS_ENGINE_TOOLS': str(tools), 'PATH': '/usr/sbin:/sbin'})
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertTrue((report / 'handover/README.md').is_file())
            row = self.validation(report)['handover/README.md']
            self.assertFalse(row['ok'])
            self.assertIn('validator unavailable', row['reason'])

    def test_the_tool_accepts_what_eaos_wrote(self):
        tools = Path(os.environ.get('EAOS_ENGINE_TOOLS', '/workspace/engine-tools'))
        if not ((tools / 'bin/markdownlint-cli2').exists() or shutil.which('markdownlint-cli2')):
            self.fail('markdownlint-cli2 is not installed: run python -m eaos tools install --stage assessment (NS17.T1)')
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / 'report'; report.mkdir()
            done = self.emit(report)
            self.assertEqual(done.returncode, 0, done.stderr)
            row = self.validation(report)['handover/README.md']
            self.assertTrue(row['ok'], row)
            self.assertEqual(row['tool'], 'markdownlint-cli2')


if __name__ == '__main__':
    unittest.main()

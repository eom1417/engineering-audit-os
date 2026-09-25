"""NS14.T1 — the reports' style and structure are checked by tools, like code.

Interface this task must provide:
    eaos/rules/vale/.vale.ini            StylesPath pointing to eaos/rules/vale/styles, with the EAOS package on *.md
    eaos/rules/vale/styles/EAOS/*.yml    rules at level error; at least: vague words in Arabic and English
                                        (ربما، إلخ، بشكل عام، تحسين عام; maybe, etc., generally, various)
    eaos/rules/.markdownlint-cli2.jsonc  the structure rules the four reports follow
    `vale --config eaos/rules/vale/.vale.ini --output JSON FILE` reports EAOS.* errors on vague text and none on
    evidenced text; `markdownlint-cli2 --config eaos/rules/.markdownlint-cli2.jsonc FILE` passes evidenced text.
"""
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STYLE = Path(__file__).parent / 'fixtures/style'
TOOLS = Path(os.environ.get('EAOS_ENGINE_TOOLS', '/workspace/engine-tools')) / 'bin'


def binary(name):
    found = TOOLS / name if (TOOLS / name).exists() else shutil.which(name)
    if not found: raise AssertionError(f'{name} is not installed: run python -m eaos tools install --stage assessment')
    return str(found)


class Style(unittest.TestCase):
    def vale(self, name):
        done = subprocess.run([binary('vale'), '--config', str(ROOT / 'eaos/rules/vale/.vale.ini'), '--output', 'JSON',
                               str(STYLE / name)], capture_output=True, text=True)
        alerts = [a for rows in json.loads(done.stdout or '{}').values() for a in rows]
        return [a for a in alerts if a['Check'].startswith('EAOS.') and a['Severity'] == 'error']

    def test_vague_text_is_rejected_in_both_languages(self):
        errors = self.vale('vague.md')
        lines = {a['Line'] for a in errors}
        self.assertIn(3, lines, errors)
        self.assertIn(5, lines, errors)

    def test_evidenced_text_passes_both_checks(self):
        self.assertEqual(self.vale('clear.md'), [])
        done = subprocess.run([binary('markdownlint-cli2'), '--config', str(ROOT / 'eaos/rules/.markdownlint-cli2.jsonc'),
                               str(STYLE / 'clear.md')], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == '__main__':
    unittest.main()

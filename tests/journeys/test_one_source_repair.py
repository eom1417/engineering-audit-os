"""The fix proof's sound repair of one source per pattern (tools/fix_proof.py `one_source`, M15.7) keeps every contract it
touches: the golden trial checks that the invoice calls the one source, this checks the lines, totals, prices and the
file to download are the same before and after, a missing quantity counted as one in the report and the export and as
none in the invoice, an explicit zero as each counted it before."""
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'tests/fixtures/baseline-app'
CASES = [[], [{'item': 'a', 'price': 2, 'quantity': 2}, {'item': 'b', 'price': 1}],
         [{'item': 'z', 'price': '3.333', 'quantity': 0}, {'item': 'm', 'price': 5}],
         [{'item': 'n', 'price': 'x', 'quantity': '3'}, {'item': 'q', 'price': 1.005, 'quantity': '2'}],
         [{'item': 'o', 'price': 10, 'quantity': None, 'owner': 'u'}, {'item': 'p', 'price': 0.1, 'quantity': 3}]]
PROBE = """const d = process.argv[1], cases = JSON.parse(process.argv[2]);
const { orderLines } = require(d + '/report'), { exportLines, exportFile } = require(d + '/export'), { invoiceLines } = require(d + '/invoice');
console.log(JSON.stringify(cases.map(c => [orderLines(c), exportLines(c), exportFile(c), invoiceLines(c)])));"""


def fix_proof():
    with mock.patch.dict(os.environ), mock.patch.object(sys, 'path', [str(ROOT / 'tools'), *sys.path]):
        return importlib.import_module('fix_proof')


def outputs(app):
    return json.loads(subprocess.run(['node', '-e', PROBE, str(app), json.dumps(CASES)], capture_output=True, text=True, check=True).stdout)


@unittest.skipUnless(shutil.which('node'), 'node runs the baseline app')
class SoundRepair(unittest.TestCase):
    def test_the_one_source_repair_keeps_the_report_the_export_and_the_invoice_as_they_were(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / 'app'
            shutil.copytree(APP, app)
            before = outputs(app)
            for edit in fix_proof().one_source(app):
                file = app / edit['path']
                text = file.read_text(encoding='utf-8')
                self.assertEqual(text.count(edit['find']), 1, edit['path'])
                file.write_text(text.replace(edit['find'], edit['replace']), encoding='utf-8')
            self.assertIn('orderLines(orders, 0)', (app / 'invoice.js').read_text(encoding='utf-8'))
            self.assertEqual(outputs(app), before)
        missing, zero = before[1], before[2]
        self.assertEqual((missing[0]['total'], missing[3]['total']), ('5.00', '4.00'), 'a missing quantity: one, and none in the invoice')
        self.assertEqual((zero[0]['lines'][1]['quantity'], zero[3]['lines'][1]['quantity']), (1, 0), 'a zero as each counted it')


if __name__ == '__main__':
    unittest.main()

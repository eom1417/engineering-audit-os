"""Structural-duplicate noise from JSX UI components and small shared-method clusters
must not reach the ledger as a business-rule claim.

A structural duplicate is reported when:
- The same code shape repeats across at least 6 distinct files (DUPLICATE_MIN); below
  this threshold it is a common idiom (an arrow function calling setState and rendering a
  button is not a duplicated business rule), and reporting it would drown the reader.
- Vendored UI libraries (shadcn's components/ui) are excluded from every extractor, so they
  do not produce duplicate-cluster facts in the first place.
"""
import json
import tempfile
import unittest
import shared_fixture  # noqa: F401  (runs without measured detector verdicts)
from pathlib import Path

from eaos.dossier import assemble


def _setup(tmp, file_count, body, fn_name='compute_total'):
    repo = Path(tmp) / 'repo'; repo.mkdir()
    for i in range(file_count):
        (repo / f'{chr(97 + i)}.py').write_text(f'def {fn_name}_{i}(items):\n' + body)
    out = Path(tmp) / 'out'
    assemble(repo, out)
    return repo, out


class StructuralDuplicateThresholdTests(unittest.TestCase):
    """Six or more occurrences make the cluster an engineering claim; fewer stay a fact."""

    def test_two_copies_of_a_function_are_not_a_claim(self):
        body = (
            '    total = sum(x.amount for x in items)\n'
            '    if items.tier == "premium":\n'
            '        total = total * 0.9\n'
            '    tax = total * 0.15\n'
            '    return round(total + tax, 2)\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            _, out = _setup(tmp, 2, body)
            claims = json.loads((out / 'dossier.json').read_text())['claims']
            dups = [c for c in claims if 'same structure' in c.get('statement', '')]
            self.assertEqual(dups, [])

    def test_five_copies_are_still_too_few(self):
        body = (
            '    total = sum(x.amount for x in items)\n'
            '    if items.tier == "premium":\n'
            '        total = total * 0.9\n'
            '    tax = total * 0.15\n'
            '    return round(total + tax, 2)\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            _, out = _setup(tmp, 5, body)
            claims = json.loads((out / 'dossier.json').read_text())['claims']
            dups = [c for c in claims if 'same structure' in c.get('statement', '')]
            self.assertEqual(dups, [])

    def test_six_copies_become_a_claim(self):
        body = (
            '    total = sum(x.amount for x in items)\n'
            '    if items.tier == "premium":\n'
            '        total = total * 0.9\n'
            '    tax = total * 0.15\n'
            '    return round(total + tax, 2)\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            _, out = _setup(tmp, 6, body)
            claims = json.loads((out / 'dossier.json').read_text())['claims']
            dups = [c for c in claims if 'same structure' in c.get('statement', '')]
            self.assertEqual(len(dups), 1)
            self.assertEqual(dups[0]['confidence'], 'CONFIRMED')


class VendoredUiExclusionTests(unittest.TestCase):
    """shadcn-style UI files do not produce fingerprint facts and so cannot create claims."""

    def test_components_ui_files_are_excluded_by_default(self):
        body = (
            'import * as React from "react";\n'
            'export function Button(props) {\n'
            '    const [open, setOpen] = React.useState(false);\n'
            '    return <button onClick={() => setOpen(!open)}>{props.label}</button>;\n'
            '}\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'repo'; repo.mkdir()
            (repo / 'src/components/ui').mkdir(parents=True)
            for name in ['button', 'dialog', 'input', 'label', 'menu', 'tab']:
                (repo / 'src/components/ui' / f'{name}.tsx').write_text(body.replace('Button', name.capitalize()))
            out = Path(tmp) / 'out'
            assemble(repo, out)
            # The fingerprint set must be empty: vendored UI files do not produce facts.
            facts = []
            for path in (out / 'facts').glob('*.json'):
                facts += json.loads(path.read_text()).get('facts', [])
            ui_fingerprints = [f for f in facts
                                if f['kind'] == 'fingerprint'
                                and 'components/ui' in f['location']['path']]
            self.assertEqual(ui_fingerprints, [])

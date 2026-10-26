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

from eaos.analysis.understanding.dossier import assemble


def _setup(tmp, file_count, body, fn_name='compute_total'):
    repo = Path(tmp) / 'repo'; repo.mkdir()
    for i in range(file_count):
        (repo / f'{chr(97 + i)}.py').write_text(f'def {fn_name}_{i}(items):\n' + body)
    out = Path(tmp) / 'out'
    assemble(repo, out)
    return repo, out


BODY = ('    total = sum(x.amount for x in items)\n'
        '    if items.tier == "premium":\n'
        '        total = total * 0.9\n'
        '    tax = total * 0.15\n'
        '    return round(total + tax, 2)\n')


class StructuralDuplicateThresholdTests(unittest.TestCase):
    """A function copied whole is a claim from two copies; a small shared shape needs six (common noise below that)."""

    def test_a_function_copied_whole_is_a_claim_from_two_copies_and_a_small_shape_needs_six(self):
        small = '    total = sum(x.amount for x in items)\n    return total\n'
        for body, copies, statement, expected in ((BODY, 2, 'copied whole', 1), (small, 5, 'same structure', 0),
                                                  (small, 6, 'same structure', 1)):
            with self.subTest(copies=copies, statement=statement), tempfile.TemporaryDirectory() as tmp:
                _, out = _setup(tmp, copies, body)
                claims = json.loads((out / 'dossier.json').read_text())['claims']
                dups = [c for c in claims if statement in c.get('statement', '')]
                self.assertEqual(len(dups), expected)
                self.assertTrue(all(c['confidence'] == 'CONFIRMED' for c in dups))


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

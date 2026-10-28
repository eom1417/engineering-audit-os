"""Vendored UI libraries (shadcn's components/ui) are excluded from every extractor, so they do not produce
duplicate-cluster facts in the first place."""
import json
import tempfile
import unittest
import shared_fixture  # noqa: F401  (runs without measured detector verdicts)
from pathlib import Path

from eaos.analysis.understanding.dossier import assemble


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

"""Decisions as MADR files: the sections every reader knows, one file per decision, accepted by markdownlint."""
from pathlib import Path

from shared_fixture import Workspace

from eaos.adr import render, write_all

DECISION = {'id': 'ADR-007', 'component_id': 'T-src', 'problem': 'It breaks two layer rules. ' * 8,
            'evidence': ['CLM-1', 'FACT-2'], 'options': ['Move 3 file(s) into `features`.', 'Add an adapter.', 'Do nothing.'],
            'chosen': 'Move 3 file(s) into `features`.', 'tradeoffs': 'The component has one cycle.',
            'consequences': ['It stays traceable.'], 'migration': ['Record the contract.', 'Move the files.']}


class AdrTests(Workspace):
    def test_the_madr_sections_are_there_in_order(self):
        text = render(DECISION)
        order = [text.index(h) for h in ('## Context and Problem Statement', '## Considered Options', '## Decision Outcome',
                                         '### Consequences', '### When to Revisit')]
        self.assertEqual(order, sorted(order))
        self.assertIn('Chosen option: "Move 3 file(s) into `features`.", because the component has one cycle.', text.replace('\n', ' '))

    def test_every_line_fits_eighty_columns_unless_one_word_is_longer(self):
        for line in render(DECISION).splitlines():
            self.assertTrue(len(line) <= 80 or ' ' not in line.strip()[:81], line)

    def test_one_file_per_decision_and_stale_files_go(self):
        folder = Path(self.tmp) / 'adr'
        folder.mkdir()
        (folder / 'ADR-999.md').write_text('old\n')
        self.assertEqual(write_all(self.tmp, [DECISION]), ['ADR-007.md'])
        self.assertFalse((folder / 'ADR-999.md').exists())

    def test_markdownlint_accepts_the_file(self):
        from eaos.emit import emit
        from eaos.engines.process import which
        if not which('markdownlint-cli2'): self.skipTest('markdownlint-cli2 is not installed')
        write_all(self.tmp, [DECISION])
        _, rows = emit(self.tmp, only=['adr'], validate=True)
        self.assertEqual([r['ok'] for r in rows], [True], rows)

"""C4 models and MADR decisions written from the records."""
import json
import re
from pathlib import Path

from shared_fixture import Workspace

from eaos.analysis.maps import c4
from eaos.report.target_architecture.adr import render, write_all
from eaos.analysis.maps.c4 import quote, workspace, write

DECISION = {'id': 'ADR-007', 'component_id': 'T-src', 'problem': 'It breaks two layer rules. ' * 8,
            'evidence': ['CLM-1', 'FACT-2'], 'options': ['Move 3 file(s) into `features`.', 'Add an adapter.', 'Do nothing.'],
            'chosen': 'Move 3 file(s) into `features`.', 'tradeoffs': 'The component has one cycle.',
            'consequences': ['It stays traceable.'], 'migration': ['Record the contract.', 'Move the files.']}


class C4Tests(Workspace):
    def report(self):
        out = Path(self.tmp)
        (out / 'facts').mkdir()
        (out / 'target-architecture.json').write_text(json.dumps({
            'reference': 'react-vite-spa-rest',
            'current_components': [{'id': 'T-src', 'name': 'src', 'origin': 'src', 'depends_on': ['src/lib'], 'relation': 'modify', 'reason': 'r'},
                                   {'id': 'T-lib', 'name': 'src/lib', 'origin': 'src/lib', 'depends_on': [], 'relation': 'retain', 'reason': 'r'}],
            'target_components': [{'name': 'feature:fleet', 'responsibility': 'fleet', 'layer': 'features'},
                                  {'name': 'api-client', 'responsibility': 'http', 'layer': 'data-access'}],
            'target_edges': [{'from': 'feature:fleet', 'to': 'api-client', 'imports': 3}]}))
        return out

    def test_names_are_quoted_and_escaped_and_identifiers_are_plain(self):
        dsl, mermaid = workspace('p', 'stack', [('a "quoted" name', 'd'), ('feature:x', 'e')], [('feature:x', 'a "quoted" name', 'uses')], [])
        self.assertIn(quote('a "quoted" name'), dsl)
        self.assertIn('\\"quoted\\"', dsl)
        self.assertEqual(dsl.count('{'), dsl.count('}'))
        for identifier in re.findall(r'^\s*(\w+) = ', dsl, re.M): self.assertRegex(identifier, r'^[A-Za-z0-9_]+$')
        self.assertIn('c2 -> c1 "uses"', dsl)
        self.assertTrue(mermaid.startswith('flowchart LR'))

    def test_every_current_and_target_component_is_in_its_model_with_its_dependencies(self):
        out = self.report()
        written = [str(getattr(entry, 'path', entry)) for entry in write(out)]
        self.assertTrue(any(name.endswith('architecture/current/workspace.dsl') for name in written), written)
        self.assertTrue(any(name.endswith('architecture/target/workspace.dsl') for name in written), written)
        current = (out / 'architecture/current/workspace.dsl').read_text()
        target = (out / 'architecture/target/workspace.dsl').read_text()
        self.assertIn('component "src"', current)
        self.assertIn('c1 -> c2 "depends on"', current)
        self.assertIn('component "feature:fleet"', target)
        self.assertIn('c1 -> c2 "3 import(s)"', target)
        self.assertTrue((out / 'architecture/target/diagram.mmd').is_file())
        # The reports stage draws the diagrams before CURRENT-STATE embeds one: a previous check's diagram (the
        # self-audit's built eaos/data/studio/assets) never reaches the page.
        from types import SimpleNamespace
        from eaos.pipeline.runners.by_rules import reports
        (out / 'architecture/current/diagram.mmd').write_text('flowchart LR\n  stale["eaos/data/studio/assets"]\n')
        reports(SimpleNamespace(out=out, language='en', target=out.parent))
        page = (out / 'CURRENT-STATE.md').read_text()
        self.assertNotIn('studio/assets', page)
        self.assertIn((out / 'architecture/current/diagram.mmd').read_text().strip().splitlines()[1].strip(), page)

    def test_a_crowded_diagram_keeps_the_strongest_links_and_says_so(self):
        names = [f'p{i}' for i in range(30)]
        edges = [(a, b, i * 30 + j) for i, a in enumerate(names) for j, b in enumerate(names) if a != b]
        text = c4.readable(names, edges, {}, limit=150)
        self.assertEqual(text.count('-->'), 150)
        self.assertIn('%% 720 of the 870 links are left out', text)
        first = next(line for line in text.splitlines() if '-->' in line)
        self.assertIn(f'|{max(n for _, _, n in edges)} imports|', first, 'the strongest link comes first')


class AdrTests(Workspace):
    def test_a_decision_is_one_madr_file_with_its_sections_in_order_and_lines_that_fit(self):
        text = render(DECISION)
        order = [text.index(h) for h in ('## Context and Problem Statement', '## Considered Options', '## Decision Outcome',
                                         '### Consequences', '### When to Revisit')]
        self.assertEqual(order, sorted(order))
        self.assertIn('Chosen option: "Move 3 file(s) into `features`.", because the component has one cycle.', text.replace('\n', ' '))
        for line in text.splitlines():
            self.assertTrue(len(line) <= 80 or ' ' not in line.strip()[:81], line)
        folder = Path(self.tmp) / 'adr'
        folder.mkdir()
        (folder / 'ADR-999.md').write_text('old\n')
        self.assertEqual(write_all(self.tmp, [DECISION]), ['ADR-007.md'])
        self.assertFalse((folder / 'ADR-999.md').exists())

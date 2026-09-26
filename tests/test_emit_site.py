"""The handover site: the reports, decisions, architecture and runbooks, built by Zensical with no broken link."""
import unittest

from shared_fixture import Workspace
import kit_fixture

from eaos.emit import emit, handover_site
from eaos.emit.engines_check import installed


class SiteTests(Workspace):
    def test_links_follow_the_site_and_a_document_it_does_not_carry_becomes_code(self):
        mapping = {'CURRENT-STATE.md': 'reports/CURRENT-STATE.md', 'ROADMAP.md': 'reports/ROADMAP.md',
                   'adr/ADR-001.md': 'adr/ADR-001.md', 'adr/ADR-002.md': 'adr/ADR-002.md'}
        text = handover_site.relink('[r](ROADMAP.md) [a](adr/ADR-001.md) [g](EXECUTION-GUIDE.md) [w](https://x.org)',
                                    'CURRENT-STATE.md', mapping)
        self.assertEqual(text, '[r](ROADMAP.md) [a](../adr/ADR-001.md) g (`EXECUTION-GUIDE.md`) [w](https://x.org)')
        self.assertEqual(handover_site.relink('[n](ADR-002.md)', 'adr/ADR-001.md', mapping), '[n](ADR-002.md)')

    def test_the_site_carries_the_reports_the_decisions_the_architecture_and_the_runbooks(self):
        _, report = kit_fixture.build(self.tmp)
        emit(report, only=['readiness', 'site'])
        docs = report / 'handover/docs'
        for page in ('index.md', 'reports/CURRENT-STATE.md', 'reports/ROADMAP.md', 'adr/ADR-001.md',
                     'architecture/target.md', 'runbooks/operate.md', 'runbooks/rollback.md', 'runbooks/incident.md'):
            self.assertTrue((docs / page).is_file(), page)
        self.assertIn('```mermaid', (docs / 'architecture/target.md').read_text())
        self.assertIn('Vercel', (docs / 'runbooks/rollback.md').read_text())
        self.assertIn('RDY-07', (docs / 'runbooks/operate.md').read_text())

    @unittest.skipUnless(installed('zensical'), 'zensical is not installed: python -m eaos tools install')
    def test_zensical_builds_it_in_strict_mode(self):
        _, report = kit_fixture.build(self.tmp)
        written, rows = emit(report, only=['readiness', 'site'], validate=True)
        site = next(r for r in rows if r['path'] == 'handover/mkdocs.yml')
        self.assertTrue(site['ok'], site)
        self.assertIn('--strict', site['command'])


if __name__ == '__main__':
    unittest.main()

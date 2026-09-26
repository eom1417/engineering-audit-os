"""The readiness kit: what a running release must show, and a checklist in which every item is a command."""
import json
import unittest
from unittest import mock

from shared_fixture import Workspace
import kit_fixture

from eaos.emit import emit, readiness
from eaos.emit.engines_check import installed
from eaos.emit.project import profile


class ReadinessTests(Workspace):
    def test_the_port_and_health_route_come_from_the_start_command_and_the_features(self):
        _, report = kit_fixture.build(self.tmp)
        text = readiness.goss(profile(report))
        self.assertIn('"tcp:4173"', text)                        # vite preview
        self.assertIn('"http://localhost:4173/health"', text)    # a route named health
        self.assertIn('dist/index.html', text)

    def test_a_python_streamlit_app_listens_on_its_default_port(self):
        _, report = kit_fixture.build(self.tmp, 'python')
        self.assertIn('"tcp:8501"', readiness.goss(profile(report)))

    def test_items_apply_by_the_facts_and_every_one_has_a_command(self):
        _, report = kit_fixture.build(self.tmp)
        items = readiness.checklist(profile(report), report)['items']
        ids = [item['id'] for item in items]
        self.assertIn('RDY-07', ids)       # Supabase is Postgres: backup and restore
        self.assertNotIn('RDY-08', ids)    # no sqlite
        self.assertNotIn('RDY-09', ids)    # no Docker
        self.assertTrue(all(item['command'].strip() for item in items))
        _, python_report = kit_fixture.build(f'{self.tmp}/py', 'python')
        self.assertIn('RDY-08', [item['id'] for item in readiness.checklist(profile(python_report), python_report)['items']])

    def test_an_item_whose_command_is_empty_is_refused(self):
        _, report = kit_fixture.build(self.tmp)
        rules = {'items': [{'id': 'RDY-X', 'title': 'x', 'applies': 'all', 'command': ' ', 'why': 'x'}]}
        with mock.patch.object(readiness.Path, 'read_text', return_value=json.dumps(rules)):
            with self.assertRaises(ValueError):
                readiness.checklist(profile(report), report)

    @unittest.skipUnless(installed('goss'), 'goss is not installed: python -m eaos tools install')
    def test_both_files_are_accepted(self):
        _, report = kit_fixture.build(self.tmp)
        written, rows = emit(report, only=['readiness'], validate=True)
        self.assertEqual([r['path'] for r in rows if not r['ok']], [], rows)


if __name__ == '__main__':
    unittest.main()

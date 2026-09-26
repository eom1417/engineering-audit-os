"""The observability kit: a Collector that writes no address, what to instrument, and SLOs from the scenarios."""
import unittest

from shared_fixture import Workspace
import kit_fixture

from eaos.emit import emit, observability
from eaos.emit.engines_check import installed
from eaos.emit.project import profile


class ObservabilityTests(Workspace):
    def test_production_is_an_environment_variable_never_a_written_address(self):
        text = observability.collector()
        self.assertIn('${env:OTEL_EXPORTER_OTLP_ENDPOINT', text)
        self.assertIn('file/sandbox', text)
        self.assertNotRegex(text.split('otlp/production')[1], r'https?://')

    def test_one_slo_per_measurable_scenario_with_its_objective(self):
        _, report = kit_fixture.build(self.tmp)
        objectives = {s['name']: s['objective'] for s in observability.slos(profile(report), 'demo')}
        self.assertEqual(objectives, {'latency': 95.0, 'errors': 99.0, 'availability': 99.5})

    def test_only_critical_surfaces_must_carry_a_span(self):
        _, report = kit_fixture.build(self.tmp)
        self.assertEqual(observability.critical_surfaces(profile(report)), [('home', '/'), ('home', '/health')])

    @unittest.skipUnless(installed('otelcol-contrib', 'sloth', 'markdownlint-cli2'), 'otelcol-contrib, sloth or markdownlint-cli2 is not installed')
    def test_every_file_is_accepted_by_its_own_tool_in_both_stacks(self):
        for stack in ('js', 'python'):
            _, report = kit_fixture.build(f'{self.tmp}/{stack}', stack)
            written, rows = emit(report, only=['observability'], validate=True)
            self.assertEqual(len(rows), 3, stack)
            self.assertEqual([r['path'] for r in rows if not r['ok']], [], rows)


if __name__ == '__main__':
    unittest.main()

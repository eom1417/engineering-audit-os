"""The per-file table: every number from a recorded fact, its source named, and an unknown never a zero."""
import json
from pathlib import Path

from shared_fixture import Workspace

from eaos.artifact_contracts import contracts, validate
from eaos.measurements import build


def fact(kind, path, value, **location):
    return {'kind': kind, 'location': {'path': path, **location}, 'value': value}


class MeasurementTests(Workspace):
    def report(self, facts, engines=('scc', 'jscpd'), verification=None):
        out = Path(self.tmp)
        (out / 'facts').mkdir(exist_ok=True)
        (out / 'facts/all.json').write_text(json.dumps({'facts': facts}))
        (out / 'facts/external.json').write_text(json.dumps({'facts': [], 'summary': {'engines_observed': list(engines)}}))
        if verification is not None: (out / 'verification.json').write_text(json.dumps(verification))
        return build(out)

    def base(self, path='src/a.ts'):
        return [fact('source_file', path, {'language': 'typescript', 'parse_status': 'OBSERVED'}),
                fact('metric', path, {'scope': 'file', 'code_lines': 30, 'branches': 2}),
                fact('metric', path, {'scope': 'function', 'branches': 6}),
                fact('history_churn', path, {'commits': 4, 'last_change': '2026-09-01T00:00:00+00:00'}),
                fact('history_ownership', path, {'authors': 2}),
                fact('graph_node', path, {'fan_in': 3, 'fan_out': 1})]

    def test_a_complete_row_names_the_source_of_every_field_and_keeps_its_contract(self):
        facts = self.base() + [fact('symbol_metric_external', 'src/a.ts', {'engine': 'scc', 'code': 28}),
                               fact('symbol_metric_external', 'src/a.ts', {'engine': 'codegraph', 'complexity': 9})]
        record = self.report(facts)
        self.assertEqual(validate(record, contracts()['measurements']), [])
        [row] = record['files']
        self.assertEqual((row['loc'], row['complexity_max'], row['churn'], row['authors'], row['fan_in']), (28, 9, 4, 2, 3))
        self.assertEqual(row['sources'], {'loc': 'scc', 'complexity_max': 'codegraph', 'duplicated_lines': 'jscpd',
                                          'churn': 'git history', 'fan_in': 'eaos.graph'})

    def test_without_the_engines_the_project_own_metrics_answer_and_say_so(self):
        [row] = self.report(self.base(), engines=())['files']
        self.assertEqual((row['loc'], row['complexity_max']), (30, 7))
        self.assertIsNone(row['duplicated_lines'])
        self.assertIn({'field': 'duplicated_lines', 'reason': 'jscpd did not run in this audit'}, row['missing'])

    def test_a_file_with_no_function_is_measured_by_its_body(self):
        facts = [f for f in self.base() if f['value'].get('scope') != 'function']
        [row] = self.report(facts)['files']
        self.assertEqual(row['complexity_max'], 3)
        self.assertEqual(row['sources']['complexity_max'], 'eaos.metrics (file body, no function)')

    def test_an_unknown_is_null_with_a_reason_never_zero(self):
        facts = [f for f in self.base() if f['kind'] not in ('history_churn', 'graph_node')]
        [row] = self.report(facts)['files']
        self.assertIsNone(row['churn'])
        self.assertIsNone(row['fan_in'])
        self.assertEqual({m['field'] for m in row['missing']}, {'churn', 'fan_in', 'coverage'})
        self.assertEqual(self.report(facts)['complete'], 0)

    def test_coverage_is_read_as_eaos_verify_writes_it(self):
        record = self.report(self.base(), verification={'coverage': {'src/a.ts': {'percent': 62.5, 'covered_lines': 5}}})
        self.assertEqual(record['files'][0]['coverage'], 0.625)

    def test_the_rows_are_the_parsed_files_and_the_rest_are_listed_with_their_reason(self):
        facts = self.base() + [fact('source_file', 'db/schema.sql', {'language': 'sql', 'parse_status': 'UNSUPPORTED'})]
        record = self.report(facts)
        self.assertEqual([row['path'] for row in record['files']], ['src/a.ts'])
        self.assertEqual(record['not_measured'], [{'path': 'db/schema.sql', 'reason': 'not parsed: UNSUPPORTED'}])

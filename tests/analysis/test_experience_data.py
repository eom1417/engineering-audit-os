"""The domain data of the simulated users (eaos/analysis/experience/domain_data.py): the external services stubbed or
said as not covered, the tables read from the facts and the SQL, the assistant's rows kept only when they hold."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.analysis.experience import domain_data

SQL = 'create table orders (\n  id serial primary key,\n  customer_email text not null,\n  total numeric(10, 2),\n  paid boolean,\n  constraint ok check (total >= 0)\n);\n'


def _fact(kind, value, location=None):
    return {'kind': kind, 'value': value, 'location': location or {'path': 'x', 'start_line': 1}}


def _report(folder):
    """A report whose facts name one table, its SQL in the project beside it, and a scenario of one goal."""
    project, report = Path(folder) / 'project', Path(folder) / 'report'
    (project / 'db').mkdir(parents=True)
    (project / 'db/schema.sql').write_text(SQL)
    (report / 'facts').mkdir(parents=True)
    (report / 'facts/run.json').write_text(json.dumps({'target': str(project)}))
    rows = [_fact('data_table', {'name': 'orders'}, {'path': 'db/schema.sql', 'start_line': 1}),
            _fact('import_edge', {'module': 'stripe', 'names': []}), _fact('env_read', {'name': 'SMTP_HOST'})]
    (report / 'facts/domain.json').write_text(json.dumps({'facts': rows}))
    (report / 'experience').mkdir()
    (report / 'experience/scenario.json').write_text(json.dumps({'personas': [{'id': 'buyer', 'role': 'visitor', 'goals': [{'id': 'order', 'goal': 'Order a lamp'}]}]}))
    return report


class Provider:
    def __init__(self, answer): self.answer, self.asked = answer, []

    def complete(self, messages, **options):
        self.asked.append(options)
        return {'result': self.answer}, {}


class DomainData(unittest.TestCase):
    def test_services_are_stubbed_or_not_covered_from_a_project_s_manifests(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'package.json').write_text(json.dumps({'dependencies': {'nodemailer': '6', 'stripe': '14', 'react': '18'}}))
            (Path(folder) / '.env.example').write_text('OPENAI_API_KEY=\nPORT=3000\n')
            found = domain_data.services(folder)
        self.assertEqual([s['service'] for s in found['stubs']], ['smtp'])
        self.assertEqual(sorted(s['service'] for s in found['not_covered']), ['openai', 'stripe'])
        self.assertTrue(all(s['why'] for s in found['not_covered']))

    def test_the_table_s_fields_come_from_its_create_table_without_what_the_database_fills(self):
        with tempfile.TemporaryDirectory() as folder:
            entities = domain_data.entities(_report(folder))
        self.assertEqual(entities, [{'name': 'Order', 'table': 'orders',
                                     'fields': {'customer_email': 'text', 'total': 'number', 'paid': 'boolean'}}])

    def test_invalid_rows_and_values_are_dropped_and_the_stubs_merged(self):
        answer = {'entities': [{'table': 'orders', 'rows': [{'customer_email': 'sara@example.com', 'total': 42, 'color': 'red'},
                                                            {'customer_email': 'sara@gmail.com'}, 'not a row']},
                               {'table': 'secrets', 'rows': [{'x': 1}]}],
                  'through_ui': [{'goal': 'buyer.order', 'values': {'Email': 'sara@example.com', 'Card': 'sk_live_abcdefghijklmnop'}},
                                 {'goal': 'nobody.none', 'values': {'Name': 'x'}}],
                  'seed': [{'table': 'orders', 'rows': [{'total': n, 'paid': True} for n in range(80)]}]}
        with tempfile.TemporaryDirectory() as folder:
            report, provider = _report(folder), Provider(answer)
            data = domain_data.plan(report, provider)
            self.assertEqual(json.loads((report / 'experience/data.json').read_text()), data)
        self.assertEqual(provider.asked[0]['stage'], 'experience_data')
        self.assertTrue(provider.asked[0]['deep'])
        self.assertEqual(data['entities'][0]['rows'], [{'customer_email': 'sara@example.com', 'total': 42}])
        self.assertEqual(data['through_ui'], [{'goal': 'buyer.order', 'values': {'Email': 'sara@example.com'}}])
        self.assertEqual(len(data['seed'][0]['rows']), domain_data.LIMIT['seed'])
        self.assertEqual([s['service'] for s in data['stubs']], ['smtp'])
        self.assertEqual([s['service'] for s in data['not_covered']], ['stripe'])

    def test_without_a_provider_the_rows_are_made_from_the_field_types(self):
        with tempfile.TemporaryDirectory() as folder:
            data = domain_data.plan(_report(folder))
        rows = data['entities'][0]['rows']
        self.assertEqual(len(rows), domain_data.LIMIT['sample'])
        self.assertEqual(rows[0], {'customer_email': 'user1@example.com', 'total': 10, 'paid': True})
        self.assertEqual(data['seed'], [{'table': 'orders', 'rows': rows}])
        self.assertEqual(data['through_ui'], [])


if __name__ == '__main__':
    unittest.main()

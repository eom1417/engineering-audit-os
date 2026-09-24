"""The artifact contracts: the validator, and that every contract is generated and owned by a real task."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f'tools/{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.contracts = tool('contracts')

    def test_the_validator_reports_each_way_a_value_breaks_its_schema(self):
        schema = {'type': 'object', 'required': ['a', 'b'], 'additionalProperties': False,
                  'properties': {'a': {'type': 'integer'}, 'b': {'enum': ['x', 'y']},
                                 'c': {'type': 'array', 'minItems': 1, 'items': {'type': 'string', 'pattern': '^Q'}}}}
        self.assertEqual(self.contracts.validate({'a': 1, 'b': 'x'}, schema), [])
        problems = self.contracts.validate({'a': True, 'c': ['Q1', 'R2'], 'd': 1}, schema)
        for fragment in ("missing required field 'b'", '$.a: expected integer', "does not match ^Q", "unexpected field 'd'"):
            self.assertTrue(any(fragment in p for p in problems), fragment)

    def test_the_schemas_are_what_the_generator_writes(self):
        before = {p.name: p.read_text(encoding='utf-8') for p in (ROOT / 'schemas/artifacts').glob('*.json')}
        tool('make_contracts')
        after = {p.name: p.read_text(encoding='utf-8') for p in (ROOT / 'schemas/artifacts').glob('*.json')}
        self.assertEqual(before, after, 'schemas/artifacts was edited by hand; edit tools/make_contracts.py instead')

    def test_every_contract_is_owned_by_a_task_of_the_plan(self):
        record = json.loads((ROOT / 'docs/north-star.json').read_text(encoding='utf-8'))
        milestones = {m['id'] for m in record['milestones']}
        tasks = {t['id'] for m in record['milestones'] for t in m['tasks']}
        for name, schema in self.contracts.contracts().items():
            for owner in schema['x-owner'].split(', '):
                self.assertTrue(owner in tasks or owner in milestones, f'{name}: owner {owner} is not in the plan')

    def test_every_contract_a_task_writes_exists(self):
        record = json.loads((ROOT / 'docs/north-star.json').read_text(encoding='utf-8'))
        written = {w[len('contract:'):] for m in record['milestones'] for t in m['tasks'] for w in t.get('writes', []) if w.startswith('contract:')}
        self.assertEqual(written - set(self.contracts.contracts()), set())


if __name__ == '__main__':
    unittest.main()

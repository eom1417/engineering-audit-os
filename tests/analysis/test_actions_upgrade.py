"""A vulnerable GitHub Action is moved where the workflows use it: a tag to the fixed tag, a pinned commit to the fixed
tag's commit with its comment, a moving major tag left as it is."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from eaos.analysis.repair import actions_upgrade

FLOW = '''jobs:
  publish:
    steps:
      - uses: pypa/gh-action-pypi-publish@76f52bc884231f62b9a034ebfe128415bbaabdfc # v1.12.4
      - uses: "pypa/gh-action-pypi-publish@v1.12.4"
      - uses: pypa/gh-action-pypi-publish@v1
      - uses: actions/checkout@v4
'''


class ActionsUpgradeTests(unittest.TestCase):
    def test_every_use_is_moved_as_the_project_writes_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            flow = Path(tmp) / '.github/workflows/publish.yaml'
            flow.parent.mkdir(parents=True)
            flow.write_text(FLOW)
            with mock.patch.object(actions_upgrade, '_commit_of', return_value='a' * 40) as asked:
                self.assertEqual(actions_upgrade.bump(tmp, 'pypa/gh-action-pypi-publish', '1.14.3'), [flow])
            lines = flow.read_text().splitlines()
        self.assertEqual(asked.call_count, 1)
        self.assertEqual(lines[3].strip(), f"- uses: pypa/gh-action-pypi-publish@{'a' * 40} # v1.14.3")
        self.assertEqual(lines[4].strip(), '- uses: "pypa/gh-action-pypi-publish@v1.14.3"')
        self.assertEqual(lines[5].strip(), '- uses: pypa/gh-action-pypi-publish@v1')
        self.assertEqual(lines[6].strip(), '- uses: actions/checkout@v4')

    def test_an_action_fact_becomes_its_codemod(self):
        fact = {'location': {'symbol': 'GitHub Actions:pypa/gh-action-pypi-publish@v1.12.4', 'path': 'sbom.cdx.json'},
                'value': {'measurements': [{'name': 'fixed_in', 'value': '1.14.3'}]}}
        self.assertEqual(actions_upgrade.action_card(fact), {'kind': 'actions',
                                                             'package': 'pypa/gh-action-pypi-publish',
                                                             'version': 'v1.12.4', 'fixed': '1.14.3'})
        self.assertIsNone(actions_upgrade.action_card({**fact, 'location': {'symbol': 'npm:a@1.0.0'}}))


if __name__ == '__main__':
    unittest.main()

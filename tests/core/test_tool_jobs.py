"""One tool per job (M18.1): every pinned tool names the jobs it does, each job has one primary, and a second tool on a
job says the part it alone gives (eaos/data/toolchain.json `jobs`)."""
import unittest
from pathlib import Path

from eaos.core.toolchain import registry

ROOT = Path(__file__).resolve().parents[2]
PRIMARY = 'primary'


class ToolJobs(unittest.TestCase):
    def setUp(self):
        self.data = registry()
        self.jobs, self.tools = self.data['jobs'], self.data['tools']

    def test_every_tool_has_a_known_job(self):
        for tool in self.tools:
            with self.subTest(tool=tool['name']):
                self.assertTrue(tool.get('jobs'), 'a pinned tool with no job has no place')
                self.assertLessEqual(set(tool['jobs']), set(self.jobs), 'a job not in the jobs map')

    def test_every_job_has_exactly_one_primary(self):
        for job, entry in self.jobs.items():
            primaries = [tool['name'] for tool in self.tools if (tool.get('jobs') or {}).get(job) == PRIMARY]
            with self.subTest(job=job):
                if entry['primary'] == 'eaos':
                    self.assertEqual(primaries, [], "EAOS's own code is this job's primary: no tool may claim it")
                    self.assertTrue(entry.get('eaos'), "an EAOS-primary job names EAOS's own modules")
                else:
                    self.assertEqual(primaries, [entry['primary']])

    def test_a_second_tool_names_its_own_part(self):
        for tool in self.tools:
            for job, part in (tool.get('jobs') or {}).items():
                with self.subTest(tool=tool['name'], job=job):
                    self.assertTrue(part == PRIMARY or len(part.split()) >= 4, 'a second tool says what it alone gives')

    def test_eaos_own_modules_exist(self):
        for job, entry in self.jobs.items():
            for path in entry.get('eaos') or []:
                with self.subTest(job=job, path=path):
                    self.assertTrue((ROOT / path).is_file())


if __name__ == '__main__':
    unittest.main()

"""The Studio's weight: the built Studio on disk, and what the report page reads to draw (its bundle and the sections
its parts need), each held to a budget. A change that grows past one must earn it and raise the budget here."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDIO = ROOT / 'eaos/data/studio'
PAGE = ROOT / 'console/src/places/report'
SECTIONS = ROOT / 'tests/fixtures/studio/v2'

STUDIO_BYTES = 1_170_000  # total size of the built Studio, in bytes
PAGE_BYTES = 22_400  # size of the report page's bundle plus the fixture sections it reads, in bytes
PAGE_SECTIONS = {'screens'}   # the pictures' part; the report for people and the files are read apart, by address


def needs():
    """Every section a part of the report page asks for, read from its source (`needs: [...]`, `NEEDS = [...]`)."""
    names = set()
    for source in PAGE.glob('*.js'):
        for listed in re.findall(r"(?:needs:|NEEDS =)\s*\[([^\]]*)\]", source.read_text(encoding='utf-8')):
            names.update(re.findall(r"'([a-z_]+)'", listed))
    return names


class Budget(unittest.TestCase):
    def test_the_built_studio_stays_within_its_budget(self):
        size = sum(p.stat().st_size for p in STUDIO.rglob('*') if p.is_file())
        self.assertLessEqual(size, STUDIO_BYTES, f'the built Studio weighs {size} bytes')

    def test_the_report_page_reads_only_its_sections_and_stays_within_its_payload(self):
        self.assertEqual(needs(), PAGE_SECTIONS)
        payload = (STUDIO / 'assets/report.js').stat().st_size + sum((SECTIONS / f'{name}.json').stat().st_size for name in PAGE_SECTIONS)
        self.assertLessEqual(payload, PAGE_BYTES, f'the report page reads {payload} bytes')


if __name__ == '__main__':
    unittest.main()

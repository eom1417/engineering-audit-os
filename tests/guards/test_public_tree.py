"""The published tree holds only the product: nothing of the machine, the container or the people EAOS was built by.

Every tracked file is read for the kinds of leak any machine has: the development host's cores and load, the
container's paths, its host name and internal address. A maintainer's own words (project names, host names,
addresses) are listed outside the repository, one regular expression a line, in the file $EAOS_PRIVATE_WORDS.
"""
import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERIC = [r'/work(?:space)/',                     # a development container's own folder
           r'\.lxd\b',                           # a container's host name
           r'\b\d+ (cores|vcpus?)\b',            # the machine's size
           r'\bload \d+(-\d+)?\b']               # the machine's load at some moment
SELF = 'tests/guards/test_public_tree.py'


def published():
    """Every tracked file, or, outside a git checkout (the check's isolated copy), the files on disk."""
    listed = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True)
    if listed.returncode == 0: return listed.stdout.split()
    return [p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if '.git' not in p.parts and '.venv' not in p.parts]


def patterns():
    words = os.environ.get('EAOS_PRIVATE_WORDS')
    lines = Path(words).read_text(encoding='utf-8').splitlines() if words and Path(words).is_file() else []
    private = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith('#')]
    return re.compile('|'.join(f'(?:{p})' for p in GENERIC + private), re.I)


class PublicTree(unittest.TestCase):
    def test_nothing_private_is_published(self):
        found, pattern = [], patterns()
        for name in published():
            path = ROOT / name
            if name == SELF or not path.is_file(): continue
            data = path.read_bytes()
            if b'\0' in data[:4096]: continue
            for number, line in enumerate(data.decode('utf-8', errors='replace').splitlines(), 1):
                if pattern.search(line): found.append(f'{name}:{number}: {line.strip()[:120]}')
        self.assertEqual(found, [], 'published, yet about the machine, the container or a private project')


if __name__ == '__main__':
    unittest.main()

"""The published tree holds only the product: nothing of the machine, the container or the people EAOS was built by.

A review of the public repository (2026-10-26) read the development host from its documents (its cores and load), the
container's paths (`/workspace/...`), its host name and internal address, and the names of private projects a check had
been tried on. Every tracked file is read for the kinds any machine has; a maintainer's own words (project names, host
names, addresses) are listed outside the repository, one regular expression a line, in the file $EAOS_PRIVATE_WORDS.
"""
import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERIC = [r'/workspace/',                       # a development container's own folder
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

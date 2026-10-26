"""Every path of EAOS that its code, tools and living references name exists: a reader follows it and lands on the file.

The code layout (2026-10-26) found about thirty such names left behind by earlier moves (`eaos/journeys/guided.py` after
guided became a package), each sending a reader, or an assistant, to a file that was no longer there.
"""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# `eaos/<folders>/<module>.py` or `eaos/<folders>/`, not inside a longer path or a word.
NAMED = re.compile(r'(?<![\w/.-])eaos/((?:[a-z_]+/)*[a-z_0-9]+)(\.py|/)')
READ = ('.py', '.md', '.toml', '.sh', '.js', '.mjs')
HISTORY = ('CHANGELOG.md', 'docs/archive/', 'tests/', 'eaos/data/studio/', 'upstreams/')
EXAMPLES = {'eaos/x.py'}          # a made-up file a docstring shows a rule with


class NamedPaths(unittest.TestCase):
    def test_every_path_eaos_names_exists(self):
        listed = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        missing = []
        for name in listed:
            if not name.endswith(READ) or name.startswith(HISTORY) or not (ROOT / name).is_file():
                continue
            text = (ROOT / name).read_text(encoding='utf-8', errors='ignore')
            for match in NAMED.finditer(text):
                path = 'eaos/' + match.group(1) + ('.py' if match.group(2) == '.py' else '')
                if path not in EXAMPLES and not (ROOT / path).exists():
                    missing.append(f'{name}:{text.count(chr(10), 0, match.start()) + 1} {match.group(0)}')
        self.assertEqual(missing, [], 'a named path that is not there')


if __name__ == '__main__':
    unittest.main()

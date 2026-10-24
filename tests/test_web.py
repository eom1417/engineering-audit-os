"""EAOS reads the web over http(s) only: urllib also opens file:// and ftp://, and an address built from a record or a
project's configuration could read a file of this computer (EAOS's check of itself, 2026-10-24: eleven such calls)."""
import tempfile
import unittest
from pathlib import Path

from eaos.core.web import opened


class OnlyTheWeb(unittest.TestCase):
    def test_a_file_or_ftp_address_is_refused_before_anything_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            secret = Path(tmp) / 'secret.txt'
            secret.write_text('never read')
            for address in (secret.as_uri(), 'ftp://example.com/x', 'FILE:///etc/hostname'):
                with self.assertRaisesRegex(ValueError, 'not an http'): opened(address)


if __name__ == '__main__':
    unittest.main()

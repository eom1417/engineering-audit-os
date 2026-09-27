"""The revision fingerprint: computed once per revision for hundreds of checks, never stale after a change."""
import time
from pathlib import Path

from shared_fixture import Workspace

from eaos.acceptance import fingerprint


class FingerprintTests(Workspace):
    def test_a_changed_file_changes_it_even_from_the_cache(self):
        root = Path(self.tmp)
        (root / 'a.txt').write_text('1')
        first = fingerprint(root)
        self.assertEqual(fingerprint(root), first)
        time.sleep(0.01)
        (root / 'a.txt').write_text('2')
        self.assertNotEqual(fingerprint(root), first)
        self.assertEqual(fingerprint(root), fingerprint(root, cached=False))

    def test_skipped_directories_do_not_count(self):
        root = Path(self.tmp)
        (root / 'a.txt').write_text('1')
        before = fingerprint(root, cached=False)
        (root / 'node_modules/pkg').mkdir(parents=True)
        (root / 'node_modules/pkg/index.js').write_text('x')
        self.assertEqual(fingerprint(root, cached=False), before)

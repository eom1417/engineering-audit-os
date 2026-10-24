"""The run's own PostgreSQL under root: pgserver's binaries in a virtualenv under /root still run."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.core import local_db


@unittest.skipUnless(os.name == 'posix' and os.geteuid() == 0, 'the dedicated account exists under root only')
class ReachableBinaries(unittest.TestCase):
    def test_binaries_in_a_closed_folder_are_copied_with_their_libraries(self):
        owner = local_db._as_owner()
        with tempfile.TemporaryDirectory() as closed, tempfile.TemporaryDirectory() as shared:
            os.chmod(closed, 0o700)                                        # as /root is
            site = Path(closed) / 'site-packages'
            bin_dir = site / 'pgserver' / 'pginstall' / 'bin'
            bin_dir.mkdir(parents=True)
            (site / 'pgserver.libs').mkdir()
            (site / 'pgserver.libs' / 'libpq.so.5').write_text('lib')
            (bin_dir / 'pg_ctl').write_text('#!/bin/sh\n')
            os.chmod(bin_dir / 'pg_ctl', 0o755)
            os.chmod(shared, 0o755)
            with mock.patch.object(local_db, 'SHARED', Path(shared) / 'eaos-pg'):
                found = local_db._reachable(bin_dir, owner)
                self.assertEqual(found, local_db._reachable(bin_dir, owner))     # copied once
            self.assertTrue(str(found).startswith(shared))
            self.assertTrue((found.parent.parent.parent / 'pgserver.libs' / 'libpq.so.5').is_file())   # $ORIGIN/../../../
            self.assertEqual(local_db.subprocess.run(['test', '-x', str(found / 'pg_ctl')], user=owner).returncode, 0)

    def test_reachable_binaries_are_used_where_they_are(self):
        with tempfile.TemporaryDirectory() as open_folder:
            os.chmod(open_folder, 0o755)
            bin_dir = Path(open_folder) / 'bin'
            bin_dir.mkdir()
            (bin_dir / 'pg_ctl').write_text('#!/bin/sh\n')
            os.chmod(bin_dir / 'pg_ctl', 0o755)
            self.assertEqual(local_db._reachable(bin_dir, local_db._as_owner()), bin_dir)


if __name__ == '__main__':
    unittest.main()

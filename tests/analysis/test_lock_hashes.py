"""A hash written by hand into a lock file is refused: only the hashes a change added are asked of their registry."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from eaos.analysis.repair import lock_hashes

URL = 'https://registry.npmjs.org/{0}/-/{1}-{2}.tgz'


def lock(*rows):
    return json.dumps({'packages': {f'node_modules/{n}': {'resolved': URL.format(n, n.split('/')[-1], v), 'integrity': h}
                                    for n, v, h in rows}})


class LockHashTests(unittest.TestCase):
    def test_only_the_added_wrong_hash_is_refused(self):
        published = {'https://registry.npmjs.org/kept/1.0.0': 'sha512-k', 'https://registry.npmjs.org/good/2.0.0': 'sha512-g',
                     'https://registry.npmjs.org/@scope/bad/3.0.0-beta.1': 'sha512-real'}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(lock_hashes, '_read', lambda url: {'dist': {'integrity': published[url]}}):
            root = Path(tmp)
            git = lambda *a: subprocess.run(['git', '-C', tmp, '-c', 'user.name=t', '-c', 'user.email=t@t', *a], check=True, capture_output=True)
            git('init', '-q')
            (root / 'package-lock.json').write_text(lock(('kept', '1.0.0', 'sha512-old-but-untouched')))
            git('add', '.'); git('commit', '-qm', 'one')
            (root / 'package-lock.json').write_text(lock(('kept', '1.0.0', 'sha512-old-but-untouched'), ('good', '2.0.0', 'sha512-g'),
                                                         ('@scope/bad', '3.0.0-beta.1', 'sha512-from-memory')))
            git('commit', '-qam', 'two')
            said = lock_hashes.wrong(root, ['package-lock.json'])
        self.assertEqual(len(said), 1)
        self.assertIn('@scope/bad/-/bad-3.0.0-beta.1.tgz', said[0])
        self.assertIn('not the one its registry publishes', said[0])


if __name__ == '__main__':
    unittest.main()

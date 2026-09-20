import tempfile
import unittest
from pathlib import Path

from eaos.runtime.context import Context
from eaos.sessions import create_run
from eaos.workspace import digest, read


class ContextRedactionTests(unittest.TestCase):
    def context(self, text):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        target = root / 'target'
        target.mkdir()
        (target / 'sample.txt').write_text(text)
        run = create_run(target, root / 'run')
        return Context(run, read(run / 'run.json'), 24000)

    def test_partial_read_inside_private_key_is_redacted(self):
        text = 'before\n-----BEGIN PRIVATE KEY-----\nSYNTHETIC_PRIVATE_BODY\n-----END PRIVATE KEY-----\nafter\n'
        context = self.context(text)
        block = context.source('sample.txt', 3, 3)
        self.assertNotIn('SYNTHETIC_PRIVATE_BODY', block['source'])
        self.assertTrue(block['redacted'])
        self.assertEqual(block['start_line'], 3)
        ref = context.evidence[block['evidence_id']]['source_ref']
        self.assertEqual(ref['range_sha256'], digest(b'SYNTHETIC_PRIVATE_BODY\n'))
        self.assertEqual(context.source('sample.txt', 5, 5)['source'], '5: after')

    def test_private_key_split_across_chunks_is_redacted(self):
        text = 'before\n-----BEGIN PRIVATE KEY-----\n' + 'SYNTHETIC_PRIVATE_BODY\n' * 300 + '-----END PRIVATE KEY-----\nafter\n'
        context = self.context(text)
        batches, omissions = context.chunks()
        blocks = [block for batch in batches for block in batch]
        self.assertGreater(len(blocks), 1)
        self.assertFalse(omissions)
        self.assertTrue(all('SYNTHETIC_PRIVATE_BODY' not in block['source'] for block in blocks))
        self.assertEqual(sum(b['end_line'] - b['start_line'] + 1 for b in blocks), len(text.splitlines()))


if __name__ == '__main__':
    unittest.main()

"""NS46.T25 owner-request acceptance (owner, 2026-10-11: the Studio on this computer opens from a plain address that
keeps working, with no token at its end; once EAOS and its tools are installed the Studio opens at once, not after a
check), planned 2026-10-11.

Real processes on a real git project: `eaos studio --background` returns at once with the address; the address carries
no token and opens the live Studio (its own page gets the token); a restarted Studio has the same address and token.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fetch(url, headers=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=10) as response:
            return response.status, response.read().decode('utf-8')
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode('utf-8')


class StudioOpen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.project = base / 'shop'
        self.project.mkdir()
        (self.project / 'app.py').write_text('print("hi")\n', encoding='utf-8')
        for argv in (['git', 'init', '-q'], ['git', 'add', '.'], ['git', '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'one']):
            subprocess.run(argv, cwd=self.project, check=True)
        self.env = {**os.environ, 'EAOS_HOME': str(base / 'home'), 'PYTHONPATH': str(ROOT)}
        self.records = Path(self.env['EAOS_HOME']) / 'studio'

    def background(self):
        done = subprocess.run([sys.executable, '-m', 'eaos', 'studio', str(self.project), '--background', '--no-open'],
                              env=self.env, capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return done.stdout.strip().split('EAOS Studio: ', 1)[1]

    def stop(self):
        for record in self.records.glob('*.json'):
            try: os.kill(json.loads(record.read_text(encoding='utf-8'))['pid'], 15)
            except (OSError, ValueError, KeyError): pass
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and list(self.records.glob('*.json')):
            time.sleep(0.2)

    def token(self, base):
        body = fetch(f'{base}/live-token.js', {'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-Dest': 'script'})[1]
        return json.loads(body.split('window.EAOS_BOOT_TOKEN=', 1)[1].split(';', 1)[0])

    def test_the_plain_address_opens_the_live_studio_and_survives_a_restart(self):
        self.addCleanup(self.stop)
        address = self.background()
        self.assertNotIn('token', address)
        base = address.split('/#', 1)[0].rstrip('/')
        self.assertIn('live-token.js', fetch(f'{base}/', {'Sec-Fetch-Site': 'none', 'Sec-Fetch-Dest': 'document'})[1])
        token = self.token(base)
        status, body = fetch(f'{base}/api/session', {'X-EAOS-Token': token})
        self.assertEqual((status, json.loads(body)['mode']), (200, 'live'))
        self.stop()
        again = self.background()
        self.assertEqual(again.split('/#', 1)[0], address.split('/#', 1)[0], 'the same address after a restart')
        self.assertEqual(self.token(base), token, 'and the same token: a saved address keeps working')

    def test_the_installer_opens_the_studio_of_the_project_it_was_run_from(self):
        text = (ROOT / 'install.sh').read_text(encoding='utf-8')
        self.assertIn('STARTED_IN="$PWD"', text)
        self.assertIn('studio "$STARTED_IN" --background', text)


if __name__ == '__main__':
    unittest.main()

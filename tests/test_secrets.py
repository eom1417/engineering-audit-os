"""Committed credentials must be reported with a severity the key itself declares."""
import base64
import json
import tempfile
import unittest
from pathlib import Path

from eaos.facts.secrets import _classify_jwt, _decode_jwt_role, _classify_text, collect, run


def _jwt_with_role(role):
    """Build a syntactically-valid JWT whose payload declares the given role."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b'=').decode()
    payload = base64.urlsafe_b64encode(json.dumps({'role': role}).encode()).rstrip(b'=').decode()
    return f"{header}.{payload}.sig"


class _Source:
    def __init__(self, root, files):
        self.target = Path(root)
        self.inventory = {'files': [{'path': rel, 'sha256': 'a' * 64,
                                     'capture': 'hashed' if not rel.startswith('.env') else 'sensitive_metadata_only'}
                                    for rel in files]}

    def readable(self):
        return [i for i in self.inventory['files'] if i['capture'] == 'hashed']

    def text(self, rel):
        try:
            return (self.target / rel).read_text()
        except (OSError, UnicodeError):
            return None


class SecretTests(unittest.TestCase):
    def test_the_key_itself_declares_whether_it_is_public_or_secret(self):
        self.assertEqual(_decode_jwt_role(_jwt_with_role('anon')), 'anon')
        for role, severity in [('anon', 'public'), ('authenticated', 'public'), ('service_role', 'secret'),
                               ('whatever', 'unknown')]:
            self.assertEqual(_classify_jwt(_jwt_with_role(role)), severity, role)
        # Key-shaped strings are built at runtime: a literal trips secret scanners on push (it is not a key).
        cases = [(f'const k = "{_jwt_with_role("anon")}";', ('jwt', 'public')),
                 (f'const k = "{_jwt_with_role("service_role")}";', ('jwt', 'secret')),
                 ('const k = `-----BEGIN RSA PRIVATE KEY-----\n' + 'MIIEowIBAAKCAQEAx' * 12 + '\n-----END RSA PRIVATE KEY-----`;',
                  ('private_key', 'secret')),
                 ('const k = "' + 'sk_' + 'live_' + '4eC39HqLyjWDarjtT1zdp7dc' + '";', ('stripe_live', 'secret')),
                 ('const k = "' + 'sb_' + 'secret_' + '4eC39HqLyjWDarjtT1zdp7dc' + '";', ('supabase_service_role', 'secret'))]
        for text, expected in cases:
            self.assertIn(expected, list(_classify_text(text, 'src/app.ts')))
        # A key marker too short to be a key is not a credential, whatever folder it is in.
        marker = '"a private key block": "-----BEGIN PRIVATE KEY-----\\nMIIE\\n-----END PRIVATE KEY-----",'
        self.assertEqual(list(_classify_text(marker, 'app/tests/release-artifact.test.mjs')), [])
        self.assertEqual(list(_classify_text(marker, 'src/config.ts')), [])

    def test_committed_keys_are_reported_by_path_and_severity_without_their_value(self):
        token = _jwt_with_role('anon')
        files = {'.env': f'SUPABASE_PUBLISHABLE_KEY="{token}"\n',
                 '.env.production': f'SB_SECRET="{_jwt_with_role("service_role")}"\n',
                 '.env.example': f'SUPABASE_PUBLISHABLE_KEY="{token}"\n', '.env.sample': 'PLACEHOLDER=foo\n',
                 'src/integrations/supabase/client.ts': f'export const K = "{token}";\n'}
        with tempfile.TemporaryDirectory() as tmp:
            for rel, content in files.items():
                (Path(tmp) / rel).parent.mkdir(parents=True, exist_ok=True)
                (Path(tmp) / rel).write_text(content)
            source = _Source(tmp, list(files))
            findings = collect(source)
            result = run(Path(tmp), source)
        self.assertEqual(sorted((f['path'], f['severity']) for f in findings),
                         [('.env', 'public'), ('.env.production', 'secret'), ('src/integrations/supabase/client.ts', 'public')],
                         'example and sample env files are excluded')
        self.assertEqual(len(result['facts']), 3)
        self.assertNotIn(token, json.dumps(result['facts'], ensure_ascii=False))

    def test_a_secrets_file_is_never_read_but_code_named_after_secrets_is(self):
        from eaos.core.workspace import SENSITIVE
        for name in ('secrets.json', 'app-secrets.yaml', 'google-credentials.json', 'credentials', '.env.local', 'id_rsa'):
            self.assertTrue(SENSITIVE.search(name), name)
        for name in ('adminSecrets.ts', 'credentialsForm.tsx', 'secrets.ts'):
            self.assertFalse(SENSITIVE.search(name), f'{name} is code: unread, its imports would be called missing')

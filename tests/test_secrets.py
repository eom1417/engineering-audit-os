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
    signature = 'sig'
    return f"{header}.{payload}.{signature}"


def _write(root, rel, content=''):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


class _Source:
    def __init__(self, root, files):
        self.target = Path(root)
        self.inventory = {'files': [{'path': rel, 'sha256': 'a' * 64,
                                      'capture': 'hashed' if not rel.startswith('.env') else 'sensitive_metadata_only'}
                                     for rel in files]}
        self._text_cache = {}

    def readable(self):
        return [i for i in self.inventory['files'] if i['capture'] == 'hashed']

    def text(self, rel):
        if rel in self._text_cache: return self._text_cache[rel]
        try:
            value = (self.target / rel).read_text()
        except (OSError, UnicodeError):
            value = None
        self._text_cache[rel] = value
        return value


class JwtDecodingTests(unittest.TestCase):
    def test_anon_role_reads_as_public(self):
        token = _jwt_with_role('anon')
        self.assertEqual(_classify_jwt(token), 'public')

    def test_authenticated_role_reads_as_public(self):
        token = _jwt_with_role('authenticated')
        self.assertEqual(_classify_jwt(token), 'public')

    def test_service_role_reads_as_secret(self):
        token = _jwt_with_role('service_role')
        self.assertEqual(_classify_jwt(token), 'secret')

    def test_unknown_role_reads_as_unknown(self):
        token = _jwt_with_role('whatever')
        self.assertEqual(_classify_jwt(token), 'unknown')

    def test_decode_returns_role_string(self):
        token = _jwt_with_role('anon')
        self.assertEqual(_decode_jwt_role(token), 'anon')


class ClassifyTextTests(unittest.TestCase):
    def test_a_publishable_jwt_inside_a_ts_file_is_public(self):
        token = _jwt_with_role('anon')
        text = f'const k = "{token}";'
        findings = list(_classify_text(text, 'src/app.ts'))
        self.assertIn(('jwt', 'public'), findings)

    def test_a_service_role_jwt_inside_a_ts_file_is_secret(self):
        token = _jwt_with_role('service_role')
        text = f'const k = "{token}";'
        findings = list(_classify_text(text, 'src/app.ts'))
        self.assertIn(('jwt', 'secret'), findings)

    def test_a_pem_private_key_is_secret(self):
        text = 'const k = `-----BEGIN RSA PRIVATE KEY-----\n' + 'MIIEowIBAAKCAQEAx' * 12 + '\n-----END RSA PRIVATE KEY-----`;'
        findings = list(_classify_text(text, 'src/k.ts'))
        self.assertIn(('private_key', 'secret'), findings)

    def test_a_key_marker_too_short_to_be_a_key_is_not_a_credential(self):
        # chief-ops tests its release scanner with this marker; no real private key is 4 characters long
        text = '"a private key block": "-----BEGIN PRIVATE KEY-----\\nMIIE\\n-----END PRIVATE KEY-----",'
        self.assertEqual(list(_classify_text(text, 'app/tests/release-artifact.test.mjs')), [])
        self.assertEqual(list(_classify_text(text, 'src/config.ts')), [])   # the folder decides nothing

    def test_a_stripe_live_key_is_secret(self):
        # Built at runtime: a literal key-shaped string trips secret scanners on push (it is not a key).
        text = 'const k = "' + 'sk_' + 'live_' + '4eC39HqLyjWDarjtT1zdp7dc' + '";'
        findings = list(_classify_text(text, 'src/billing.ts'))
        self.assertIn(('stripe_live', 'secret'), findings)

    def test_a_supabase_service_role_is_secret(self):
        text = 'const k = "' + 'sb_' + 'secret_' + '4eC39HqLyjWDarjtT1zdp7dc' + '";'
        findings = list(_classify_text(text, 'src/admin.ts'))
        self.assertIn(('supabase_service_role', 'secret'), findings)


class CollectTests(unittest.TestCase):
    def test_env_file_with_publishable_jwt_is_reported_as_public(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, '.env', f'SUPABASE_PUBLISHABLE_KEY="{_jwt_with_role("anon")}"\n')
            source = _Source(tmp, ['.env'])
            findings = collect(source)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]['path'], '.env')
            self.assertEqual(findings[0]['severity'], 'public')

    def test_env_file_with_service_role_jwt_is_reported_as_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, '.env.production', f'SB_SECRET="{_jwt_with_role("service_role")}"\n')
            source = _Source(tmp, ['.env.production'])
            findings = collect(source)
            self.assertEqual(findings[0]['severity'], 'secret')

    def test_safe_env_files_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, '.env.example', f'SUPABASE_PUBLISHABLE_KEY="{_jwt_with_role("anon")}"\n')
            _write(tmp, '.env.sample', 'PLACEHOLDER=foo\n')
            source = _Source(tmp, ['.env.example', '.env.sample'])
            findings = collect(source)
            self.assertEqual(findings, [])

    def test_a_publishable_jwt_inside_a_ts_file_is_reported_with_its_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            token = _jwt_with_role('anon')
            _write(tmp, 'src/integrations/supabase/client.ts', f'export const K = "{token}";\n')
            source = _Source(tmp, ['src/integrations/supabase/client.ts'])
            findings = collect(source)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]['path'], 'src/integrations/supabase/client.ts')
            self.assertEqual(findings[0]['severity'], 'public')

    def test_fact_does_not_carry_the_secret_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            token = _jwt_with_role('anon')
            _write(tmp, '.env', f'KEY="{token}"\n')
            source = _Source(tmp, ['.env'])
            result = run(Path(tmp), source)
            self.assertEqual(len(result['facts']), 1)
            serialised = json.dumps(result['facts'][0], ensure_ascii=False)
            self.assertNotIn(token, serialised)


class SensitiveNameTests(unittest.TestCase):
    def test_a_secrets_file_is_never_read_but_code_named_after_secrets_is(self):
        from eaos.workspace import SENSITIVE
        for name in ('secrets.json', 'app-secrets.yaml', 'google-credentials.json', 'credentials', '.env.local', 'id_rsa'):
            self.assertTrue(SENSITIVE.search(name), name)
        for name in ('adminSecrets.ts', 'credentialsForm.tsx', 'secrets.ts'):
            self.assertFalse(SENSITIVE.search(name), f'{name} is code: unread, its imports would be called missing')

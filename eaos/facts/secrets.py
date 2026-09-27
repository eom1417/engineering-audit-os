"""Committed credentials."""
import base64
import json
import re
from . import digest, make

NAME = 'secrets'
VERSION = '1'
LIMITATIONS = [
    'A credential is reported only when its key family is recognized; novel formats are missed, not mis-classified.',
    'A JWT role is read from the payload; a key signed with a custom claim structure may read as "unknown".',
    'A private key embedded as a non-PEM byte sequence is not detected; PEM blocks starting with ----- are.',
    'The tool never reproduces the secret value in a fact; severity and key family are recorded instead.',
]

ENV_SAFE = {'.env.example', '.env.sample', '.env.template', '.env.test'}
# A literal string that looks like a JWT: three base64url segments separated by dots.
JWT = re.compile(r'\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b')
# PEM private keys (PEM-encoded RSA/ECDSA/OpenSSH/PGP).
PEM_PRIVATE = re.compile(r'-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----')
PEM_BLOCK = re.compile(r'-----BEGIN ((?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY)-----(.*?)(?:-----END \1-----|$)', re.S)
# The shortest real private key (an EC P-256 key) carries well over 100 base64 characters. A block with less is a
# marker a test or a scanner rule uses to talk about keys (chief-ops: "-----BEGIN PRIVATE KEY-----\nMIIE\n..."),
# decided from the payload like every other severity here, never from the file's name or folder.
PEM_MIN_BODY = 100
# Common third-party secret prefixes.
SK_LIVE = re.compile(r'\bsk_live_[A-Za-z0-9]{16,}\b')
SB_SECRET = re.compile(r'\bsb_secret_[A-Za-z0-9_-]{16,}\b')


def _decode_jwt_role(token):
    """Return the JWT payload role claim."""
    parts = token.split('.')
    if len(parts) != 3: return None
    payload = parts[1]
    # base64url with optional padding stripped
    payload += '=' * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload.encode('ascii'))
    except (ValueError, UnicodeEncodeError):
        return None
    try:
        data = json.loads(decoded.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return None
    role = data.get('role')
    return role if isinstance(role, str) else None


def _classify_jwt(token):
    """A JWT role names its blast radius."""
    role = _decode_jwt_role(token)
    if role in {'anon', 'authenticated', 'publishable', 'public'}:
        return 'public'
    if role in {'service_role', 'secret', 'admin'}:
        return 'secret'
    return 'unknown'


def _classify_text(text, rel):
    """Yield (key_family, severity) for every credential embedded in the file text."""
    for match in JWT.finditer(text):
        role = _decode_jwt_role(match.group(0))
        if role in {'anon', 'authenticated', 'publishable', 'public'}:
            yield ('jwt', 'public')
        elif role in {'service_role', 'secret', 'admin'}:
            yield ('jwt', 'secret')
        else:
            yield ('jwt', 'unknown')
    for match in PEM_BLOCK.finditer(text):
        body = re.sub(r'[^A-Za-z0-9+/=]', '', match.group(2).replace('\\n', '\n'))
        if len(body) >= PEM_MIN_BODY: yield ('private_key', 'secret')
    if SK_LIVE.search(text):
        yield ('stripe_live', 'secret')
    if SB_SECRET.search(text):
        yield ('supabase_service_role', 'secret')


def _env_severity(path, text):
    """A committed .env carries at least one credential; the most sensitive one wins."""
    severities = {'public': 1, 'unknown': 2, 'secret': 3}
    highest = 0
    for _, severity in _classify_text(text, path):
        highest = max(highest, severities.get(severity, 0))
    return {1: 'public', 2: 'unknown', 3: 'secret'}.get(highest, 'unknown')


def _read_text(source, rel):
    """Read a file text even when it is flagged sensitive."""
    from pathlib import PurePosixPath
    if PurePosixPath(rel).is_absolute() or '..' in PurePosixPath(rel).parts:
        return None
    target = source.target / rel
    try:
        if target.is_symlink(): return None
        if not target.is_file(): return None
        return target.read_text(encoding='utf-8', errors='replace')
    except (OSError, UnicodeError):
        return None


def collect(source):
    """Walk every readable file and yield fact-ready records for every credential."""
    findings = []
    items = list(source.inventory['files'])
    for item in items:
        rel = item['path']
        name = rel.rsplit('/', 1)[-1]
        if name in ENV_SAFE or any(rel.endswith(suffix) for suffix in ENV_SAFE):
            continue
        is_env = name == '.env' or name.startswith('.env.')
        # Inline credentials live in source code (TS/JS/Python) and in committed .env files.
        if not (is_env or rel.endswith(('.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.py', '.json'))):
            continue
        text = source.text(rel) if item.get('capture') == 'hashed' else _read_text(source, rel)
        if text is None: continue
        if is_env:
            severity = _env_severity(rel, text)
            findings.append({'path': rel, 'key_family': 'env_file',
                             'severity': severity, 'line': 1})
        else:
            line = 1
            offset = 0
            for segment in re.findall(r'[^\n]*\n|[^\n]+$', text):
                for family, severity in _classify_text(segment, rel):
                    findings.append({'path': rel, 'key_family': family, 'severity': severity, 'line': line})
                line += 1
                offset = 0
    return findings


def run(target, source, **options):
    findings = collect(source)
    facts_list = [make('committed_credential', NAME, VERSION, digest(record['path'].encode('utf-8')),
                       {'path': record['path'], 'start_line': record['line']},
                       {'path': record['path'], 'key_family': record['key_family'],
                        'severity': record['severity'],
                        'note': 'severity is read from the key, never the filename; the value is not recorded.'},
                       limitations=LIMITATIONS)
                  for record in findings]
    summary = {'credentials': len(facts_list),
               'by_severity': {'public': sum(1 for f in facts_list if f['value']['severity'] == 'public'),
                                'secret': sum(1 for f in facts_list if f['value']['severity'] == 'secret'),
                                'unknown': sum(1 for f in facts_list if f['value']['severity'] == 'unknown')},
               'by_family': {family: sum(1 for f in facts_list if f['value']['key_family'] == family)
                              for family in {f['value']['key_family'] for f in facts_list}},
               'interpretation': 'A credential is reported with the severity its payload declares, not by its filename.'}
    return {'facts': facts_list, 'summary': summary, 'available': True,
            'input_sha': digest(';'.join(sorted(record['path'] for record in findings)).encode('utf-8')),
            'reason': None}

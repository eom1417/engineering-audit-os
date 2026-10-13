"""Configuration surface: which environment variables and config keys the code actually reads.

Names only. No value is ever recorded — not from source, not from a .env file, not from a default —
so this extractor cannot become a way to copy secrets out of a repository.
"""
from collections import Counter
import json
from pathlib import PurePosixPath
import re
from . import digest, make
from .source import language_of

NAME = 'config'
VERSION = '1'
LIMITATIONS = [
    'Values are deliberately never captured; only names and whether a default exists.',
    'Variables assembled at runtime (prefix + name) are not detected.',
    'A key present in a config file is not proof that any code reads it, and vice versa.',
    'Secret-shaped names are a naming signal only, not a finding that a secret is exposed.',
]
SECRET_SHAPE = re.compile(r'(secret|token|password|passwd|api[_-]?key|private[_-]?key|credential|auth)', re.I)
PATTERNS = {
    'python': [re.compile(r'os\.environ\.get\(\s*[\'"](?P<name>[A-Za-z_][\w]*)[\'"](?P<rest>\s*,)?'),
               re.compile(r'os\.environ\[\s*[\'"](?P<name>[A-Za-z_][\w]*)[\'"]\s*\]'),
               re.compile(r'os\.getenv\(\s*[\'"](?P<name>[A-Za-z_][\w]*)[\'"](?P<rest>\s*,)?')],
    'javascript': [re.compile(r'process\.env\.(?P<name>[A-Za-z_][\w]*)'),
                   re.compile(r'process\.env\[\s*[\'"](?P<name>[A-Za-z_][\w]*)[\'"]\s*\]')],
    'go': [re.compile(r'os\.(?:Getenv|LookupEnv)\(\s*"(?P<name>[A-Za-z_][\w]*)"')],
    'java': [re.compile(r'System\.getenv\(\s*"(?P<name>[A-Za-z_][\w]*)"')],
    'ruby': [re.compile(r'ENV\[\s*[\'"](?P<name>[A-Za-z_][\w]*)[\'"]\s*\]')],
    'php': [re.compile(r'getenv\(\s*[\'"](?P<name>[A-Za-z_][\w]*)[\'"]')],
    'bash': [re.compile(r'\$\{?(?P<name>[A-Z][A-Z0-9_]{2,})\}?')],
}
PATTERNS['typescript'] = PATTERNS['tsx'] = PATTERNS['javascript']
PATTERNS['csharp'] = [re.compile(r'Environment\.GetEnvironmentVariable\(\s*"(?P<name>[A-Za-z_][\w]*)"')]
# .env and similar paths are classified sensitive by the snapshot and are never read; we record
# only that such a configuration surface exists, so the gap is visible instead of silent.
COMPOSE = re.compile(r'\s*-?\s*([A-Z][A-Z0-9_]{2,})\s*[:=]')


def line_of(text, offset): return text.count('\n', 0, offset) + 1


def _compose_keys(text):
    return [(match.group(1), index, 'compose') for index, line in enumerate(text.split('\n'), start=1)
            if (match := COMPOSE.match(line))]


def config_keys(rel, text):
    name = PurePosixPath(rel).name
    if name in {'docker-compose.yml', 'docker-compose.yaml'}: return _compose_keys(text)
    if not name.endswith('.json') or name in {'package-lock.json', 'package.json', 'tsconfig.json'}: return []
    try: parsed = json.loads(text)
    except ValueError: return []
    return [(key, 1, 'json_config') for key in sorted(parsed)] if isinstance(parsed, dict) else []


def _file_facts(item, text):
    """The environment variables one readable file reads and the config keys it declares."""
    rel, sha, language = item['path'], item['sha256'], language_of(item['path'])
    facts = [make('env_read', NAME, VERSION, sha, {'path': rel, 'start_line': line_of(text, match.start())},
                  {'name': match.group('name'), 'has_default': bool(match.groupdict().get('rest')), 'language': language,
                   'secret_shaped': bool(SECRET_SHAPE.search(match.group('name')))}, limitations=LIMITATIONS)
             for pattern in PATTERNS.get(language, []) for match in pattern.finditer(text)]
    return facts + [make('config_key', NAME, VERSION, sha, {'path': rel, 'start_line': line},
                         {'key': key, 'source': kind, 'secret_shaped': bool(SECRET_SHAPE.search(key))}, limitations=LIMITATIONS)
                    for key, line, kind in config_keys(rel, text)]


def _summary(facts, unread):
    reads = Counter(f['value']['name'] for f in facts if f['kind'] == 'env_read')
    declared = {f['value']['key'] for f in facts if f['kind'] == 'config_key'}
    return {'env_variables_read': len(reads), 'env_read_sites': sum(reads.values()),
            'config_keys_declared': len(declared),
            'read_but_not_declared': sorted(set(reads) - declared),
            'declared_but_not_read': sorted(declared - set(reads)),
            'unread_sensitive_config_files': sorted(unread),
            'secret_shaped_names': sorted({f['value'].get('name') or f['value'].get('key') or f['location']['path'] for f in facts if f['value'].get('secret_shaped')}),
            'interpretation': 'Names only; no configuration value was captured. A mismatch between declared and read names is a question, not a defect.'}


def run(target, source, **options):
    facts, fingerprints = [], set()
    for item in source.readable():
        text = source.text(item['path'])
        found = _file_facts(item, text) if text is not None else []
        if found: fingerprints.add(item['sha256'])
        facts += found
    unread = [item for item in source.files if item['capture'] == 'sensitive_metadata_only']
    facts += [make('config_file_unread', NAME, VERSION, digest(item['path'].encode('utf-8')), {'path': item['path']},
                   {'reason': 'Path classified sensitive by the snapshot; contents are never read by any extractor.',
                    'bytes': item['size']}, limitations=LIMITATIONS) for item in unread]
    facts.sort(key=lambda f: (f['kind'], f['value'].get('name') or f['value'].get('key') or f['location']['path'], f['location']['path'], f['location'].get('start_line') or 0))
    return {'facts': facts, 'summary': _summary(facts, [item['path'] for item in unread]), 'available': True,
            'input_sha': digest(''.join(sorted(fingerprints)).encode('utf-8')), 'reason': None}

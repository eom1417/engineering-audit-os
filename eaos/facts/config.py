"""Configuration surface: which environment variables and config keys the code actually reads.

Names only. No value is ever recorded — not from source, not from a .env file, not from a default —
so this extractor cannot become a way to copy secrets out of a repository.
"""
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


def config_keys(rel, text):
    name = PurePosixPath(rel).name
    if name in {'docker-compose.yml', 'docker-compose.yaml'}:
        keys = []
        for index, line in enumerate(text.split('\n'), start=1):
            match = COMPOSE.match(line)
            if match: keys.append((match.group(1), index, 'compose'))
        return keys
    if name.endswith('.json') and name not in {'package-lock.json'}:
        try: parsed = json.loads(text)
        except ValueError: return []
        if isinstance(parsed, dict) and name not in {'package.json', 'tsconfig.json'}:
            return [(key, 1, 'json_config') for key in sorted(parsed)]
    return []


def run(target, source, **options):
    facts, fingerprints = [], []
    reads, files_with_reads = {}, {}
    for item in source.readable():
        rel = item['path']
        text = source.text(rel)
        if text is None: continue
        language = language_of(rel)
        for pattern in PATTERNS.get(language, []):
            for match in pattern.finditer(text):
                name = match.group('name')
                line = line_of(text, match.start())
                has_default = bool(match.groupdict().get('rest'))
                fingerprints.append(item['sha256'])
                reads[name] = reads.get(name, 0) + 1
                files_with_reads.setdefault(rel, set()).add(name)
                facts.append(make('env_read', NAME, VERSION, item['sha256'], {'path': rel, 'start_line': line},
                                  {'name': name, 'has_default': has_default, 'language': language,
                                   'secret_shaped': bool(SECRET_SHAPE.search(name))}, limitations=LIMITATIONS))
        for key, line, kind in config_keys(rel, text):
            fingerprints.append(item['sha256'])
            facts.append(make('config_key', NAME, VERSION, item['sha256'], {'path': rel, 'start_line': line},
                              {'key': key, 'source': kind, 'secret_shaped': bool(SECRET_SHAPE.search(key))},
                              limitations=LIMITATIONS))
    unread = []
    for item in source.files:
        if item['capture'] == 'sensitive_metadata_only':
            unread.append(item['path'])
            facts.append(make('config_file_unread', NAME, VERSION, digest(item['path'].encode('utf-8')),
                              {'path': item['path']},
                              {'reason': 'Path classified sensitive by the snapshot; contents are never read by any extractor.',
                               'bytes': item['size']}, limitations=LIMITATIONS))
    facts.sort(key=lambda f: (f['kind'], f['value'].get('name') or f['value'].get('key') or f['location']['path'], f['location']['path'], f['location'].get('start_line') or 0))
    declared = {f['value']['key'] for f in facts if f['kind'] == 'config_key'}
    summary = {'env_variables_read': len(reads), 'env_read_sites': sum(reads.values()),
               'config_keys_declared': len(declared),
               'read_but_not_declared': sorted(set(reads) - declared),
               'declared_but_not_read': sorted(declared - set(reads)),
               'unread_sensitive_config_files': sorted(unread),
               'secret_shaped_names': sorted({f['value'].get('name') or f['value'].get('key') or f['location']['path'] for f in facts if f['value'].get('secret_shaped')}),
               'interpretation': 'Names only; no configuration value was captured. A mismatch between declared and read names is a question, not a defect.'}
    return {'facts': facts, 'summary': summary, 'available': True,
            'input_sha': digest(''.join(sorted(set(fingerprints))).encode('utf-8')), 'reason': None}

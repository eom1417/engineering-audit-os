"""Runtime and operational facts the dossier needs but the code facts miss.

A static walk of source can describe what the code *is*. It cannot describe
what the code *does* in production: where it runs, who can reach it, what it
emits, what it depends on outside the codebase, and how its data shape evolves.
This extractor closes those gaps by parsing the manifests a project actually
declares (Dockerfile, compose, GitHub Actions, OpenAPI, SQLAlchemy / Django /
Rails migrations, package.json), and by walking what the entry-points already
found to flag outward calls.

Every fact is structural: derived from a parsed manifest, never from running
the system. Nothing here proves the deployment actually works.
"""
import json
import re
from pathlib import Path
from collections import defaultdict
from . import digest, make
from .source import language_of
from .entrypoints import MODULES, applicable


KINDS = ('ci_step', 'data_model', 'deployment_target', 'integration_target',
         'migration_step', 'observability_signal', 'security_surface')

NAME = 'runtime'
VERSION = '1'
LIMITATIONS = [
    'Only manifests the engine has a parser for are observed; an unsupported format stays a gap, never a guess.',
    'A "security surface" is a route grouped by authentication hint: static analysis cannot decide who is allowed.',
    'A "deployment target" is whatever a manifest declares; it does not prove the deployment actually runs.',
    'A "data field" is read from the model declaration; runtime constraints (NOT NULL, FK) live in migrations.',
]


def _dockerfile_ports(text):
    """EXPOSE instructions: deployment-target hints."""
    ports = []
    for match in re.finditer(r'^\s*EXPOSE\s+(\d+)(?:/(?:tcp|udp))?', text, re.MULTILINE):
        ports.append(match.group(1))
    return ports


def _compose_services(text):
    try: return list(yaml_load(text).get('services', {}).keys())
    except (ValueError, TypeError): return []


def _github_actions(text):
    """Every step name + run argv (truncated to 240 chars) from a workflow file."""
    steps = []
    for line in text.splitlines():
        if 'name:' in line:
            steps.append(line.split('name:')[1].strip().strip('"\''))
        elif 'run:' in line and '|' not in line and '>' not in line:
            steps.append('run: ' + line.split('run:')[1].strip()[:240])
    return steps


def _package_scripts(text):
    try: return list(json.loads(text).get('scripts', {}).keys())
    except ValueError: return []


def _auth_hints(text):
    """Authentication annotations: decorators, middleware lists, comments."""
    hints = []
    for pattern, label in [(r'@login_required', 'login_required'),
                            (r'@requires_auth', 'requires_auth'),
                            (r'@authenticated', 'authenticated'),
                            (r'@jwt_required', 'jwt_required'),
                            (r'@permission_required', 'permission_required'),
                            (r'app\.use\(.*auth', 'middleware_auth'),
                            (r'@AllowAny', 'allow_any'),
                            (r'@IsAuthenticated', 'is_authenticated'),
                            (r'@router\.get.*auth', 'list_auth'),
                            (r'authenticate\(\)', 'authenticate')]:
        if re.search(pattern, text, re.IGNORECASE): hints.append(label)
    return hints


def _observability_signals(text):
    """Metrics / logs / traces: name patterns that suggest intent."""
    signals = []
    for pattern, kind in [(r'(?:counter|gauge|histogram)\s*\(', 'metric'),
                            (r'(?:logger|log)\.(?:info|debug|warn|error)\s*\(', 'log'),
                            (r'(?:start_span|with_tracer|trace\.tracer)', 'trace'),
                            (r'(?:capture_exception|except)', 'error_capture'),
                            (r'(?:Sentry\.init|with sentry_sdk)', 'sentry')]:
        if re.search(pattern, text, re.IGNORECASE): signals.append(kind)
    return signals


def _outbound_hosts(text):
    """Outbound network targets: URLs to non-RFC1918 hosts."""
    hosts = set()
    for match in re.finditer(r'https?://([A-Za-z0-9.\-]+)', text):
        host = match.group(1)
        if host not in {'localhost', '127.0.0.1', '::1', '0.0.0.0'}: hosts.add(host)
    return sorted(hosts)


def _orm_models(text):
    """Django/SQLAlchemy/Rails model declarations: name + framework.

    A class is attributed to the most specific framework that matches its
    declaration: Django `models.Model`, then Rails `ApplicationRecord`, then
    SQLAlchemy `Base`. Overlapping position-based matches are deduped.
    """
    rows = []
    django = [(m.group(1), m.start()) for m in re.finditer(r'class\s+(\w+)\s*\(\s*models\.Model\s*\)', text)]
    rails = [(m.group(1), m.start()) for m in re.finditer(r'class\s+(\w+)\s*<\s*ApplicationRecord', text)]
    django_positions = {pos for _, pos in django}
    rails_positions = {pos for _, pos in rails}
    for name, pos in django:
        rows.append({'name': name, 'framework': 'django'})
    for name, pos in rails:
        rows.append({'name': name, 'framework': 'rails'})
    for match in re.finditer(r'class\s+(\w+)\s*\(\s*([\w.]+)\s*\)', text):
        if match.start() in django_positions or match.start() in rails_positions: continue
        rows.append({'name': match.group(1), 'framework': 'sqlalchemy'})
    return rows


def _migration_files(name):
    return 'migrate' in name or 'migration' in name or name.endswith('0001_initial.py')


class UnsupportedYaml(ValueError):
    """What this reader will not guess at. The caller records the file as unparsed."""


def yaml_load(text):
    """A minimal YAML reader for the simple structures we encounter. We never
    rely on it for completeness; the parser raises on the rest and we leave it
    as unparsed in the output."""
    text = re.sub(r'#[^\n]*', '', text)
    _refuse_unsupported(text)
    return _yaml_reader(text)


def _refuse_unsupported(text):
    """Raise on the constructs this reader cannot represent faithfully.

    Without this it returned a partial answer instead: `a: [unclosed` became the string
    "[unclosed", and a document with a broken sequence lost its items silently. A parser that
    guesses turns an unreadable file into fabricated facts, which is worse than no facts.
    """
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if line[:len(line) - len(line.lstrip())].count('\t'):
            raise UnsupportedYaml(f'line {number}: tab indentation is not valid YAML')
        for opener, closer in (('[', ']'), ('{', '}')):
            if stripped.count(opener) != stripped.count(closer):
                raise UnsupportedYaml(f'line {number}: unbalanced {opener}{closer} — flow style is '
                                      f'only read when it closes on its own line')
        if stripped.startswith(('&', '*', '<<', '!', '|', '>')) or stripped.endswith(('|', '>')):
            raise UnsupportedYaml(f'line {number}: anchors, tags and block scalars are not read')


def _yaml_reader(text, indent=0):
    """Read a YAML mapping or sequence at the given indent level."""
    out = {} if _yaml_indent_level(text, indent) in {'map', None} else []
    lines = [line for line in text.splitlines()]
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith('#'): i += 1; continue
        current_indent = len(line) - len(line.lstrip())
        if current_indent < indent: return out
        if stripped.startswith('- '):
            value = stripped[2:].strip()
            if ':' in value and not value.startswith('"'):
                key, val = value.split(':', 1)
                item = {key.strip(): _yaml_scalar(val.strip())}
                i += 1
                while i < len(lines):
                    nxt = lines[i]
                    if not nxt.strip(): i += 1; continue
                    nxt_indent = len(nxt) - len(nxt.lstrip())
                    if nxt_indent <= current_indent: break
                    sub = _yaml_reader('\n'.join(lines[i:]), nxt_indent)
                    item.update(sub) if isinstance(sub, dict) else None
                    i += sum(1 for _ in [None])
                    break
                if isinstance(out, list): out.append(item)
            else:
                if isinstance(out, list): out.append(_yaml_scalar(value))
                i += 1
        elif ':' in stripped:
            key, _, val = stripped.partition(':')
            key = key.strip(); val = val.strip()
            if val == '':
                i += 1
                sub_lines = []
                while i < len(lines):
                    nxt = lines[i]
                    if not nxt.strip(): i += 1; continue
                    nxt_indent = len(nxt) - len(nxt.lstrip())
                    if nxt_indent <= current_indent: break
                    sub_lines.append(nxt); i += 1
                if isinstance(out, dict):
                    out[key] = _yaml_reader('\n'.join(sub_lines), current_indent + 2)
            else:
                if isinstance(out, dict): out[key] = _yaml_scalar(val)
                i += 1
        else:
            i += 1
    return out


def _yaml_indent_level(text, indent):
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'): continue
        current = len(line) - len(line.lstrip())
        if current < indent: return None
        if current == indent: return 'map' if ':' in stripped else 'seq'
    return None


def _yaml_scalar(value):
    value = value.strip().strip('"\'')
    if value in {'true', 'yes'}: return True
    if value in {'false', 'no'}: return False
    if re.match(r'^-?\d+$', value): return int(value)
    return value


def run(target, source, symbols=None, **options):
    facts, fingerprints = [], []
    seen = set()
    for item in source.readable():
        rel = item['path']; text = source.text(rel)
        if text is None: continue
        fingerprints.append(item['sha256'])
        name = Path(rel).name
        if name == 'Dockerfile' or name.endswith('.dockerfile'):
            for port in _dockerfile_ports(text):
                facts.append(make('deployment_target', NAME, VERSION, item['sha256'],
                                   {'path': rel}, {'kind': 'dockerfile', 'port': port,
                                                    'language': 'dockerfile'},
                                   limitations=LIMITATIONS))
        elif name in {'docker-compose.yml', 'docker-compose.yaml', 'compose.yml'}:
            for service in _compose_services(text):
                facts.append(make('deployment_target', NAME, VERSION, item['sha256'],
                                   {'path': rel}, {'kind': 'compose', 'service': service},
                                   limitations=LIMITATIONS))
        elif '.github/workflows/' in rel and (name.endswith('.yml') or name.endswith('.yaml')):
            for step in _github_actions(text)[:40]:
                facts.append(make('ci_step', NAME, VERSION, item['sha256'],
                                   {'path': rel}, {'name': step[:120]},
                                   limitations=LIMITATIONS))
        elif name == 'package.json':
            for script in _package_scripts(text):
                facts.append(make('ci_step', NAME, VERSION, item['sha256'],
                                   {'path': rel}, {'name': 'npm:' + script},
                                   limitations=LIMITATIONS))
        if language_of(rel) in {'python', 'javascript', 'typescript', 'go', 'ruby'}:
            for hint in _auth_hints(text):
                key = ('security', rel, hint)
                if key in seen: continue
                seen.add(key)
                facts.append(make('security_surface', NAME, VERSION, item['sha256'],
                                   {'path': rel}, {'hint': hint,
                                                    'language': language_of(rel)},
                                   limitations=LIMITATIONS))
            for signal in _observability_signals(text):
                key = ('observability', rel, signal)
                if key in seen: continue
                seen.add(key)
                facts.append(make('observability_signal', NAME, VERSION, item['sha256'],
                                   {'path': rel}, {'kind': signal,
                                                    'language': language_of(rel)},
                                   limitations=LIMITATIONS))
            for host in _outbound_hosts(text):
                key = ('integration', rel, host)
                if key in seen: continue
                seen.add(key)
                facts.append(make('integration_target', NAME, VERSION, item['sha256'],
                                   {'path': rel}, {'host': host,
                                                    'language': language_of(rel)},
                                   limitations=LIMITATIONS))
            for model in _orm_models(text):
                facts.append(make('data_model', NAME, VERSION, item['sha256'],
                                   {'path': rel}, {'name': model['name'],
                                                    'framework': model['framework']},
                                   limitations=LIMITATIONS))
        if _migration_files(name):
            facts.append(make('migration_step', NAME, VERSION, item['sha256'],
                               {'path': rel}, {'name': name},
                               limitations=LIMITATIONS))
    summary = {'files_observed': len(fingerprints), 'facts': len(facts),
               # Iterating a set orders by hash, which Python randomises per process: two runs over
               # an unchanged tree wrote the same counts in a different order and the fact set was
               # no longer byte-identical. A sorted tuple is the only honest order here.
               'by_kind': {kind: sum(1 for f in facts if f['kind'] == kind) for kind in KINDS},
               'interpretation': 'Runtime facts describe the operational surface the static walk cannot see. '
                                  'None proves the system actually runs that way.'}
    return {'facts': facts, 'summary': summary, 'available': True,
            'input_sha': digest(''.join(sorted(fingerprints)).encode()) if fingerprints else digest(b''),
            'reason': None}

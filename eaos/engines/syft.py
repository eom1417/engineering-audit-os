"""Syft: every dependency the project declares or locks, as a CycloneDX SBOM.

The SBOM is inventory, not judgement, so it produces no finding: it is written to the report as
sbom.cdx.json, and OSV-Scanner reads it for the components no lockfile of its own names.

Syft reads lockfiles and installed packages; a Python project that only declares ranges (pyproject.toml
[project.dependencies], requirements*.txt) has none, and Syft lists nothing for it. Those declarations are
added to the report's SBOM with their range and the file that declares them (property eaos:declared), so
the inventory is complete and a reader sees that these versions are not locked: no scan can judge a
version nobody pinned. Syft's own output is kept unchanged beside it.
"""
import json
import re
from pathlib import Path

from . import tool
from .contract import ERROR, OBSERVED, Report
from .process import run, which

NAME = BINARY = 'syft'
PINNED = tool.pinned(NAME)


def capabilities():
    return []


def version():
    return tool.version(BINARY)


REQUIREMENT = re.compile(r'^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*([^;#]*)')


def declared(target):
    """[(name, range, file)] for Python dependencies declared as ranges in pyproject.toml or requirements*.txt."""
    target, found = Path(target), []
    pyproject = target / 'pyproject.toml'
    if pyproject.is_file():
        import tomllib
        try: project = tomllib.loads(pyproject.read_text(encoding='utf-8')).get('project') or {}
        except (tomllib.TOMLDecodeError, UnicodeDecodeError): project = {}
        found += [(line, 'pyproject.toml [project.dependencies]') for line in project.get('dependencies') or []]
    for path in sorted(target.glob('requirements*.txt')):
        found += [(line, path.name) for line in path.read_text(encoding='utf-8', errors='replace').splitlines()
                  if line.strip() and not line.lstrip().startswith(('#', '-'))]
    rows = []
    for line, where in found:
        match = REQUIREMENT.match(line)
        if match: rows.append((match.group(1).lower().replace('_', '-'), match.group(3).strip(), where))
    return rows


def complete(sbom, target):
    """The SBOM plus every declared Python dependency Syft did not list; returns how many were added."""
    components = sbom.setdefault('components', [])
    known = {str(c.get('name', '')).lower().replace('_', '-') for c in components}
    added = 0
    for name, spec, where in declared(target):
        if name in known: continue
        known.add(name)
        components.append({'type': 'library', 'name': name, 'purl': f'pkg:pypi/{name}',
                           'properties': [{'name': 'eaos:declared', 'value': spec or 'any version'},
                                          {'name': 'eaos:source', 'value': where}]})
        added += 1
    return added


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target)
    if declined: return declined
    found = version()
    workdir = Path(workdir) / NAME
    workdir.mkdir(parents=True, exist_ok=True)
    sbom = workdir / 'sbom.cdx.json'
    command = [which(BINARY), 'scan', f'dir:{target}', '-o', f'cyclonedx-json={sbom}', '-q']
    for pattern in exclude: command += ['--exclude', f'./{pattern}/**']
    code, _, error, seconds = run(command)
    if code or not sbom.is_file():
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
    record = json.loads(sbom.read_text(encoding='utf-8'))
    unlocked = complete(record, target)
    merged = workdir / 'sbom.report.cdx.json'
    merged.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    components = record.get('components') or []
    by_type = {}
    for component in components:
        kind = next((p['value'] for p in component.get('properties') or [] if p.get('name') == 'syft:package:type'),
                    component.get('type', 'unknown'))
        by_type[kind] = by_type.get(kind, 0) + 1
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, raw=str(sbom),
                  coverage={'status': 'observed', 'components': len(components), 'by_type': dict(sorted(by_type.items())),
                            'declared_not_locked': unlocked},
                  artifacts={'sbom.cdx.json': str(merged)})

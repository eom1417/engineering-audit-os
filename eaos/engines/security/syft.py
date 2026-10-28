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

from .. import tool
from ..contract import OBSERVED, Report
from ..process import run, which

NAME = BINARY = 'syft'
PINNED = tool.pinned(NAME)


def capabilities():
    return []


REQUIREMENT = re.compile(r'^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*([^;#]*)')


def declared(target):
    """[(name, range, file)] for Python dependencies declared as ranges in pyproject.toml or requirements*.txt."""
    target = Path(target)
    found = _pyproject(target / 'pyproject.toml')
    for path in sorted(target.glob('requirements*.txt')):
        found += [(line, path.name) for line in path.read_text(encoding='utf-8', errors='replace').splitlines()
                  if line.strip() and not line.lstrip().startswith(('#', '-'))]
    rows = []
    for line, where in found:
        match = REQUIREMENT.match(line)
        if match: rows.append((match.group(1).lower().replace('_', '-'), match.group(3).strip(), where))
    return rows


def _pyproject(pyproject):
    """[(line, where)] of the dependencies pyproject.toml declares in [project.dependencies]."""
    if not pyproject.is_file(): return []
    import tomllib
    try: project = tomllib.loads(pyproject.read_text(encoding='utf-8')).get('project') or {}
    except (tomllib.TOMLDecodeError, UnicodeDecodeError): project = {}
    return [(line, 'pyproject.toml [project.dependencies]') for line in project.get('dependencies') or []]


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


@tool.engine(NAME, BINARY)
def analyze(target, workdir, exclude, formats, found):
    sbom = workdir / 'sbom.cdx.json'
    command = [which(BINARY), 'scan', f'dir:{target}', '-o', f'cyclonedx-json={sbom}', '-q']
    for pattern in exclude: command += ['--exclude', f'./{pattern}/**']
    code, _, error, seconds = run(command)
    if code or not sbom.is_file():
        return tool.failed(NAME, found, seconds, code, error)
    record = json.loads(sbom.read_text(encoding='utf-8'))
    unlocked = complete(record, target)
    merged = workdir / 'sbom.report.cdx.json'
    merged.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    components = record.get('components') or []
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, raw=str(sbom),
                  coverage={'status': 'observed', 'components': len(components), 'by_type': _by_type(components),
                            'declared_not_locked': unlocked},
                  artifacts={'sbom.cdx.json': str(merged)})


def _by_type(components):
    """{package type: how many components}, sorted: Syft's own type of each, else its CycloneDX type."""
    by_type = {}
    for component in components:
        kind = next((p['value'] for p in component.get('properties') or [] if p.get('name') == 'syft:package:type'),
                    component.get('type', 'unknown'))
        by_type[kind] = by_type.get(kind, 0) + 1
    return dict(sorted(by_type.items()))

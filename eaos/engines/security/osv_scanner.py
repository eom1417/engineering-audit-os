"""OSV-Scanner: every locked dependency version checked against the OSV advisory database.

It reads the project's lockfiles itself (the most exact source: 17 vulnerable packages in one real finance app
where Syft's SBOM alone yields 7), and Syft's SBOM for the components no lockfile names. A package
found through several sources is one finding with every source as a site. The lookup is
deterministic: this exact version is listed as affected. What it cannot say is whether the vulnerable
code is reachable from this project; the claim says that too.

The database is online (api.osv.dev): without network the run is an error with its reason, not a clean result.
"""
import json
import re
from pathlib import Path

from .. import tool
from ..contract import DETERMINISTIC, OBSERVED, Report, finding, measurement, subject
from ..process import run, which

NAME = BINARY = 'osv-scanner'
PINNED = tool.pinned(NAME)
AFTER = ('syft',)
SEVERITIES = ('low', 'medium', 'high', 'critical')


def capabilities():
    from ..contract import Capability
    return [Capability('vulnerability', 'osv.vulnerable_dependency', method=DETERMINISTIC)]


def version(): return tool.version(BINARY)


def _key(text):
    """A version as comparable parts: 1.10.0 > 1.9.2; a pre-release sorts before its release."""
    main, _, pre = str(text).partition('-')
    return tuple(int(part) for part in re.findall(r'\d+', main)), (0,) if pre else (1,)


def score_severity(score):
    try: value = float(score)
    except (TypeError, ValueError): return None
    return 'critical' if value >= 9 else 'high' if value >= 7 else 'medium' if value >= 4 else 'low'


def label_severity(label):
    return {'moderate': 'medium'}.get(str(label).lower(), str(label).lower()) if label else None


def fixed_in(vulnerability, name, current):
    """The lowest version that fixes this advisory for the installed version, or None when none is known."""
    fixes = [fix for affected in vulnerability.get('affected') or [] if (affected.get('package') or {}).get('name') in (None, name)
             for spans in affected.get('ranges') or [] if spans.get('type') in ('SEMVER', 'ECOSYSTEM')
             for fix in _range_fixes(spans, current)]
    return min(fixes, key=_key) if fixes else None


def _range_fixes(spans, current):
    """The fixed versions of one range whose introduced..fixed span holds the installed version."""
    fixes, introduced = [], None
    for event in spans.get('events') or []:
        if 'introduced' in event: introduced = event['introduced']
        if 'fixed' not in event or introduced is None: continue
        low = (0,) if introduced == '0' else _key(introduced)
        if (introduced == '0' or _key(current) >= low) and _key(current) < _key(event['fixed']):
            fixes.append(event['fixed'])
    return fixes


def packages(payload, target):
    """{(ecosystem, name, version): {'sites', 'advisories'}} merged over every source OSV-Scanner read."""
    merged = {}
    for result in payload.get('results') or []:
        path = (result.get('source') or {}).get('path') or ''
        site = Path(path).relative_to(target).as_posix() if path.startswith(str(target)) else 'sbom.cdx.json'
        for row in result.get('packages') or []: _add_package(merged, row, site)
    return merged


def _add_package(merged, row, site):
    """One package row of a source: its site and its advisories joined to the package's entry."""
    package = row.get('package') or {}
    key = (package.get('ecosystem'), package.get('name'), package.get('version'))
    entry = merged.setdefault(key, {'sites': set(), 'advisories': {}})
    entry['sites'].add(site)
    scores = {vid: group.get('max_severity') for group in row.get('groups') or [] for vid in group.get('ids') or []}
    for vulnerability in row.get('vulnerabilities') or []:
        entry['advisories'][vulnerability['id']] = _advisory(vulnerability, scores.get(vulnerability['id']), key)


def _advisory(vulnerability, score, key):
    """An advisory's severity (its score, else its database's label, else medium), its fix for this version, its summary."""
    severity = (score_severity(score)
                or label_severity((vulnerability.get('database_specific') or {}).get('severity')) or 'medium')
    return {'severity': severity, 'fixed_in': fixed_in(vulnerability, key[1], key[2]),
            'summary': (vulnerability.get('summary') or '')[:160]}


def normalise(payload, target, found):
    findings = []
    for (ecosystem, name, installed), entry in sorted(packages(payload, target).items(), key=lambda item: [str(p) for p in item[0]]):
        advisories = entry['advisories']
        if not advisories: continue
        worst = max((a['severity'] for a in advisories.values()), key=SEVERITIES.index)
        upgrade = _upgrade(advisories)
        ids = sorted(advisories)
        # The SBOM is a report file, not the project's: it is a site only when no lockfile names the package.
        sites = sorted(entry['sites'] - {'sbom.cdx.json'}) or ['sbom.cdx.json']
        message = (f"{name}@{installed} ({ecosystem}) has {len(ids)} known "
                   f"{'vulnerability' if len(ids) == 1 else 'vulnerabilities'} ({', '.join(ids[:5])}"
                   f"{' …' if len(ids) > 5 else ''}), highest {worst}; "
                   + (f'fixed in {upgrade}' if upgrade else 'no fixed version covers every advisory'))
        findings.append(finding(
            NAME, found, 'osv.vulnerable_dependency', 'vulnerability',
            subject('package', f'{ecosystem}:{name}@{installed}', sites[0], None), message,
            measurements=[measurement('severity', worst), measurement('advisories', len(ids)),
                          measurement('fixed_in', upgrade), measurement('advisory_ids', ids)],
            method=DETERMINISTIC, raw_ref='osv-scanner/osv.json', sites=[{'path': site, 'line': None} for site in sites]))
    return findings


def _upgrade(advisories):
    """The one version that fixes every advisory of a package, or None when one of them has no known fix."""
    fixes = [a['fixed_in'] for a in advisories.values() if a['fixed_in']]
    return max(fixes, key=_key) if fixes and len(fixes) == len(advisories) else None


def _scan(target, workdir):
    """Run the scanner on the project's lockfiles, and on Syft's SBOM when there is one: (exit code, stderr, seconds,
    report path, SBOM path)."""
    output = workdir / NAME / 'osv.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [which(BINARY), 'scan', 'source', '-r', '--format', 'json', '--output', str(output), str(target)]
    sbom = workdir / 'syft' / 'sbom.cdx.json'
    if sbom.is_file(): command[3:3] = ['-L', str(sbom)]
    code, _, error, seconds = run(command)
    return code, error, seconds, output, sbom


def analyze(target, workdir, exclude=(), formats=None):
    declined, found = tool.started(NAME, BINARY, target)
    if declined: return declined
    target = Path(target)
    code, error, seconds, output, sbom = _scan(target, Path(workdir))
    # 0: nothing vulnerable; 1: vulnerabilities found; 128: no package source at all. Anything else failed.
    if code == 128:
        return Report(NAME, found, PINNED, OBSERVED, seconds=seconds,
                      coverage={'status': 'observed', 'sources': [], 'packages_checked': 0,
                                'note': 'no lockfile or SBOM component OSV-Scanner can read'},
                      evaluated={'vulnerability': {'status': 'observed', 'granularity': 'package'}})
    if code not in (0, 1) or not output.is_file():
        return tool.failed(NAME, found, seconds, code, error)
    payload = json.loads(output.read_text(encoding='utf-8'))
    findings = normalise(payload, target, found)
    sources = _sources(payload)
    checked = re.findall(r'found (\d+) packages', error)
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, raw=str(output),
                  coverage={'status': 'observed', 'sources_with_findings': sources,
                            'packages_checked': sum(int(n) for n in checked) or None,
                            'sbom_read': sbom.is_file()},
                  evaluated={'vulnerability': {'status': 'observed', 'granularity': 'package'}})


def _sources(payload):
    """Each source OSV-Scanner read, as `<its type>:<its file name>`."""
    return sorted({(r.get('source') or {}).get('type', '?') + ':' + Path((r.get('source') or {}).get('path', '')).name
                   for r in payload.get('results') or []})

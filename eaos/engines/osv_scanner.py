"""OSV-Scanner: every locked dependency version checked against the OSV advisory database.

It reads the project's lockfiles itself (the most exact source: 17 vulnerable packages in finance-os
where Syft's SBOM alone yields 7), and Syft's SBOM for the components no lockfile names. A package
found through several sources is one finding with every source as a site. The lookup is
deterministic: this exact version is listed as affected. What it cannot say is whether the vulnerable
code is reachable from this project; the claim says that too.

The database is online (api.osv.dev): without network the run is an error with its reason, not a clean result.
"""
import json
import re
from pathlib import Path

from . import tool
from .contract import DETERMINISTIC, ERROR, OBSERVED, Report, finding, measurement, subject
from .process import run, which

NAME = BINARY = 'osv-scanner'
PINNED = tool.pinned(NAME)
AFTER = ('syft',)
SEVERITIES = ('low', 'medium', 'high', 'critical')


def capabilities():
    from .contract import Capability
    return [Capability('vulnerability', 'osv.vulnerable_dependency', method=DETERMINISTIC)]


def version():
    return tool.version(BINARY)


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
    fixes = []
    for affected in vulnerability.get('affected') or []:
        if (affected.get('package') or {}).get('name') not in (None, name): continue
        for spans in affected.get('ranges') or []:
            if spans.get('type') not in ('SEMVER', 'ECOSYSTEM'): continue
            introduced = None
            for event in spans.get('events') or []:
                if 'introduced' in event: introduced = event['introduced']
                if 'fixed' in event and introduced is not None:
                    low = (0,) if introduced == '0' else _key(introduced)
                    if (introduced == '0' or _key(current) >= low) and _key(current) < _key(event['fixed']):
                        fixes.append(event['fixed'])
    return min(fixes, key=_key) if fixes else None


def packages(payload, target):
    """{(ecosystem, name, version): {'sites', 'advisories'}} merged over every source OSV-Scanner read."""
    merged = {}
    for result in payload.get('results') or []:
        source = result.get('source') or {}
        path = source.get('path') or ''
        site = Path(path).relative_to(target).as_posix() if path.startswith(str(target)) else 'sbom.cdx.json'
        for row in result.get('packages') or []:
            package = row.get('package') or {}
            key = (package.get('ecosystem'), package.get('name'), package.get('version'))
            entry = merged.setdefault(key, {'sites': set(), 'advisories': {}})
            entry['sites'].add(site)
            scores = {vid: group.get('max_severity') for group in row.get('groups') or [] for vid in group.get('ids') or []}
            for vulnerability in row.get('vulnerabilities') or []:
                severity = (score_severity(scores.get(vulnerability['id']))
                            or label_severity((vulnerability.get('database_specific') or {}).get('severity')) or 'medium')
                entry['advisories'][vulnerability['id']] = {
                    'severity': severity, 'fixed_in': fixed_in(vulnerability, key[1], key[2]),
                    'summary': (vulnerability.get('summary') or '')[:160]}
    return merged


def normalise(payload, target, found):
    findings = []
    for (ecosystem, name, installed), entry in sorted(packages(payload, target).items(), key=lambda item: [str(p) for p in item[0]]):
        advisories = entry['advisories']
        if not advisories: continue
        worst = max((a['severity'] for a in advisories.values()), key=SEVERITIES.index)
        fixes = [a['fixed_in'] for a in advisories.values() if a['fixed_in']]
        upgrade = max(fixes, key=_key) if fixes and len(fixes) == len(advisories) else None
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


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target)
    if declined: return declined
    found = version()
    target = Path(target)
    workdir = Path(workdir)
    output = workdir / NAME / 'osv.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [which(BINARY), 'scan', 'source', '-r', '--format', 'json', '--output', str(output), str(target)]
    sbom = workdir / 'syft' / 'sbom.cdx.json'
    if sbom.is_file(): command[3:3] = ['-L', str(sbom)]
    code, _, error, seconds = run(command)
    # 0: nothing vulnerable; 1: vulnerabilities found; 128: no package source at all. Anything else failed.
    if code == 128:
        return Report(NAME, found, PINNED, OBSERVED, seconds=seconds,
                      coverage={'status': 'observed', 'sources': [], 'packages_checked': 0,
                                'note': 'no lockfile or SBOM component OSV-Scanner can read'},
                      evaluated={'vulnerability': {'status': 'observed', 'granularity': 'package'}})
    if code not in (0, 1) or not output.is_file():
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
    payload = json.loads(output.read_text(encoding='utf-8'))
    findings = normalise(payload, target, found)
    sources = sorted({(r.get('source') or {}).get('type', '?') + ':' + Path((r.get('source') or {}).get('path', '')).name
                      for r in payload.get('results') or []})
    checked = re.findall(r'found (\d+) packages', error)
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, raw=str(output),
                  coverage={'status': 'observed', 'sources_with_findings': sources,
                            'packages_checked': sum(int(n) for n in checked) or None,
                            'sbom_read': sbom.is_file()},
                  evaluated={'vulnerability': {'status': 'observed', 'granularity': 'package'}})

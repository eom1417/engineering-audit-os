"""Reforge: 33 rules, each carrying its own coverage status and a measurement with its threshold.

Every rule ships disabled, so the adapter writes the configuration that enables them. The report
states its schema version; an unknown one is refused rather than guessed at.
"""
import json
from pathlib import Path

from .contract import (Capability, Report, OBSERVED, UNAVAILABLE, ERROR, SCHEMA_MISMATCH, FILE, finding,
                       measurement, subject)
from . import tool
from .process import run, which

NAME, BINARY, PINNED, SCHEMA = 'reforge', 'reforge', '0.3.0', 27

RULES = ['adapter_boundary_bypass', 'complex_function', 'config_key_drift', 'data_clump', 'debt_marker',
         'deep_nesting', 'dependency_cycle', 'dependency_hub', 'directory_drift', 'duplicate_type_shape',
         'file_naming_drift', 'fixture_factory_drift', 'function_proliferation', 'generic_bucket_drift',
         'happy_path_only_tests', 'import_heavy_file', 'large_directory', 'large_file', 'large_public_surface',
         'large_type', 'long_function', 'many_parameters', 'parallel_implementation', 'repeated_error_pattern',
         'repeated_literal', 'shadowed_abstraction', 'similar_functions', 'stale_compatibility_path',
         'test_duplication', 'unused_function']
FLOW_RULES = ['adapter_flow_bypass', 'excessive_relay', 'flow_fan_out']
KIND_BY_FAMILY = {'function_readability': 'complexity', 'literal_ownership': 'literal_duplication',
                  'dependency_topology': 'coupling', 'dataflow_ownership': 'dataflow',
                  'test_support': 'test_quality', 'test_coverage': 'test_quality',
                  'responsibility_decomposition': 'complexity', 'dead_code': 'dead_code',
                  'data_shape_duplication': 'duplication', 'compatibility_retirement': 'dead_code',
                  'module_surface': 'surface', 'boundary_integrity': 'boundary', 'naming': 'naming',
                  'directory_organization': 'naming', 'implementation_duplication': 'duplication',
                  'cycle': 'cycle'}


# Which rules answer which question, so "this engine evaluated cycles" is read off what ran.
_RULES_BY_KIND = {'cycle': ('dependency_cycle',), 'coupling': ('dependency_hub',),
                    'complexity': ('complex_function', 'long_function', 'deep_nesting', 'many_parameters',
                                   'large_file', 'large_type', 'function_proliferation'),
                    'literal_duplication': ('repeated_literal',),
                    'duplication': ('similar_functions', 'parallel_implementation', 'duplicate_type_shape',
                                    'shadowed_abstraction'),
                    'dead_code': ('unused_function', 'stale_compatibility_path'),
                    'dataflow': ('flow_fan_out', 'excessive_relay', 'adapter_flow_bypass'),
                    'surface': ('large_public_surface',), 'boundary': ('adapter_boundary_bypass',),
                    'naming': ('file_naming_drift', 'directory_drift'),
                    'test_quality': ('test_duplication', 'happy_path_only_tests', 'fixture_factory_drift')}


def capabilities():
    return ([Capability('complexity', f'reforge.codebase.{rule}') for rule in RULES]
            + [Capability('dataflow', f'reforge.dataflow.{rule}') for rule in FLOW_RULES])


def version():
    return tool.version(BINARY)


def _configuration(exclude):
    enabled = [f'reforge.codebase.{rule}' for rule in RULES] + [f'reforge.dataflow.{rule}' for rule in FLOW_RULES]
    ignored = ''.join(f'  "{pattern}",\n' for pattern in exclude)
    return ('version = 2\n\n[analysis]\nenabled = ["codebase", "dataflow"]\n\n'
            f'[scope]\nignore-paths = [\n{ignored}]\n\n'
            '[rules]\nenable = [\n' + ''.join(f'  "{rule}",\n' for rule in enabled) + ']\n\n'
            '[codebase]\npreset = "balanced"\n')


def _run_report(target, workdir, exclude):
    """Run the binary with the configuration that enables every rule: (exit code, stderr, seconds, report path)."""
    workdir = Path(workdir) / 'reforge'
    workdir.mkdir(parents=True, exist_ok=True)
    # The binary refuses any configuration file not named exactly reforge.toml.
    (workdir / 'reforge.toml').write_text(_configuration(exclude), encoding='utf-8')
    report_path = workdir / 'report.json'
    code, _, error, seconds = run([which(BINARY), 'analyze', str(target), '--config', str(workdir / 'reforge.toml'),
                                   '--output', 'json', '--output-file', str(report_path), '--reproducible'])
    return code, error, seconds, report_path


def _count(unmapped, key):
    unmapped[key] = unmapped.get(key, 0) + 1


def _evidence_finding(found, issue, kind, members, evidence):
    """One finding for one piece of an issue's evidence, at its places; None when it has no place at all."""
    holder = issue.get('subject') or {}
    entity = holder.get('entity') or {}
    sites = members + [{'path': spot.get('path'), 'line': spot.get('line')} for spot in evidence.get('locations', [])]
    if not sites:
        sites = [{'path': entity.get('path'), 'line': None}] if entity.get('path') else []
    if not sites: return None
    anchor = sorted(sites, key=lambda spot: (str(spot['path']), spot['line'] or 0))[0]
    return finding(
        NAME, found, evidence['rule'], kind,
        subject(holder.get('kind', 'file'), entity.get('key') or anchor['path'], anchor['path'], anchor['line']),
        evidence.get('message', issue['title']),
        measurements=[measurement(m['name'], m.get('value'), m.get('threshold'), m.get('unit'))
                      for m in evidence.get('measurements', [])],
        raw_ref='reforge/report.json', sites=sites)


def _issue_findings(found, issue, findings, unmapped):
    """An issue's findings added to `findings`; a family EAOS does not map, or evidence with no place, is counted."""
    family = issue['family'].rsplit('.', 1)[-1]
    kind = KIND_BY_FAMILY.get(family)
    if kind is None:
        _count(unmapped, family)
        return
    # A group issue names every member; a single issue names one entity. Both must land as places.
    members = [{'path': member.get('path'), 'line': None} for member in (issue.get('subject') or {}).get('members', [])]
    for evidence in issue.get('evidence', []):
        made = _evidence_finding(found, issue, kind, members, evidence)
        if made is None: _count(unmapped, family + ':unlocated')
        else: findings.append(made)


def _evaluated(report):
    """{kind: status} for each question some rule that ran answers."""
    status_by_rule = {}
    for section in ('codebase', 'dataflow'):
        for rule, detail in (((report.get('coverage') or {}).get(section) or {}).get('rules', {})).items():
            status_by_rule[rule.rsplit('.', 1)[-1]] = detail.get('status')
    evaluated = {}
    for kind, rules in _RULES_BY_KIND.items():
        seen = {status_by_rule[rule] for rule in rules if rule in status_by_rule}
        if seen:
            evaluated[kind] = {'status': 'observed' if 'observed' in seen else sorted(seen)[0], 'granularity': FILE}
    return evaluated


def _coverage(report):
    codebase = (report.get('coverage') or {}).get('codebase') or {}
    return {'status': 'observed', 'scanned_files': (report.get('summary') or {}).get('scanned_files'),
            'rules': {rule: detail.get('status') for rule, detail in codebase.get('rules', {}).items()},
            'languages': codebase.get('languages', {})}


def analyze(target, workdir, exclude=(), formats=None):
    found = version()
    if found is None:
        return Report(NAME, None, PINNED, UNAVAILABLE, reason='reforge is not installed')
    code, error, seconds, report_path = _run_report(target, workdir, exclude)
    if not report_path.is_file():
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if report.get('schema_version') != SCHEMA:
        return Report(NAME, found, PINNED, SCHEMA_MISMATCH, seconds=seconds,
                      reason=f"report schema {report.get('schema_version')} is not the pinned {SCHEMA}")
    findings, unmapped = [], {}
    for issue in report.get('issues', []): _issue_findings(found, issue, findings, unmapped)
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, coverage=_coverage(report),
                  provenance=report.get('provenance', {}), raw=str(report_path), unmapped=unmapped, evaluated=_evaluated(report))

"""Write schemas/artifacts/*.schema.json: the contract of every artifact the north-star plan produces.

The schemas are generated from this file; edit here, then run python tools/make_contracts.py.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / 'schemas/artifacts'
S, I, N, B = {'type': 'string'}, {'type': 'integer'}, {'type': 'number'}, {'type': 'boolean'}
NS = {'type': ['string', 'null']}
NN = {'type': ['number', 'null']}
NI = {'type': ['integer', 'null']}
STAGE = {'type': 'string', 'pattern': '^S(0[1-9]|1[0-5])$'}


def obj(props, required=None, extra=True):
    out = {'type': 'object', 'required': list(props) if required is None else required, 'properties': props}
    if not extra: out['additionalProperties'] = False
    return out


def arr(items, min_items=0):
    out = {'type': 'array', 'items': items}
    if min_items: out['minItems'] = min_items
    return out


def enum(*values): return {'type': 'string', 'enum': list(values)}


CONTRACTS = {
 'intake': ('intake.json', 'NS11', 'What the owner must protect and where he is going: every question answered or on a declared default, and the quality scenarios derived from them.',
  obj({'schema_version': {'const': 1},
       'questions': arr(obj({'id': S, 'question': S, 'answer': {}, 'status': enum('answered', 'default'),
                             'default_reason': S}, ['id', 'question', 'answer', 'status']), 1),
       'run_command': NS,
       'scenarios': arr(obj({'id': {'type': 'string', 'pattern': '^QS-[0-9]{3}$'},
                             'kind': enum('load', 'latency', 'availability', 'privacy', 'security', 'recovery', 'maintainability'),
                             'stimulus': S, 'response': S,
                             'measure': obj({'metric': S, 'threshold': N, 'unit': S}),
                             'source': enum('answer', 'default'), 'question_id': S}))},
      ['schema_version', 'questions', 'scenarios'])),
 'features': ('features.json', 'NS3.T4', 'What the program does for its user: each feature tied to the surfaces that expose it and the data it touches.',
  obj({'schema_version': {'const': 1},
       'features': arr(obj({'name': S, 'description': S,
                            'surfaces': arr(S, 1), 'tables': arr(S), 'files': arr(S),
                            'writes': arr(S), 'endpoints': arr(S), 'evidence': arr(S, 1), 'critical': B, 'target_component': NS},
                           ['name', 'description', 'surfaces', 'tables', 'evidence', 'critical']), 1),
       'unassigned_surfaces': arr(S)}, ['schema_version', 'features', 'unassigned_surfaces'])),
 'sbom': ('sbom.cdx.json', 'NS12.T1', 'CycloneDX written by Syft, kept as Syft wrote it. Only the fields EAOS reads are constrained.',
  obj({'bomFormat': {'const': 'CycloneDX'}, 'specVersion': S,
       'components': arr(obj({'name': S, 'version': S, 'purl': S}, ['name']), 1)}, ['bomFormat', 'components'])),
 'tools-doctor': ('tools-doctor.json', 'NS17.T1', 'Standard output of `eaos tools doctor --json`.',
  obj({'tools': arr(obj({'name': S, 'role': enum('read', 'emit', 'run', 'validate'),
                         'stages': arr(STAGE), 'pinned': S, 'found': NS, 'ok': B, 'reason': S,
                         'license_note': S},
                        ['name', 'role', 'pinned', 'found', 'ok']), 1)})),
 'measurements': ('measurements.json', 'NS18.T1', 'One row per analysed source file. A field without a source is null and its reason is in `missing`; never zero for unknown.',
  obj({'schema_version': {'const': 1},
       'files': arr(obj({'path': S, 'language': S, 'loc': NI, 'complexity_max': NN, 'duplicated_lines': NI,
                         'churn': NI, 'authors': NI, 'last_changed': NS, 'fan_in': NI, 'fan_out': NI,
                         'coverage': NN, 'missing': arr(obj({'field': S, 'reason': S}))},
                        ['path', 'language', 'loc', 'complexity_max', 'churn', 'fan_in', 'missing']), 1)})),
 'debt-register': ('debt-register.json', 'NS18.T2', 'The technical debt register. high and critical need two witnesses from different tools, or one deterministic witness.',
  obj({'schema_version': {'const': 1}, 'formula': S,
       'items': arr(obj({'id': {'type': 'string', 'pattern': '^DEBT-[0-9]{3}$'}, 'title': S,
                         'category': enum('security', 'reliability', 'maintainability', 'architecture', 'data', 'supply_chain', 'dead_code'),
                         'severity': enum('low', 'medium', 'high', 'critical'),
                         'witnesses': arr(obj({'tool': S, 'finding_id': S, 'kind': enum('heuristic', 'deterministic', 'probe')}), 1),
                         'files': arr(S), 'hotspot': {'type': ['object', 'null']}, 'impact': S, 'recommendation': S,
                         'claim_id': NS},
                        ['id', 'title', 'category', 'severity', 'witnesses', 'files', 'impact', 'recommendation']))},
      ['schema_version', 'formula', 'items'])),
 'behavior-lock-plan': ('behavior-lock/plan.json', 'NS15.T1', 'Which spec locks which feature. `path` is relative to behavior-lock/.',
  obj({'schema_version': {'const': 1},
       'specs': arr(obj({'feature': S, 'tool': enum('playwright', 'schemathesis', 'pact', 'approvaltests'),
                         'path': S, 'surfaces': arr(S)}, ['feature', 'tool', 'path']), 1)})),
 'behavior-lock-results': ('behavior-lock/results.json', 'NS26.T1', 'Runtime artifact: the lock suite on the original code. results-after.json (NS20.T1) has the same shape.',
  obj({'schema_version': {'const': 1}, 'commit': S, 'backend': enum('docker', 'unshare', 'process'),
       'results': arr(obj({'path': S, 'status': enum('passed', 'failed', 'quarantined', 'error'), 'reason': S},
                          ['path', 'status']), 1)})),
 'nfr-experiments': ('nfr/experiments.json', 'NS15.T2', 'Fault experiments for Toxiproxy, one per critical dependency and toxic.',
  obj({'schema_version': {'const': 1},
       'experiments': arr(obj({'id': S, 'dependency': S, 'proxy': S, 'toxic': enum('latency', 'timeout', 'down'),
                               'params': {'type': 'object'}, 'expected': S, 'features': arr(S)},
                              ['id', 'dependency', 'proxy', 'toxic', 'expected']))})),
 'handover-validation': ('handover/validation.json', 'NS17.T3', 'Every file EAOS generated in a tool\'s own format, and that tool\'s verdict on it.',
  obj({'schema_version': {'const': 1},
       'files': arr(obj({'path': S, 'tool': S, 'command': S, 'ok': B, 'output': S, 'reason': S},
                        ['path', 'tool', 'ok']), 1)})),
 'report-quality': ('report-quality.json', 'NS14.T2', 'Style and structure errors in each of the four reports. A tool that did not run is `null`, never 0.',
  obj({'schema_version': {'const': 1},
       'reports': arr(obj({'name': enum('CURRENT-STATE.md', 'TARGET-STATE.md', 'GAP-AND-STRATEGY.md', 'EXECUTION-PLAN.md'),
                           'vale_errors': NI, 'markdownlint_errors': NI}, ['name', 'vale_errors', 'markdownlint_errors']))})),
 'runtime-performance': ('runtime/performance.json', 'NS26.T2, NS22.T1', 'Runtime artifact. `after` exists only once `before` does, under the same conditions.',
  obj({'schema_version': {'const': 1},
       'conditions': obj({'build': S, 'warmup_s': N, 'vus': I, 'duration_s': N, 'machine': S}),
       'scenarios': arr(obj({'id': S, 'script': S, 'threshold': obj({'p95_ms': N, 'error_rate': N}),
                             'before': obj({'p95_ms': N, 'error_rate': N}),
                             'after': {'type': ['object', 'null'], 'required': ['p95_ms', 'error_rate'],
                                       'properties': {'p95_ms': N, 'error_rate': N}}},
                            ['id', 'script', 'threshold', 'before']), 1)})),
 'runtime-security': ('runtime/security.json', 'NS21.T1', 'Runtime artifact: open findings after the change, static and live.',
  obj({'schema_version': {'const': 1}, 'static': obj({'critical': I, 'high': I, 'tools': arr(S, 1)}),
       'dast': obj({'tool': S, 'high': I, 'medium': I})})),
 'runtime-resilience': ('runtime/resilience.json', 'NS23.T1', 'Runtime artifact: what the application did under each injected fault.',
  obj({'schema_version': {'const': 1},
       'experiments': arr(obj({'id': S, 'dependency': S, 'toxic': S, 'expected': S, 'observed': S, 'ok': B}), 1)})),
 'runtime-telemetry': ('runtime/telemetry.json', 'NS24.T1', 'Runtime artifact: spans seen per surface while the lock suite and k6 ran.',
  obj({'schema_version': {'const': 1},
       'surfaces': arr(obj({'surface': S, 'critical': B, 'spans': I}), 1)})),
 'production-readiness': ('PRODUCTION-READINESS.json', 'NS16.T1', 'Runtime artifact: every readiness item with the command that decided it.',
  obj({'schema_version': {'const': 1},
       'items': arr(obj({'id': S, 'title': S, 'command': {'type': 'string', 'minLength': 1}, 'ok': B, 'output': S},
                        ['id', 'command', 'ok']), 1)})),
 'execution-log': ('runtime/execution.json', 'NS9.T1', 'Runtime artifact: every plan card executed in an isolated copy, by its codemod or by a model, and what came of it.',
  obj({'schema_version': {'const': 1},
       'tasks': arr(obj({'id': S, 'tool': enum('codemod', 'model'),
                         'status': enum('VERIFIED_IN_ISOLATED_COPY', 'NEEDS_REVIEW', 'BASELINE_FAILED', 'FAILED'),
                         'acceptance_exit': I, 'result': S}, ['id', 'tool', 'status', 'acceptance_exit']), 1)})),
 'runtime-guarantee': ('runtime/guarantee.json', 'NS20.T1', 'Runtime artifact: the output of eaos guarantee after the change, copied as written: predicted against observed indicator deltas.',
  obj({'status': enum('COMPARED', 'UNAVAILABLE'),
       'rows': arr(obj({'indicator': S, 'predicted': N, 'observed': N, 'verdict': enum('HONEST', 'OVERSTATED', 'UNDERSTATED')},
                       ['indicator', 'verdict']))}, ['status', 'rows'])),
 'authorization': ('authorization.json', 'NS17.T5', 'The owner\'s written permission to run his project\'s code. Without it no execution-contract stage starts.',
  obj({'schema_version': {'const': 1}, 'project': S, 'commit': {'type': 'string', 'pattern': '^[0-9a-f]{40}$'},
       'granted_by': S, 'stages': arr(STAGE, 1), 'env_allow': arr(S), 'expires': S})),
 'sandbox-run': ('sandbox-run.json', 'NS17.T5', 'What an isolated run did, and what it could not isolate.',
  obj({'schema_version': {'const': 1}, 'backend': enum('docker', 'unshare', 'process'),
       'commands': arr(obj({'argv': arr(S, 1), 'exit': I, 'seconds': N})),
       'limitations': arr(S)})),
 'plan-fragment': ('plan.json', 'NS8', 'Only the fields the north-star plan adds to plan.json; the rest of the file keeps its existing contract.',
  obj({'tasks': arr(obj({'effort': enum('S', 'M', 'L'),
                         'section': enum('frontend', 'backend', 'data', 'infrastructure', 'security', 'quality'),
                         'codemod': {'type': ['object', 'null'], 'required': ['tool', 'command', 'dry_run'],
                                     'properties': {'tool': S, 'command': S,
                                                    'dry_run': obj({'exit': I, 'files_changed': I})}}}, [])),
       'milestones': arr(obj({'id': S, 'goal': S, 'exit': S, 'tasks': arr(S, 1)}))}, [])),
 'target-fragment': ('target-architecture.json', 'NS7', 'Only the fields the north-star plan adds to target-architecture.json.',
  obj({'target_components': arr(obj({'name': S, 'responsibility': S, 'layer': S, 'reference': S}, ['name', 'responsibility', 'layer'])),
       'infrastructure': arr(obj({'area': enum('hosting', 'data', 'identity', 'configuration', 'ci', 'dependencies', 'observability',
                                               'slo', 'iac', 'rollout', 'routing', 'migrations', 'backup', 'secrets', 'tests'),
                                  'present': B, 'decision': S, 'tool': NS, 'evidence': S, 'alternative': S},
                                 ['area', 'present', 'decision', 'evidence'])),
       'current_components': arr(obj({'relation': enum('retain', 'modify', 'rebuild', 'delete'), 'reason': S,
                                      'target_component': NS}, ['relation', 'reason']))}, [])),
}

for name, (artifact, owner, description, schema) in CONTRACTS.items():
    schema = {'$schema': 'http://json-schema.org/draft-07/schema#', 'title': artifact, 'description': description,
              'x-artifact': artifact, 'x-owner': owner, **schema}
    (OUT / f'{name}.schema.json').write_text(json.dumps(schema, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(len(CONTRACTS), 'contracts')

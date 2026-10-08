"""Write schemas/artifacts/*.schema.json: the contract of every artifact the north-star plan produces.

The schemas are generated from this file; edit here, then run python tools/make_contracts.py.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / 'schemas/artifacts'
MIRROR = Path(__file__).resolve().parent.parent / 'eaos/data/schemas/artifacts'
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
 'intake': ('intake.json', 'NS11', 'What the owner must protect and where they are going: every question answered or on a declared default, and the quality scenarios derived from them.',
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
       'tasks': arr(obj({'id': S, 'tool': enum('codemod', 'model', 'assistant'),
                         'status': enum('VERIFIED_IN_ISOLATED_COPY', 'NEEDS_REVIEW', 'BASELINE_FAILED', 'FAILED'),
                         'acceptance_exit': I, 'result': S}, ['id', 'tool', 'status', 'acceptance_exit']), 1)})),
 'runtime-guarantee': ('runtime/guarantee.json', 'NS20.T1', 'Runtime artifact: the output of eaos guarantee after the change, copied as written: predicted against observed indicator deltas.',
  obj({'status': enum('COMPARED', 'UNAVAILABLE'),
       'rows': arr(obj({'indicator': S, 'predicted': N, 'observed': N, 'verdict': enum('HONEST', 'OVERSTATED', 'UNDERSTATED')},
                       ['indicator', 'verdict']))}, ['status', 'rows'])),
 'authorization': ('authorization.json', 'NS17.T5', 'The owner\'s written permission to run their project\'s code. Without it no execution-contract stage starts.',
  obj({'schema_version': {'const': 1}, 'project': S, 'commit': {'type': 'string', 'pattern': '^[0-9a-f]{40}$'},
       'granted_by': S, 'stages': arr(STAGE, 1), 'env_allow': arr(S), 'expires': S})),
 'run-profile': ('run.json', 'NS26', 'How an authorised project runs in the sandbox: install, build, prepare, start, health route and sign-in, all declared, none guessed. env holds only values the run chooses, never an owner secret.',
  obj({'schema_version': {'const': 1}, 'app': S,
       'install': arr(arr(S, 1)), 'build': arr(arr(S, 1)), 'prepare': arr(arr(S, 1)),
       'start': arr(S, 1), 'port': I, 'health': S, 'start_timeout': I,
       'env': {'type': 'object', 'additionalProperties': {'type': 'string'}},
       'seed': arr(arr(S, 1)), 'sign_in': arr(S), 'baseline': {'type': 'object'},
       'checks': arr(arr(S, 1)), 'database': obj({'kind': enum('postgres', 'sqlite'), 'name': S}, ['kind', 'name']),
       'limitations': arr(S)}, ['schema_version', 'install', 'start', 'port', 'health'])),
 'approvals': ('approvals.json', 'NS17.T4', 'A person\'s recorded approval of a stage whose gate needs a human (S06: the target architecture). EAOS never writes it; eaos engage approve does, on the owner\'s command.',
  obj({'schema_version': {'const': 1},
       'approvals': arr(obj({'stage': STAGE, 'by': {'type': 'string', 'minLength': 1}, 'at': S, 'note': S}, ['stage', 'by', 'at']), 1)})),
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
  obj({'root': S,
       'target_components': arr(obj({'name': S, 'responsibility': S, 'layer': S, 'reference': S}, ['name', 'responsibility', 'layer'])),
       'infrastructure': arr(obj({'area': enum('hosting', 'data', 'identity', 'configuration', 'ci', 'dependencies', 'observability',
                                               'slo', 'iac', 'rollout', 'routing', 'migrations', 'backup', 'secrets', 'tests'),
                                  'present': B, 'decision': S, 'tool': NS, 'evidence': S, 'alternative': S},
                                 ['area', 'present', 'decision', 'evidence'])),
       'current_components': arr(obj({'relation': enum('retain', 'modify', 'rebuild', 'delete'), 'reason': S,
                                      'target_component': NS}, ['relation', 'reason']))}, [])),
}

# The Studio's data contract (NS36, docs/STUDIO.md): studio/manifest.json and one file per section, written by EAOS
# after every check. Every section carries the contract version; a ratio is bounded to 0..1; a number the Studio shows
# is a measure with its source; what was not measured is null, never 0; a path is relative to the project.
STUDIO_CONTRACT = 1
SECTIONS = ('meta', 'head', 'health', 'cards', 'evidence', 'story', 'docs', 'plans', 'decisions', 'media')
REF = lambda name: {'$ref': f'#/$defs/{name}'}
DEFS = {
    'ratio': {'type': 'number', 'minimum': 0, 'maximum': 1},
    'source': {'type': 'string', 'minLength': 1, 'description': 'file#field, or the formula, the number comes from'},
    'measure': obj({'value': {'type': ['number', 'null'], 'minimum': 0}, 'src': REF('source'),
                    'unit': enum('count', 'seconds', 'bytes', 'lines')}, ['value', 'src']),
    'ratio_measure': obj({'value': {'type': ['number', 'null'], 'minimum': 0, 'maximum': 1}, 'src': REF('source')},
                         ['value', 'src']),
    'path': {'type': 'string', 'minLength': 1, 'pattern': r'^(?![/\\~])(?![A-Za-z]:)(?!(.*/)?\.\.(/|$))'},
    'scan': obj({'commit': NS, 'branch': NS, 'at': S}),
}
CARD_STATES = ('open', 'in_batch', 'on_branch', 'done', 'resolved', 'skipped')
PLAN_STATES = ('draft', 'registered', 'approved', 'rejected', 'active', 'review', 'merged', 'closed', 'regressed', 'archived')
TASK_STATES = ('todo', 'active', 'done', 'blocked', 'regressed')


def section(props, required):
    return obj({'schema_version': {'const': 1}, 'contract': {'const': STUDIO_CONTRACT}, **props},
               ['schema_version', 'contract', *required])


STUDIO = {
 'manifest': ('The index of the Studio\'s data, written last so a reader never sees a half-written set: which EAOS built it, which scan, and every section with its fingerprint.',
  section({'built': obj({'version': S, 'commit': S, 'digest': S, 'studio_digest': S, 'built': S}),
           'project': obj({'name': {'type': 'string', 'minLength': 1}}),
           'scanned': REF('scan'),
           'sections': arr(obj({'name': enum(*SECTIONS), 'file': {'type': 'string', 'pattern': '^[a-z]+\\.json$'},
                                'sha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
                                'bytes': {'type': 'integer', 'minimum': 0}}), 1)},
          ['built', 'project', 'scanned', 'sections'])),
 'meta': ('What the project is: its languages, its size and the stages of the check that ran.',
  section({'languages': arr(obj({'name': S, 'files': {'type': 'integer', 'minimum': 0}, 'share': REF('ratio')})),
           'files': REF('measure'), 'lines': REF('measure'),
           'stages': arr(obj({'id': S, 'title': S, 'state': enum('done', 'partial', 'skipped', 'failed')}))},
          ['languages', 'files', 'lines', 'stages'])),
 'head': ('What every page shows on top: the scan, the EAOS that made it, whether it is still fresh, the verdict in one sentence and the next step.',
  section({'scanned': REF('scan'), 'eaos': obj({'version': S, 'commit': S, 'digest': S}),
           'freshness': enum('fresh', 'branch_moved', 'eaos_updated', 'unknown'),
           'verdict': S, 'next': obj({'action': S, 'tool': NS}, ['action'])},
          ['scanned', 'eaos', 'freshness', 'verdict', 'next'])),
 'health': ('The project\'s health: one score by one formula, its domains, and the score after every scan.',
  section({'score': REF('ratio_measure'), 'formula': S,
           'domains': arr(obj({'id': S, 'name': S, 'score': REF('ratio_measure'), 'cards': {'type': 'integer', 'minimum': 0}})),
           'history': arr(obj({'at': S, 'commit': NS, 'score': {'type': ['number', 'null'], 'minimum': 0, 'maximum': 1}}))},
          ['score', 'formula', 'domains', 'history'])),
 'cards': ('Every card of the plan on its own file and evidence, with its state read from the ledger.',
  section({'cards': arr(obj({'id': S, 'key': S, 'title': S, 'kind': S, 'category': S,
                             'severity': enum('critical', 'high', 'medium', 'low', 'info'),
                             'fixable': B, 'needs_decision': B, 'scope': enum('place', 'group'),
                             'place': {'type': ['string', 'null']}, 'paths': arr(REF('path')),
                             'evidence': arr(S), 'state': enum(*CARD_STATES), 'milestone': NS,
                             'confidence': {'type': ['number', 'null'], 'minimum': 0, 'maximum': 1}},
                            ['id', 'key', 'title', 'kind', 'severity', 'fixable', 'scope', 'paths', 'evidence', 'state']))},
          ['cards'])),
 'evidence': ('The facts the cards cite: which engine found what, and where.',
  section({'facts': arr(obj({'id': S, 'kind': S, 'engine': NS, 'path': {'type': ['string', 'null']}, 'line': NI,
                             'summary': S, 'sites': arr(obj({'path': REF('path'), 'line': NI}, ['path']))},
                            ['id', 'kind', 'summary']))},
          ['facts'])),
 'story': ('The current state, the ideal picture and the gap between them, as one story.',
  section({'current': obj({'summary': S, 'components': arr(obj({'name': S, 'layer': NS, 'files': {'type': 'integer', 'minimum': 0}},
                                                                 ['name', 'files']))}),
           'target': obj({'summary': S, 'components': arr(obj({'name': S, 'responsibility': S, 'layer': NS}, ['name', 'responsibility']))}),
           'gap': arr(obj({'component': S, 'relation': enum('retain', 'modify', 'rebuild', 'delete', 'missing'), 'to': NS,
                           'files': {'type': 'integer', 'minimum': 0}, 'cards': arr(S), 'closed': {'type': 'integer', 'minimum': 0}},
                          ['component', 'relation', 'files', 'cards'])),
           'indicators': arr(obj({'id': S, 'name': S, 'today': REF('measure'), 'expected': REF('measure'), 'target': REF('measure')},
                                 ['id', 'name', 'today', 'target']))},
          ['current', 'target', 'gap', 'indicators'])),
 'docs': ('Every document the check wrote, grouped by purpose, in reading order.',
  section({'docs': arr(obj({'id': S, 'title': S, 'path': REF('path'), 'group': S,
                            'bytes': {'type': 'integer', 'minimum': 0}, 'order': NI}, ['id', 'title', 'path', 'group']))},
          ['docs'])),
 'plans': ('Every plan in one model (fix, build, product, owner and sub-plans): steps, tasks and gates, with states computed from git, gates and recorded decisions, never set by hand.',
  section({'plans': arr(obj({'id': S, 'title': S, 'kind': enum('fix', 'build', 'product', 'owner', 'sub'), 'parent': NS,
                             'state': enum(*PLAN_STATES), 'goal': S, 'indicators': arr(S), 'progress': REF('ratio_measure'),
                             'steps': arr(obj({'id': S, 'title': S, 'state': enum(*TASK_STATES), 'weight': {'type': 'number', 'minimum': 0},
                                               'gate': NS, 'depends_on': arr(S), 'sub_plan': NS,
                                               'tasks': arr(obj({'id': S, 'title': S, 'state': enum(*TASK_STATES),
                                                                 'acceptance': NS, 'depends_on': arr(S)}, ['id', 'title', 'state']))},
                                              ['id', 'title', 'state', 'tasks']))},
                            ['id', 'title', 'kind', 'state', 'steps', 'progress']))},
          ['plans'])),
 'decisions': ('What waits for the person: one question each, its recommendation, and what it blocks.',
  section({'decisions': arr(obj({'id': S, 'question': S, 'recommendation': S,
                                 'options': arr(obj({'id': S, 'label': S})), 'blocks': arr(S),
                                 'state': enum('waiting', 'answered', 'withdrawn'), 'answer': NS, 'plan': NS,
                                 'asked': S, 'tool': NS}, ['id', 'question', 'recommendation', 'state']))},
          ['decisions'])),
 'media': ('The images of the project: screens before and after each batch, diagrams and charts.',
  section({'images': arr(obj({'id': S, 'path': REF('path'), 'title': S, 'kind': enum('screen', 'diagram', 'chart'),
                              'batch': NS, 'phase': {'type': ['string', 'null'], 'enum': ['before', 'after', 'baseline', None]},
                              'route': NS, 'viewport': NS, 'pair': NS}, ['id', 'path', 'title', 'kind']))},
          ['images'])),
}
for _name, (_description, _schema) in STUDIO.items():
    _schema = {**_schema, '$defs': DEFS}
    if _name == 'manifest': _schema['x-sections'] = list(SECTIONS)
    CONTRACTS[f'studio-{_name}'] = (f'studio/{_name}.json', 'NS36', _description, _schema)

def main():
    for name, (artifact, owner, description, schema) in CONTRACTS.items():
        schema = {'$schema': 'http://json-schema.org/draft-07/schema#', 'title': artifact, 'description': description,
                  'x-artifact': artifact, 'x-owner': owner, **schema}
        text = json.dumps(schema, indent=2, ensure_ascii=False) + '\n'
        (OUT / f'{name}.schema.json').write_text(text, encoding='utf-8')
        # The packaged mirror an installed eaos reads (eaos/artifact_contracts.py); tools/validate.py keeps them equal.
        MIRROR.mkdir(parents=True, exist_ok=True)
        (MIRROR / f'{name}.schema.json').write_text(text, encoding='utf-8')
    print(len(CONTRACTS), 'contracts')


if __name__ == '__main__':
    main()

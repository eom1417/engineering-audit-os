"""Write eaos/data/schemas/artifacts/*.schema.json: the contract of every artifact EAOS writes.

The schemas are generated from this file (the report's artifacts) and contracts_ai.py beside it (one AI node's run),
written with contract_shapes.py; edit there, then run python tools/make_contracts.py.
"""
import json
from pathlib import Path

from contract_shapes import B, I, N, NI, NN, NS, S, STAGE, arr, enum, obj
from contracts_ai import AI_NODE

OUT = Path(__file__).resolve().parent.parent / 'eaos/data/schemas/artifacts'

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
                            'writes': arr(S), 'endpoints': arr(S), 'evidence': arr(S, 1), 'critical': B}, ['name', 'description', 'surfaces', 'tables', 'evidence', 'critical']), 1),
       'unassigned_surfaces': arr(S)}, ['schema_version', 'features', 'unassigned_surfaces'])),
 'measurements': ('measurements.json', 'NS18.T1', 'One row per analysed source file. A field without a source is null and its reason is in `missing`; never zero for unknown.',
  obj({'schema_version': {'const': 1},
       'files': arr(obj({'path': S, 'language': S, 'loc': NI, 'complexity_max': NN, 'duplicated_lines': NI,
                         'churn': NI, 'authors': NI, 'last_changed': NS, 'fan_in': NI, 'fan_out': NI,
                         'coverage': NN, 'missing': arr(obj({'field': S, 'reason': S}))},
                        ['path', 'language', 'loc', 'complexity_max', 'churn', 'fan_in', 'missing']), 1)})),
 'behavior-lock-plan': ('behavior-lock/plan.json', 'NS15.T1', 'Which spec locks which feature. `path` is relative to behavior-lock/.',
  obj({'schema_version': {'const': 1},
       'specs': arr(obj({'feature': S, 'tool': enum('playwright', 'schemathesis', 'pact', 'approvaltests'),
                         'path': S, 'surfaces': arr(S)}, ['feature', 'tool', 'path']), 1)})),
 'runtime-performance': ('runtime/performance.json', 'NS26.T2, NS22.T1', 'Runtime artifact. `after` exists only once `before` does, under the same conditions.',
  obj({'schema_version': {'const': 1},
       'conditions': obj({'build': S, 'warmup_s': N, 'vus': I, 'duration_s': N, 'machine': S}),
       'scenarios': arr(obj({'id': S, 'script': S, 'threshold': obj({'p95_ms': N, 'error_rate': N}),
                             'before': obj({'p95_ms': N, 'error_rate': N}),
                             'after': {'type': ['object', 'null'], 'required': ['p95_ms', 'error_rate'],
                                       'properties': {'p95_ms': N, 'error_rate': N}}},
                            ['id', 'script', 'threshold', 'before']), 1)})),
 'execution-log': ('runtime/execution.json', 'NS9.T1', 'Runtime artifact: every plan card executed in an isolated copy, by its codemod or by a model, and what came of it.',
  obj({'schema_version': {'const': 1},
       'tasks': arr(obj({'id': S, 'tool': enum('codemod', 'model', 'assistant'),
                         'status': enum('VERIFIED_IN_ISOLATED_COPY', 'NEEDS_REVIEW', 'BASELINE_FAILED', 'FAILED'),
                         'acceptance_exit': I, 'result': S}, ['id', 'tool', 'status', 'acceptance_exit']), 1)})),
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
       'screens': {'description': 'How the app keeps its language and theme (in localStorage, a key and, for a JSON object, its field; or a query parameter), so every screen is pictured in each language (eaos/live/screens/audit.py variants).', 'type': 'object', 'properties': {k: S for k in ('lang_key', 'lang_field', 'lang_param', 'theme_key', 'theme_field', 'theme_param')}},
       'limitations': arr(S)}, ['schema_version', 'install', 'start', 'port', 'health'])),
 'approvals': ('approvals.json', 'NS17.T4', 'A person\'s recorded approval of a stage whose gate needs a human (S06: the target architecture). EAOS never writes it; eaos engage approve does, on the owner\'s command.',
  obj({'schema_version': {'const': 1},
       'approvals': arr(obj({'stage': STAGE, 'by': {'type': 'string', 'minLength': 1}, 'at': S, 'note': S}, ['stage', 'by', 'at']), 1)})),
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
CONTRACTS['ai-node'] = AI_NODE


def texts():
    """{file name: its text}: every schema as this file makes it (tests/guards/test_artifact_contract.py holds the
    files on disk to it, so a schema is never edited by hand)."""
    out = {}
    for name, (artifact, owner, description, schema) in CONTRACTS.items():
        schema = {'$schema': 'http://json-schema.org/draft-07/schema#', 'title': artifact, 'description': description,
                  'x-artifact': artifact, 'x-owner': owner, **schema}
        out[f'{name}.schema.json'] = json.dumps(schema, indent=2, ensure_ascii=False) + '\n'
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in texts().items(): (OUT / name).write_text(text, encoding='utf-8')
    print(len(CONTRACTS), 'contracts')


if __name__ == '__main__':
    main()

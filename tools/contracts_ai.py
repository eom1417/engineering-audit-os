"""One AI node's run (`ai-node`), the shape tools/make_contracts.py writes as its schema."""
from contract_shapes import B, NN, NS, S, arr, enum, obj

COUNT = {'type': 'integer', 'minimum': 0}
REFS = arr(S)
# The AI nodes (eaos/features/ai_review/analysis/): a stage whose input is a deterministic output and whose output is
# a structured decision, routed on by declared branches. `ai-node` is one node's run (<report>/nodes/<node>/last.json),
# whose decisions all share one shape.
NODE_STATES = ('decided', 'rules_only', 'failed')
_QUESTION = obj({'id': S, 'question': S, 'options': REFS, 'recommendation': NS},
                ['id', 'question', 'options', 'recommendation'])
DECISION = obj({'subject': S, 'decision': S, 'options': REFS, 'evidence': arr(S, 1),
                'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1}, 'why': S,
                'open_questions': arr(_QUESTION),
                'source': enum('model', 'rules'), 'detail': {'type': 'object'}},
               ['subject', 'decision', 'options', 'evidence', 'confidence', 'why', 'open_questions', 'source'])
_DROPPED = obj({'subject': NS, 'decision': NS, 'evidence': REFS, 'why': S}, ['subject', 'decision', 'evidence', 'why'])
_ROUTE = obj({'decision': S, 'to': S, 'when': S, 'subjects': REFS}, ['decision', 'to', 'when', 'subjects'])
AI_NODE = ('nodes/<node>/last.json', 'NS46.T15',
 "One AI node's run: what it read (the inputs' digest) and asked (the prompt's digest), which assistant, "
 "model and tier answered (and the tier it was asked again on, when a cheaper one failed or would have "
 "closed something) or "
 "that the rules decided alone, the time it took and what it cost, whether it came from the cache, every "
 "decision in the "
 "shared shape (the decision, its options, the evidence ids it stands on, the confidence, why, the open "
 "questions), what "
 "the evidence check dropped and why, and where the router sent each subject.",
 obj({'schema_version': {'const': 1}, 'node': S, 'title': S, 'kind': {'const': 'ai'}, 'state': enum(*NODE_STATES),
      'method': enum('model', 'rules'), 'assistant': NS, 'model': NS, 'at': S, 'inputs': S, 'prompt': NS, 'schema': NS,
      'passes': REFS, 'cached': B, 'seconds': NN, 'calls': COUNT, 'cost_usd': NN, 'why': NS,
      'summary': S, 'decisions': arr(DECISION), 'dropped': arr(_DROPPED), 'routes': arr(_ROUTE, 1),
      'critique': {'type': ['object', 'null']},
      'batches': obj({'asked': COUNT, 'failed': COUNT, 'why': S}, ['asked', 'failed', 'why']),
      'tier': {'type': ['string', 'null'], 'enum': ['light', 'standard', 'deep', None]},
      'escalated': {'type': ['object', 'null'], 'properties': {'from': NS, 'to': S, 'why': S},
                    'required': ['to', 'why']}},
     ['schema_version', 'node', 'kind', 'state', 'method', 'assistant', 'model', 'at', 'inputs', 'prompt',
      'cached', 'seconds',
      'cost_usd', 'why', 'decisions', 'dropped', 'routes']))

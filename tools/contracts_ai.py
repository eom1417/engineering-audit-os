"""The Studio's planned ideal and AI nodes sections, and one AI node's run (`ai-node`) (tools/make_contracts.py)."""
from contract_shapes import B, NN, NS, S, arr, enum, obj
from contracts_maps import STUDIO_V2
from contracts_studio import COUNT, OPERATIONS, REF, REFS, section_v2

# The planned ideal (studio/ideal.json, eaos/ai/ideal/planner.py, docs/STUDIO.md D10): every Target/Ideal view from the
# rules, then planned by the person's assistant on top of them, each element citing the evidence it stands on, and each
# view with its provenance. Every section that draws a target carries the same optional `provenance`.
IDEAL_VIEWS = ('system', 'change', 'journeys', 'paths', 'data_paths', 'infra', 'pipeline', 'plan_order')
IDEAL_STATES = ('planned', 'not_planned', 'stale', 'failed')
_WORDS = obj({'en': S, 'ar': S}, ['en', 'ar'])
_CONFIDENCE = {'type': ['number', 'null'], 'minimum': 0, 'maximum': 1}
PROVENANCE = obj({
    'method': enum('rules', 'planned'), 'state': enum(*IDEAL_STATES), 'assistant': NS, 'model': NS, 'at': NS,
    'confidence': _CONFIDENCE, 'message': _WORDS, 'inputs': NS,
    'departures': arr(obj({'rule_says': S, 'plan_chose': S, 'because': S, 'element': NS, 'cites': REFS},
                          ['rule_says', 'plan_chose', 'because'])),
    'open_questions': arr(obj({'id': S, 'question': S, 'recommendation': NS}, ['id', 'question']))},
    ['method', 'assistant', 'model', 'at', 'confidence', 'departures', 'open_questions'])
_IDEAL_ELEMENT = obj({'id': S, 'kind': S, 'title': S, 'operation': enum(*OPERATIONS), 'subject': NS, 'detail': S,
                      'cites': arr(S, 1), 'context': REFS, 'unresolved': REFS},
                     ['id', 'kind', 'title', 'operation', 'subject', 'cites'])
_RULES_ELEMENT = obj({'id': S, 'kind': S, 'title': S, 'operation': enum(*OPERATIONS), 'subject': NS, 'detail': S,
                      'cites': REFS, 'rules': REFS},
                     ['id', 'kind', 'title', 'operation', 'cites'])
_IDEAL_VIEW = obj({
    'provenance': PROVENANCE,
    'rules': obj({'summary': S, 'elements': arr(_RULES_ELEMENT), 'count': REF('measure')}, ['summary', 'elements', 'count']),
    'planned': {'oneOf': [{'type': 'null'}, obj({'summary': S, 'confidence': _CONFIDENCE, 'elements': arr(_IDEAL_ELEMENT),
                                                 'count': REF('measure')}, ['summary', 'confidence', 'elements', 'count'])]},
    'differences': arr(obj({'element': S, 'kind': enum('added', 'changed', 'dropped_from_rules', 'same'), 'subject': NS,
                            'rules': NS, 'planned': NS}, ['element', 'kind']))},
    ['provenance', 'rules', 'planned', 'differences'])
STUDIO_V2['ideal'] = (
 "The ideal picture of every Target/Ideal view (structure, change, journeys, paths, data, infrastructure, pipeline and the plan's order): the rules' baseline with its evidence, the ideal the person's assistant planned on top of it after a critique pass, every planned element citing facts, claims, cards or rules that exist (an uncited element is dropped by the evidence check and listed), and each view's provenance: how it was made, by which assistant and model, when, its confidence, where it departs from the rules and why, and the questions it leaves for the person.",
 section_v2({'state': enum(*IDEAL_STATES), 'message': _WORDS, 'provenance': PROVENANCE,
             'views': obj({name: _IDEAL_VIEW for name in IDEAL_VIEWS}, list(IDEAL_VIEWS), extra=False),
             'evidence': obj({'share': REF('ratio_measure'), 'raw_share': REF('ratio_measure'), 'elements': REF('measure'),
                              'dropped': arr(obj({'view': S, 'id': S, 'title': S, 'why': S}, ['view', 'id', 'why']))},
                             ['share', 'raw_share', 'elements', 'dropped']),
             'critique': {'oneOf': [{'type': 'null'}, obj({'missed': arr({'type': 'object'}), 'risks': arr({'type': 'object'}),
                                                           'order': arr({'type': 'object'})}, ['missed', 'risks', 'order'])]},
             'questions': arr(obj({'id': S, 'view': S, 'question': S, 'options': REFS, 'recommendation': NS, 'why': S},
                                  ['id', 'view', 'question', 'options'])),
             'runs': arr(obj({'at': S, 'state': enum(*IDEAL_STATES), 'assistant': NS, 'model': NS, 'seconds': NN,
                              'passes': REFS, 'message': S}, ['at', 'state', 'passes']))},
            ['state', 'message', 'provenance', 'views', 'evidence', 'critique', 'questions', 'runs']))
# The AI nodes (eaos/ai/nodes/, docs/STUDIO.md D11): a stage whose input is a deterministic output and whose output is
# a structured decision, routed on by declared branches. `ai-node` is one node's run (<report>/nodes/<node>/last.json),
# whose decisions all share one shape; `studio-nodes` is what the Studio draws of every node.
NODE_STATES = ('decided', 'rules_only', 'failed')
_QUESTION = obj({'id': S, 'question': S, 'options': REFS, 'recommendation': NS}, ['id', 'question', 'options', 'recommendation'])
DECISION = obj({'subject': S, 'decision': S, 'options': REFS, 'evidence': arr(S, 1),
                'confidence': {'type': 'number', 'minimum': 0, 'maximum': 1}, 'why': S, 'open_questions': arr(_QUESTION),
                'source': enum('model', 'rules'), 'detail': {'type': 'object'}},
               ['subject', 'decision', 'options', 'evidence', 'confidence', 'why', 'open_questions', 'source'])
_DROPPED = obj({'subject': NS, 'decision': NS, 'evidence': REFS, 'why': S}, ['subject', 'decision', 'evidence', 'why'])
_ROUTE = obj({'decision': S, 'to': S, 'when': S, 'subjects': REFS}, ['decision', 'to', 'when', 'subjects'])
AI_NODE = ('nodes/<node>/last.json', 'NS46.T15',
 "One AI node's run: what it read (the inputs' digest) and asked (the prompt's digest), which assistant and model answered or "
 "that the rules decided alone, the time it took and what it cost, whether it came from the cache, every decision in the "
 "shared shape (the decision, its options, the evidence ids it stands on, the confidence, why, the open questions), what "
 "the evidence check dropped and why, and where the router sent each subject.",
 obj({'schema_version': {'const': 1}, 'node': S, 'title': S, 'kind': {'const': 'ai'}, 'state': enum(*NODE_STATES),
      'method': enum('model', 'rules'), 'assistant': NS, 'model': NS, 'at': S, 'inputs': S, 'prompt': NS, 'schema': NS,
      'passes': REFS, 'cached': B, 'seconds': NN, 'calls': COUNT, 'cost_usd': NN, 'why': NS,
      'summary': S, 'decisions': arr(DECISION), 'dropped': arr(_DROPPED), 'routes': arr(_ROUTE, 1), 'critique': {'type': ['object', 'null']}, 'batches': obj({'asked': COUNT, 'failed': COUNT, 'why': S}, ['asked', 'failed', 'why'])},
     ['schema_version', 'node', 'kind', 'state', 'method', 'assistant', 'model', 'at', 'inputs', 'prompt', 'cached', 'seconds',
      'cost_usd', 'why', 'decisions', 'dropped', 'routes']))
_NODE_LOG = obj({'at': S, 'state': enum(*NODE_STATES), 'assistant': NS, 'model': NS, 'prompt': NS, 'inputs': S, 'cached': B,
                 'seconds': NN, 'cost_usd': NN}, ['at', 'state', 'model', 'prompt', 'inputs', 'cached'])
STUDIO_V2['nodes'] = (
 "The AI nodes of EAOS's pipeline: each node with its title, the passes it makes, the nodes it waits for, its router's declared "
 "branches (the decision, where it sends the work, the condition in plain words, how many subjects took it), how its last run "
 "was decided (by which assistant and model, or by the rules alone, and why), its time and cost, its decisions with their "
 "evidence, what the evidence check dropped, and its run log; the questions that wait for the person go to the Decisions inbox.",
 section_v2({'nodes': arr(obj({'id': S, 'title': _WORDS, 'kind': {'const': 'ai'}, 'passes': REFS, 'requires': REFS,
                               'routes': arr(obj({'decision': S, 'to': S, 'when': _WORDS, 'subjects': COUNT},
                                                 ['decision', 'to', 'when', 'subjects']), 1),
                               'state': enum(*NODE_STATES, 'not_run'), 'method': {'type': ['string', 'null'], 'enum': ['model', 'rules', None]},
                               'assistant': NS, 'model': NS, 'at': NS, 'cached': B, 'seconds': NN, 'cost_usd': NN, 'why': NS, 'summary': NS, 'decisions': arr(DECISION), 'dropped': arr(_DROPPED), 'log': arr(_NODE_LOG)},
                              ['id', 'title', 'kind', 'passes', 'requires', 'routes', 'state', 'method', 'assistant', 'model', 'at',
                               'cached', 'why', 'decisions', 'dropped', 'log'])),
             'sinks': arr(obj({'id': S, 'title': _WORDS}, ['id', 'title'])),
             'questions': arr(obj({'id': S, 'node': S, 'subject': S, 'question': S, 'options': REFS, 'recommendation': NS},
                                  ['id', 'node', 'subject', 'question', 'options'])),
             'counts': {'type': 'object', 'additionalProperties': REF('measure')}},
            ['nodes', 'sinks', 'questions', 'counts']))

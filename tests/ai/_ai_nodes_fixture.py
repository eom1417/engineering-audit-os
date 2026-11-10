"""Shared by the AI-node tests: the ideal reports, the fake assistant, and the base class."""
import json


def _ideal_report(base):
    """The smallest report the planner reads: the rules' target, one fact, one card, a plan."""
    report = base / 'report'
    (report / 'facts').mkdir(parents=True)
    (report / 'studio').mkdir()
    (report / 'target-architecture.json').write_text(json.dumps({
        'reference': 'react-vite-spa-rest', 'gap_matrix': [], 'decisions': [], 'target_edges': [],
        'current_components': [{'id': 'T-src', 'name': 'src', 'relation': 'modify', 'reason': 'Everything else.',
                                'files': 2,
                                'paths': ['src/a.ts', 'src/b.ts']}],
        'target_components': [{'name': 'api-client', 'layer': 'api-client',
                               'responsibility': 'The only code that knows endpoints',
                               'files': 1, 'paths': ['src/a.ts']}],
        'infrastructure': [{'area': 'ci', 'present': False, 'decision': 'Introduce CI', 'tool': 'GitHub Actions',
                            'evidence': 'no workflow'}]}),
        encoding='utf-8')
    (report / 'facts/graph.json').write_text(json.dumps({'facts': [{'id': 'FACT-0001', 'kind': 'graph_node',
                                                                    'location': {'path': 'src/a.ts'},
                                                                    'value': {'fan_in': 1, 'fan_out': 0,
                                                                              'depends_on': []}}]}), encoding='utf-8')
    (report / 'studio/cards.json').write_text(json.dumps({'cards': [{'id': 'TASK-001',
                                                                     'title': 'Two writers of one table',
                                                                     'severity': 'high',
                                                                     'kind': 'ownership', 'paths': ['src/a.ts'],
                                                                     'state': 'open'}]}), encoding='utf-8')
    (report / 'plan.json').write_text(json.dumps({'milestones': [{'id': 'M1', 'goal': 'Stabilise',
                                                                  'tasks': ['TASK-001']}]}), encoding='utf-8')
    return report


def _fill(schema):
    """A value of `schema`: each decision list holds one decision per subject the schema allows, citing the subject,
    after one decision that cites an id that does not exist."""
    kind = schema.get('type')
    kind = next((k for k in kind if k != 'null'), 'null') if isinstance(kind, list) else kind
    if 'enum' in schema: return schema['enum'][0]
    if 'oneOf' in schema: return _fill(next(s for s in schema['oneOf'] if s.get('type') != 'null'))
    if kind == 'object':  # a confirm names who is harmed (the card triage)
        return {name: 'the app users' if name == 'harmed' else _fill(sub)
                for name, sub in (schema.get('properties') or {}).items()}
    if kind == 'array':
        items = schema.get('items') or {}
        subject = (items.get('properties') or {}).get('subject') or {}
        if subject.get('enum'):
            rows = []
            for i, value in enumerate(subject['enum']):
                row = _fill(items)
                row.update(subject=value, evidence=[value], confidence=0.8, why='the evidence says so')
                if i == 0: rows.append(dict(row, evidence=['FACT-invented'], why='invented'))
                rows.append(row)
            return rows
        return []
    return {'string': '', 'number': 0.5, 'integer': 1, 'boolean': False}.get(kind)


class _NodeLauncher:
    assistant, model = 'Claude Code', 'test-model'

    def __init__(self, sleep=0, cost=None):
        self.sleep, self.cost_usd, self.calls = sleep, cost, []

    def __call__(self, name, prompt, schema):
        import time
        self.calls.append(name)
        if self.sleep: time.sleep(self.sleep)
        return _fill(schema)


FAKE_CLAUDE = r'''import json, os, sys
sys.stdin.read()
with open(os.environ['FAKE_SEEN'], 'w') as seen: json.dump(sys.argv[1:], seen)
answer = {'summary': '', 'decisions': []}
print(json.dumps({'type': 'system', 'subtype': 'init', 'model': 'fake-model-2'}), flush=True)
print(json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False, 'structured_output': answer, 'total_cost_usd': 0.42}), flush=True)
'''


class Answer:
    """A launcher that answers each pass with `make(pass, schema)` and counts its calls."""
    assistant, model = 'Claude Code', 'test-model'

    def __init__(self, make):
        self.make, self.calls, self.cost_usd = make, [], None

    def __call__(self, name, prompt, schema):
        self.calls.append((name, prompt))
        answer = dict(self.make(name, schema))
        if name == 'critique' and 'decisions' in answer: answer.setdefault('critique', {'missed': [], 'risks': []})
        return answer


def decision(subject, choice, evidence, **extra):
    return {'subject': subject, 'decision': choice, 'options': [], 'evidence': list(evidence), 'confidence': 0.8,
            'why': 'because',
            'open_questions': [], 'detail': extra.pop('detail', {}), **extra}

"""The fifteen stages are the plan's pipeline, and each gate is decided by the report, in order."""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from shared_fixture import Workspace

from eaos import engage

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads((ROOT / 'docs/north-star.json').read_text(encoding='utf-8'))
CONTRACTS = {'تقييم: قراءة فقط': 'assessment', 'تقييم ثم تنفيذ': 'mixed', 'تنفيذ: عزل وتفويض': 'execution'}
# Every indicator any gate names, at a value that passes it.
PASSING = {check.indicator: (1.0, 'test') for stage in engage.STAGES for check in stage.gate if check.indicator}


class PlanConsistencyTests(Workspace):
    def test_the_stages_are_the_pipeline_of_the_plan(self):
        self.assertEqual([(s.id, s.key, s.contract) for s in engage.STAGES],
                         [(s['id'], s['key'], CONTRACTS[s['contract']]) for s in PLAN['pipeline']])

    def test_every_indicator_a_plan_gate_names_is_gated_or_declared_corpus_only(self):
        known = {i['id'] for c in PLAN['capabilities'] for i in c['indicators']}
        for spec, stage in zip(PLAN['pipeline'], engage.STAGES):
            named = set(re.findall(r'\b[A-Z]\d{1,2}\b', spec['gate'])) & known
            # "T1–T7" and "P1–P9" are ranges in the plan's text.
            for letter, low, high in re.findall(r'\b([A-Z])(\d)–[A-Z](\d)\b', spec['gate']):
                named |= {f'{letter}{n}' for n in range(int(low), int(high) + 1)}
            gated = {c.indicator for c in stage.gate if c.indicator} | set(stage.corpus_only)
            self.assertEqual(named - gated, set(), stage.id)

    def test_no_gate_asks_more_than_the_indicator_target(self):
        target = {i['id']: i['target'] for c in PLAN['capabilities'] for i in c['indicators']}
        for stage in engage.STAGES:
            for check in stage.gate:
                if check.indicator: self.assertLessEqual(check.minimum, target[check.indicator], (stage.id, check.indicator))

    def test_the_adapters_that_apply_are_the_plans_adopted_adapters(self):
        from eaos.toolchain import registry
        tools = {t['name']: t['applies'] for t in registry()['tools'] if t.get('applies')}
        self.assertEqual(tools, {a['name']: a['applies'] for a in PLAN['adopted_adapters']})


class GateTests(Workspace):
    def gate(self, stage, values=PASSING, **extra):
        with mock.patch.object(engage.Context, 'values', lambda self: dict(values)):
            return engage.check_gate(stage, self.tmp, **extra)

    def grant(self, stages, expires=None):
        expires = expires or (datetime.now(timezone.utc) + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        Path(self.tmp, 'authorization.json').write_text(json.dumps(
            {'schema_version': 1, 'project': 'p', 'commit': 'a' * 40, 'granted_by': 'owner', 'stages': stages,
             'env_allow': [], 'expires': expires}))

    def complete(self):
        """Every static artifact a gate asks for, and the approval S06 needs; no runtime artifact."""
        for path in ('CURRENT-STATE.md', 'architecture/current/workspace.dsl', 'baseline/baseline.json'):
            Path(self.tmp, path).parent.mkdir(parents=True, exist_ok=True)
            Path(self.tmp, path).write_text('{}')
        engage.approve('S06', self.tmp, 'owner')

    def test_a_gate_fails_on_the_first_earlier_stage_that_fails(self):
        self.complete()
        code, message = self.gate('S04', {**PASSING, 'U4': (0.0, 'no features')})
        self.assertEqual(code, 1)
        self.assertTrue(message.startswith('S02'), message)

    def test_an_assessment_gate_passes_when_every_stage_up_to_it_passes(self):
        self.complete()
        self.assertEqual(self.gate('S07')[0], 0)

    def test_the_target_architecture_needs_a_persons_approval(self):
        self.complete()
        Path(self.tmp, 'approvals.json').unlink()
        code, message = self.gate('S06')
        self.assertEqual(code, 1)
        self.assertIn('approve S06', message)

    def test_an_execution_stage_needs_an_unexpired_grant_that_names_it(self):
        self.complete()
        self.assertEqual(self.gate('S08')[0], 3)
        self.grant(['S09'])
        self.assertIn('not among the granted stages', self.gate('S08')[1])
        self.grant(['S08'], expires='2020-01-01T00:00:00Z')
        self.assertIn('expired', self.gate('S08')[1])

    def test_a_mixed_stage_needs_its_run_half_only_before_execution(self):
        self.complete()
        self.grant(['S08'])
        self.assertEqual(self.gate('S07')[0], 0)
        code, message = self.gate('S08')
        self.assertEqual(code, 1)
        self.assertTrue(message.startswith('S05'), message)
        self.assertIn('runtime-performance', message)

    def test_an_indicator_below_its_minimum_says_what_it_is_and_what_it_needs(self):
        code, message = self.gate('S01', {**PASSING, 'U1': (0.9, 'parse_coverage: p 0.9')})
        self.assertEqual(code, 1)
        self.assertIn('U1 = 0.9, needs >= 0.95', message)


class ApprovalTests(Workspace):
    def test_only_the_engage_command_records_an_approval(self):
        import ast
        callers = set()
        for path in sorted((ROOT / 'eaos').rglob('*.py')):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.Call) and getattr(node.func, 'attr', getattr(node.func, 'id', '')) == 'approve':
                    callers.add(path.relative_to(ROOT).as_posix())
                if isinstance(node, ast.Constant) and node.value == 'approvals.json':
                    callers.add(path.relative_to(ROOT).as_posix())
        self.assertEqual(callers, {'eaos/engage.py'})


class StatusTests(Workspace):
    def test_every_stage_reports_its_artifacts_and_a_reason_when_open(self):
        with mock.patch.object(engage.Context, 'values', lambda self: {}):
            stages = engage.status(self.tmp)['stages']
        self.assertEqual(len(stages), 15)
        for stage in stages:
            self.assertTrue(stage['gate']['passed'] or stage['gate']['reasons'], stage['id'])
        self.assertIn('run', stages[4])
        self.assertTrue(stages[7]['gate']['reasons'][0].startswith('authorization'))
